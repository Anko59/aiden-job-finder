from .models import UserProfile


def get_documents_and_profile(profile):
    documents = []
    first_name = profile["first_name"]
    last_name = profile["last_name"]
    for profile in UserProfile.objects.filter(first_name=first_name, last_name=last_name):
        documents.append(
            {
                "name": profile.profile_title,
                "path": profile.cv_name - ".pdf",
            }
        )
    return documents, profile.profile_info.__dict__


def get_available_profiles():
    for profile in UserProfile.objects.filter(profile_title="default_profile"):
        yield {
            "first_name": profile.first_name,
            "last_name": profile.last_name,
            "photo_url": profile.photo.url,
        }
