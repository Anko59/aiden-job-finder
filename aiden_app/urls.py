from django.urls import path

from . import views

chat_view = views.ChatView.as_view()

urlpatterns = [
    path("", chat_view, name="chat_view"),
]
