from django.urls import path
from aiden_app.consumers import ProfileConsumer

websocket_urlpatterns = [
    path("ws/get_profiles/", ProfileConsumer.as_asgi()),
]
