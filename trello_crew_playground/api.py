from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from trello_crew_playground.settings import Settings, get_settings
from trello_crew_playground.state_store import StateStore
from trello_crew_playground.trello_client import TrelloClient
from trello_crew_playground.workflow import TrelloCrewWorkflow

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def create_app() -> FastAPI:
    settings = get_settings()
    trello = TrelloClient(settings)
    state_store = StateStore(settings.state_file)
    workflow = TrelloCrewWorkflow(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.trello = trello
        app.state.state_store = state_store
        app.state.workflow = workflow
        app.state.poll_task = None
        app.state.poll_task = asyncio.create_task(_poll_loop(app))
        yield
        if app.state.poll_task:
            app.state.poll_task.cancel()
            try:
                await app.state.poll_task
            except asyncio.CancelledError:
                pass

    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "mode": settings.trigger_mode,
            "status": "running",
        }

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/poll/once")
    async def poll_once() -> dict[str, Any]:
        return await _poll_now(app)

    return app


async def _process_card(app: FastAPI, card_id: str, source: str) -> dict[str, Any]:
    settings: Settings = app.state.settings
    trello: TrelloClient = app.state.trello
    state_store: StateStore = app.state.state_store
    workflow: TrelloCrewWorkflow = app.state.workflow

    if state_store.is_processed(card_id):
        return {"card_id": card_id, "status": "skipped", "reason": "already processed"}

    card = trello.get_card(card_id)
    in_progress_list_id = trello.resolve_list_id(settings.trello_in_progress_list_name)
    done_list_id = trello.resolve_list_id(settings.trello_done_list_name)

    if card.id_list != in_progress_list_id:
        return {
            "card_id": card_id,
            "status": "ignored",
            "reason": f"card not in '{settings.trello_in_progress_list_name}'",
        }

    list_name = trello.get_card_list_name(card_id)
    result = await asyncio.to_thread(workflow.run, card, list_name)

    trello.add_comment(card_id, result.comment_text)
    trello.move_card_to_list(card_id, done_list_id)

    state_store.mark_processed(
        card_id,
        {
            "source": source,
            "card_name": card.name,
            "list_name": list_name,
            "markdown_path": result.markdown_path,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    return {
        "card_id": card_id,
        "card_name": card.name,
        "markdown_path": result.markdown_path,
        "status": "done",
    }


async def _poll_now(app: FastAPI) -> dict[str, Any]:
    settings: Settings = app.state.settings
    trello: TrelloClient = app.state.trello
    in_progress_list_id = trello.resolve_list_id(settings.trello_in_progress_list_name)
    cards = trello.get_board_cards()
    matched = [card for card in cards if card.get("idList") == in_progress_list_id]
    processed = []
    for card in matched:
        processed.append(await _process_card(app, card["id"], source="poll"))
    return {"matched": len(matched), "processed": processed}


async def _poll_loop(app: FastAPI) -> None:
    settings: Settings = app.state.settings
    while True:
        try:
            await _poll_now(app)
        except Exception:  # pragma: no cover - playground guardrail
            logger.exception("poll loop failed")
        await asyncio.sleep(settings.poll_interval_seconds)
