from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("aiden_app.urls")),
    path("", include("django.contrib.auth.urls")),  # For built-in auth views like login, logout, password reset
]
