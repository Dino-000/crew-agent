from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any


@dataclass
class StateStore:
    path: Path
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"processed_cards": {}}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"processed_cards": {}}

    def _save(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def is_processed(self, card_id: str) -> bool:
        with self._lock:
            data = self._load()
            return card_id in data.get("processed_cards", {})

    def mark_processed(self, card_id: str, payload: dict[str, Any]) -> None:
        with self._lock:
            data = self._load()
            processed = data.setdefault("processed_cards", {})
            processed[card_id] = payload
            self._save(data)

    def all_records(self) -> dict[str, Any]:
        with self._lock:
            return self._load()

