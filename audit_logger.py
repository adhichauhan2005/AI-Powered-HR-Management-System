import json
from datetime import datetime, timezone
from pathlib import Path

from config_loader import settings


def write_audit_log(event: dict) -> None:
    """
    Write one audit event to the JSONL audit log file.

    Each line in the file is a complete JSON object representing
    one API request or system event.
    """

    log_path = settings.get("logging", {}).get(
        "audit_log_path",
        "logs/audit_log.jsonl",
    )

    Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    event["timestamp"] = datetime.now(timezone.utc).isoformat()

    with open(log_path, "a", encoding="utf-8") as file:
        file.write(json.dumps(event, default=str) + "\n")