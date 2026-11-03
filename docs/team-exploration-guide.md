# Team exploration guide

How to take a new team from "Amber + Snowish Laru + Flora" to a trustworthy `out/<team>.xlsx`. It's written from the FL Noya and Amber sessions (`docs/validation/2026-11-01-*.md`). Read `specs/README.md` (spec schema) and `docs/assumptions.md` (modelling choices) alongside it.

## The loop

1. **Find the Trekkers and decide roles.** The first named is usually the main; ask if it's unclear. `python -m ssr.inspect trekker <name> main|support` prints element, class, skills (CD, ult energy, text, resolved Params) and every potential pool with decoded modifiers.
2. **Ask the user for timings up front** (list below). Don't guess what they can measure in a minute.
3. **Write a kit spec per Trekker:** `specs/trekkers/<char id>.yaml`. Copy the shape of `103.yaml` (main with an ammo auto string), `162.yaml` (main with Marks/statuses), `158.yaml` (summoner support, no ult) or `126.yaml` (buffer support with statuses). Author **all three pools**: pink, normal **and common** (the ult-branch potentials). The reference build picks from all of them, and an unspecced one runs on assumed 100% uptimes.
4. **Write a team file:** `teams/<name>.yaml`. Start with placeholder pinks and `filler` discs.
5. **Sanity-sim:** check the damage share per member and slot, cast counts, on-field time and status uptimes (snippet below). Look for anything absurd before running the slow commands.
6. **Pink search:** `python -m ssr teams/<name>.yaml --pinks <main> <support1> <support2>` (~3–5 min). Show the user the ranking: they know which builds are used in practice and can confirm it.
7. **Disc pass:** run the rating once with filler discs. Read the Discs sheet's Notes column for the top ~10: "uptime 1 x N assumed" and "scripted, not modelled" mean the number isn't trustworthy yet. Pin those down with disc specs, re-rate, then put the top 3 main discs in the team file.
8. **Full run:** `python -m ssr teams/<name>.yaml -o out/` (~1–2 min).
9. **Regression:** after any change to `src/` or to a disc spec, re-run `teams/fl_noya_skill.yaml` and compare with `docs/validation/2026-11-01-fl-noya-skill.md` (the Maygi-calibrated team). Report any moves.
10. **Write it up:** `docs/validation/<date>-<team>.md` covers the setup, the user's timings, results, model changes, the Noya impact and open questions. Run `pytest` and add tests for new engine features (e.g. `tests/test_amber_team.py`).

The slow commands (pink search, full rating) should run in the background, two at a time where they're independent. Restart them if you change specs or code mid-run: they read specs lazily and will mix old and new.

## What to ask the user

They play the game and can time things frame by frame (they report `seconds,frames` at 30 fps: `04,15` = 4.5 s). Ask for:

- **Main, per action (skill, ult, any follow-up):** how long until autos resume (`lock`), when each hit lands relative to the cast, and how many hits there are. Hit counts in the text can be wrong: Amber's skill text says "x4" small hits, but there are 8. Ask for a cast **with no potentials** and one with each hit-adding potential, so the base and the potential's extra hits can be told apart.
- **Main auto string:** duration of one full string, hits per strike, reload or pause times (Amber: 12 shots in 2.03 s + 0.77 s reload).
- **Cooldown timing:** does the CD start at cast or after the action ends? Amber's skill CD starts after the Precise Temperature Control recast ends (`starts_cd`).
- **Supports:** seconds on the battlefield per skill and per ult (`on_field`; Laru 14 s, most 4 s). Does the CD tick while they're there? Is the ult actually used? (Laru's isn't, so her kit leaves `ult` out.)
- **Which pinks the community uses**, to check the pink search against.
- **Mechanics the data can't explain:** ICDs, how statuses convert or stack, what "enters combat" means, what a scripted disc does (Voyage Blueprint's shield → Ignis DMG 12 s every 20 s came from the user).
- **Ambiguous stats:** e.g. Derivative DMG (EAT 68). Nobody knows what it applies to; ask before inventing.

Surface everything you can't model as a list for the user to decide on. Don't silently pick.

## Where the data is

Game tables are JSON in `data_src/StellaSoraData/EN/bin/` and texts in `language/en_US/` (loaded by `GameData`). `ssr.inspect` covers most lookups. For anything else, `grep -l <id> data_src/StellaSoraData/EN/bin/*.json` finds which tables mention an id.

| Need | Table / key | Notes |
| --- | --- | --- |
| Element, class, energy share | `Character` (`EET`, `Class`, `EnergyConvRatio`) | EET 1 Aqua, 2 Ignis, 3 Terra, 4 Ventus, 5 Lux, 6 Umbra, 7 neutral (discs); Class 1 Vanguard, 2 Versatile, 3 Support |
| Skills per role | `Character.{NormalAtkId, SkillId, UltimateId}` / `Assist*` → `Skill` | `SkillCD`/10000, `UltraEnergy`/10000, `GetEnergyLimit`, `Param*` |
| Variant skill rows | `Skill` ids next to the base (e.g. `10331030` = Amber's recast) | list `Skill` rows by char prefix to find them |
| Hits | `HitDamage` (`DamageType` 1 auto, 2 skill, 3 ult, 4 other, 5 mark, 7 minion; `SkillPercentAmend` per level; `EnergyCharge`; `levelTypeData`/`LevelData`) | `python -m ssr.inspect hits <char id>` |
| Potential pools | `CharPotential` (`Master*`/`Assist*` Specific = pink, Normal; `CommonPotentialIds` = ult branch) |  |
| Potential text and Params | `Potential` + text `Potential.<id>.2` | Params are refs like `Effect,LevelUp,10350501,EffectTypeParam1,HdPct`; `ssr.refs.resolve` reads them |
| Stat effects | `Effect`, `EffectValue` (`EffectType` 12/52 stat add, 45 conditional, 6 apply buff; `EffectTypeFirstSubtype` = EAT stat id) | stat names: `ssr.stats.stat_name` |
| Buff durations and stacks | `Buff`, `BuffValue` (`Time`/10000 s, `LaminatedNum` = max stacks, `Effects` list) |  |
| Per-hit or attribute bonuses | `OnceAdditionalAttribute(Value)` | always on but scoped to some hits: the kit must set `hit_tags` |
| Script constants (ICDs, counts) | `ScriptParameterValue` (`CommonData`) | often missing (ERR): fall back to the text |
| Keywords (statuses, marks, minions) | `Word` + `Word.<id>.1/2` | `python -m ssr.inspect word "<name>"`; e.g. Ode 6002 explains Snowy Night Surprise |
| Discs | `Disc` (`EET`, group ids) → `MainSkill` (melody, by level), `SecondarySkill` (harmonies) | text placeholders are `{1}`..`{n}` = `Param1`..; `python -m ssr.inspect disc "<name>"` |

## Engine features you'll likely need

All are documented in `specs/README.md`:

- **Marks:** `applies_mark` on support hits, `triggers_mark` on main hits, `mark: {hit}` on the main.
- **Statuses:** a named buff, tested with `while:status:<name>`. `per_stack` scales with stacks, `stacks_from` adds stacks from another status, `add` adds N stacks per event (e.g. 3 butterflies per cast).
- **Events:** `cast:<who>:<action>`, `hit:<who>:<tag|any|slot_dmg>`, `mark:<who>`, joined with `|`.
- **Buff timing:** `icd`, `every`, `reset_on` (Ardent Trigger resets on reload).
- **Gating:** `requires` / `excludes` / `requires_all` on hits and buffs, for potential-dependent variants. Amber's auto string has one variant per magazine pink.
- **Actions:** `add_actions` with a `followup` (after an action, or every N events). `starts_cd` sets when a cooldown begins. `reset_cd` and `cd_reduce` also exist.
- **Procs:** with `icd`, `every` and `when` (only while a status holds); `chance` (expected value) and `resilience` (removes a fraction of the enemy's bar).
- **Enemy:** for a Boss Blitz team, set `enemy: {preset: <boss>}` (`specs/enemies/`), which brings the boss's RES, resilience bar and ability, and a 180 s fight. Use `while:broken` for "against a broken / stunned target" effects.
- **Supports:** an `on_field` window per action; `while:on_field:<who>` effects use it.
- **Disc specs:** entries for scripted parts and `overrides` for data parts: `event`, `duration`, `max_stacks`, `every`, `icd`, `uptime`, `event: always`, `drop`.

If the team needs something new, add it generally (not team-specific), document it in `specs/README.md`, and test it.

## Pitfalls that cost time

- **Unknown triggers default to 100% uptime at max stacks.** That's the biggest source of overvaluation (Mystic Brushstrokes, Meowing Cat God, A Moment in the Afternoon). Check the Notes column and pin triggers from the text.
- **Duplicate Lv1 rows:** a Param that names its stat through a `NoLevel` ref to the Lv1 row also decodes as a modifier (Two-Gun Salute's 0.29 next to the leveled 1.17). Drop the Lv1 duplicate with an override.
- **Defensive lines:** "Reduces DMG taken by the main" now decodes onto the owner (no damage effect). Watch for any other defensive line leaking into damage.
- **Kill-based effects** are worth 0 against a single boss: drop them, with a note.
- **Element lock:** disc effects only reach Trekkers of the disc's element (neutral discs reach everyone). Generic stat buffs in a squad-wide disc text still need checking against the text's target ("main Ignis Trekker" vs "squad").
- **Single-element approximations:** `Ignis Skill DMG Taken` is written as plain `Skill DMG Taken` (61). That's fine in mono-element teams but wrong in mixed ones, so revisit it.
- **A support's own potentials** can target the main ("main Ignis Trekker"): set `target: main`, or `team` for "squad".
- **The reference build** includes common-pool potentials. If they aren't specced, the reference build and every gain measured against it shift.
- **Minions only get some buffs:** buffs scoped to "Trekkers" or "squad" skip minions; "minions" or "friendly/all units" reach them (read from text, see `specs/README.md` → Minions). For a summoner, check the `minions` flag of each of their potentials (`resolve_potential(...).modifiers`) and override where the text names the summon instead of saying "minions" (Laru's "their Crit DMG").
- **Per-Trekker statuses:** "Ode can only be converted by that Trekker's minion"-style rules need `&recent:` on the event, not `hit:any:...`.
- **Summon timelines:** use marker hits (`hit: 0`) for summon-ready / periodic-stack moments and pure statuses for minion counts (`specs/trekkers/141.yaml`). Ask the user for damage numbers from one clip: ratios between hits in the same clip cancel the account's stats and pin down stack timings and hit rows.
- **Mixed-element teams:** disc specs written for single-element teams may use `hit:any:` / `cast:any:` where the text says "any Ignis Trekker". Use `element<N>` (`hit:element2:skill_dmg`), and intersections like `support/element6` ("an Umbra support"). "The main Ignis Trekker" effects are gated on the main's element automatically. Marks are per element.
- **Dynamic summons** (minions that are replaced, refreshed, sacrificed or re-summoned): use a `minions:` pool, not per-cast hit lists (`specs/trekkers/135.yaml`).
- **Timing:** hits outside `fight_length` are dropped, and an auto string restarts after every cast. Make the auto `duration` longer than any gap between casts when the first magazine differs (Dominant Firepower, Bullet Storm).

## Comparing teams

Shares don't rank teams; totals do. `python -m ssr.compare teams/a.yaml teams/b.yaml --split 30,15,15` gives each team a greedy build within per-member level budgets (team order, main first; ~4 min per team). Use the user's real splits (typically 30/15/15; the main gets more). Without `--split`, the budget can go anywhere, which overstates kits with many strong potentials.

## Snippets

Sanity sim:

```python
from ssr.data import GameData
from ssr.team import load_team, Build
from ssr.sim import simulate
gd = GameData(); t = load_team(gd, "teams/<name>.yaml"); r = simulate(gd, t, Build())
print({k: f"{v / r.total:.1%}" for k, v in sorted(r.by_slot.items())})
print(r.casts, r.on_field_time, r.status_time)
for u in r.unknown_modifiers: print("ASSUMED", u)
```

Check one potential's resolved modifiers after writing overrides:

```python
from ssr.kit import resolve_potential
rp = resolve_potential(gd, t.members[i].kit, <potential id>, 6)
print([(m.label(), m.value, m.target, m.hit_tags, m.trigger) for m in rp.modifiers])
```

Disc work: `python -m ssr.inspect scripted-discs --element <EET>` lists discs of the team's element (plus neutral) that still have unmodelled parts. `python -m ssr.inspect disc "<name>"` shows a disc's text next to what the model decodes.
