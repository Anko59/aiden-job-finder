from django import forms
from .models import UserProfile


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = "__all__"
        exclude = ["user"]
        widgets = {
            "photo": forms.FileInput(attrs={"class": "form-control"}),
        }


class UserCreationForm(forms.Form):
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    photo = forms.ImageField()
    profile_info = forms.CharField(max_length=10000)

    def llm_input(self):
        return {
            "first_name": self.cleaned_data["first_name"],
            "last_name": self.cleaned_data["last_name"],
            "profile_info": self.cleaned_data["profile_info"],
            "photo_url": "user_photo.png",
            "profile_title": "default_profile",
        }
