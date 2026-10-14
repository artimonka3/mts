"""Create missing local secrets without printing or replacing existing values."""

import base64
import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
p = root / ".env"
content = p.read_text() if p.exists() else (root / ".env.example").read_text()
values = {
    line.split("=", 1)[0]: line.split("=", 1)[1]
    for line in content.splitlines()
    if "=" in line and not line.startswith("#")
}
for name, generator in {
    "MTS_DATA_ENCRYPTION_KEY": lambda: base64.urlsafe_b64encode(
        secrets.token_bytes(32)
    ).decode(),
    "MTS_AUDIO_ENCRYPTION_KEY": lambda: base64.urlsafe_b64encode(
        secrets.token_bytes(32)
    ).decode(),
    "MTS_CRM_WEBHOOK_TOKEN": lambda: secrets.token_urlsafe(32),
    "MTS_DEMO_PASSWORD": lambda: secrets.token_urlsafe(18),
}.items():
    if not values.get(name):
        content = (
            "\n".join(
                line for line in content.splitlines() if not line.startswith(name + "=")
            )
            + "\n"
            + name
            + "="
            + generator()
            + "\n"
        )
p.write_text(content)
os.chmod(p, 0o600)
(root / ".local").mkdir(mode=0o700, exist_ok=True)
(root / ".local/audio").mkdir(mode=0o777, exist_ok=True)
os.chmod(root / ".local/audio", 0o777)
print("Local environment ready; keys are stored in .env only. Back up keys separately.")
