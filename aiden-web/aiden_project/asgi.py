import os
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
import aiden_app.routing

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "aiden_project.settings")

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": AuthMiddlewareStack(URLRouter(aiden_app.routing.websocket_urlpatterns)),
    }
)

print(application)
print("Websocket URL patterns: ", aiden_app.routing.websocket_urlpatterns)
