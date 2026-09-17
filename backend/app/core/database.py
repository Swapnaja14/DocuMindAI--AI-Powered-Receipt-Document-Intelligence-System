from pymongo import MongoClient

from app.core.config import settings

client = MongoClient(settings.mongodb_url)
db = client[settings.mongodb_database]

users_collection = db["users"]
documents_collection = db["documents"]


def create_indexes() -> None:
    users_collection.create_index(
        "email",
        unique=True,
    )

    documents_collection.create_index(
        [
            ("user_id", 1), # ascending according to User id
            ("processing.uploaded_at", -1) # descending according to upload time (newest first)
        ]
    )

    documents_collection.create_index(
        "status",
    )
