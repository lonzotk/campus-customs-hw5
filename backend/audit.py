from __future__ import annotations

import json
import os
import threading
import uuid
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .models import AuditEvent


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT_PATH = PROJECT_ROOT / "output" / "audit_trail.json"


def json_safe(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return json_safe(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "structured_content"):
        structured = value.structured_content
        if structured is not None:
            return json_safe(structured)
    if hasattr(value, "model_dump"):
        return json_safe(value.model_dump(mode="json"))
    return str(value)


class AuditTrail:
    def __init__(self, path: Path = DEFAULT_AUDIT_PATH) -> None:
        self.path = path
        self._lock = threading.RLock()

    def record(
        self,
        *,
        run_id: str,
        actor: str,
        event: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        audit_event = AuditEvent(
            run_id=run_id,
            actor=actor,
            event=event,
            details=json_safe(details or {}),
        )
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists():
                existing = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(existing, list):
                    raise ValueError(f"Audit trail must contain a JSON array: {self.path}")
            else:
                existing = []
            existing.append(audit_event.model_dump(mode="json"))
            temporary = self.path.with_name(
                f".{self.path.name}.{uuid.uuid4().hex}.tmp"
            )
            try:
                temporary.write_text(
                    json.dumps(existing, indent=2, ensure_ascii=True) + "\n",
                    encoding="utf-8",
                )
                os.replace(temporary, self.path)
            finally:
                temporary.unlink(missing_ok=True)