from uuid import uuid4

from django.http import JsonResponse, StreamingHttpResponse
from django.template.loader import render_to_string
from qdrant_client.models import PointStruct
from rest_framework import status

from aiden_app import USER_COLLECTION, qdrant_client
from aiden_app.forms import UserProfileForm
from aiden_app.models import ProfileInfo, UserProfile
from aiden_app.services.agents.mistral_agent import MistralAgent
from aiden_app.services.tools.utils.cv_editor import CVEditor


class ChatService:
    @staticmethod
    def get_agent_from_session(session):
        agent_json = session.get("agent")
        if not agent_json:
            return None
        return MistralAgent.from_json(agent_json)

    @classmethod
    def chat_wrapper(cls, agent, question):
        def generate_responses():
            yield render_to_string("langui/message.html", {"role": "user", "content": question})
            for message, is_last in agent.chat(question):
                if message["content"] == "" and not is_last:
                    continue
                response = {
                    "role": message["role"],
                    "content": message["content"],
                }
                if message["role"] == "tool" and message["name"] == "edit_user_profile":
                    response["documents"] = cls.get_documents(agent.profile)
                yield render_to_string("langui/message.html", response)

        return StreamingHttpResponse(generate_responses())

    @classmethod
    def start_chat(cls, profile):
        agent = MistralAgent.from_profile(profile)
        response = {
            "role": "assistant",
            "content": "Hello! How can I assist you today?",
            "is_last": True,
            "tokens_used": 0,
        }
        return agent, response

    @staticmethod
    def get_available_profiles():
        for profile in UserProfile.objects.filter(profile_title="default_profile"):
            yield {
                "first_name": profile.first_name,
                "last_name": profile.last_name,
                "photo_url": profile.photo.url,
            }

    @classmethod
    def create_profile(cls, profile_data: dict, form_data: dict, request):
        agent = MistralAgent()
        profile_info = agent.create_profile(profile_data)
        profile = form_data
        embeddings = agent.embed(profile_data["profile_info"])
        embeddings_vector = embeddings.data[0].embedding
        profile_embeddings_uuid = str(uuid4())
        qdrant_client.upload_points(
            collection_name=USER_COLLECTION,
            points=[PointStruct(id=profile_embeddings_uuid, vector=embeddings_vector, payload={"profile_info": profile["profile_info"]})],
        )
        profile_info.update({"embeddings_id": profile_embeddings_uuid})
        profile_info = ProfileInfo.from_json(profile_info)
        profile["profile_info"] = profile_info
        profile["profile_title"] = "default_profile"
        profile_form = UserProfileForm(profile, request.FILES)
        if profile_form.is_valid():
            user_profile = profile_form.save()

        else:
            return JsonResponse({"error": "Invalid profile data"}, status=status.HTTP_400_BAD_REQUEST)

        agent = MistralAgent.from_profile(user_profile)
        request.session["agent"] = agent.to_json()
        CVEditor().generate_cv(user_profile)
        return JsonResponse({"success": "Profile created successfully"})

    @staticmethod
    def get_documents(profile):
        return [
            {
                "name": profile.profile_title,
                "path": "media/cv/" + profile.cv_name.replace(".pdf", ".png"),
            }
            for profile in UserProfile.objects.filter(first_name=profile.first_name, last_name=profile.last_name)
        ]
