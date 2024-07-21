import json
import os
from uuid import uuid4

import httpx
import markdown2
from aiden_shared.constants import JOB_COLLECTION
from aiden_shared.models import JobOffer
from aiden_shared.utils import reference_to_uuid
from django.http import JsonResponse, StreamingHttpResponse
from django.template.loader import render_to_string
from qdrant_client.models import PointStruct
from rest_framework import status

from aiden_app import USER_COLLECTION, qdrant_client
from aiden_app.forms import UserProfileForm
from aiden_app.models import ProfileInfo, UserProfile
from aiden_app.services.agents.agent import Agent
from aiden_app.services.agents.mistral_agent import MistralAgent
from aiden_app.services.tools.utils.cv_editor import CVEditor


class ChatService:
    @staticmethod
    def get_agent_from_session(session) -> MistralAgent:
        agent_json = session.get("agent")
        if not agent_json:
            return None
        return MistralAgent.from_json(agent_json)

    @staticmethod
    def get_profile_from_session(session) -> UserProfile:
        profile_json = session.get("profile")
        profile = UserProfile.objects.get(
            first_name=profile_json.get("first_name"), last_name=profile_json.get("last_name"), profile_title="default_profile"
        )
        return profile

    @classmethod
    def chat_wrapper(cls, agent: Agent, question):
        def generate_responses():
            yield render_to_string("langui/message.html", {"role": "user", "content": question})
            for message in agent.chat(question):
                message = message.model_dump()
                role = message["role"]
                content = message["content"]
                if role == "assistant":
                    content = markdown2.markdown(content)
                elif role == "tool":
                    content = json.loads(content)
                    try:
                        content["result"] = json.loads(content["result"])
                        for i in range(len(content["result"])):
                            try:
                                content["result"][i]["profile"] = markdown2.markdown(content["result"][i]["profile"])
                            except Exception:
                                pass
                        for i in range(len(content["result"])):
                            try:
                                content["result"][i]["organization"]["description"] = markdown2.markdown(
                                    content["result"][i]["organization"]["description"]
                                )
                            except Exception:
                                pass
                    except Exception:
                        pass
                response = {
                    "role": role,
                    "content": content,
                }
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
        profile_info = ProfileInfo.from_json(profile_info, user=request.user)
        profile["profile_info"] = profile_info
        profile["profile_title"] = "default_profile"
        profile["user"] = request.user
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

    @staticmethod
    def job_offer_from_reference(reference):
        response = qdrant_client.retrieve(collection_name=JOB_COLLECTION, ids=[str(reference_to_uuid(reference).hex)], with_payload=True)
        point = response[0]
        return JobOffer(**point.payload)

    @classmethod
    def get_offer_focus(cls, request, job_offer: JobOffer):
        yield render_to_string("langui/offer-focus.html", {"offer": job_offer})
        yield render_to_string(
            "langui/message.html",
            {"role": "assistant", "content": "I will now search for the information required to apply for this job offer."},
        )
        url = f"{os.environ.get('RECOMMENDER_API_URL')}/get_form"
        payload = {
            "job_reference": job_offer.reference,
        }
        response = httpx.post(url=url, json=payload, timeout=60)
        response.raise_for_status()

        results = response.json()
        fields = json.loads(results["json_content"])["properties"]
        agent = cls.get_agent_from_session(request.session)
        base_profile = cls.get_profile_from_session(request.session)
        if "resume" in fields:
            new_profile_info = agent.edit_profile(base_profile.profile_info.to_json(), job_offer.model_dump())
            embeddings = agent.embed(json.dumps(new_profile_info))
            embeddings_vector = embeddings.data[0].embedding
            profile_embeddings_uuid = str(uuid4())
            qdrant_client.upload_points(
                collection_name=USER_COLLECTION,
                points=[PointStruct(id=profile_embeddings_uuid, vector=embeddings_vector, payload={"profile_info": new_profile_info})],
            )
            new_profile_info.update({"embeddings_id": profile_embeddings_uuid})
            profile_info = ProfileInfo.from_json(new_profile_info, user=request.user)
            profile_title = profile_info.cv_title
            if UserProfile.objects.filter(
                first_name=base_profile.first_name, last_name=base_profile.last_name, profile_title=profile_info.cv_title
            ).exists():
                profile_title = profile_info.cv_title + "_" + str(uuid4())[0:4]
            new_profile = UserProfile.objects.create(
                first_name=base_profile.first_name,
                last_name=base_profile.last_name,
                profile_title=profile_title,
                profile_info=profile_info,
                photo=base_profile.photo,
                user=request.user,
            )
            new_profile.save()
            request.session["profile"] = new_profile.to_json()
            CVEditor().generate_cv(new_profile)
            resume = {"name": new_profile.cv_name, "path": "media/cv/" + new_profile.cv_name.replace(".pdf", ".png")}
            del fields["resume"]
            yield render_to_string("langui/edited-cv-display.html", {"resume": resume})

        if "cover_letter" in fields:
            cover_letter = agent.generate_cover_letter(job_offer.model_dump(), base_profile.profile_info.to_json())
            del fields["cover_letter"]
            yield render_to_string("langui/cover-letter-display.html", {"cover_letter": cover_letter})
        if fields:
            filled_fields = agent.fill_form(fields, job_offer.model_dump(), base_profile.profile_info.to_json())
            filled_fields = [{"title": k, "value": v} for k, v in filled_fields.items()]
            yield render_to_string("langui/filled-form-display.html", {"fields": filled_fields})
