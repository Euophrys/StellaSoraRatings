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

## Effects

- **ATK/DEF/HP flat vs %:** `EffectTypeSecondSubtype` 2 = %, 1 (base) and 3 (flat) = flat. Matches `EffectDesc.Type2ID` (1 Base, 2 %, 3 flat) and data values (subtype 2 values are fractions, 1/3 are integers). For other stats the second subtype is ignored and values are additive. `OnceAdditionalAttribute`: `ParameterType` 2 = % (ATK only in practice).
- **EffectType 52** is treated like 12 (stat add). Every 52 row seen is a slot-DMG / Mark-DMG add.
- **When a potential effect is on:**
  - In the potential's `EffectIdN` with `Trigger` 1 → always on.
  - Listed in some `BuffValue.Effects` → a buff with that row's duration (`Time`/10000 s; `Time` −1 = permanent) and `LaminatedNum` stacks. Its trigger is not in data (scripts apply it), so it is **assumed** until the kit YAML names the event or an uptime.
  - Otherwise (only in Params) → applied by script, condition unknown, **assumed**, noted.
- **Target:** any "DMG Taken" stat (element, slot, general) or an effect whose `Target1` is 2 goes on the enemy; everything else on the owner. Squad-wide effects ("increases the squad's…") are not distinguishable in data; disc effects follow `assumptions.disc_stats_target` and potentials are re-targeted in kit YAML.
- **OnceAdditionalAttribute** modifiers are always on but usually apply only to some hits ("longsword attacks and Glows"); they're flagged `needs_scope` and the kit YAML sets `hit_tags`.
- **Single-level refs:** a `LevelUp` ref whose id has no level rows reads the row at the id itself (e.g. Sinbreaker `16204011`). A ref whose row is missing entirely is noted, not fatal.
