import json

from django.http import JsonResponse, StreamingHttpResponse

from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework import status
from django.views import View

from .agents.mistral_agent import MistralAgent
from .agents.prompts import START_CHAT_PROMPT
from .utils import get_available_profiles, get_documents
from django.views.decorators.csrf import csrf_protect
from .tools.utils.cv_editor import CVEditor
from .models import ProfileInfo, UserProfile
from .forms import UserCreationForm, UserProfileForm


class ChatView(View):
    def get(self, request):
        return render(request, "chat.html")


@csrf_protect
@api_view(["POST"])
def handle_question(request):
    question = request.data.get("question")
    if not question:
        return JsonResponse({"error": "Invalid question parameter"}, status=status.HTTP_400_BAD_REQUEST)

    agent = MistralAgent.from_json(request.session.get("agent"))
    if agent is None:
        return JsonResponse({"error": "Agent not initialized"}, status=status.HTTP_404_NOT_FOUND)

    return chat_wrapper(agent, question)


@csrf_protect
@api_view(["POST"])
def handle_start_chat(request):
    profile = request.data.get("profile")
    profile = UserProfile.objects.get(first_name=profile["first_name"], last_name=profile["last_name"], profile_title="default_profile")
    if not profile:
        return JsonResponse({"error": "Invalid profile parameter"}, status=status.HTTP_400_BAD_REQUEST)

    response, agent = start_chat(profile)
    request.session["agent"] = agent.to_json()
    return JsonResponse(response)


@csrf_protect
@api_view(["POST"])
def handle_get_profiles(request):
    profiles = list(get_available_profiles())

    if profiles is None:
        return JsonResponse({"error": "No profiles available"}, status=status.HTTP_404_NOT_FOUND)

    return JsonResponse({"role": "get_profiles", "content": profiles})


@csrf_protect
@api_view(["POST"])
def handle_create_profile(request):
    form = UserCreationForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse({"error": "Invalid form data"}, status=status.HTTP_400_BAD_REQUEST)

    profile_data = form.llm_input()
    agent = MistralAgent()
    profile_info = agent.create_profile(profile_data)
    profile = form.cleaned_data
    profile_info = ProfileInfo.from_json(profile_info)
    profile["profile_info"] = profile_info
    profile["profile_title"] = "default_profile"
    profile_form = UserProfileForm(profile, request.FILES)
    if profile_form.is_valid():
        user_profile = profile_form.save()

    else:
        return JsonResponse({"error": "Invalid profile data"}, status=status.HTTP_400_BAD_REQUEST)

    response, agent = start_chat(user_profile)
    request.session["agent"] = agent.to_json()

    return StreamingHttpResponse(respond_create_profile(user_profile, response))


def chat_wrapper(agent, question):
    def generate_responses():
        for message, is_last in agent.chat(question):
            if message["content"] == "" and not is_last:
                continue
            response = {
                "role": message["role"],
                "content": message["content"],
                "tokens_used": agent.tokens_used,
                "is_last": is_last,
            }
            if message["role"] == "tool" and message["name"] == "edit_user_profile":
                response["documents"] = get_documents(agent.profile)
            yield json.dumps(response)

    return StreamingHttpResponse(generate_responses())


def start_chat(profile: UserProfile):
    documents = get_documents(profile)
    agent = MistralAgent.from_profile(profile)
    response = {
        "role": "assistant",
        "content": START_CHAT_PROMPT,
        "is_last": True,
        "documents": documents,
        "tokens_used": 0,
    }
    return response, agent


def respond_create_profile(profile: UserProfile, response):
    CVEditor().generate_cv(profile)
    profiles = list(get_available_profiles())

    yield json.dumps({"role": "get_profiles", "content": profiles})

    yield json.dumps(response)
