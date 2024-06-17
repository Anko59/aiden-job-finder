from uuid import uuid4
from typing import Any, Iterable
from django.http import JsonResponse, HttpRequest
from mistralai.models.chat_completion import ChatMessage
from rest_framework import status

from qdrant_client.models import PointStruct

from aiden_app import USER_COLLECTION, qdrant_client
from aiden_app.models import UserProfile, ProfileInfo, UserProfileResponse, DocumentResponse, CreateProfileResponse, ErrorResponse
from aiden_app.forms import UserProfileForm
from aiden_app.services.agents.mistral_agent import MistralAgent
from aiden_app.services.tools.utils.cv_editor import CVEditor


def get_agent_from_session(session: dict[str, Any]) -> MistralAgent | None:
    """Retrieve the agent from the session if available."""
    agent_json = session.get("agent")
    return MistralAgent.from_json(agent_json) if agent_json else None


def start_chat(profile: UserProfile) -> tuple[MistralAgent, dict[str, Any]]:
    """Initialize a chat with the given user profile."""
    agent = MistralAgent.from_profile(profile)
    response = ChatMessage(
        role="assistant",
        content="Hello! How can I assist you today?",
    ).model_dump()
    return agent, response


def get_available_profiles() -> Iterable[dict[str, Any]]:
    """Yield available profiles with the title 'default_profile'."""
    for profile in UserProfile.objects.filter(profile_title="default_profile"):
        yield UserProfileResponse(
            first_name=profile.first_name,
            last_name=profile.last_name,
            photo_url=profile.photo.url,
        ).model_dump()


def create_profile(profile_data: dict[str, Any], form_data: dict[str, Any], request: HttpRequest) -> JsonResponse:
    """Create a user profile and save embeddings to Qdrant."""
    agent = MistralAgent()
    profile_info = agent.create_profile(profile_data)
    embeddings = agent.embed(profile_data["profile_info"])
    embeddings_vector = embeddings.data[0].embedding
    profile_embeddings_uuid = str(uuid4())

    qdrant_client.upload_points(
        collection_name=USER_COLLECTION,
        points=[PointStruct(id=profile_embeddings_uuid, vector=embeddings_vector, payload={"profile_info": profile_data["profile_info"]})],
    )

    profile_info.update({"embeddings_id": profile_embeddings_uuid})
    profile_info = ProfileInfo.from_json(profile_info)
    form_data["profile_info"] = profile_info
    form_data["profile_title"] = "default_profile"

    profile_form = UserProfileForm(form_data, request.FILES)
    if profile_form.is_valid():
        user_profile = profile_form.save()
        agent = MistralAgent.from_profile(user_profile)
        request.session["agent"] = agent.to_json()
        CVEditor().generate_cv(user_profile)
        return JsonResponse(CreateProfileResponse(success="Profile created successfully").model_dump())
    else:
        return JsonResponse(ErrorResponse(error="Invalid profile data").model_dump(), status=status.HTTP_400_BAD_REQUEST)


def get_documents(profile: UserProfile) -> list[dict[str, Any]]:
    """Retrieve documents associated with the given user profile."""
    return [
        DocumentResponse(name=profile.profile_title, path=f"media/cv/{profile.cv_name.replace('.pdf', '.png')}").model_dump()
        for profile in UserProfile.objects.filter(first_name=profile.first_name, last_name=profile.last_name)
    ]
