import json
import os

from django.http import JsonResponse, StreamingHttpResponse

from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework import status
from django.views import View

from .agents.mistral_agent import MistralAgent
from .agents.prompts import START_CHAT_PROMPT
from .utils import get_available_profiles, get_documents


class ChatView(View):
    def get(self, request):
        return render(request, "chat.html")


@api_view(["POST"])
def handle_question(request):
    question = request.data.get("question")
    if not question:
        return JsonResponse({"error": "Invalid question parameter"}, status=status.HTTP_400_BAD_REQUEST)

    agent = MistralAgent.from_json(request.session.get("agent"))
    if agent is None:
        return JsonResponse({"error": "Agent not initialized"}, status=status.HTTP_404_NOT_FOUND)

    return chat_wrapper(agent, question)


@api_view(["POST"])
def handle_start_chat(request):
    profile = request.data.get("profile")
    if not profile:
        return JsonResponse({"error": "Invalid profile parameter"}, status=status.HTTP_400_BAD_REQUEST)

    response, agent = start_chat(profile)
    request.session["agent"] = agent.to_json()
    return JsonResponse(response)


@api_view(["POST"])
def handle_get_profiles(request):
    profiles = list(get_available_profiles())
    if not profiles:
        return JsonResponse({"error": "No profiles available"}, status=status.HTTP_404_NOT_FOUND)

    return JsonResponse({"role": "get_profiles", "content": profiles})


@api_view(["POST"])
def handle_create_profile(request):
    first_name = request.POST.get("first_name")
    last_name = request.POST.get("last_name")
    profile_info = request.POST.get("profile_info")
    photo = request.FILES.get("photo")
    if not all([first_name, last_name, profile_info, photo]):
        return JsonResponse({"error": "Missing data"}, status=status.HTTP_400_BAD_REQUEST)

    profile_data = {"first_name": first_name, "last_name": last_name, "profile_info": profile_info, "photo": photo}

    return StreamingHttpResponse(create_profile(profile_data, request))


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
                response["documents"], _ = get_documents(agent.profile)
            yield json.dumps(response)

    return StreamingHttpResponse(generate_responses())


def start_chat(profile):
    documents, user_dir = get_documents(profile)
    default_profile_file = os.path.join(user_dir, "default_profile.json")
    with open(default_profile_file, "r") as f:
        profile = json.load(f)
    agent = MistralAgent.from_profile(profile)
    response = {
        "role": "assistant",
        "content": START_CHAT_PROMPT,
        "is_last": True,
        "documents": documents,
        "tokens_used": 0,
    }
    return response, agent


def create_profile(profile_info, request):
    agent = MistralAgent()
    user_photo = profile_info.pop("photo")
    photo_filename = f"{profile_info['first_name']}_{profile_info['last_name']}.{user_photo.name.split('.')[-1]}"
    user_photo_path = os.path.join(os.path.dirname(__file__), "static/images/user_images/profile", photo_filename)
    with open(user_photo_path, "wb") as f:
        f.write(user_photo.read())
    profile_info["photo_url"] = photo_filename
    profile = agent.create_profile(profile_info)
    profiles = list(get_available_profiles())

    yield json.dumps({"role": "get_profiles", "content": profiles})
    response, agent = start_chat(profile)
    request.session["agent"] = agent.to_json()
    yield json.dumps(response)
