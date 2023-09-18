import gzip
import os
import sys
import pickle
from textwrap import dedent

import numpy as np
from tree_sitter import Tree
from tree_sitter_languages import get_parser
from tqdm import tqdm


def _supported_file_extensions():
    return {
        '.rb': 'ruby',
        '.go': 'go',
        '.rs': 'rust',
        '.java': 'java',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.py': 'python',
        '.c': 'c',
        '.h': 'c',
        '.cpp': 'cpp',
        '.hpp': 'cpp',
        '.kt': 'kotlin',
        '.kts': 'kotlin',
        '.ktm': 'kotlin',
        '.php': 'php',
        '.cs' : 'c_sharp',
        '.md' : 'markdown',
        }

def _traverse_tree(tree: Tree):
    cursor = tree.walk()
    reached_root = False
    while reached_root is False:
        yield cursor.node
        if cursor.goto_first_child():
            continue
        if cursor.goto_next_sibling():
            continue
        retracing = True
        while retracing:
            if not cursor.goto_parent():
                retracing = False
                reached_root = True
            if cursor.goto_next_sibling():
                retracing = False


def _extract_functions(nodes, fp, file_content, relevant_node_types, supported_file_extensions):
    out = []
    for n in nodes:
        if n.type in relevant_node_types:
            node_text = dedent('\n'.join(file_content.split('\n')[
                               n.start_point[0]:n.end_point[0]+1]))
            out.append(
                {'file': fp, 'line': n.start_point[0], 'text': node_text, 'ext': supported_file_extensions.get(fp[fp.rfind('.'):])})
    return out


def _get_repo_functions(root, supported_file_extensions, relevant_node_types, sub_project = None):
    functions = []

    sub_project = "D:/off1/src/outlook/outllib"
    
    root = sub_project if sub_project is not None else root
    sub_project = None

    print('Extracting functions from {}'.format(root))

    file_list = [root + '/' + f for f in os.popen('git -C {} ls-files'.format(root)).read().split('\n')]

    print("File list size is ", file_list.__len__()) 

    for fp in tqdm([f for f in file_list if os.path.isfile(f) and (sub_project is None or sub_project is not None and f in sub_project)]):
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                lang = supported_file_extensions.get(fp[fp.rfind('.'):])
                if lang:
                    parser = get_parser(lang)
                    file_content = f.read()
                    tree = parser.parse(bytes(file_content, 'utf8'))
                    all_nodes = list(_traverse_tree(tree.root_node))
                    functions.extend(_extract_functions(
                        all_nodes, fp, file_content, relevant_node_types, supported_file_extensions))
        except Exception as e:
            print('Error parsing {}: {}'.format(fp, e))
            continue
        
    return functions


def do_embed(args, model):
    nodes_to_extract = ['function_definition', 'method_definition',
                        'function_declaration', 'method_declaration']
    functions = _get_repo_functions(
        args.path_to_repo, _supported_file_extensions(), nodes_to_extract, args.sub_project)

    if not functions:
        print('No supported languages found in {}. Exiting'.format(args.path_to_repo))
        sys.exit(1)

    print('Embedding {} functions in {} batches. This is done once and cached in .embeddings'.format(
        len(functions), int(np.ceil(len(functions)/args.batch_size))))
    corpus_embeddings = model.encode(
        [f['text'] for f in functions], convert_to_tensor=True, show_progress_bar=True, batch_size=args.batch_size)

    dataset = {'functions': functions,
               'embeddings': corpus_embeddings, 'model_name': args.model_name_or_path}
    
    root = args.path_to_repo if args.sub_project is None else args.sub_project

    with gzip.open(root + '/' + '.embeddings', 'w') as f:
        f.write(pickle.dumps(dataset))
    return dataset


def embed(model, path_to_repo, model_name_or_path, batch_size, sub_project):
    nodes_to_extract = ['function_definition', 'method_definition',
                        'function_declaration', 'method_declaration']
    functions = _get_repo_functions(
        path_to_repo, _supported_file_extensions(), nodes_to_extract, sub_project)

    if not functions:
        print('No supported languages found in {}. Exiting'.format(path_to_repo))
        sys.exit(1)

    print('Embedding {} functions in {} batches. This is done once and cached in .embeddings'.format(
        len(functions), int(np.ceil(len(functions)/batch_size))))
    corpus_embeddings = model.encode(
        [f['text'] for f in functions], convert_to_tensor=True, show_progress_bar=True, batch_size=batch_size)

    dataset = {'functions': functions,
               'embeddings': corpus_embeddings, 'model_name': model_name_or_path}
    
    root = path_to_repo if sub_project is None else sub_project

    with gzip.open(root + '/' + '.embeddings', 'w') as f:
        f.write(pickle.dumps(dataset))
    return dataset