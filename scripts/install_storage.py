"""Install the pinned Windows local storage binary after SHA-256 verification."""

import hashlib
import os
import urllib.request
import zipfile
from pathlib import Path

VERSION = "4.47"
SHA256 = "8809359079e62fcd60574ff661449160899622c52072f3f569d346669079efe9"
root = Path(__file__).resolve().parent.parent
runtime = root / ".runtime"
runtime.mkdir(exist_ok=True)
if os.name != "nt":
    raise SystemExit(
        "This helper installs Windows AMD64 only. Install the matching SeaweedFS release for your OS into .runtime/seaweedfs/."
    )
archive = runtime / "seaweedfs.zip"
if not archive.exists() or hashlib.file_digest(archive.open("rb"), "sha256").hexdigest() != SHA256:
    print(f"Downloading SeaweedFS {VERSION} from its official GitHub release...")
    urllib.request.urlretrieve(
        f"https://github.com/seaweedfs/seaweedfs/releases/download/{VERSION}/windows_amd64.zip", archive
    )
with archive.open("rb") as stream:
    if hashlib.file_digest(stream, "sha256").hexdigest() != SHA256:
        raise SystemExit("Checksum mismatch: binary was not installed.")
destination = runtime / "seaweedfs"
destination.mkdir(exist_ok=True)
with zipfile.ZipFile(archive) as bundle:
    # Extract only the expected executable, not arbitrary archive paths.
    (destination / "weed.exe").write_bytes(bundle.read("weed.exe"))
print(f"SeaweedFS {VERSION} installed and checksum verified.")
