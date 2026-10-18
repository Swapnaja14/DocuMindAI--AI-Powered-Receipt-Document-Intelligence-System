import argparse
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.services.backup_service import BackupService


def main():
    parser = argparse.ArgumentParser(
        description="DocuMind AI Backup and Disaster Recovery Management Tool"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--backup",
        action="store_true",
        help="Generate a complete disaster recovery snapshot (MongoDB, uploads, FAISS)",
    )
    group.add_argument(
        "--restore",
        type=str,
        metavar="PATH",
        help="Restore complete system state from a specified backup bundle archive",
    )
    group.add_argument(
        "--rebuild-index",
        action="store_true",
        help="Reconstruct FAISS vector index directly from MongoDB chunk embeddings",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="storage/backups",
        help="Directory where backup bundles are stored (default: storage/backups)",
    )
    parser.add_argument(
        "--rebuild-faiss-on-restore",
        action="store_true",
        help="Rebuild FAISS index from MongoDB during restoration instead of copying archived index files",
    )

    args = parser.parse_args()
    service = BackupService()

    if args.backup:
        print("[*] Creating full DocuMind AI disaster recovery snapshot...")
        bundle_path = service.create_full_snapshot(output_root=Path(args.output_dir))
        print(f"[+] Backup successfully generated: {bundle_path}")

    elif args.restore:
        archive_path = Path(args.restore)
        print(f"[*] Restoring DocuMind AI state from: {archive_path}")
        result = service.restore_full_snapshot(
            bundle_path=archive_path,
            rebuild_faiss_from_db=args.rebuild_faiss_on_restore,
        )
        print("[+] Restoration completed successfully!")
        print(f"  MongoDB Restored: {result['mongodb_restored']}")
        print(f"  Upload Files Restored: {result['uploads_restored']}")
        print(f"  FAISS Restored: {result['faiss_restored']}")

    elif args.rebuild_index:
        print("[*] Rebuilding FAISS vector index from MongoDB chunk embeddings...")
        status = service.rebuild_faiss_from_database()
        print("[+] FAISS vector index rebuild complete!")
        print(f"  Status: {status}")


if __name__ == "__main__":
    main()
