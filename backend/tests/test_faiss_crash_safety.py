import json
import os
from pathlib import Path
from unittest.mock import patch

import faiss
import numpy as np
import pytest

from app.services.faiss_service import FAISSService


def test_crash_safe_save_creates_manifest_and_valid_files(tmp_path):
    """
    Test that saving creates chunks.index, chunk_mapping.json, and manifest.json
    with matching counts and valid contents.
    """
    index_file = str(tmp_path / "test.index")
    mapping_file = str(tmp_path / "test_mapping.json")
    manifest_file = str(tmp_path / "manifest.json")

    faiss_service = FAISSService(
        index_path=index_file,
        mapping_path=mapping_file,
        manifest_path=manifest_file,
    )

    chunks = [
        {"chunk_id": "c1", "embedding": [0.1, 0.2, 0.3]},
        {"chunk_id": "c2", "embedding": [0.4, 0.5, 0.6]},
    ]
    faiss_service.add_embeddings(chunks)

    assert Path(index_file).exists()
    assert Path(mapping_file).exists()
    assert Path(manifest_file).exists()

    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["total_vectors"] == 2
    assert manifest["mapped_chunks"] == 2
    assert manifest["index_file"] == "test.index"
    assert manifest["mapping_file"] == "test_mapping.json"


def test_backup_retained_across_updates(tmp_path):
    """
    Test that the previous valid snapshot (.bak) is preserved when a new version is saved.
    """
    index_file = str(tmp_path / "test.index")
    mapping_file = str(tmp_path / "test_mapping.json")
    manifest_file = str(tmp_path / "manifest.json")

    faiss_service = FAISSService(
        index_path=index_file,
        mapping_path=mapping_file,
        manifest_path=manifest_file,
    )

    # First version: 2 chunks
    faiss_service.add_embeddings([
        {"chunk_id": "c1", "embedding": [0.1, 0.2, 0.3]},
        {"chunk_id": "c2", "embedding": [0.4, 0.5, 0.6]},
    ])

    backup_index = Path(str(tmp_path / "test.index.bak"))
    backup_mapping = Path(str(tmp_path / "test_mapping.json.bak"))

    # Second version: add 1 more chunk -> total 3 chunks
    faiss_service.add_embedding("c3", [0.7, 0.8, 0.9])

    assert backup_index.exists()
    assert backup_mapping.exists()

    # Verify backup contains version 1 (2 vectors)
    bak_idx = faiss.read_index(str(backup_index))
    assert bak_idx.ntotal == 2

    with open(backup_mapping, "r", encoding="utf-8") as f:
        bak_map = json.load(f)
    assert len(bak_map) == 2


def test_recovery_from_corrupted_index_file(tmp_path):
    """
    Simulate application crash causing a corrupted/truncated index file.
    Verify that FAISSService detects corruption and recovers the previous valid snapshot.
    """
    index_file = str(tmp_path / "test.index")
    mapping_file = str(tmp_path / "test_mapping.json")
    manifest_file = str(tmp_path / "manifest.json")

    service = FAISSService(
        index_path=index_file,
        mapping_path=mapping_file,
        manifest_path=manifest_file,
    )

    # Save initial valid snapshot (2 vectors)
    service.add_embeddings([
        {"chunk_id": "chunk_1", "embedding": [0.1, 0.2, 0.3]},
        {"chunk_id": "chunk_2", "embedding": [0.4, 0.5, 0.6]},
    ])

    # Save second snapshot (3 vectors) to generate a valid .bak (2 vectors)
    service.add_embedding("chunk_3", [0.7, 0.8, 0.9])
    assert service.count() == 3

    # Corrupt the primary active index file (simulate power loss / interrupted write)
    with open(index_file, "wb") as f:
        f.write(b"CORRUPTED_INDEX_BINARY_DATA_TRUNCATED")

    # Re-instantiate FAISSService -> Should detect corruption and safely recover from backup
    recovered_service = FAISSService(
        index_path=index_file,
        mapping_path=mapping_file,
        manifest_path=manifest_file,
    )

    status = recovered_service.status()
    assert status["loaded"] is True
    assert status["total_vectors"] == 2
    assert status["mapped_chunks"] == 2
    assert "chunk_1" in recovered_service.chunk_id_to_id
    assert "chunk_2" in recovered_service.chunk_id_to_id


def test_recovery_from_count_mismatch(tmp_path):
    """
    Simulate an interrupted save where FAISS index was updated to 3 vectors,
    but chunk_mapping.json remained at 2 entries.
    Verify that load detects the count mismatch and recovers from the valid backup.
    """
    index_file = str(tmp_path / "test.index")
    mapping_file = str(tmp_path / "test_mapping.json")
    manifest_file = str(tmp_path / "manifest.json")

    service = FAISSService(
        index_path=index_file,
        mapping_path=mapping_file,
        manifest_path=manifest_file,
    )

    # Initial valid snapshot: 2 items
    service.add_embeddings([
        {"chunk_id": "c1", "embedding": [0.1, 0.2, 0.3]},
        {"chunk_id": "c2", "embedding": [0.4, 0.5, 0.6]},
    ])

    # Second snapshot: 3 items (creates backup of 2 items)
    service.add_embedding("c3", [0.7, 0.8, 0.9])

    # Simulate mismatch: tamper primary mapping to only have 1 item
    with open(mapping_file, "w", encoding="utf-8") as f:
        json.dump({"0": "c1"}, f)

    # Re-instantiate -> Mismatch (3 vectors vs 1 mapped chunk) -> recovers from backup (2 items)
    recovered_service = FAISSService(
        index_path=index_file,
        mapping_path=mapping_file,
        manifest_path=manifest_file,
    )

    status = recovered_service.status()
    assert status["loaded"] is True
    assert status["total_vectors"] == 2
    assert status["mapped_chunks"] == 2


def test_recovery_from_malformed_json_mapping(tmp_path):
    """
    Simulate crash during JSON write resulting in partial / invalid JSON.
    Verify recovery from backup.
    """
    index_file = str(tmp_path / "test.index")
    mapping_file = str(tmp_path / "test_mapping.json")

    service = FAISSService(index_path=index_file, mapping_path=mapping_file)
    service.add_embeddings([
        {"chunk_id": "c1", "embedding": [0.1, 0.2, 0.3]},
        {"chunk_id": "c2", "embedding": [0.4, 0.5, 0.6]},
    ])
    service.add_embedding("c3", [0.7, 0.8, 0.9])

    # Simulate truncated JSON write
    with open(mapping_file, "w", encoding="utf-8") as f:
        f.write('{"0": "c1", "1": "c2", "2": ')  # Truncated invalid JSON

    recovered_service = FAISSService(index_path=index_file, mapping_path=mapping_file)
    assert recovered_service.status()["loaded"] is True
    assert recovered_service.status()["total_vectors"] == 2


def test_temporary_files_cleaned_up_on_save_failure(tmp_path):
    """
    Verify that if validation fails or an error occurs during saving,
    temporary files are removed and existing valid files are not corrupted.
    """
    index_file = str(tmp_path / "test.index")
    mapping_file = str(tmp_path / "test_mapping.json")

    service = FAISSService(index_path=index_file, mapping_path=mapping_file)
    service.add_embeddings([
        {"chunk_id": "c1", "embedding": [0.1, 0.2, 0.3]},
    ])

    # Simulate validation failure on temporary files
    with patch.object(service, "_validate_pair", return_value=(None, None)):
        with pytest.raises(RuntimeError, match="FAISS persistence validation failed"):
            service._save()

    # Verify no dangling temporary files (.tmp.) exist
    tmp_files = list(tmp_path.glob("*.tmp.*"))
    assert len(tmp_files) == 0

    # Verify original file remains intact
    reload_service = FAISSService(index_path=index_file, mapping_path=mapping_file)
    assert reload_service.status()["total_vectors"] == 1
