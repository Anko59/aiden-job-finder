import json
from django.http import JsonResponse, StreamingHttpResponse
from rest_framework import status

from aiden_app.services.agents.mistral_agent import MistralAgent
from aiden_app.services.agents.prompts import START_CHAT_PROMPT
from aiden_app.services.tools.utils.cv_editor import CVEditor
from aiden_app.models import UserProfile, ProfileInfo
from aiden_app.forms import UserProfileForm


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
                    response["documents"] = cls.get_documents(agent.profile)
                yield json.dumps(response)

        return StreamingHttpResponse(generate_responses())

    @classmethod
    def start_chat(cls, profile):
        documents = cls.get_documents(profile)
        agent = MistralAgent.from_profile(profile)
        response = {
            "role": "assistant",
            "content": "Hello! How can I assist you today?",
            "is_last": True,
            "documents": documents,
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

        return StreamingHttpResponse(cls._respond_create_profile(user_profile))

    @classmethod
    def _respond_create_profile(cls, profile: UserProfile):
        CVEditor().generate_cv(profile)
        profiles = list(cls.get_available_profiles())

        yield json.dumps({"role": "get_profiles", "content": profiles})
        documents = cls.get_documents(profile)
        response = {
            "role": "assistant",
            "content": START_CHAT_PROMPT,
            "is_last": True,
            "documents": documents,
            "tokens_used": 0,
        }
        yield json.dumps(response)

    @staticmethod
    def get_documents(profile):
        return [
            {
                "name": profile.profile_title,
                "path": "media/cv/" + profile.cv_name.replace(".pdf", ".png"),
            }
            for profile in UserProfile.objects.filter(first_name=profile.first_name, last_name=profile.last_name)
        ]
