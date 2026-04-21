from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict


CHUNK_SIZE = 1024 * 1024



def compute_hashes(file_path: Path) -> Dict[str, str]:
    sha256 = hashlib.sha256()
    md5 = hashlib.md5()
    with file_path.open("rb") as handle:
        while True:
            chunk = handle.read(CHUNK_SIZE)
            if not chunk:
                break
            sha256.update(chunk)
            md5.update(chunk)
    return {"sha256": sha256.hexdigest(), "md5": md5.hexdigest()}
