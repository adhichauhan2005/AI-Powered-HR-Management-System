import json
from datetime import datetime
from pathlib import Path

from config_loader import settings


def write_audit_log(event: dict) -> None:
    log_path = settings["logging"]["audit_log_path"]
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    event["timestamp"] = datetime.utcnow().isoformat()

    with open(log_path, "a", encoding="utf-8") as file:
        file.write(json.dumps(event, default=str) + "\n")