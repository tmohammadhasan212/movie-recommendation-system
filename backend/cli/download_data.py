"""Download a verified MovieLens archive only on an explicit operator command."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

SOURCE_URL = "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip"
EXPECTED_FILES = {"movies.csv", "links.csv", "ratings.csv"}
MAX_ARCHIVE_BYTES = 25 * 1024 * 1024
MAX_EXPANDED_BYTES = 100 * 1024 * 1024
DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def verify_archive(path: Path, expected_sha256: str) -> dict[str, str]:
    """Check operator-provided SHA-256 and a bounded, flat ZIP layout."""
    expected_sha256 = expected_sha256.lower().strip()
    if len(expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_sha256):
        raise ValueError("Set DATA_EXPECTED_SHA256 to a verified 64-character hex digest")
    if path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("MovieLens archive exceeds maximum allowed size")
    digest = hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
    if digest != expected_sha256:
        raise ValueError(f"SHA-256 mismatch: expected {expected_sha256}, got {digest}")
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        names = [item.filename for item in members if not item.is_dir()]
        if len(names) != len(set(names)):
            raise ValueError("ZIP contains duplicate paths")
        if sum(item.file_size for item in members) > MAX_EXPANDED_BYTES:
            raise ValueError("ZIP expanded size exceeds limit")
        for item in members:
            if item.is_dir() and item.filename == "ml-latest-small/":
                continue
            parts = Path(item.filename).parts
            if len(parts) != 2 or parts[0] != "ml-latest-small" or parts[1] in {".", ".."}:
                raise ValueError(f"Unexpected ZIP path: {item.filename}")
            if item.is_dir():
                continue
            if ((item.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError("ZIP symlink is not allowed")
        if not EXPECTED_FILES.issubset({Path(name).name for name in names}):
            raise ValueError("MovieLens archive is missing required CSV files")
    return {"sha256": digest, "source_url": SOURCE_URL}


def download() -> None:
    expected = os.environ.get("DATA_EXPECTED_SHA256", "")
    if not expected:
        raise SystemExit("DATA_EXPECTED_SHA256 is required; verify it independently before download")
    DATA_DIR.mkdir(exist_ok=True)
    archive_path = DATA_DIR / "ml-latest-small.zip"
    temp_path = DATA_DIR / "ml-latest-small.zip.partial"
    if not archive_path.exists():
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "RecSys-demo/0.1"})
                with urllib.request.urlopen(request, timeout=30) as response, temp_path.open("wb") as target:
                    if response.geturl() != SOURCE_URL:
                        raise ValueError("Unexpected download redirect")
                    copied = 0
                    while chunk := response.read(1024 * 1024):
                        copied += len(chunk)
                        if copied > MAX_ARCHIVE_BYTES:
                            raise ValueError("Download exceeds size limit")
                        target.write(chunk)
                temp_path.replace(archive_path)
                break
            except (OSError, ValueError, urllib.error.URLError) as error:
                last_error = error
                temp_path.unlink(missing_ok=True)
                if attempt < 2:
                    time.sleep(2**attempt)
        else:
            raise SystemExit(f"Download failed after three attempts: {last_error}")
    try:
        provenance = verify_archive(archive_path, expected)
        target_dir = DATA_DIR / "ml-latest-small"
        target_dir.mkdir(exist_ok=True)
        hashes: dict[str, str] = {}
        with zipfile.ZipFile(archive_path) as archive:
            for item in archive.infolist():
                if item.is_dir():
                    continue
                name = Path(item.filename).name
                with archive.open(item) as source, (target_dir / name).open("wb") as target:
                    shutil.copyfileobj(source, target)
                with (target_dir / name).open("rb") as source:
                    hashes[name] = hashlib.file_digest(source, "sha256").hexdigest()
        manifest = {
            **provenance,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "files": hashes,
            "parser_version": 1,
        }
        (DATA_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"Verified and extracted {len(hashes)} files; SHA-256 {provenance['sha256']}")
    except Exception:
        archive_path.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    download()
