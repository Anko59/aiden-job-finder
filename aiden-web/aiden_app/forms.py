import json

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import ProfileInfo, UserProfile


class SignUpForm(UserCreationForm):
    email = forms.EmailField(max_length=254, help_text="Required. Inform a valid email address.")

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data["usable_password"] = True
        return cleaned_data


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = "__all__"
        widgets = {
            "photo": forms.FileInput(attrs={"class": "form-control"}),
        }


class UserProfileCreationForm(forms.Form):
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    profile_info = forms.CharField(max_length=10000)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super(UserProfileCreationForm, self).__init__(*args, **kwargs)

    def llm_input(self):
        return {
            "first_name": self.cleaned_data["first_name"],
            "last_name": self.cleaned_data["last_name"],
            "profile_info": self.cleaned_data["profile_info"],
            "profile_title": "default_profile",
        }

    def save(self):
        profile_info_data = json.loads(self.cleaned_data["profile_info"])
        if profile_info_data["email"] is None:
            profile_info_data["email"] = self.user.email
        profile_info = ProfileInfo.from_json(profile_info_data, user=self.user)
        user_profile = UserProfile.objects.create(
            user=self.user,
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
            profile_info=profile_info,
        )
        return user_profile
