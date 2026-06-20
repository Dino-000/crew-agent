from __future__ import annotations

import requests

from trello_crew_playground.schemas import TrelloCard
from trello_crew_playground.settings import Settings


class TrelloClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = "https://api.trello.com/1"
        self._list_cache: dict[str, str] | None = None

    def _request(self, method: str, path: str, params: dict | None = None) -> requests.Response:
        query = {
            "key": self.settings.trello_api_key,
            "token": self.settings.trello_token,
        }
        if params:
            query.update(params)
        response = requests.request(method, f"{self.base_url}{path}", params=query, timeout=30)
        response.raise_for_status()
        return response

    def get_board_lists(self) -> list[dict]:
        return self._request("GET", f"/boards/{self.settings.trello_board_id}/lists").json()

    def get_board_cards(self) -> list[dict]:
        return self._request(
            "GET",
            f"/boards/{self.settings.trello_board_id}/cards",
            params={"fields": "name,desc,url,idList"},
        ).json()

    def get_card(self, card_id: str) -> TrelloCard:
        data = self._request(
            "GET",
            f"/cards/{card_id}",
            params={"fields": "name,desc,url,idList"},
        ).json()
        return TrelloCard(
            id=data["id"],
            name=data["name"],
            desc=data.get("desc", ""),
            url=data.get("url", ""),
            id_list=data["idList"],
        )

    def get_card_list_name(self, card_id: str) -> str:
        data = self._request("GET", f"/cards/{card_id}/list", params={"fields": "name"}).json()
        return data["name"]

    def add_comment(self, card_id: str, text: str) -> dict:
        return self._request("POST", f"/cards/{card_id}/actions/comments", params={"text": text}).json()

    def move_card_to_list(self, card_id: str, list_id: str) -> dict:
        return self._request("PUT", f"/cards/{card_id}", params={"idList": list_id}).json()

    def resolve_list_id(self, list_name: str) -> str:
        if self._list_cache is None:
            self._list_cache = {
                item.get("name", "").strip().lower(): item["id"]
                for item in self.get_board_lists()
                if item.get("name")
            }
        cached = self._list_cache.get(list_name.strip().lower())
        if cached:
            return cached
        raise ValueError(f'Could not find Trello list "{list_name}" on board {self.settings.trello_board_id}')
