import argparse
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.core.database import db
from app.repositories.chunk_repository import ChunkRepository
from app.services.faiss_service import FAISSService
from app.services.faiss_index_service import FAISSIndexService


def main():
    parser = argparse.ArgumentParser(
        description="Verify MongoDB <-> FAISS index consistency and optionally auto-recover."
    )
    parser.add_argument(
        "--fix",
        "--auto-recover",
        dest="auto_recover",
        action="store_true",
        help="Automatically rebuild the FAISS index if any discrepancy is detected.",
    )

    args = parser.parse_args()

    chunk_repository = ChunkRepository(db)
    faiss_service = FAISSService()

    index_service = FAISSIndexService(
        chunk_repository=chunk_repository,
        faiss_service=faiss_service,
    )

    print("=== Auditing MongoDB <-> FAISS Consistency ===")
    report = index_service.check_consistency()

    for k, v in report.items():
        print(f"  {k}: {v}")

    if report["consistent"]:
        print("\n[OK] MongoDB and FAISS are fully synchronized.")
    else:
        print("\n[WARNING] Discrepancy detected between MongoDB and FAISS.")
        if args.auto_recover:
            print("\nExecuting recovery: rebuilding FAISS index from MongoDB...")
            recovery_result = index_service.rebuild_index()
            print("Recovery completed. Post-recovery report:")
            for k, v in recovery_result["consistency"].items():
                print(f"  {k}: {v}")
            if recovery_result["consistency"]["consistent"]:
                print("\n[SUCCESS] Consistency restored.")
            else:
                print("\n[ERROR] Recovery failed to achieve consistency.")
        else:
            print("Run with `--fix` or execute `python scripts/build_faiss_index.py --rebuild` to recover.")


if __name__ == "__main__":
    main()
