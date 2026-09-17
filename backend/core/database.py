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
        "user_id",
    )

    documents_collection.create_index(
        "status",
    )

    documents_collection.create_index(
        "processing.uploaded_at",
    )