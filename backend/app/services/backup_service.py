import os
import shutil
import tarfile
import logging
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from bson import json_util

from app.core.config import settings
from app.core.database import (
    db,
    users_collection,
    documents_collection,
    document_chunks_collection,
    vector_mappings_collection,
    create_indexes,
)
from app.repositories.chunk_repository import ChunkRepository
from app.services.faiss_service import FAISSService
from app.services.faiss_index_service import FAISSIndexService

logger = logging.getLogger(__name__)

TRACKED_COLLECTIONS = {
    "users": users_collection,
    "documents": documents_collection,
    "document_chunks": document_chunks_collection,
    "vector_mappings": vector_mappings_collection,
}


class BackupService:
    """
    Orchestrates backup and disaster recovery for:
    1. MongoDB metadata, documents, chunks, and vector mappings.
    2. Physical storage files (uploaded PDFs, images, receipts).
    3. FAISS vector search index and mapping files.
    4. Index rebuilding procedure directly from restored MongoDB chunk embeddings.
    """

    def __init__(
        self,
        upload_dir: Optional[str] = None,
        faiss_index_path: Optional[str] = None,
        database=None,
    ):
        self.upload_dir = Path(upload_dir or settings.upload_dir)
        self.faiss_index_path = Path(faiss_index_path or settings.faiss_index_path)
        self.db = database if database is not None else db
        self.collections = {
            "users": self.db["users"],
            "documents": self.db["documents"],
            "document_chunks": self.db["document_chunks"],
            "vector_mappings": self.db["vector_mappings"],
        }

    # ------------------------------------------------------------------------
    # 1. MongoDB Backup & Restoration
    # ------------------------------------------------------------------------

    def backup_mongodb(self, dest_dir: Path) -> Dict[str, int]:
        """Export all collections to JSON files using BSON serialization."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        counts = {}

        for name, collection in self.collections.items():
            records = list(collection.find())
            out_file = dest_dir / f"{name}.json"
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(json_util.dumps(records, indent=2))
            counts[name] = len(records)
            logger.info("Backed up %d records from MongoDB collection '%s'", len(records), name)

        return counts

    def restore_mongodb(self, source_dir: Path, drop_existing: bool = True) -> Dict[str, int]:
        """Restore collections from BSON-encoded JSON files and recreate indexes."""
        counts = {}

        for name, collection in self.collections.items():
            in_file = source_dir / f"{name}.json"
            if not in_file.exists():
                logger.warning("Backup file not found for collection '%s': %s", name, in_file)
                counts[name] = 0
                continue

            with open(in_file, "r", encoding="utf-8") as f:
                records = json_util.loads(f.read())

            if drop_existing:
                collection.delete_many({})

            if records:
                collection.insert_many(records)
            counts[name] = len(records)
            logger.info("Restored %d records to MongoDB collection '%s'", len(records), name)

        # Rebuild unique and compound database indexes
        try:
            create_indexes()
        except Exception as err:
            logger.warning("Error recreating database indexes after restore: %s", err)

        return counts

    # ------------------------------------------------------------------------
    # 2. Upload Storage Backup & Restoration
    # ------------------------------------------------------------------------

    def backup_uploads(self, dest_file: Path) -> int:
        """Create a compressed tar.gz archive of all uploaded files."""
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        file_count = 0

        if not self.upload_dir.exists():
            self.upload_dir.mkdir(parents=True, exist_ok=True)

        with tarfile.open(dest_file, "w:gz") as tar:
            for root, _, files in os.walk(self.upload_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(self.upload_dir)
                    tar.add(file_path, arcname=arcname)
                    file_count += 1

        logger.info("Archived %d uploaded files to %s", file_count, dest_file)
        return file_count

    def restore_uploads(self, source_archive: Path, clean_existing: bool = False) -> int:
        """Extract uploads from archive into configured upload directory."""
        if not source_archive.exists():
            logger.warning("Uploads archive does not exist: %s", source_archive)
            return 0

        if clean_existing and self.upload_dir.exists():
            shutil.rmtree(self.upload_dir)

        self.upload_dir.mkdir(parents=True, exist_ok=True)
        file_count = 0

        with tarfile.open(source_archive, "r:gz") as tar:
            if hasattr(tarfile, "data_filter"):
                tar.extractall(path=self.upload_dir, filter="data")
            else:
                tar.extractall(path=self.upload_dir)
            file_count = len(tar.getmembers())

        logger.info("Restored %d files to %s", file_count, self.upload_dir)
        return file_count

    # ------------------------------------------------------------------------
    # 3. FAISS Index Backup, Restoration, & Database Rebuild
    # ------------------------------------------------------------------------

    def backup_faiss(self, dest_dir: Path) -> Dict[str, Any]:
        """Copy the FAISS binary index and JSON mapping file into dest_dir."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        mapping_file = self.faiss_index_path.with_suffix(".json")

        copied = {"index": False, "mapping": False}
        if self.faiss_index_path.exists():
            shutil.copy2(self.faiss_index_path, dest_dir / self.faiss_index_path.name)
            copied["index"] = True

        if mapping_file.exists():
            shutil.copy2(mapping_file, dest_dir / mapping_file.name)
            copied["mapping"] = True

        logger.info("FAISS backup completed: %s", copied)
        return copied

    def restore_faiss(self, source_dir: Path) -> Dict[str, Any]:
        """Restore FAISS binary index and mapping file from source_dir."""
        self.faiss_index_path.parent.mkdir(parents=True, exist_ok=True)
        mapping_file = self.faiss_index_path.with_suffix(".json")

        source_index = source_dir / self.faiss_index_path.name
        source_mapping = source_dir / mapping_file.name

        restored = {"index": False, "mapping": False}
        if source_index.exists():
            shutil.copy2(source_index, self.faiss_index_path)
            restored["index"] = True

        if source_mapping.exists():
            shutil.copy2(source_mapping, mapping_file)
            restored["mapping"] = True

        logger.info("FAISS restore completed: %s", restored)
        return restored

    def rebuild_faiss_from_database(self) -> Dict[str, Any]:
        """
        Reconstruct the FAISS vector index from scratch using active MongoDB chunk embeddings.
        Guarantees complete recoverability even if FAISS index files are destroyed.
        """
        chunk_repo = ChunkRepository(self.db)
        faiss_service = FAISSService(
            index_path=str(self.faiss_index_path),
            mapping_path=str(self.faiss_index_path.with_suffix(".json")),
        )
        index_service = FAISSIndexService(
            chunk_repository=chunk_repo,
            faiss_service=faiss_service,
        )
        return index_service.rebuild_index()

    # ------------------------------------------------------------------------
    # 4. Full Snapshot Creation & Disaster Recovery
    # ------------------------------------------------------------------------

    def create_full_snapshot(self, output_root: Optional[Path] = None) -> Path:
        """
        Generate a complete, self-contained disaster recovery bundle:
        <output_root>/backup_<timestamp>.tar.gz containing:
          - manifest.json
          - mongodb/ (all collections)
          - uploads.tar.gz
          - faiss/ (index and mapping)
        """
        out_base = Path(output_root or "storage/backups")
        out_base.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
        staging_dir = out_base / f"staging_{timestamp}"
        staging_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 1. MongoDB export
            mongo_counts = self.backup_mongodb(staging_dir / "mongodb")

            # 2. Uploads archive
            uploads_count = self.backup_uploads(staging_dir / "uploads.tar.gz")

            # 3. FAISS index files
            faiss_status = self.backup_faiss(staging_dir / "faiss")

            # 4. Manifest
            manifest = {
                "timestamp": timestamp,
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "mongodb_records": mongo_counts,
                "upload_files_count": uploads_count,
                "faiss_backup": faiss_status,
                "format_version": "1.0",
            }
            with open(staging_dir / "manifest.json", "w", encoding="utf-8") as f:
                f.write(json_util.dumps(manifest, indent=2))

            # Package staging directory into final tar.gz bundle
            final_bundle = out_base / f"documind_backup_{timestamp}.tar.gz"
            with tarfile.open(final_bundle, "w:gz") as tar:
                for item in staging_dir.iterdir():
                    tar.add(item, arcname=item.name)

            logger.info("Full disaster recovery backup bundle created at %s", final_bundle)
            return final_bundle
        finally:
            if staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)

    def restore_full_snapshot(
        self,
        bundle_path: Path,
        rebuild_faiss_from_db: bool = False,
    ) -> Dict[str, Any]:
        """
        Complete disaster recovery restoration workflow:
        1. Extract backup bundle.
        2. Restore all MongoDB collections.
        3. Restore all uploaded files.
        4. Restore FAISS files or cleanly rebuild vectors from MongoDB.
        """
        if not bundle_path.exists():
            raise FileNotFoundError(f"Backup bundle not found: {bundle_path}")

        temp_extract = bundle_path.parent / f"extract_{bundle_path.stem}"
        temp_extract.mkdir(parents=True, exist_ok=True)

        try:
            with tarfile.open(bundle_path, "r:gz") as tar:
                if hasattr(tarfile, "data_filter"):
                    tar.extractall(path=temp_extract, filter="data")
                else:
                    tar.extractall(path=temp_extract)

            # Read manifest
            manifest = {}
            manifest_file = temp_extract / "manifest.json"
            if manifest_file.exists():
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest = json_util.loads(f.read())

            # 1. Restore MongoDB
            mongo_dir = temp_extract / "mongodb"
            mongo_results = self.restore_mongodb(mongo_dir) if mongo_dir.exists() else {}

            # 2. Restore Uploads
            uploads_archive = temp_extract / "uploads.tar.gz"
            uploads_restored = self.restore_uploads(uploads_archive, clean_existing=True)

            # 3. Restore or Rebuild FAISS
            if rebuild_faiss_from_db:
                faiss_result = self.rebuild_faiss_from_database()
            else:
                faiss_dir = temp_extract / "faiss"
                faiss_result = self.restore_faiss(faiss_dir) if faiss_dir.exists() else {}

            return {
                "status": "success",
                "manifest": manifest,
                "mongodb_restored": mongo_results,
                "uploads_restored": uploads_restored,
                "faiss_restored": faiss_result,
            }
        finally:
            if temp_extract.exists():
                shutil.rmtree(temp_extract, ignore_errors=True)
