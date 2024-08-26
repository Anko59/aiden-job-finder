import json
import os
from typing import Iterable
from uuid import uuid4
import httpx
from aiden_shared.constants import JOB_COLLECTION
from aiden_shared.models import JobOffer
from aiden_shared.utils import reference_to_uuid
from django.http import JsonResponse, StreamingHttpResponse
from django.template.loader import render_to_string
from qdrant_client.models import PointStruct
from rest_framework import status
from mistralai.models.chat_completion import FunctionCall, ToolCall

from aiden_app import USER_COLLECTION, qdrant_client
from aiden_app.forms import UserProfileForm
from aiden_app.models import ProfileInfo, UserProfile, AssistantMesssage, ToolMessage
from aiden_app.services.agents.mistral_agent import MistralAgent
from aiden_app.services.tools.utils.cv_editor import CVEditor
from aiden_app.services.tools.scraper_tool import ScraperTool
from aiden_app.storage import get_presigned_url
from aiden_app.models import Conversation, Message
from aiden_app.services.agents.agent import Agent


def get_conversation_from_session(session) -> Conversation:
    conversation_json = session.get("conversation")
    if not conversation_json:
        return None
    from loguru import logger

    logger.error(conversation_json)
    return Conversation.objects.get(conversation_id=conversation_json.get("conversation_id"))


def get_agent_from_session(session) -> MistralAgent:
    agent_json = session.get("agent")
    if not agent_json:
        return None
    return MistralAgent.from_json(agent_json)


def get_profile_from_session(request) -> UserProfile:
    profile_json = request.session.get("profile")
    profile = UserProfile.objects.get(
        first_name=profile_json.get("first_name"),
        last_name=profile_json.get("last_name"),
        profile_title="default_profile",
        user=request.user,
    )
    return profile


def chat_wrapper(request, question: str, agent: Agent, conversation: Conversation):
    def generate_responses():
        Message.objects.create(
            conversation=conversation,
            human=True,
            content=question,
            user=request.user,
        )
        yield AssistantMesssage(
            title="User", content=render_to_string("langui/message.html", {"role": "user", "content": question})
        ).model_dump_json()
        for message in agent.chat(question):
            message: ToolMessage = message
            Message.objects.create(
                conversation=conversation,
                human=False,
                content=message.user_message,
                user=request.user,
            )
            yield AssistantMesssage(
                title=message.function_nane,
                content=message.user_message,
                container_id=message.container_id,
            ).model_dump_json()
        request.session["agent"] = agent.to_json()
        request.session.save()

    return StreamingHttpResponse(generate_responses())


def start_chat(profile):
    conversation = Conversation.objects.create(user=profile.user, user_profile=profile)
    agent = MistralAgent.from_profile(profile)
    response = {
        "role": "assistant",
        "content": f"Hello! How can I assist you today {profile} ? ",
        "is_last": True,
        "tokens_used": 0,
    }
    Message.objects.create(conversation=conversation, human=False, content=response["content"], user=profile.user)
    return agent, response, conversation


def get_available_profiles(user):
    for profile in UserProfile.objects.filter(user=user, profile_title="default_profile"):
        yield {
            "first_name": profile.first_name,
            "last_name": profile.last_name,
            "photo_url": get_presigned_url(profile.photo.name),
        }


def create_profile(profile_data: dict, form_data: dict, request):
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
    profile_info["email"] = profile.get("email") or request.user.email
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


def job_offer_from_reference(reference):
    response = qdrant_client.retrieve(collection_name=JOB_COLLECTION, ids=[str(reference_to_uuid(reference).hex)], with_payload=True)
    point = response[0]
    return JobOffer(**point.payload)


def get_offer_focus(request, job_offer: JobOffer):
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
    agent = get_agent_from_session(request.session)
    base_profile = get_profile_from_session(request)
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
        new_cv = CVEditor().generate_cv(new_profile)
        resume = {"name": new_cv.name, "path": get_presigned_url(new_cv.file.name)}
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
    request.session["agent"] = agent.to_json()
    request.session.save()


def load_next_page(request, page: int, container_id: str) -> Iterable[str]:
    agent = get_agent_from_session(request.session)
    scraper_tool: ScraperTool = agent.tool_aggregator.get_tool("ScraperTool")
    for message in scraper_tool.get_next_page_jobs(container_id, page):
        message: ToolMessage = message
        if message.agent_message is not None:
            agent.messages.append(
                agent.message_class(
                    role="assistant",
                    content="",
                    tool_calls=[ToolCall(id=uuid4().hex[0:9], function=FunctionCall(name="search_jobs", arguments=""))],
                )
            )
            agent.messages.append(agent.message_class(**message.agent_message))
            agent.messages.append(
                agent.message_class(
                    role="assistant",
                    content="I performed a job search.",
                )
            )
        if message.user_message is not None:
            yield AssistantMesssage(
                title=message.function_nane,
                content=message.user_message,
                container_id=message.container_id,
            ).model_dump_json()
    request.session["agent"] = agent.to_json()
    request.session.save()
