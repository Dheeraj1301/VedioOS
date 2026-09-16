"""Run a real local S3 service. Bind every component to loopback only."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

root = Path(__file__).resolve().parent.parent
load_dotenv(root / ".env")
for scope in [
    "JWT_SIGNING_KEY",
    "JWT_SIGNING_READ_KEY",
    "JWT_FILER_SIGNING_KEY",
    "JWT_FILER_SIGNING_READ_KEY",
]:
    os.environ[f"WEED_{scope}"] = hashlib.sha256((os.environ["SECRET_KEY"] + scope).encode()).hexdigest()
runtime = root / ".runtime"
data = runtime / "storage"
data.mkdir(parents=True, exist_ok=True)
config = runtime / "s3.json"
config.write_text(
    json.dumps(
        {
            "identities": [
                {
                    "name": "vedioos-local",
                    "credentials": [
                        {"accessKey": os.environ["S3_ACCESS_KEY"], "secretKey": os.environ["S3_SECRET_KEY"]}
                    ],
                    "actions": ["Admin", "Read", "List", "Tagging", "Write"],
                }
            ]
        }
    ),
    encoding="utf-8",
)
binary = runtime / "seaweedfs" / ("weed.exe" if os.name == "nt" else "weed")
if not binary.exists():
    raise SystemExit("SeaweedFS binary missing. See README local storage setup.")
command = [
    str(binary),
    "server",
    f"-dir={data}",
    "-ip=127.0.0.1",
    "-ip.bind=127.0.0.1",
    "-s3.port=9000",
    f"-s3.config={config}",
    "-s3",
    "-filer",
    "-master.port=28000",
    "-master.port.grpc=38000",
    "-volume.port=28001",
    "-volume.port.grpc=38001",
    "-filer.port=28002",
    "-filer.port.grpc=38002",
    "-s3.port.grpc=38003",
    "-s3.port.iceberg=0",
    "-s3.port.lance=0",
    "-s3.iam=false",
    "-volume.max=50",
    "-master.volumeSizeLimitMB=256",
    "-filer.disableDirListing",
    "-filer.exposeDirectoryData=false",
]
raise SystemExit(subprocess.call(command, cwd=runtime))
