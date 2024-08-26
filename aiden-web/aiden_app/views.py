from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.decorators import api_view
from loguru import logger

from aiden_app.forms import UserProfileCreationForm
from aiden_app.models import Conversation, Document, UserProfile
from aiden_app.services.chat_service import (
    get_agent_from_session,
    chat_wrapper,
    start_chat,
    get_available_profiles,
    create_profile,
    job_offer_from_reference,
    get_offer_focus,
    get_conversation_from_session,
    load_next_page,
)
from .forms import SignUpForm
from aiden_app.storage import get_presigned_url


@login_required
def langui_view(request):
    return render(request, "chat.html")


@login_required
@csrf_protect
@api_view(["POST"])
def handle_question(request):
    question = request.data.get("question")
    if not question:
        return JsonResponse({"error": "Invalid question parameter"}, status=status.HTTP_400_BAD_REQUEST)

    agent = get_agent_from_session(request.session)
    conversation = get_conversation_from_session(request.session)
    if agent is None:
        return JsonResponse({"error": "Agent not initialized"}, status=status.HTTP_404_NOT_FOUND)

    return chat_wrapper(request, question, agent, conversation)


@login_required
@csrf_protect
@api_view(["POST"])
def handle_start_chat(request):
    profile = request.data
    profile = UserProfile.objects.get(
        first_name=profile.get("first_name"), last_name=profile.get("last_name"), profile_title="default_profile", user=request.user
    )
    if not profile:
        return JsonResponse({"error": "Invalid profile parameter"}, status=status.HTTP_400_BAD_REQUEST)

    agent, response, conversation = start_chat(profile)
    request.session["agent"] = agent.to_json()
    request.session["profile"] = profile.to_json()
    request.session["conversation"] = conversation.to_json()
    return render(request, "langui/message.html", response)


@login_required
@csrf_protect
@api_view(["GET"])
def handle_get_profiles(request):
    profiles = list(get_available_profiles(request.user))

    if profiles is None:
        return JsonResponse({"error": "No profiles available"}, status=status.HTTP_404_NOT_FOUND)

    return render(request, "langui/profile-icons.html", {"items": profiles})


@login_required
@csrf_protect
@api_view(["POST"])
def get_conversations(request):
    profile_data = request.data
    profile = get_object_or_404(
        UserProfile,
        user=request.user,
        first_name=profile_data.get("first_name"),
        last_name=profile_data.get("last_name"),
        profile_title="default_profile",
    )
    conversations = Conversation.objects.filter(user=request.user, user_profile=profile)
    return render(request, "langui/conversation-display.html", {"conversations": conversations})


@login_required
@csrf_protect
@api_view(["GET"])
def get_profile_creation_form(request):
    return render(request, "langui/create-profile.html")


@login_required
@csrf_protect
@api_view(["POST"])
def get_user_documents(request):
    profile_data = request.data
    profile = get_object_or_404(
        UserProfile,
        user=request.user,
        first_name=profile_data.get("first_name"),
        last_name=profile_data.get("last_name"),
        profile_title="default_profile",
    )
    docs = []
    profiles = UserProfile.objects.filter(
        user=request.user, first_name=profile_data.get("first_name"), last_name=profile_data.get("last_name")
    )
    for profile in profiles:
        documents = Document.objects.filter(profile=profile.profile_info)
        for document in documents:
            document.presigned_url = get_presigned_url(document.file.name)
            docs.append(document)
    return render(request, "langui/document-display.html", {"documents": docs})


@login_required
@csrf_protect
@api_view(["POST"])
def handle_create_profile(request):
    form = UserProfileCreationForm(request.POST, request.FILES, user=request.user)
    if not form.is_valid():
        logger.error("An error occured")
        logger.error(form.errors)
        logger.error(form.non_field_errors())
        logger.error(form.errors.as_data())
        return JsonResponse({"error": "Invalid form data"}, status=status.HTTP_400_BAD_REQUEST)

    profile_data = form.llm_input()
    return create_profile(profile_data, form.cleaned_data, request)


@login_required
@csrf_protect
@api_view(["POST"])
def handle_offer_focus(request):
    offer_id = request.data.get("offer_id")
    if not offer_id:
        return JsonResponse({"error": "Invalid offer_id parameter"}, status=status.HTTP_400_BAD_REQUEST)

    offer = job_offer_from_reference(offer_id)
    if not offer:
        return JsonResponse({"error": "Invalid offer_id parameter"}, status=status.HTTP_400_BAD_REQUEST)
    return StreamingHttpResponse(get_offer_focus(request, offer))


@csrf_protect
@login_required
@api_view(["POST"])
def load_next_page_api(request):
    page = request.data.get("page")
    container_id = request.data.get("container_id")
    if not page or not container_id:
        return JsonResponse({"error": "Invalid parameters"}, status=status.HTTP_400_BAD_REQUEST)
    return StreamingHttpResponse(load_next_page(request, page, container_id))


def signup_view(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get("username")
            raw_password = form.cleaned_data.get("password1")
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            return redirect("home")
    else:
        form = SignUpForm()
    return render(request, "signup.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect("home")
    else:
        form = AuthenticationForm()
    return render(request, "login.html", {"form": form})


def home_view(request):
    return render(request, "home.html")
