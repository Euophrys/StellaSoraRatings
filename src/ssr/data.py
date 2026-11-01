"""Game data loader for the mined Stella Sora tables."""
from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_ROOT = REPO_ROOT / "data_src" / "StellaSoraData" / "EN"


class GameData:
    def __init__(self, root: Path = DEFAULT_DATA_ROOT):
        self.root = Path(root)
        self._tables: dict[str, dict[str, dict]] = {}

    def table(self, name: str) -> dict[str, dict]:
        if name not in self._tables:
            with open(self.root / "bin" / f"{name}.json", encoding="utf-8") as f:
                self._tables[name] = json.load(f)
        return self._tables[name]

    @cached_property
    def _texts(self) -> dict[str, str]:
        merged: dict[str, str] = {}
        for p in sorted((self.root / "language" / "en_US").glob("*.json")):
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                merged.update({k: v for k, v in d.items() if isinstance(v, str)})
        return merged

    def text(self, key: str) -> str | None:
        return self._texts.get(key)

    def item_name(self, id: int) -> str:
        return self.text(f"Item.{id}.1") or f"<item {id}>"

    def char_name(self, id: int) -> str:
        return self.text(f"Character.{id}.1") or f"<char {id}>"

    def find_char(self, name: str) -> int:
        hits = [int(k) for k in self.table("Character") if self.char_name(int(k)) == name]
        if len(hits) != 1:
            raise KeyError(f"character {name!r}: {len(hits)} matches")
        return hits[0]

    def find_item(self, name: str, prefix: bool = False, within: str | None = None) -> int:
        """Find an Item id by English name. `within` restricts to ids that are keys of that table."""
        keys = self.table(within).keys() if within else None
        hits = []
        for k in self.table("Item"):
            if keys is not None and k not in keys:
                continue
            n = self.item_name(int(k))
            if (n.startswith(name) if prefix else n == name):
                hits.append(int(k))
        if len(hits) != 1:
            raise KeyError(f"item {name!r}: {len(hits)} matches {hits[:5]}")
        return hits[0]
