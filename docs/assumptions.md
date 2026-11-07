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
- **Energy:** each main hit gives `HitDamage.EnergyCharge`/10000, capped per cast by `Skill.GetEnergyLimit` (per strike for autos). Supports receive the same gain × `Character.EnergyConvRatio` (0.75), GUESS. There is no passive energy (user-tested 2026-11-03: standing in a boss fight without attacking gains none), so every kit has `energy_per_second: 0`. Check: Nanoha's sim ult is ready ~60 s after her first hit vs ~76 s in game with ~10 dodges and chasing. Casting the ult empties energy.
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

Maygi: 8.65% / 0.05%. **Chosen: RES 145**, i.e. a "weak" enemy (250) with ~105 PEN already in the build (the gist's "weak + 1 rainbow PEN" ≈ 140). The first line matches exactly; the second line can't get closer than ~0.4% on this curve without breaking the first, since RES − 2×110 is below zero at any RES that gives 8.65% for the first line. Not forced further: the near-zero second line likely means Maygi's baseline already had more PEN or he measured differently. Enemy DEF 500 (user, 2026-11-01: base enemy DEF; ×0.5 damage). DEF only scales everything equally unless a DEF PEN source is rated. Enemy DEF reductions (Ridge's Corrosive Vines / Root Grasp) are flat and subtract from the 500 before defAmend (user confirmed the 500, 2026-11-03), so they're worth more as DEF drops: −150 = +20.5%, −301 = +47.6%.

**Element weakness** (user, 2026-11-02): the reference formula's RES bands are 250 weak, 570 raid, 750 neutral, 2000 resisted. Maygi's PEN numbers fit "weak" (above), so a boss is weak to the team's main element, and off-element Trekkers hit a neutral RES. A team file's `enemy.weak: [Umbra]` keeps `res` (145) for the weak elements and gives every other element `res_neutral` (default 645 = 750 minus the same ~105 baseline PEN). Off-element hits then deal ~0.54× (0.494 vs 0.916 RES multiplier). Without `weak`, every element uses `res` (all earlier teams are single-element, so nothing changes for them).

## Harmony notes

Each main disc's harmonies are assumed at **Lv1**, and the team gets the notes those harmonies need (user, 2026-11-03). Notes are shared across the run, so each note type's count is the largest any one harmony asks for (not the sum). Requirements come from `SecondarySkill.NeedSubNoteSkills`: 10 of each of 3 types, or 15 of each of 2 types, at Lv1 (25/30 at Lv2 … 70/75 at Lv5). A note's bonus is its `EffectValue` Lv1 value × count. Linear scaling past the 9 levels in data was checked in game by the user. Notes are squad-wide (they follow `disc_stats_target`) and always on.

- Real runs vary a lot. The user's Noya run had 36 Lux and roughly 35–43 of the main types, which put 5 harmonies at Lv2 and 1 at Lv1. Lv1 notes (15 each for that team) are conservative.
- Team assumption `harmony_notes: N` grants the notes for harmony Lv N. `0` turns notes off (the earlier behaviour). Harmony *effects* stay at Lv1 either way.
- Support-disc starting notes aren't counted on top. They only help reach the requirement, which is already assumed met.

## Discs with scripted effects

46 of 104 discs have a melody or harmony with no `EffectId` (the effect lives in a script, only text + Params in data). These are modelled by `specs/discs/<id>.yaml`; a scripted part without a spec is **listed as "scripted, not modelled"** in the Discs sheet's Notes. Since 2026-11-04 every available disc has a spec and none has an unknown trigger (`python -m ssr.inspect scripted-discs` lists nothing). Some parts still have GUESS uptimes, marked in their spec.

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
- Team assumption `minion_buffs: all` gives minions every buff again, for comparison. Before the battle-start snapshot rule (below) and the Prayer of Raging Flame drop, the text rule took Chixia's share from 68% to 62%. Since then (2026-11-02) `text` and `all` give the same shares on both minion teams: Chixia 65.1% (test fixture build) / 62.9% (saved build), Laru 54.3%. Every triggered buff in those kits and discs either names minions or doesn't apply to them.
- **Battle-start snapshot** (user, in-game, 2026-11-01): minions summon with the summoner's stat sheet as it was at the start of the battle. So every always-on buff on the summoner reaches minions, whatever its wording (e.g. a disc melody's "Ignis Trekkers' Ignis DMG"). Buffs that come and go (on cast, on hit, while X) reach minions only if they name minions / friendly units, per the rule above. Chixia's triggered self-buffs ("Chixia's ATK", Dragon Blaze) don't reach them. Buffs averaged as `uptime × stacks` (a GUESS uptime or an unknown trigger) count as coming and going, not as always on.
- **Prayer of Raging Flame's ATK buff is not modelled**: in game it only stacks when hitting multiple targets and never fires on a single boss (user-checked, plus community reports). The text doesn't say so. Its ult Ignis Mark still applies.
- **Snowy Night Surprise's Hymn** needs the summoner's own Ode, which comes from her own Skill DMG (Word 6002): `&recent:skill_dmg:12.25`.

## Build guide page: emblems (2026-11-01)

- **Emblem "+N" on a potential not taken in the run** is assumed to give that potential at level N (user, 2026-11-01; real behaviour unknown). With a target it fights at target + N, capped at 9.
- **Charge Efficiency (AttrType 37)** lines: "(Main)" applies only while the trekker is the main, "(Support)" only while a support (Claude's reading; the data names their attributes `EnergyEfficiency` / `EnergyConvRatio`). Each multiplies the energy that trekker gains from the main's hits by `1 + value`; passive energy per second is unchanged. Unconfirmed in game.
- **Emblem stat lines are offered in every slot** (Lv70/80/90); `CharGemAttrValue` has three TypeId groups that look like per-slot pools (the third lacks element PEN and Charge Efficiency), but which group is which slot isn't confirmed, so the page doesn't restrict by them.

## Chitose / Freesia / Teresa (2026-11-01)

- **Stored skill uses:** `Skill.SectionAmount` = stored uses, `UseInterval`/10000 = min seconds between them (Torrent Flash: 2 uses, 0.5 s; the user saw 0.4-0.6 s gaps). One recharge timer refills uses one at a time and keeps its progress across casts (user, in game: at 2.5 uses a cast leaves 1.5).
- **Torrent Flash: Scale** replaces a Torrent Flash cast and spends a use (user): every 3rd cast, every 2nd with Cascade of Ruin (`cycle` on the skill hits). With Returning Tide, every cast after the first is a Scale against a boss (user-observed; a miss breaks the chain, not modelled). The user's build had Flowing Circle (3 uses).
- **Mirror Images** deal their hits at the stated share of Chitose's multiplier (`mult` on the hit). Against the Flow's image triggers Aqua Marks; those Mark hits are full value (GUESS).
- **Chill** (Word 1027) is a pure enemy status stacked by every Aqua Mark Chitose triggers (10 s, 3 stacks). With Marks applied by Teresa's domain, Surge: Ripple and Freesia's skill, it's up ~all fight; Frozen (3 stacks) isn't modelled separately: "Chill/Frozen" conditions test Chill.
- **Freesia's Berserk autos** (support, after her ult) are ult-action hits: first string user-timed, then one string every 3 s (GUESS) until she leaves at +17 s.
- **Surging Shield** appears 0.8 s after the cast and lasts its full duration (8 s with Surge: Infinite, user-timed unhit); boss hits breaking it aren't modelled.
- **Aqua disc specs** (user answers, 2026-11-01): Teresa's Surging Shield counts as "the main gains / has a shield" (Summer Afternoon Rain). Destiny Cards (United by Fate) only exist in a side mode: 0. "Aqua VUL" = Aqua DMG Taken debuffs, assumed always up (Winter's Grip / Wave Breaker). Bosses count as elite or higher. Getting hit (Soda Shopping) is low uptime (10%, GUESS). Main above 80% HP (Steam Syndrome): always. Tide Weave (Fleeting Glimmers) is a disc-only buff with the listed effects; its support-ult Energy refund isn't modelled.
- **Bosses can't be Frozen** (user): "Chill/Frozen" conditions test Chill only.

## Resilience breaks and Boss Blitz enemies (2026-11-03)

Spec: `docs/superpowers/specs/2026-11-03-resilience-break-design.md`. Validation: `docs/validation/2026-11-03-boss-blitz-breaks.md`.

- **The bar:** 250M resilience (`MonsterValueTemplete.Toughness`) for both Boss Blitz bosses and Generic (user). At 0 the enemy is broken for 10 s (`Monster.ToughnessBrokenTime`), then the bar refills to full (`IsToughnessRecorver`). `enemy.resilience: 0` turns it off (regression anchor: `fl_noya_skill` then reproduces the pre-resilience totals exactly).
- **Resilience per hit (inferred, no per-hit table found):** the hit's damage without the break ratio × the hitter's `Attribute.ToughnessDamageAdjust`/10000 (15000 = ×1.5 for Tilia, Firefly, Freesia, Teresa, Cosette, Chitose, Shia, Snowish Laru, FL Noya; ×1.0 otherwise; minions use their owner's) × (1 + Resilience Break Efficiency, EAT 43). Evidence: Noya's ~7.7M DPS × 1.5 fills 250M in ~22 s (user measured ~22–25 s of active time per break); Chitose's team broke once on 239M.
- **Break ratio ×1.5** (`break_ratio`), unverified: the reference tester's "150%"; ×2.5 is the other reading (validation doc compares them). The hit that breaks the bar isn't boosted; only later hits are.
- **Lock (GUESS):** after a break ends, the bar can't be lowered from `lock_delay` 1.3 s for `lock_time` 4.7 s (fight time: the recorded 8.86 s lock minus a 4.2 s frozen Tilia-ult animation inside it). **Open question:** the second recorded lock lasted only ~0.3 s; no rule in the data explains either.
- **Preset RES** = data `{W,F,S,A,L,D}ERFix` − `baseline_pen` 105 (weak 250 → 145, neutral 750 → 645, own element 2000 → 1895), following the RES calibration above. A team-file `res` override moves the preset's weak elements with it.
- **Boss abilities** use the stats the ability text names (Mark / Skill DMG Taken); the data's EffectType subtype is 53 (generic DMG Taken) on all of them. Count of the Duloos' "main takes +10% DMG" is defensive and not modelled; its Max HP +20% is.
- **Chance procs** use exact expected values: a proc with `chance` p and ICD has, per trigger, p × (1 − proc mass already spent in the ICD window) (`ExpectedICD`). Cosette's Form Breaker: 30% per claw, ICD 0.5 s → ~3.05 procs per 13-claw cast, each removing 0.4/0.5/0.6% of the bar.
- **`while:broken`** with the bar off falls back to `unknown_trigger_uptime` (spec). "Stunned" alternatives count as broken; bosses are stun-immune (Tilia's Enemy Counter already assumes so), so stun-applying potentials (Flora 512642, Tilia 510741, Shia 515528, Mistique 513508, Cosette 514228) don't break or stun the boss.
- **EAT 42 ("Resilience")** lines are the Trekker's own superarmor: not modelled.

## Disc pass: every disc specced (2026-11-04)

- **Dodges** (user): the main dodges once every `dodge_interval` s on average (team assumption, default 10; event `dodge:main`). A dodge needs control: one due during a skill/ult lock (no control, but immune) waits for the lock to end. The schedule keeps its average rate, because the 10 s came from a real fight with locks included. Two dodges are at least 1 s apart (`DODGE_CD`, the dodge cooldown; user corrected 3 s -> 1 s). Each dodge costs 10 frames of attacking (`dodge_time` 0.333 s, pauses the auto string). Fewer auto hits also mean less energy, so ults come later, the supports' too. Zesty Curiosity and every kit dodge potential use it (Decisive Moment, Starlit Dash, Waltz of Ripples, Hunt is On, Swiftstep; Tremble and Fall's instant last strike after a dodge).
- **Dodge-cancel** (user, Nanoha): a chain is 2.40 s without a dodge and 2.13 s with a late dodge after the final throw, so dodging at the end of every auto string is strictly better, even without a dodge potential. The kit's `auto.dodge_cancel: {at: 1.4, duration: 2.0}` emits a dodge at that offset and shortens the string to 2.0 s (the measured 0.267 s saving; a perfectly timed dodge may save ~0.2 s more). Those dodges replace the periodic ones (`dodge_cancel: false` in a team's assumptions turns it off). Nanoha teams +5.6% to +6.6% pinks only; Starlit Dash Lv6 +4.8% -> +13.7%.
- **Dodge-cancel** (user, Amber, Precise Temperature Control): a dodge cuts the hits still to come, and the skill CD starts at the recast's dodge instead of when the recast ends. Timings (30 fps): recast ready 2,10 after the skill (38,12 -> 40,22), first auto 1,25 after the recast (41,03 -> 42,28). The kit dodges each cast at the earliest frame that keeps every hit: the first cast at 1,24 with the recast 0,10 later (41,26 -> 42,06), the recast at 1,13 with autos 0,11 later (39,25 -> 40,06). Both casts take 3,17 instead of 4,05. The 1,13 dodge and the CD start combine clips rather than coming from one. Each dodge takes the place of the next periodic one.
  - **Cutting the third volley loses damage.** Sim vs no dodges, 120 / 180 / 600 s, 3 Amber teams, with and without Grand Finale Lv6: dodging after the last hit +0.69% to +2.40%, cutting the recast's volley -1.77% to -6.29%, cutting both -3.76% to -8.70%. Cutting both only saves 8 more frames per cycle. The recast's big hits give 0.71 Energy each against 23.1 per cast, so cutting its volley also costs ults (16-18 -> 13 in 600 s, against 17-19 with the default dodges).
  - **No gain on autos** (user): dodging before the reload only moves the reload after the dodge, and the reload is too fast to interrupt reliably. Casting on an empty magazine needs no reload, as the string already restarts full after every cast.
- **Amber's recast is its own skill** (user's clips, 2026-11-06): it has its own script and hit rows, and they depend on whether the first cast triggered a Mark. Each clip's crit multiplier is constant across hits (2.416 with Flora's butterflies, Incineration included), so non-crit values can be recovered from crits.
  - **No Mark:** big / small are 13091 / 2106 (106% / 17%, rows `103303004` / `103303003`), with no Precise Temperature Control bonus. The first cast is 11855 / 850 (106% / 7.6%). Not modelled: in the 3 Amber teams every first cast triggers a Mark (52 of 52 in 600 s).
  - **Marked (modelled):** both big hits are equal, and big / volley is 10109 / 7454 and 12801 / 10408, which fits rows `103303001` (22.7%) and `103303003` (17%). The clips' 1.356 and 1.230 sit either side of the rows' 1.335. Row `103303002` (29.7%) isn't seen in game.
  - **The +65% is a separate multiplier (`mult: 1.65` on every recast hit), not DMG bucket.** The stat is EAT 85 "DMG Multiplier". The recast's per-% scale against the first cast's volley just before it is 1.98x and 2.35x in the two clips, which +65% in the bucket can't reach even with nothing else in it.
  - **Why the jump is above 1.65x:** buffs change between the casts. With the clips' Amber build (skill Lv8; Dominant Firepower, Precise Temperature Control, Grand Finale 6, Ardent Trigger 6, Fiery Rhythm 2; sim team Amber / Flora / Chixia), the sim's ratio varies per cycle from 1.41x to 2.24x, against the clips' 1.98x and 2.35x. A bucket bonus would top out near 1.93x on the same timing. This favours the multiplier without proving it: no clip has the same buffs on both casts. The first cast's rise of about 11% after its first hit (21098 -> 23503, 23092 -> 25657) also shows in the sim (8-10%), even without Fiery Rhythm. Its source wasn't traced; the user's guess for these spikes is Chixia's tiger (ATK buffs) or Flora's potential that gives ATK% when the main crits.
  - **Marks:** the recast can trigger them when one is up (Incineration on its shots 1 and 3, `2026-11-01-amber-flora-chixia.md`; on shot 2 in a 2026-11-06 clip).
  - **Grand Finale:** its 2 extra rounds are big hits on the first cast only; its Skill DMG bonus is still applied to the recast.
- **Dodge on cooldown** (user): `dodge_spam: {interval: 3, potentials: [ids]}` makes the main dodge every 3 s, but only in builds with one of those potentials (without them it only costs damage, and a team-wide rate would inflate the potentials' rating). Set for Mistique (Decisive Moment: weak autos), Chitose (Waltz of Ripples) and Nazuna as main (Swiftstep: Gerie does most of the damage). Gerie stays at 10 s (−2.7% at 3 s even with Hunt is On); Nanoha dodge-cancels instead (below). With Tremble and Fall, Chitose's autos become a dodge loop: dodge, last strike +0.833 / +0.933 s, next dodge +0.967 s (user-timed). The Mirror Image and Serpent's Glide follow the dodge strikes.
- **Getting hit** (user): the main is hit about every 20 s (`hit_taken_interval`, event `hit_taken:main`), never while the boss is broken (a broken boss doesn't attack). It depends on the boss and on melee vs ranged. It replaces the 10% GUESS uptime of Soda Shopping, The Shining, Unknown Fragrance, Cage of Roses, ★Rolling Life★ and Delusion, and drives Prayer Beneath Light's shield.
- **Disc shields last their full duration** (user): most boss hits are chip damage, and losing a shield to a big hit is usually a player mistake. Shields (EffectType 42) are tracked as statuses in the disc spec. New Star Prelude's shield is a 20 s timer from battle start (data: `Trigger` 19, condition 29, param 20), so it's up 15 s of every 20 s.
- **Battle-start Energy** (EffectType 34, the 3★ "restore 15 Energy at the start of battle" melodies) starts the receiving Trekkers' Energy at that value (pseudo stat `START_ENERGY`).
- **VUL** = an elemental DMG Taken debuff on the target (user, United by Fate). "vs targets with X VUL" lines use `while:vul:<element>`, which holds while any modifier of that element's DMG Taken (EAT 35–40) is up on the enemy. Slot-only Taken stats (e.g. "Ventus Skill DMG Taken", written as Skill DMG Taken) don't count.
- **"While the main's Ultimate is active"** (Summer Sanctuary, user): until the main regains control after the cast (its ult `lock`), `while:in_action:0:ult`.
- **Fly, O Caged Bird's Starlit Hope** (GUESS, user will test): one stack per second a Ventus Versatile support is on the battlefield (`on_field_1s`). Cyclone / Blossom Marks are Noya's / Nanoha's Ventus Marks (their kits tag the Mark hit).
- **Defensive lines** ("reduces DMG taken by the main") are dropped in the specs. **Kill-based** lines are dropped (single boss). **Destiny Cards:** 0.
- **Per-caster buffs** ("increases their Skill DMG" after any Ventus Trekker's skill): the main's cast buffs the main; any support's cast buffs both supports.
- **Status stacks shared per team:** Touch of Miracle's Assembly and Little Paradise's Loaded are one status for all Terra Vanguards. "Has N stacks" is read as N or more. Their max is 3 because both harmonies are always active in the sim.
- **Chance-based debuffs** (Laceration, Shock: 35% per non-Auto hit, 8 s) fire on every 3rd such hit, so they're near-permanent in practice. Both are named statuses, so their "vs Lacerated / Shocked targets" harmonies test them.
- **One Shot, One Down's ATK ramp** is now simulated (+1 stack every 8 s from 0 s, max 10) instead of the 120 s average. That gives one stack early.
