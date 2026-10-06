from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")

db = client["documind"]

users_collection = db["users"]
documents_collection = db["documents"]
document_chunks_collection = db["document_chunks"]


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

    document_chunks_collection.create_index(
        [
            ("document_id", 1),
            ("chunk_id", 1),
        ],
        unique=True,
    )
