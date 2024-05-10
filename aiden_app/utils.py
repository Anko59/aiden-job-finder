import os
import json


def get_documents(profile):
    first_name = profile["first_name"]
    last_name = profile["last_name"]
    user_data_dir = os.path.join(os.path.dirname(__file__), "user_data")
    user_dir = os.path.join(
        user_data_dir,
        f"{first_name.lower()}_{last_name.lower()}",
    )
    documents = [
        {
            "name": f,
            "path": os.path.join(
                "static",
                "images",
                "user_images",
                "cv",
                f'cv_{first_name}_{last_name}_{f.split(".")[0]}.png',
            ),
        }
        for f in os.listdir(user_dir)
        if f.endswith(".json")
    ]
    return documents, user_dir


def get_available_profiles():
    user_data_dir = os.path.join(os.path.dirname(__file__), "user_data")
    user_folders = [f for f in os.listdir(user_data_dir) if os.path.isdir(os.path.join(user_data_dir, f))]
    default_profile_files = [os.path.join(user_data_dir, folder, "default_profile.json") for folder in user_folders]

    for profile_file in default_profile_files:
        with open(profile_file, "r") as f:
            profile = json.load(f)
            yield {
                "first_name": profile["first_name"],
                "last_name": profile["last_name"],
                "photo_url": profile["photo_url"],
            }
