from django.contrib import admin
from django.urls import include, path
from django.conf.urls.i18n import i18n_patterns


urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("", include("django.contrib.auth.urls")),
    *i18n_patterns(path("", include("aiden_app.urls"))),
]
