from django.http import JsonResponse
from django.shortcuts import render
from django.views import View
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.decorators import api_view

from aiden_app.forms import UserCreationForm
from aiden_app.models import UserProfile
from aiden_app.services.chat_service import ChatService


class LanguiView(View):
    def get(self, request):
        return render(request, "chat.html")


@csrf_protect
@api_view(["POST"])
def handle_question(request):
    question = request.data.get("question")
    if not question:
        return JsonResponse({"error": "Invalid question parameter"}, status=status.HTTP_400_BAD_REQUEST)

    agent = ChatService.get_agent_from_session(request.session)
    if agent is None:
        return JsonResponse({"error": "Agent not initialized"}, status=status.HTTP_404_NOT_FOUND)

    return ChatService.chat_wrapper(agent, question)


@csrf_protect
@api_view(["POST"])
def handle_start_chat(request):
    profile = request.data
    profile = UserProfile.objects.get(
        first_name=profile.get("first_name"), last_name=profile.get("last_name"), profile_title="default_profile"
    )
    if not profile:
        return JsonResponse({"error": "Invalid profile parameter"}, status=status.HTTP_400_BAD_REQUEST)

    agent, response = ChatService.start_chat(profile)
    request.session["agent"] = agent.to_json()
    return render(request, "langui/message.html", response)


@csrf_protect
@api_view(["GET"])
def handle_get_profiles(request):
    profiles = list(ChatService.get_available_profiles())

    if profiles is None:
        return JsonResponse({"error": "No profiles available"}, status=status.HTTP_404_NOT_FOUND)

    return render(request, "langui/profile-icons.html", {"items": profiles})


@csrf_protect
@api_view(["GET"])
def get_profile_creation_form(request):
    return render(request, "langui/create-profile.html")


@csrf_protect
@api_view(["POST"])
def get_user_documents(request):
    profile = request.data
    profile = UserProfile.objects.get(
        first_name=profile.get("first_name"), last_name=profile.get("last_name"), profile_title="default_profile"
    )
    if not profile:
        return JsonResponse({"error": "Invalid profile parameter"}, status=status.HTTP_400_BAD_REQUEST)
    documents = ChatService.get_documents(profile)
    return render(request, "langui/document-display.html", {"documents": documents})


@csrf_protect
@api_view(["POST"])
def handle_create_profile(request):
    form = UserCreationForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse({"error": "Invalid form data"}, status=status.HTTP_400_BAD_REQUEST)

    profile_data = form.llm_input()
    return ChatService.create_profile(profile_data, form.cleaned_data, request)
