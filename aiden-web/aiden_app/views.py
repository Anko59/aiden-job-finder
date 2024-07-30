from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.decorators import api_view

from aiden_app.forms import UserProfileCreationForm
from aiden_app.models import Document, UserProfile
from aiden_app.services.chat_service import ChatService
from django.core.files.storage import default_storage
from .forms import SignUpForm


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

    agent = ChatService.get_agent_from_session(request.session)
    if agent is None:
        return JsonResponse({"error": "Agent not initialized"}, status=status.HTTP_404_NOT_FOUND)

    return ChatService.chat_wrapper(agent, question)


@login_required
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
    request.session["profile"] = profile.to_json()
    return render(request, "langui/message.html", response)


@login_required
@csrf_protect
@api_view(["GET"])
def handle_get_profiles(request):
    profiles = list(ChatService.get_available_profiles(request.user))

    if profiles is None:
        return JsonResponse({"error": "No profiles available"}, status=status.HTTP_404_NOT_FOUND)

    return render(request, "langui/profile-icons.html", {"items": profiles})


@login_required
@csrf_protect
@api_view(["GET"])
def get_profile_creation_form(request):
    return render(request, "langui/create-profile.html")


@login_required
def serve_document(request, document_id):
    document = get_object_or_404(Document, id=document_id, user_profile__user=request.user)
    response = HttpResponse(default_storage.open(document.file.name).read(), content_type="application/octet-stream")
    response["Content-Disposition"] = f'attachment; filename="{document.name}"'
    return response


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
    documents = Document.objects.filter(user_profile=profile)
    return render(request, "langui/document-display.html", {"documents": documents})


@login_required
@csrf_protect
@api_view(["POST"])
def handle_create_profile(request):
    form = UserProfileCreationForm(request.POST, request.FILES, user=request.user)
    if not form.is_valid():
        return JsonResponse({"error": "Invalid form data"}, status=status.HTTP_400_BAD_REQUEST)

    profile_data = form.llm_input()
    return ChatService.create_profile(profile_data, form.cleaned_data, request)


@login_required
@csrf_protect
@api_view(["POST"])
def handle_offer_focus(request):
    offer_id = request.data.get("offer_id")
    if not offer_id:
        return JsonResponse({"error": "Invalid offer_id parameter"}, status=status.HTTP_400_BAD_REQUEST)

    offer = ChatService.job_offer_from_reference(offer_id)
    if not offer:
        return JsonResponse({"error": "Invalid offer_id parameter"}, status=status.HTTP_400_BAD_REQUEST)
    return StreamingHttpResponse(ChatService.get_offer_focus(request, offer))


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
