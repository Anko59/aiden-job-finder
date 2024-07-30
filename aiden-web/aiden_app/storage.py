from storages.backends.s3boto3 import S3Boto3Storage
import os
import uuid


class UUIDS3Boto3Storage(S3Boto3Storage):
    def get_available_name(self, name, max_length=None):
        ext = os.path.splitext(name)[1]
        name = f"{uuid.uuid4()}{ext}"
        return super().get_available_name(name, max_length)
