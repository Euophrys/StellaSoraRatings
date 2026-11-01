"""The game's potential preset share codes (preset screen import/export).

base64 of 27 bytes: three big-endian uint32 trekker ids (main first), then per trekker 40 bits, MSB first:
4 pink bits in `{Master|Assist}SpecificPotentialIds` order (1 = taken), then 12 x 3-bit target levels in
`{Master|Assist}NormalPotentialIds + CommonPotentialIds` order (data order). Main uses Master*, supports Assist*.
"""
from __future__ import annotations

import base64
import binascii
import struct
from dataclasses import dataclass, field

from .data import GameData

_LEN = 27
_BAD = "not a Stella Sora preset code"


@dataclass
class SharePreset:
    char_ids: list[int]
    pinks: list[list[int]] = field(default_factory=list)
    levels: list[dict[int, int]] = field(default_factory=list)   # per member: potential id -> level (0 omitted)


def _lists(gd: GameData, cid: int, idx: int) -> tuple[list[int], list[int]]:
    cp = gd.table("CharPotential").get(str(cid))
    if cp is None:
        raise ValueError(f"{_BAD}: unknown trekker id {cid}")
    pre = "Master" if idx == 0 else "Assist"
    return list(cp[f"{pre}SpecificPotentialIds"]), list(cp[f"{pre}NormalPotentialIds"]) + list(cp["CommonPotentialIds"])


def decode_share(gd: GameData, code: str) -> SharePreset:
    try:
        raw = base64.b64decode(code.strip(), validate=True)
    except (binascii.Error, ValueError, AttributeError) as e:
        raise ValueError(f"{_BAD}: bad base64") from e
    if len(raw) != _LEN:
        raise ValueError(f"{_BAD}: {len(raw)} bytes, expected {_LEN}")
    ids = list(struct.unpack(">3I", raw[:12]))
    bits = int.from_bytes(raw[12:], "big")
    nbits = (_LEN - 12) * 8
    preset = SharePreset(ids)
    for k, cid in enumerate(ids):
        pinks, pots = _lists(gd, cid, k)
        block = (bits >> (nbits - 40 * (k + 1))) & ((1 << 40) - 1)
        pink_bits = block >> 36
        preset.pinks.append([p for j, p in enumerate(pinks[:4]) if pink_bits >> (3 - j) & 1])
        lv = {}
        for j, p in enumerate(pots[:12]):
            v = (block >> (33 - 3 * j)) & 7
            if v > 6:
                raise ValueError(f"{_BAD}: level {v} for {gd.item_name(p)}")
            if v:
                lv[p] = v
        preset.levels.append(lv)
    return preset


def encode_share(gd: GameData, preset: SharePreset) -> str:
    bits = 0
    for k, cid in enumerate(preset.char_ids):
        pinks, pots = _lists(gd, cid, k)
        chosen = set(preset.pinks[k]) if k < len(preset.pinks) else set()
        levels = preset.levels[k] if k < len(preset.levels) else {}
        block = 0
        for j in range(4):
            block = block << 1 | (1 if j < len(pinks) and pinks[j] in chosen else 0)
        for j in range(12):
            v = levels.get(pots[j], 0) if j < len(pots) else 0
            block = block << 3 | max(0, min(6, int(v)))
        bits = bits << 40 | block
    raw = struct.pack(">3I", *preset.char_ids) + bits.to_bytes(_LEN - 12, "big")
    return base64.b64encode(raw).decode()
