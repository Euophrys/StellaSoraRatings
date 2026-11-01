# Modelling assumptions

A running log of every modelling choice that isn't read straight from the game data.

## Data decoding

- **Param `LevelUp` refs:** level n of base id X is row `X + n×10` in the `<Source>Value` table (e.g. `16241001` → Lv1 `16241011`, Lv9 `16241091`). Missing levels clamp to the highest row present. `NoLevel` refs read the named table at the id as given, whatever the level.
- **Formats:** any format starting `10K` is divided by 10000. `HdPct`, `Pct`, `Hd`, `Fixed` are used raw. `Enum,EAT` returns the integer stat id.
- **Stat names (EAT):** `EffectDesc` rows with Id 12xxxx, `Type2ID` 2. Other `EffectDesc` families reuse `TypeID` for skill/potential level-ups.
- **Hit DamageType → slot:** 1 auto, 2 skill, 3 ult, 4 other, 5 mark. **7 → "proj" (Derivative DMG, EAT 68).** DamageType 7 hits (52 of them) sit under both skills (SkillSlotType 2) and autos (5); the Attribute table has a `PROJECTILEDMG` column, the only bucket left unaccounted for. Assumed, not verified.
- **Disc base stats:** `Attribute` row (group `AttrBaseGroupId`, lvl 90, max Break) gives flat ATK/HP/DEF plus one percentage substat: `WEE/FEE/SEE/AEE/LEE/DEE` = Aqua/Ignis/Terra/Ventus/Lux/Umbra DMG, `NORMALDMG/SKILLDMG/ULTRADMG` = Auto/Skill/Ult DMG, value ÷ 10000 (My Guiding Star `LEE 1500` = +15% Lux DMG). Copies n add `DiscExtraAttribute` Break n−1.

## Damage formula

- Gist formula with these extra buckets, each `1 + sum`: general DMG (EAT 49 DMG Dealt + 50 DMG), Final DMG (51 + 52), general DMG Taken on the enemy (53 + 54). Ignore-element-RES (EAT 29–34) scales RES before PEN, as in the decompile.
- RES bands are chosen by effective RES (≤250 low, ≤750 middle, else high); beyond 2000 clamps to 0.99 amend.
- Crit is applied as an expected value: `(1 − p) + p × (critDmg + slotCritDmg)`, `p` capped at 1. "Other" DMG hits get no slot crit.
- `dmgPlus`, `finalDmgPlus`, `perkIntensity`, talent amends: not modelled (gist: unused).
