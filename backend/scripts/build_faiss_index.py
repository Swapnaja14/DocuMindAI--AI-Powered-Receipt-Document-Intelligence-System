import argparse
import sys
from pathlib import Path

# Add project root to sys.path so script can be run directly as `python scripts/build_faiss_index.py`
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.core.database import db
from app.repositories.chunk_repository import ChunkRepository
from app.services.faiss_service import FAISSService
from app.services.faiss_index_service import FAISSIndexService


def main():
    parser = argparse.ArgumentParser(
        description="Build, rebuild, or verify consistency of the FAISS vector index against MongoDB."
    )
    parser.add_argument(
        "--rebuild",
        "--recover",
        action="store_true",
        help="Perform a clean rebuild: purge stale FAISS vectors and reindex active MongoDB embeddings.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Perform a bidirectional consistency check without mutating the index.",
    )

    args = parser.parse_args()

    chunk_repository = ChunkRepository(db)
    faiss_service = FAISSService()

    index_service = FAISSIndexService(
        chunk_repository=chunk_repository,
        faiss_service=faiss_service,
    )

    if args.check:
        print("Auditing MongoDB <-> FAISS consistency...")
        report = index_service.check_consistency()
        print("Consistency Report:")
        for k, v in report.items():
            print(f"  {k}: {v}")
        return

    if args.rebuild:
        print("Rebuilding FAISS index from scratch (Recovery mode)...")
        result = index_service.rebuild_index()
        print("FAISS Index Rebuilt Successfully!")
        print("Status:", result["status"])
        print("Post-Rebuild Consistency:", result["consistency"])
    else:
        print("Synchronizing MongoDB embeddings into FAISS index...")
        status = index_service.build_index(force_clean=False)
        print("FAISS index built successfully:")
        print(status)
        consistency = index_service.check_consistency()
        print("Consistency Status:", "Consistent" if consistency["consistent"] else "Discrepancy Detected")


if __name__ == "__main__":
    main()

