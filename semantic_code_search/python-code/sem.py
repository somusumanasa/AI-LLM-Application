import gzip
import os
import pickle
import sys
import torch
from sentence_transformers import util
from transformers import GPT2TokenizerFast
import pkgutil
from embed import embed
from LLMClient import LLMClient
from sentence_transformers import SentenceTransformer

DELIMITER = '='
tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")

def _search(query_embedding, corpus_embeddings, functions, k=5):
    # TODO: filtering by file extension
    cos_scores = util.cos_sim(query_embedding, corpus_embeddings)[0]
    top_results = torch.topk(cos_scores, k=min(k, len(cos_scores)), sorted=True)
    out = []
    for score, idx in zip(top_results[0], top_results[1]):
        print("score and idx are ", score, functions[idx]['file'])
        out.append((score, functions[idx]))
    return out

def do_query(args):
    answer = query(args.query_text, args.path_to_repo, args.n_results, args.model_name_or_path, args.sub_project, args.batch_size)
    print(answer)

def query(query_text, path_to_repo="D:/off1/src", n_results=20, model_name_or_path = 'krlvi/sentence-msmarco-bert-base-dot-v5-nlpl-code_search_net', sub_project="D:/off1/src/outlook/outllib", batch_size = 32, context=None):
    if not query_text:
        return 'Please provide a query.'

    model = SentenceTransformer(model_name_or_path)

    sub_project = "D:/off1/src/outlook/outllib"

    root = path_to_repo if sub_project is None else sub_project

    print("Root is ---------", root)
    print("sub_project is ---------", sub_project)
    print("path_to_repo is ---------", path_to_repo)

    print("Finding embeddings:", os.path.isfile(root + '/' + '.embeddings'))

    if not os.path.isfile(root + '/' + '.embeddings'):
            print('Embeddings not found in {}. Generating embeddings now.'.format(
                root))
            embed(model, path_to_repo, model_name_or_path, batch_size, sub_project)

    query = rephrase(query_text)
    # query = query_text

    snippets = _get_embeddings(path_to_repo, n_results, model_name_or_path, sub_project, batch_size, model, query)
              
    # print("snippets are here", snippets)

    snippet = select(path_to_repo, snippets, query_text)

    if snippet is None:
        return "No snippet is found, please revise your question."
    # print ("Snippet is here", snippet)

    answer = explain(query_text, snippet, context)

    result = """
{}

Path: [{PATH1}](https://dev.azure.com/office/_git/Office?path={PATH2})

Snippet:

```c++
{TEXT}
```
    """.format(answer, PATH1 = snippet['file'][len(path_to_repo):], PATH2 = snippet['file'][len(path_to_repo):], TEXT = snippet['text'])
    return result

def _get_embeddings(path_to_repo, n_results, model_name_or_path, sub_project, batch_size, model, query):
    with gzip.open(path_to_repo + '/' + '.embeddings', 'r') as f:
        dataset = pickle.loads(f.read())
        if dataset.get('model_name') != model_name_or_path:
            print('Model name mismatch. Regenerating embeddings.')
            dataset = embed(model, path_to_repo, model_name_or_path, batch_size, sub_project)
        query_embedding = model.encode(query, convert_to_tensor=True)

        snippets = _search(query_embedding, dataset.get(
            'embeddings'), dataset.get('functions'), k=n_results)
            
    return snippets


def select(path_to_repo, snippets, query):
    system = pkgutil.get_data(__name__, 'prompts/select.txt').decode('utf-8')
    number_of_tokens = gpt_token_count(system)
    prompt=""

    for i, snippet in enumerate(snippets):
        snippet[1]['repo'] = os.path.basename(path_to_repo)
        entry = "Repository: {}\nPath: {}\nIndex: {}\n\n{}\n{}\n".format(snippet[1]['repo'], snippet[1]['file'], i + 1, snippet[1]['text'], DELIMITER)
        new_count = number_of_tokens + gpt_token_count(entry)
        if new_count < 4000:
            prompt += entry
            number_of_tokens = new_count
    
    prompt += system.format(COUNT = len(snippets), QUERY = query, DELIMITER = DELIMITER)

    index = int(send(prompt, max_tokens=97))

    print("Length and Index chosen:", len(snippets), index)

    if index > 0:
        return snippets[index-1][1]
    else:
        return None

def rephrase(query_text):
    system = pkgutil.get_data(__name__, 'prompts/rephrase.txt').decode('utf-8')
    system += '\nUser: {}\n'.format(query_text)
    system += 'Query: '

    return send(system)

def explain(query_text, snippet, context):
    
    grow_text = grow_snippet(snippet)
    prompt = build_explain_prompt(query_text, snippet, grow_text, context)

    max_tokens = 38000 - gpt_token_count(prompt) 

    if (max_tokens < 0):
        return "token count exceed limit"
    
    return send(prompt, max_tokens=3800 - gpt_token_count(prompt))


def grow(doc, snippet, grow_size=40):
    lines = doc.splitlines()
    snippet_start = snippet['line'] # adjust for zero-based indexing
    snippet_end = snippet_start + len(snippet['text'].splitlines()) - 1
    
    new_start = max(0, snippet_start - grow_size)
    new_end = min(len(lines) - 1, snippet_end + grow_size)
    new_text = "\n".join(lines[new_start:new_end + 1])

    if new_text != snippet['text']:
        return new_text
    else:
        return None


def build_explain_prompt(query_text, snippet, grow_text, context):
    system = pkgutil.get_data(__name__, 'prompts/explain.txt').decode('utf-8')
    prompt = ""
    prompt += system.format(PATH = snippet['file'], REPO = snippet['repo'], TEXT = grow_text)

    for chat in context:
        prompt += '{}: {}\n'.format(chat['role'], chat['content'])

    prompt += '\nUser: {}\n'.format(query_text)
    prompt += 'Assistant:'
    
    return prompt

# def build_explain_prompt(query_text, snippet, grow_text, context):
#     system = pkgutil.get_data(__name__, 'prompts/explain.txt').decode('utf-8')
#     prompt = ""
#     prompt += system.format(PATH = snippet['file'], REPO = snippet['repo'], TEXT = grow_text)

#     for chat in context:
#         prompt += '{}: {}\n'.format(chat['role'], chat['content'])

#     prompt += '\nUser: {}\n'.format(query_text)
#     prompt += 'Assistant:'
    
#     return prompt


def grow_snippet(snippet):
    doc = open(snippet['file'], "r").read()

    grow_size = 40

    while True:
        grown_text = grow(doc, snippet, grow_size)
        if grown_text is not None:
            token_count = gpt_token_count(grown_text)
            if token_count > 2000 or grow_size > 100:
                break
            else:
                grow_size += 10
        else:
            grown_text = snippet['text']
            break
    
    return grown_text


def gpt_token_count(text):
    return len(tokenizer(text)['input_ids'])


def send(prompt, max_tokens=1000):
    llm_client = LLMClient()
    model = 'dev-text-davinci-003'
    # model = 'code-search-ada-text-001'
    request_data = {
            "prompt":prompt,
            "max_tokens":max_tokens,
            "temperature":0.6,
            "top_p":1,
            "n":1,
            "stream":False,
            "logprobs":None,
            "stop":"\r\n"
    }

    response = llm_client.send_request(model, request_data)
    print("Response from LLM is ", response)

    return response['choices'][0]['text']