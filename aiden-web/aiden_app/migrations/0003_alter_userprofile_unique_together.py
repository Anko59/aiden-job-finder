# Generated by Django 5.0.6 on 2024-05-13 21:31

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("aiden_app", "0002_alter_userprofile_photo"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="userprofile",
            unique_together={("first_name", "last_name", "profile_title")},
        ),
    ]
