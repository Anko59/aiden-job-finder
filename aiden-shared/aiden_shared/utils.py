import hashlib
import uuid


def reference_to_uuid(reference: str) -> uuid.UUID:
    return uuid.UUID(hashlib.md5(reference.encode()).hexdigest())
