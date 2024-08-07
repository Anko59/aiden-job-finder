from django.urls import path, re_path

from . import views, views_v2

urlpatterns = [
    path("chat/", views.langui_view, name="langui_view"),
    path("api/question", views.handle_question, name="question"),
    path("api/start_chat", views.handle_start_chat, name="start_chat"),
    path("api/get_profiles", views.handle_get_profiles, name="get_profiles"),
    path("api/create_profile", views.handle_create_profile, name="create_profile"),
    path("api/get_profile_creation_form", views.get_profile_creation_form, name="get_profile_creation_form"),
    path("api/get_documents", views.get_user_documents, name="get_documents"),
    path("api/get_offer_focus", views.handle_offer_focus, name="get_document"),
    re_path(r"^api/v2/(?P<endpoint>.+)/$", views_v2.api_dispatcher, name="api_dispatcher"),
    path("signup/", views.signup_view, name="signup"),
    path("login/", views.login_view, name="login"),
    path("", views.home_view, name="home"),
]
