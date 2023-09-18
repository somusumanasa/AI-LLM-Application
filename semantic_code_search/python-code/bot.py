# from semantic_code_search import sem
import panel as pn  # GUI
import sem

# Import a CSS style sheet
css = '''
body {
    font-family: Arial, Helvetica, sans-serif;
}

input {
    border: 2px solid #ccc;
    border-radius: 10px;
    padding: 10px;
    font-size: 16px;
}

button {
    border: none;
    border-radius: 10px;
    padding: 10px 20px;
    font-size: 16px;
    background-color: #1E90FF;
    color: white;
}

.markdown {
    border: 2px solid #ccc;
    border-radius: 10px;
    padding: 10px;
    font-size: 16px;
}

.user {
    background-color: #F0F8FF;
    text-align: left; /* align the user text to the left */
}

.assistant {
    background-color: #F6F6F6;
    text-align: left; /* align the assistant text to the left */
}
'''
# Add the CSS to the extension
pn.extension(raw_css=[css])

panels = [] # collect display 

context = []  # accumulate messages

def collect_messages(_):
    prompt = inp.value_input
    inp.value = ''
    response = sem.query(query_text=prompt, context=context)
    context.append({'role':'user', 'content':f"{prompt}"})
    context.append({'role':'assistant', 'content':f"{response.split('Path:')[0].rstrip() if 'Path:' in response else response}"})
    panels.append(
        pn.Row('Q:', pn.pane.Markdown(prompt, css_classes=['markdown', 'user']), align='start')) # Add css classes and align the row to the start
    panels.append(
        pn.Row('A:', pn.pane.Markdown(response, css_classes=['markdown', 'assistant']), align='start')) # Add css classes and align the row to the end
 
    return pn.Column(*panels, align='center', sizing_mode='stretch_width') # Align the column to the center

inp = pn.widgets.TextInput(value="Hi", placeholder='Question')
button_conversation = pn.widgets.Button(name="Ask", align='center')

interactive_conversation = pn.bind(collect_messages, button_conversation)

# Add a title and a subtitle
title = pn.pane.Markdown("# Code Search Bot", align='center', margin=(20, 0, 0, 0))
subtitle = pn.pane.Markdown("## A semantic code search assistant for the code repository", align='center', margin=(0, 0, 20, 0))

# Add a Spacer widget to create some vertical space
spacer = pn.Spacer(height=20)


dashboard = pn.Column(
    title,
    subtitle,
    inp,
    pn.Row(button_conversation, align='center'), # Align the button to the center
    pn.Column(pn.panel(interactive_conversation, loading_indicator=True, width=800, height=300, sizing_mode='stretch_width'), align='center'), # Align the column to the center
    spacer,
    sizing_mode='stretch_width', # Use a responsive sizing mode
    margin=(50, 50, 50, 50) # Adjust the margins
)

pn.serve(dashboard)