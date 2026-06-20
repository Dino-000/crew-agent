from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "trello-crew-playground"
    trigger_mode: Literal["webhook", "poll"] = "poll"
    poll_interval_seconds: int = 60

    trello_api_key: str = Field(default="", alias="TRELLO_API_KEY")
    trello_token: str = Field(default="", alias="TRELLO_TOKEN")
    trello_board_id: str = Field(default="", alias="TRELLO_BOARD_ID")
    trello_to_do_list_name: str = Field(default="To Do", alias="TRELLO_TO_DO_LIST_NAME")
    trello_in_progress_list_name: str = Field(default="In Progress", alias="TRELLO_IN_PROGRESS_LIST_NAME")
    trello_done_list_name: str = Field(default="Done", alias="TRELLO_DONE_LIST_NAME")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    use_crewai: bool = Field(default=False, alias="USE_CREWAI")

    output_dir: Path = Field(default=Path("output"), alias="OUTPUT_DIR")
    state_file: Path = Field(default=Path("data/state.json"), alias="STATE_FILE")
    comment_delivery_mode: Literal["comment", "file", "both"] = Field(
        default="both",
        alias="COMMENT_DELIVERY_MODE",
    )
    max_comment_chars: int = Field(default=3500, alias="MAX_COMMENT_CHARS")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    settings.state_file.parent.mkdir(parents=True, exist_ok=True)
    return settings
