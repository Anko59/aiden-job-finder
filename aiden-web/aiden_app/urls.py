from django.urls import path, re_path

from . import views
from . import views_v2

langui_view = views.LanguiView.as_view()

urlpatterns = [
    path("", langui_view, name="langui_view"),
    path("api/question", views.handle_question, name="question"),
    path("api/start_chat", views.handle_start_chat, name="start_chat"),
    path("api/get_profiles", views.handle_get_profiles, name="get_profiles"),
    path("api/create_profile", views.handle_create_profile, name="create_profile"),
    path("api/get_profile_creation_form", views.get_profile_creation_form, name="get_profile_creation_form"),
    path("api/get_documents", views.get_user_documents, name="get_documents"),
    re_path(r"^api/v2/(?P<endpoint>.+)/$", views_v2.api_dispatcher, name="api_dispatcher"),
]
