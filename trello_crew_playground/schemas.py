from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class TrelloCard:
    id: str
    name: str
    desc: str
    url: str
    id_list: str


@dataclass(slots=True)
class WorkflowResult:
    card_id: str
    card_name: str
    list_name: str
    markdown_path: str | None
    comment_text: str
    raw_output: str
    meta: dict[str, Any]

