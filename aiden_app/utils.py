from .models import UserProfile


def get_documents(profile):
    return [
        {
            "name": profile.profile_title,
            "path": "media/cv/" + profile.cv_name.replace(".pdf", ".png"),
        }
        for profile in UserProfile.objects.filter(first_name=profile.first_name, last_name=profile.last_name)
    ]


def get_available_profiles():
    for profile in UserProfile.objects.filter(profile_title="default_profile"):
        yield {
            "first_name": profile.first_name,
            "last_name": profile.last_name,
            "photo_url": profile.photo.url,
        }
