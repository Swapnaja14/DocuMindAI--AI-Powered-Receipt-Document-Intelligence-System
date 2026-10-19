from typing import Any, Dict, List, Optional, Union
from bson import ObjectId


class DocumentRepository:
    """
    Data access layer for the documents collection.
    """

    def __init__(self, db):
        self.collection = db["documents"]

    def get_by_id(self, document_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
        """
        Retrieve a single document by its ID (string or ObjectId).
        """
        if isinstance(document_id, str) and ObjectId.is_valid(document_id):
            query = {"_id": ObjectId(document_id)}
        elif isinstance(document_id, ObjectId):
            query = {"_id": document_id}
        else:
            query = {"_id": document_id}

        return self.collection.find_one(query)

    def get_by_ids(self, document_ids: List[Union[str, ObjectId]]) -> List[Dict[str, Any]]:
        """
        Retrieve multiple documents by their IDs in a single query.
        """
        if not document_ids:
            return []

        object_ids = [
            ObjectId(d) for d in document_ids if isinstance(d, str) and ObjectId.is_valid(d)
        ]
        string_ids = [str(d) for d in document_ids]

        conditions: List[Dict[str, Any]] = [{"_id": {"$in": string_ids}}]
        if object_ids:
            conditions.append({"_id": {"$in": object_ids}})

        return list(self.collection.find({"$or": conditions}))

    def get_user_documents_by_ids(
        self, document_ids: List[Union[str, ObjectId]], user_id: str
    ) -> List[Dict[str, Any]]:
        """
        Retrieve documents matching document_ids belonging strictly to user_id.
        Enforces tenant isolation directly in the MongoDB query.
        """
        if not document_ids:
            return []

        object_ids = [
            ObjectId(d) for d in document_ids if isinstance(d, str) and ObjectId.is_valid(d)
        ]
        string_ids = [str(d) for d in document_ids]

        id_conditions: List[Dict[str, Any]] = [{"_id": {"$in": string_ids}}]
        if object_ids:
            id_conditions.append({"_id": {"$in": object_ids}})

        user_conditions: List[Dict[str, Any]] = [{"user_id": str(user_id)}]
        if ObjectId.is_valid(str(user_id)):
            user_conditions.append({"user_id": ObjectId(str(user_id))})

        query = {
            "$and": [
                {"$or": id_conditions},
                {"$or": user_conditions},
            ]
        }
        return list(self.collection.find(query))

    def find_user_documents_filtered(
        self,
        user_id: str,
        vendor: Optional[str] = None,
        min_total: Optional[float] = None,
        max_total: Optional[float] = None,
        currency: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Query documents strictly scoped to user_id matching structured extraction filters.
        Supports filtering by vendor, numeric total range, currency, and date range.
        """
        import re

        user_conditions: List[Dict[str, Any]] = [{"user_id": str(user_id)}]
        if ObjectId.is_valid(str(user_id)):
            user_conditions.append({"user_id": ObjectId(str(user_id))})

        and_clauses: List[Dict[str, Any]] = [{"$or": user_conditions}]

        if vendor and vendor.strip():
            escaped_vendor = re.escape(vendor.strip())
            and_clauses.append({
                "$or": [
                    {"extracted_data.vendor": {"$regex": escaped_vendor, "$options": "i"}},
                    {"filename": {"$regex": escaped_vendor, "$options": "i"}},
                ]
            })

        if currency and currency.strip():
            and_clauses.append({
                "extracted_data.currency": {
                    "$regex": f"^{re.escape(currency.strip())}$",
                    "$options": "i",
                }
            })

        total_clauses: Dict[str, Any] = {}
        if min_total is not None:
            total_clauses["$gte"] = float(min_total)
        if max_total is not None:
            total_clauses["$lte"] = float(max_total)
        if total_clauses:
            and_clauses.append({"extracted_data.total": total_clauses})

        if start_date and start_date.strip():
            and_clauses.append({
                "$or": [
                    {"extracted_data.date": {"$gte": start_date.strip()}},
                    {"created_at": {"$gte": start_date.strip()}},
                ]
            })

        if end_date and end_date.strip():
            and_clauses.append({
                "$or": [
                    {"extracted_data.date": {"$lte": end_date.strip()}},
                    {"created_at": {"$lte": end_date.strip()}},
                ]
            })

        query = {"$and": and_clauses} if len(and_clauses) > 1 else and_clauses[0]

        cursor = self.collection.find(query).sort("created_at", -1).limit(limit)
        return list(cursor)

    def get_expense_summary(self, user_id: str, params: Any = None):
        """
        Calculates structured expense summary metrics for the given user.
        """
        from app.services.expense_service import ExpenseService
        service = ExpenseService(self.collection.database)
        return service.compute_summary(user_id=user_id, params=params)

