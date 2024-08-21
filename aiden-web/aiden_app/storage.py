from storages.backends.s3boto3 import S3Boto3Storage
import os
import uuid
from aiden_project import settings
import boto3


class UUIDS3Boto3Storage(S3Boto3Storage):
    def __init__(self, object_folder: str, **settings):
        super().__init__(**settings)
        self.object_folder = object_folder

    def get_available_name(self, name, max_length=None):
        ext = os.path.splitext(name)[1]
        name = f"{self.object_folder}/{uuid.uuid4()}{ext}"
        return super().get_available_name(name, max_length)


def get_s3_client():
    return boto3.client(
        service_name="s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
    )


def get_presigned_url(file_key: str, expiration=500) -> str:
    # create client for s3 given acces key and secret key
    s3_client = get_s3_client()
    presigned_url = s3_client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
            "Key": file_key,
        },
        ExpiresIn=expiration,  # URL expires in 5 minutes
    )
    # return presigned url
    external_url = presigned_url.replace(settings.AWS_S3_ENDPOINT_URL, settings.AWS_S3_EXTERNAL_DOMAIN)
    return external_url
