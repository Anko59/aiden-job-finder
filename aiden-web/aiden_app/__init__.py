import os

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, VectorParams

USER_COLLECTION = "user_profile"

if (qdrant_url := os.getenv("QDRANT_URL")) is None:
    raise Exception("QDRANT_URL env variable is not set")
qdrant_client = QdrantClient(url=qdrant_url)

try:
    qdrant_client.create_collection(
        collection_name=USER_COLLECTION,
        vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
    )
except UnexpectedResponse:
    pass
