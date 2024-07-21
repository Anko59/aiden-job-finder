from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_protect
from pydantic import ValidationError
from rest_framework import status
from rest_framework.decorators import api_view

import aiden_app.services.chat_service_v2 as chat_service
from aiden_app.forms import UserProfileCreationForm
from aiden_app.models import ErrorResponse, QuestionRequest, StartChatRequest, UserProfile


@csrf_protect
def api_dispatcher(request: HttpRequest, endpoint: str) -> JsonResponse:
    """Dispatch API requests to the appropriate endpoint."""
    dispatch_map = {
        "question": question,
        "start_chat": start_chat,
        "get_profiles": get_profiles,
        "create_profile": create_profile,
        "get_documents": get_documents,
    }

    if endpoint in dispatch_map:
        return dispatch_map[endpoint](request)
    else:
        return JsonResponse(ErrorResponse(error=f"Invalid endpoint: {endpoint}").model_dump(), status=status.HTTP_404_NOT_FOUND)


@csrf_protect
@api_view(["POST"])
def question(request: HttpRequest) -> JsonResponse:
    """
    Handle user question and respond via streaming HTTP.

    Expected Input (JSON):
    - question: str

    Expected Output (StreamingHttpResponse):
    - A stream of `ChatMessage` objects.
    """
    try:
        data = QuestionRequest(**request.data)
    except ValidationError as e:
        return JsonResponse(ErrorResponse(error=str(e)).model_dump(), status=status.HTTP_400_BAD_REQUEST)

    agent = chat_service.get_agent_from_session(request.session)
    if not agent:
        return JsonResponse(ErrorResponse(error="Agent not initialized").model_dump(), status=status.HTTP_404_NOT_FOUND)

    return StreamingHttpResponse(agent.chat(data.question))


@csrf_protect
@login_required
def start_chat(request: HttpRequest) -> JsonResponse:
    """
    Start a chat session with a given profile.

    Expected Input (JSON):
    - first_name: str
    - last_name: str

    Expected Output (JSON):
    - Initial chat response.
    """
    try:
        data = StartChatRequest(**request.data)
    except ValidationError as e:
        return JsonResponse(ErrorResponse(error=str(e)).model_dump(), status=status.HTTP_400_BAD_REQUEST)

    try:
        profile = UserProfile.objects.get(first_name=data.first_name, last_name=data.last_name, profile_title="default_profile")
    except UserProfile.DoesNotExist:
        return JsonResponse(ErrorResponse(error="Invalid profile parameter").model_dump(), status=status.HTTP_400_BAD_REQUEST)

    agent, response = chat_service.start_chat(profile)
    request.session["agent"] = agent.to_json()
    return JsonResponse(response)


@csrf_protect
@api_view(["GET"])
def get_profiles(request: HttpRequest) -> JsonResponse:
    """
    Retrieve available user profiles.

    Expected Input:
    - None

    Expected Output (JSON):
    - List of profiles.
    """
    profiles = list(chat_service.get_available_profiles())
    if not profiles:
        return JsonResponse(ErrorResponse(error="No profiles available").model_dump(), status=status.HTTP_404_NOT_FOUND)
    return JsonResponse(profiles, safe=False)


@csrf_protect
@api_view(["POST"])
def create_profile(request: HttpRequest) -> JsonResponse:
    """
    Create a new user profile from submitted form data.

    Expected Input:
    - Multipart form data with fields required by UserProfileCreationForm

    Expected Output (JSON):
    - Success or error message.
    """
    form = UserProfileCreationForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse(ErrorResponse(error="Invalid form data").model_dump(), status=status.HTTP_400_BAD_REQUEST)

    profile_data = form.llm_input()
    return chat_service.create_profile(profile_data, form.cleaned_data, request)


@csrf_protect
@api_view(["POST"])
def get_documents(request: HttpRequest) -> JsonResponse:
    """
    Get documents associated with a given profile.

    Expected Input (JSON):
    - first_name: str
    - last_name: str

    Expected Output (JSON):
    - List of documents.
    """
    try:
        data = StartChatRequest(**request.data)
    except ValidationError as e:
        return JsonResponse(ErrorResponse(error=str(e)).model_dump(), status=status.HTTP_400_BAD_REQUEST)

    try:
        profile = UserProfile.objects.get(first_name=data.first_name, last_name=data.last_name, profile_title="default_profile")
    except UserProfile.DoesNotExist:
        return JsonResponse(ErrorResponse(error="Invalid profile parameter").model_dump(), status=status.HTTP_400_BAD_REQUEST)
    return JsonResponse(chat_service.get_documents(profile), safe=False)
