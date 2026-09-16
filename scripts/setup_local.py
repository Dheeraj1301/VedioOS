"""Create isolated local secrets; never overwrite existing configuration."""

import secrets
from pathlib import Path

root = Path(__file__).resolve().parent.parent
(root / ".runtime").mkdir(exist_ok=True)
env = root / ".env"
if env.exists():
    print(".env already exists; preserved.")
else:
    env.write_text(
        "\n".join(
            [
                "DEBUG=true",
                f"SECRET_KEY={secrets.token_urlsafe(64)}",
                "ALLOWED_HOSTS=localhost,127.0.0.1,testserver",
                "S3_ENDPOINT_URL=http://127.0.0.1:9000",
                "S3_BUCKET=vedioos-private",
                f"S3_ACCESS_KEY={secrets.token_hex(12)}",
                f"S3_SECRET_KEY={secrets.token_urlsafe(40)}",
                "UPLOAD_TTL_SECONDS=900",
                "DOWNLOAD_TTL_SECONDS=60",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print("Created .env with random local secrets. Do not commit it.")
