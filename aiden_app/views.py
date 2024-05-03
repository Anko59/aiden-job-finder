import json
import os

from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render

from .agents.mistral_agent import MistralAgentToolOnly
from .agents.prompts import START_CHAT_PROMPT


def get_documents(user_input):
    first_name = user_input['first_name']
    last_name = user_input['last_name']
    user_data_dir = os.path.join(os.path.dirname(__file__), 'user_data')
    user_dir = os.path.join(
        user_data_dir,
        first_name.lower() + '_' + last_name.lower(),
    )
    documents = [
        {
            'name': f,
            'path': os.path.join(
                'static',
                'images',
                'user_images',
                'cv',
                f'cv_{first_name}_{last_name}_{f.split(".")[0]}.png',
            ),
        }
        for f in os.listdir(user_dir)
        if f.endswith('.json')
    ]
    return documents, user_dir


def chat_wrapper(agent, user_input):
    def generate_responses():
        for message, is_last in agent.chat(user_input):
            if message.content == '' and not is_last:
                continue
            response = {
                'role': message.role,
                'content': message.content,
                'tokens_used': agent.tokens_used,
                'is_last': is_last,
            }
            if message.role == 'tool' and message.name == 'edit_user_profile':
                response['documents'], _ = get_documents(agent.profile)

            yield json.dumps(response)

    return StreamingHttpResponse(generate_responses())


def get_available_profiles():
    user_data_dir = os.path.join(os.path.dirname(__file__), 'user_data')
    user_folders = [f for f in os.listdir(user_data_dir) if os.path.isdir(os.path.join(user_data_dir, f))]
    default_profile_files = [os.path.join(user_data_dir, folder, 'default_profile.json') for folder in user_folders]

    for profile_file in default_profile_files:
        with open(profile_file, 'r') as f:
            profile = json.load(f)
            yield {
                'first_name': profile['first_name'],
                'last_name': profile['last_name'],
                'photo_url': profile['photo_url'],
            }


def start_chat(user_input):
    documents, user_dir = get_documents(user_input)
    default_profile_file = os.path.join(user_dir, 'default_profile.json')
    with open(default_profile_file, 'r') as f:
        profile = json.load(f)
    agent = MistralAgentToolOnly(profile)
    response = {
        'role': 'assistant',
        'content': START_CHAT_PROMPT,
        'is_last': False,
        'documents': documents,
        'tokens_used': 0,
    }
    return response, agent


agent = None


def chat_view(request):
    global agent
    if request.method == 'POST':
        body = json.loads(request.body)
        user_input = body['user_input']
        input_type = body['input_type']

        if input_type == 'question':
            if agent is None:
                return JsonResponse({'error': 'Agent not initialized'})
            return chat_wrapper(agent, user_input)
        elif input_type == 'start_chat':
            response, agent = start_chat(user_input)
            return JsonResponse(response)
        elif input_type == 'get_profiles':
            return JsonResponse({'role': 'get_profiles', 'content': list(get_available_profiles())})

    return render(request, 'chat.html')


def generate_responses(responses):
    for response in responses:
        breakpoint()
        yield json.dumps(response)
