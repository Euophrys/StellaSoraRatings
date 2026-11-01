# Modelling assumptions

A running log of every modelling choice that isn't read straight from the game data.

## Data decoding

- **Param `LevelUp` refs:** level n of base id X is row `X + n×10` in the `<Source>Value` table (e.g. `16241001` → Lv1 `16241011`, Lv9 `16241091`). Missing levels clamp to the highest row present. `NoLevel` refs read the named table at the id as given, whatever the level.
- **Formats:** any format starting `10K` is divided by 10000. `HdPct`, `Pct`, `Hd`, `Fixed` are used raw. `Enum,EAT` returns the integer stat id.
- **Stat names (EAT):** `EffectDesc` rows with Id 12xxxx, `Type2ID` 2. Other `EffectDesc` families reuse `TypeID` for skill/potential level-ups.
- **Hit DamageType → slot:** 1 auto, 2 skill, 3 ult, 4 other, 5 mark, **7 minion (Minion DMG, EAT 66; Minion Crit 74/81).** Only summoner Trekkers have DamageType 7 hits (Snowish Laru's Colonel Walnut / General Curly, whose text says "Minion DMG"). Derivative DMG (EAT 68) is a separate stat (its own emblem line) that nothing feeds; what it applies to is unknown.
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

## Fight simulation

- Tick 0.05 s, 120 s. Supports cast skill at t=0; the main's first skill at 1.0 s. Afterwards each Trekker casts its ult when energy and cooldown allow, else its skill when off cooldown (supports first, then the main).
- **Main busy time:** after any main cast, another cast can't start for 1.5 s (`DEFAULT_BUSY`, GUESS) or the action's lock, whichever is shorter. Autos stay blocked for the action's `lock` (FL Noya: skill 5 s, ult 4 s, Radiance Flurry 3 s — user-timed).
- **Follow-up actions** (Dawnflare's Radiance Flurry) are cast after every Nth cast of their parent, once the parent's lock ends; they don't use a cooldown. **Extra casts** fire 1.5 s after the original.
- **Autos:** the string loops while the main isn't locked and restarts from strike 1 after every cast.
- **Energy:** each main hit gives `HitDamage.EnergyCharge`/10000, capped per cast by `Skill.GetEnergyLimit` (per strike for autos). Supports receive the same gain × `Character.EnergyConvRatio` (0.75), GUESS. Everyone also gets `energy_per_second` (kit, GUESS 2/s). Casting the ult empties energy.
- **Marks:** a support hit with `applies_mark` puts a Mark up; a main hit that can trigger Marks consumes it and deals the Mark hit, at most once per `mark_icd` (1 s). One Mark at a time (GUESS).
- **Hit levels:** `levelTypeData` 1 → that potential's level (pinks Lv1); 3 → skill level of `LevelData` slot (5 auto, 2/1 skill, 4 ult) incl. emblem +N; 4 → ascension (9th entry); none → the casting action's skill level.
- **Modifiers:** triggered buffs add a stack per matching event (refreshing the oldest past `max_stacks`) and expire after their duration. Unknown triggers are a constant `uptime × max_stacks`. Disc stats and disc effects go to the whole team (`disc_stats_target: team`).

## Enemy RES calibration (Task 9)

Noya's Lux PEN emblem lines (110 PEN each, best roll) against the baseline team (pinks, Maygi's top-3 discs at C1, no emblems):

| enemy RES | 1st line | 2nd line |
| --- | --- | --- |
| 110 | 5.09% | 0.00% |
| 140 | 8.12% | 0.36% |
| **145** | **8.65%** | **0.49%** |
| 150 | 9.19% | 0.64% |
| 250 (weak) | 22.88% | 8.12% |
| 570 (raid) | 10.64% | 5.61% |

Maygi: 8.65% / 0.05%. **Chosen: RES 145**, i.e. a "weak" enemy (250) with ~105 PEN already in the build (the gist's "weak + 1 rainbow PEN" ≈ 140). The first line matches exactly; the second line can't get closer than ~0.4% on this curve without breaking the first, since RES − 2×110 is below zero at any RES that gives 8.65% for the first line. Not forced further: the near-zero second line likely means Maygi's baseline already had more PEN or he measured differently. Enemy DEF left at 0 (unknown); DEF only scales everything equally unless a DEF PEN source is rated.

## Discs with scripted effects

46 of 104 discs have a melody or harmony with no `EffectId` (the effect lives in a script, only text + Params in data). These are modelled by `specs/discs/<id>.yaml` where written (My Guiding Star, Ripples of Nostalgia, Summer Sanctuary, Sparkling Moment, Stellar Destination, Seed Alike, Eternal Brilliance) and otherwise **listed as "scripted, not modelled"** in the Discs sheet's Notes. Their ratings understate them.

- "Lux Versatile Trekkers" = `Character.Class` 2 (Firefly here; FL Noya is class 1 Vanguard, Tilia class 3 Support).

## Glimmer, on-field time, conditional effects (second pass)

- **Glimmer** (Word 4029 → Effect/BuffValue 3012): Lux DMG Taken +0.5% per stack, 6 s, max 3 stacks. Noya adds one stack per Lucent (Mark trigger). It's tracked as a named status (`name: glimmer` in `specs/trekkers/162.yaml`).
- **EAT 85** = DMG dealt to targets with Glimmer, applied in the general DMG bucket. Noya's auto attacks get it once per Glimmer stack (`OnceAdditionalAttribute` 16290001 at auto level). Resolve: Blitz and Searing Sun get it while any Glimmer is up.
- **EffectType 45** = a stat add under a condition (e.g. "if the main's HP is above 80%"). It's treated as a stat add with an assumed trigger unless a spec pins it down.
- **On the battlefield:** a support is on the field for `on_field` seconds after each skill or ult cast (default 4 s, GUESS). `while:on_field:<who>` effects are active only then.
- **Stellar Crash:** each blade adds as many Lux DMG Taken stacks as the target has Glimmer stacks.

## Amber / Snowish Laru / Flora (2026-11-01)

- **Negative "DMG Taken"** ("reduces DMG taken by the main") is defensive and goes on the owner, not the enemy. It used to decode as an enemy debuff that *lowered* team damage (10 discs, incl. A Moment in the Afternoon and Sparkling Moment).
- **Duplicate Lv1 rows:** when a potential's Param names a stat through a `NoLevel` ref to the Lv1 row (e.g. Two-Gun Salute `15825011`), that row also decodes as a modifier. Such duplicates are dropped in the kit spec (Lv1 value = the leveled ref's first value).
- **Amber's auto:** 12 shots in ~2 s + ~0.5 s reload (user-timed); every cast restarts it with a full magazine.
- **Supports can skip their ult** (kit leaves it out): Snowish Laru's ult isn't used in the reference video.
- **Snowish Laru on-field 14 s** per skill (user-timed); her skill CD keeps ticking meanwhile.

## Amber / Flora / Chixia: minions (2026-11-01)

- **Which buffs reach minions** (user, from community knowledge of the "minion bug"): buffs scoped to "Trekkers" (e.g. "all Ignis Trekkers' Ignis DMG", "the squad's ATK") **don't** reach minions. Buffs that say "minions" or "friendly/all units" do. Enemy debuffs (DMG Taken) always count. Minion hits get the summoner's stat sheet (base stats, disc stats and emblems), Minion DMG/Crit stats, enemy debuffs and modifiers that reach minions.
- The flag is read from the text (`effects.text_reaches_minions`): it looks at what the sentence naming the stat *increases* (the part after "increase"), or at the whole text when the stat is only a `&ParamN&` placeholder. Specs set `minions: true|false` where the text names minions differently (Laru's Heart's Edict: "their Crit DMG" = Walnut's and Curly's).
- Team assumption `minion_buffs: all` gives minions every buff again, for comparison. With the text rule, Chixia's share falls from 68% to 62%. The Laru team moves less than 2%.
- **Chixia's own buffs on herself** ("Chixia's ATK", Dragon Blaze) don't reach her minions. The Word text says minions "inherit 100% of Chixia's ATK"; that's read as her stat sheet, not her buffs.
- **Snowy Night Surprise's Hymn** needs the summoner's own Ode, which comes from her own Skill DMG (Word 6002): `&recent:skill_dmg:12.25`.
