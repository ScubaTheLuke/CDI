import os
from typing import Any, Dict, List, Optional

import requests

SCRYFALL_API_BASE = os.getenv("SCRYFALL_API_BASE", "https://api.scryfall.com")


class ScryfallError(RuntimeError):
    pass


class ScryfallClient:
    def __init__(self, base_url: Optional[str] = None, timeout: int = 10) -> None:
        self.base_url = base_url or SCRYFALL_API_BASE.rstrip("/")
        self.timeout = timeout

    def _request(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = requests.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise ScryfallError("Unable to reach Scryfall API") from exc
        if response.status_code >= 400:
            raise ScryfallError(f"Scryfall API error ({response.status_code})")
        return response.json()

    def search_cards(self, query: str, unique: str = "prints", order: str = "name") -> List[Dict[str, Any]]:
        payload = self._request(
            "/cards/search",
            {
                "q": query,
                "unique": unique,
                "order": order,
            },
        )
        if payload.get("object") != "list":
            raise ScryfallError("Unexpected Scryfall response")
        return [self._simplify_card(entry) for entry in payload.get("data", [])]

    def get_card_by_name(self, name: str, set_code: Optional[str] = None) -> Dict[str, Any]:
        params = {"exact": name}
        if set_code:
            params["set"] = set_code
        payload = self._request("/cards/named", params)
        return self._simplify_card(payload)

    def get_card_by_id(self, scryfall_id: str) -> Dict[str, Any]:
        payload = self._request(f"/cards/{scryfall_id}")
        return self._simplify_card(payload)

    def _simplify_card(self, card: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": card.get("id"),
            "name": card.get("name"),
            "set_code": card.get("set"),
            "set_name": card.get("set_name"),
            "collector_number": card.get("collector_number"),
            "rarity": card.get("rarity"),
            "released_at": card.get("released_at"),
            "prices": card.get("prices", {}),
            "image": self._preferred_image_uri(card),
            "set_image": self._set_symbol_uri(card),
            "oracle_text": card.get("oracle_text"),
            "type_line": card.get("type_line"),
            "mana_cost": card.get("mana_cost"),
            "scryfall_uri": card.get("scryfall_uri"),
        }

    def _preferred_image_uri(self, card: Dict[str, Any]) -> Optional[str]:
        image_uris = card.get("image_uris")
        if isinstance(image_uris, dict):
            return image_uris.get("normal") or image_uris.get("large")
        card_faces = card.get("card_faces")
        if isinstance(card_faces, list):
            for face in card_faces:
                image = face.get("image_uris")
                if isinstance(image, dict) and image.get("normal"):
                    return image["normal"]
        return None

    def _set_symbol_uri(self, card: Dict[str, Any]) -> Optional[str]:
        set_uri = card.get("set_icon_svg_uri")
        if set_uri:
            return set_uri
        if card.get("set_uri"):
            return f"https://api.scryfall.com/sets/{card.get('set')}?format=image"
        return None


_default_client: Optional[ScryfallClient] = None


def get_client() -> ScryfallClient:
    global _default_client
    if _default_client is None:
        _default_client = ScryfallClient()
    return _default_client


def search_cards(query: str) -> List[Dict[str, Any]]:
    return get_client().search_cards(query)


def get_card(name: str, set_code: Optional[str] = None) -> Dict[str, Any]:
    return get_client().get_card_by_name(name, set_code)


def get_card_by_id(scryfall_id: str) -> Dict[str, Any]:
    return get_client().get_card_by_id(scryfall_id)
