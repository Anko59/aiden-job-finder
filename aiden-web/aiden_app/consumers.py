from channels.generic.websocket import AsyncWebsocketConsumer
from aiden_app.services.chat_service import ChatService
from django.template.loader import render_to_string


class ProfileConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        await self.send_profiles()

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data):
        pass

    async def send_profiles(self):
        # Example data, replace with actual profile data fetching
        profiles = list(ChatService.get_available_profiles())
        profiles = render_to_string("aiden_app/templates/langui/profile-icons.html", {"profiles": profiles})
        await self.send(text_data=profiles)
