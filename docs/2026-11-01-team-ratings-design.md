# Stella Sora Team Ratings — Design

## Intent

Reproduce, for any team, the kind of ratings in Maygi's Firstlight Noya chart (`example.jpeg`): how much team damage each potential, disc and emblem stat is worth. The user plays Stella Sora and wants these numbers to drive decisions at three moments:

1. **Emblems** — set up outside a run.
2. **Discs** — chosen at the start of a run.
3. **Potentials** — picked mid-run from offers of 3. This is the most frequent decision. The game has _build reminders_ that flag recommended potentials and a target level; the output should translate directly into those reminders.

Success for the first milestone: the Firstlight Noya **skill build** team produces disc and potential rankings that approximate Maygi's chart.

## Goals

- Mine all game numbers from data, not hand entry.
- Model damage with a simple, tunable 120-second fight simulation.
- Output a spreadsheet per team/build.
- Re-runnable after each game patch.

## Non-goals

- Exact frame-accurate damage. Approximate relative rankings are the target.
- A UI / web app. The output is a spreadsheet file.
- Survivability, healing, or utility value (only damage is rated).
- Teams other than the first one, until it's validated (but the design must not be Noya-specific).

## Anti-goals

- Numbers typed in by hand that the game data already has.
- Behaviour rules buried in code so the user can't tweak timing without reading Python.

## Game facts (from the user)

- Team = 1 main Trekker + 2 supports. Supports don't auto attack; they contribute their support skill + ultimate damage and any buffs they give.
- **Pink potentials:** each Trekker has 4; you take exactly 2, always get the ones you want, and they don't level. A _build_ (e.g. "skill build" vs "auto build") is just which 2 pinks the main takes. The main uses `CharPotential.MasterSpecificPotentialIds`; supports use `AssistSpecificPotentialIds`.
- **Other potentials** (normal + common pools) level 1–6 within a run. Levels 7–9 exist in data only because emblems can roll "+3" to a potential.
- **Discs:** "C1…C6" = number of copies owned; copies raise stats and main effect. It is never a choice between C1 and C6; a weaker disc at high C can beat a stronger one at C1. Each team has 3 main-slot discs (stats + melody + harmony) and 3 support-slot discs (base stats and starting notes only; their melody/harmony don't apply).
- **Emblems:** character-specific; 3 emblem slots (Lv70, Lv80, Lv90). Emblem 1 rolls **stats only**. Emblem 2 rolls **skill level-ups (auto/skill/support/ult +N) and stats**. Emblem 3 rolls **potential +3s and stats**.
- **Fight:** ~120 s. Opening: support skills fire first, main skill ~1 s later. After that everything is cast as soon as it's available.
- **Animation gaps:** after a skill, autos resume after ~3 s (baseline); after an ultimate ~5 s. The user can time these in game to tune.
- **Cooldown manipulation exists:** e.g. Amber potentials let her cast her skill twice in a row, or refresh it after her ultimate.
- **Marks** are generally triggered by the main's skill hits; each hit of a multi-hit skill can trigger a mark if marks are up.
- **Enemy RES:** elemental RES is not a plain field in the monster tables. The user estimated ~40–45 (display units), inferred from Maygi's chart where the first emblem Lux PEN line is worth 8.65% and a second line 0.05% (PEN beyond RES is ~worthless). The formula gist uses internal units (weak ≈ 250, raid ≈ 570, neutral = 750, "rainbow PEN" ≈ 110), so the builder must reconcile units against emblem PEN roll values in `CharGemAttrValue.json` and calibrate the default enemy RES so the two Lux PEN lines land near 8.65% / 0.05%. The user notes the near-zero second line is odd if enemy RES is high. It may mean Maygi compared against something else, the build already has Lux PEN, or the curve behaves unexpectedly. Treat this as an open investigation and don't force a fit; report what the model gives.
- **Ult energy** (user-confirmed, matches `Skill.UltraEnergy` ÷ 10000): FL Noya 235, Tilia 190, Firefly 300.

## Data source

`data_src/StellaSoraData/EN` — a sparse clone of <https://github.com/Hiro420/StellaSoraData>, auto-updated datamined tables (JSON) with English text in `EN/language/en_US/`. Matches the local install (game patch Oct 30 2026). The local game archives (`*.arcx`) are encrypted; we don't decrypt them ourselves.

Verified mappings:

| Need | Where |
| --- | --- |
| Trekker list, element, skill IDs, cooldown-bearing skills | `Character.json` (`SkillId`, `AssistSkillId`, `UltimateId`, `NormalAtkId`) |
| Skill cooldown / ult energy | `Skill.json` `SkillCD` (÷10000 = s), `UltraEnergy` (÷10000) |
| Per-hit multipliers, element, damage type | `HitDamage.json` (`SkillPercentAmend` per level, `ElementType`, `DamageType`, `SourceType`) |
| Potential pools per Trekker | `CharPotential.json` |
| Potential definition | `Potential.json`; name = `Item.<id>.1` in `language/en_US/Item.json`; text = `Potential.<id>.2` |
| Description placeholders | `Potential.ParamN` strings, e.g. `Effect,LevelUp,16241001,EffectTypeParam1,HdPct`. `LevelUp` → id + (level−1)×10 (16241001 → 16241011…16241091 for Lv1–9). Sources: `EffectValue`, `OnceAdditionalAttributeValue`, `BuffValue`, `ScriptParameterValue`, `HitDamage` |
| Stat type enum (EAT) | `EffectDesc.json` `TypeID` → English label (57 Skill DMG, 71 Skill Crit Rate, 27 Lux PEN, …) |
| Discs | `Disc.json`; main effect per C-level `MainSkill.json` (`GroupId`=`MainSkillGroupId`, `Level` 1–6, `Param1..`); harmony `SecondarySkill.json`; base stats via `AttrBaseGroupId`/`AttrExtraGroupId` |
| Emblem stat rolls | `CharGemAttrValue.json`, `CharGem.json` |
| Base character stats | `Attribute.json` |

Not in tables (must be hand-authored): hits per cast (sometimes stated in description text, e.g. "fires 9 Glows"), energy generation details, enemy RES/DEF, animation gaps, and _behavioural_ effects of potentials (extra casts, cooldown resets, new attacks that only exist with another potential).

## How it works

### Pipeline (per team + build)

The user's proposed iterative order:

1. **Baseline:** 3 Trekkers with their chosen pinks.
2. **Discs:** rate every disc for main slot and support slot; fill the team's discs into the baseline.
   - _Main slot_ (3 discs): base stats + melody (main skill at C-level) + harmony skills at L1, notes excluded. Rated by swapping the disc in place of a filler "stat stick" disc, with the other slots also filler. **Filler disc (user-specified):** a stats-only disc with the stats of **Eternal Brilliance (214067) at Lv90, C6**: base 883 ATK + 650 extra ATK (`DiscExtraAttribute` group 301, Break 5) = **1533 ATK, 6990 HP** (`Attribute.json` group 21096, `lvl` 90). It has no melody or harmony. C6 because event "welfare" discs are easy to max, so Maygi most likely assumed C6.
   - _Support slot_ (3 discs): **base stats only** (flat ATK/HP etc.) plus starting notes. Their melody and harmony do not apply. Starting notes only feed main-disc harmony, which is L1/notes-excluded here, so support value is effectively base stats. Same filler comparison.
   - Shown at C1 and C6 (and owned copies if given).
3. **Emblems Lv70 / Lv80:** rate each stat line, and for emblem 2 each skill level-up line (+N to auto/skill/support/ult, via `SkillPercentAmend` at the higher level). These don't touch potentials; add the chosen lines to the baseline. Emblems are **character-specific** (can't move between Trekkers), so each Trekker gets its own emblem table. "Personal" = buffs the wearer only; "team" = the resulting change in total team damage.
4. **Potentials:** rated against a **reference finished run**, built in steps (the user's design):
   - Step 1: rate every non-pink potential against the baseline (pinks + discs + emblems). Take the top 2 for the main and the top 1 for each support; set them to Lv6.
   - Step 2: re-rate with those in; again take the top 2 main and top 1 per support at Lv6.
   - Step 3 (final): rate every potential at Lv1–9 against that reference build. For a potential already in the reference, the cell is the value at Lv n vs. that potential removed.
   - This gives the reference ~24 main levels and ~12 per support. That's near the user's current runs (~30 main / ~15 per support, ~60 total). Number of steps and picks per step should be configurable, since totals rise at higher ascension.
5. **Emblem Lv90:** the "+3 to potential X" value is read straight off the potential table, shown both from the target level (e.g. 6→9) and 0→3 (builder's call).

### Damage model

Use the decompiled game formula from AutumnVN's gist (user-provided): <https://gist.github.com/AutumnVN/91afd7a37a9743488419b70f07225950>, saved locally in `docs/reference/damage-formula/` (overview `.md`, `def.c`, `res.c`, `config.json` with the RES curve constants, `fulldamage.txt` with annotated decompilation). Effective form:

```
Damage = Base × skillPercent × skillIntensity × slotDmg × elementDmg
       × (critDmg + slotCritDmg)      # applied as expectation using crit rate
       × erAmend × defAmend × slotDmgTaken × elementDmgTaken × resilienceBreakDmg
```

- `Base` = the stat named by the hit's `DamageBonusType` (ATK, or Max HP for Noya-style hits). `skillPercent` = `HitDamage.SkillPercentAmend[level] × 1e-6`.
- `slotDmg` = Auto/Skill/Ult/Other/Mark/Projectile/Minion DMG bucket; `elementDmg` = elemental DMG bucket. Each bucket is (1 + sum of its sources); buckets multiply.
- `skillIntensity` = "increase <named skill> DMG by x%" effects (a few potentials).
- `defAmend = 1 − 40·DEF / (32·DEF + 24000)`.
- `erAmend`: piecewise quadratic on effective RES (RES − PEN) per `config.json`; VUL/Suppress only when effective RES ≤ 0.
- `resilienceBreakDmg` ≈ 1.5 while the enemy is broken (gist's testing). Whether to model break uptime is the builder's call; it can be a constant.
- Crit: base crit DMG from `Attribute.CritPower`; crit rate from stats + slot crit rate; use expected value.

### Fight simulation

Event-driven timeline over 120 s:

- Actions: main auto attacks (filler), main skill, main ult, each support's support skill and ult.
- Cast when ready (cooldown elapsed, energy full for ults), with opening order supports → main skill +1 s.
- After a cast, the main can't auto for the configured gap (3 s skill, 5 s ult by default).
- Buffs/debuffs tracked with duration and stacks so uptime falls out of the timeline rather than being guessed.
- Ult energy cost from data (above). How energy is _gained_ isn't fully in the tables (`Skill.GetEnergyLimit` hints at per-skill caps), so it's approximate and configurable per Trekker.

### Per-Trekker rotation files

One human-editable file per Trekker (YAML or similar) describing what the tables can't:

- For each skill/ult/auto: list of `HitDamage` ids and how many times each lands per cast, and which hits can trigger marks.
- Animation gaps (override defaults).
- Energy gain assumptions.
- For each potential with behaviour beyond a stat number: a small rule (e.g. "adds hit 162310005 ×9 to skill", "skill can be recast within 2 s", "ult refreshes skill cooldown"). Pure stat potentials need no entry; they're read from data automatically.

### Team config

One file per team+build: the 3 Trekkers, chosen pinks, disc lineup with copy counts, chosen emblem lines, enemy assumptions (RES, DEF, level), fight length, and character levels/skill levels.

### Output

One `.xlsx` per team+build:

- **Potentials tab:** rows = every non-pink potential across the 3 Trekkers (grouped by Trekker), columns = Lv1…Lv9, cells = % team damage gain over the reference build (see Pipeline step 4), with a marker on potentials in the reference. **No automatic target level for now:** the user will judge from the data how to turn values into build-reminder levels; a rule may be added later.
- **Discs tab:** main-slot value and support-slot value at C1 and C6 (and at owned copies if given), like Maygi's table.
- **Emblems tab:** each stat line's personal and team DMG gain, including the diminishing second PEN line.
- Optionally a breakdown tab: damage share by source (auto/skill/ult/mark, per Trekker) from the baseline sim, so the user can sanity-check.

## First milestone: Firstlight Noya skill build

- Main: Firstlight Noya (162), pinks **Lucent Blitz**, **Dawnflare**.
- Support: Firefly (115), pinks **Radiance Blade: Twin Shadow**, **Radiance Blade: Firefly**.
- Support: Tilia (107), pinks **Perfect Spiral**, **Renewed Spectrum**.
- Discs and emblems as in `example.jpeg` (left half).
- Compare against Maygi's numbers: e.g. My Guiding Star main slot 78.4% (C1) / 140.8% (C6); Ripples of Nostalgia 32.9% / 51.3%; support values ~6–8%. Potential letter grades: Argent Mirage S, Prism Warp A, Resolve: Blitz B+, Astral Brilliance B+, Guiding Star B+, Lucent Tide B, Searing Sun B, Veteran's Grit C.

## Success criteria (builder's call)

"Approximates Maygi" = broadly the same rank order for discs and potentials, with values in the same ballpark. Exact match isn't expected: Maygi's character/skill levels, disc promotion and enemy DEF are unknown.

## Rotation file authorship (builder's call)

The builder drafts the Noya, Firefly and Tilia rotation files from skill descriptions and data, using default gaps. The user then corrects them with in-game timings. Every guessed number is marked as a guess in the file.

## Left to the builder

- Language (Python suggested; it's the user's choice to override) and libs.
- Exact file formats for rotation/team configs, as long as they're human-editable.
- Formula details, researched from data and community sources, documented as assumptions in one place.
- How to show potentials that only matter alongside another potential (a note column is fine).
