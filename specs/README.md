# Kit spec files (`specs/trekkers/<char id>.yaml`)

One file per Trekker. It says what the game tables can't: how many times each hit lands, timing, which hits trigger or apply Marks, and what potentials _do_ beyond adding a stat. **Every number the game data has is read from the data**; these files only carry semantics (counts, timings, tags, triggers, uptimes). Anything guessed is marked `# GUESS` so you can correct it with in-game timings.

A file has a `main:` section (used when the Trekker is the main) and a `support:` section (used when they're a support). Supports never auto attack. `stub: true` in a section means it only holds placeholder hits: not timed in game, potentials not modelled. The build page warns about stubs, and about a role with no section, which can't be simulated. Remove the flag when the kit is authored. `untimed: true` means the kit is authored from the game text but nothing has been timed in game, so its animations are conservative guesses and minions are skipped (`docs/assumptions.md`, Untimed kits). The build page warns about those too. Remove the flag once the kit's timings are measured.

## Actions

```yaml
main:
  actions:
    auto: # the full auto-attack string, looped while the main isn't locked
      duration: 3.0 # seconds for one full string            # GUESS
      hits:
        - { hit: 162100001, count: 2, tags: [greatsword] }
    skill:
      lock: 5.0 # main can't auto for this long after casting (default 3.0)
      hits:
        - {
            hit: 162310001,
            count: 5,
            interval: 0.15,
            tags: [longsword],
            triggers_mark: true,
          }
    ult:
      lock: 4.0 # default 5.0
      hits: [...]
```

`HitSpec` fields:

| field | meaning |
| --- | --- |
| `hit` | `HitDamage` id (multiplier, element, damage bucket all come from data) |
| `count` | times it lands per cast (default 1) |
| `offset` | seconds after the cast before the first one lands (default 0) |
| `interval` | seconds between repeats (default 0.1) |
| `tags` | names other rules refer to (`glow`, `longsword`, ...) |
| `triggers_mark` | this hit can trigger a Mark already on the enemy (needs a `mark:` in the kit) |
| `applies_mark` | this hit puts a Mark on the enemy (supports) |
| `requires` | only lands if any of these potential ids is in the build |
| `excludes` | doesn't land if any of these potential ids is in the build |
| `requires_all` | only lands if all of these potential ids are in the build |
| `cycle` | `[n, i]`: lands only on the i-th of every n casts of its action, e.g. a skill whose every 3rd cast is an upgraded form |
| `from_cast` / `upto_cast` | lands only from / up to the Nth cast of its action |
| `mult` | damage multiplier on the hit (default 1), e.g. `0.5` for a Mirror Image with 50% of the DMG Multiplier |
| `when` | procs only: fires only while a condition holds, e.g. `"while:status:butterfly"` |
| `restart` | procs only: a new firing drops this proc's hits still pending (a DoT that refreshes instead of stacking, e.g. Dark Burn) |
| `chance` | procs only: probability per matching event (default 1); not allowed with `restart`; `every` counts events before the chance. The sim uses the expected value: the proc lands with `mult` x its expected share, and `icd` becomes an expected-value ICD (procs in one ICD window are mutually exclusive) |
| `resilience` | procs only: fraction of the enemy's max resilience bar removed per proc (number or `{param: ParamN}`); with `hit: 0` the proc deals no damage, e.g. Cosette's Form Breaker `{hit: 0, event: "hit:self:claw", chance: 0.3, icd: 0.5, resilience: {param: Param1}}` |
| `energy` | procs only: Energy granted to the proc's owner per proc (number or `{param: ParamN}`), scaled by `chance` as an expected value. It's flat: Charge Efficiency doesn't apply, and supports don't get a share. E.g. Knight's Seal `{hit: 0, event: "mark:any", energy: {param: Param3}}` |

A hit with `hit: 0` is a **marker**: it deals no damage and only emits `marker:<who>:<tag>` for each tag at its time. Use it for things that happen on a schedule without dealing damage (a summon becoming ready, a stack every 2 s):

```yaml
- { hit: 0, offset: 3.967, tags: [tiger_up] } # Tiger is ready
- { hit: 0, count: 3, offset: 2.8, interval: 2.0, tags: [tiger_tick] } # a stack every 2 s
```

Cooldown and ult energy cost come from `Skill.json`. **Stored uses:** a skill whose row has `SectionAmount` > 1 (Chitose's Torrent Flash: 2) stores that many uses; a cast spends one and the cooldown recharges them one at a time, keeping its progress across casts (user, in game: at 2.5 uses, a cast leaves 1.5). Stored uses are cast at least `UseInterval` apart (data). An action can set `charges: N` / `use_interval: <s>` to override. `cd_start: <s>`: the action's cooldown starts that many seconds after its cast (Noya's skill: 2.0 s, user-timed). Energy gained per hit is `HitDamage.EnergyCharge`, capped per cast by `Skill.GetEnergyLimit`.

A support kit can leave out `ult` (the support never casts it).

## On the battlefield (supports)

```yaml
support:
  on_field: { skill: 4.0, ult: 4.0 } # seconds a support stays on the battlefield after casting
```

`wait_on_field: true` (support section): the support starts no cast while still on the battlefield from the previous one (Cosette's ult cancels her running skill, so it waits for the skill to end).

Supports appear to cast and then leave. Effects that only work while a support is on the battlefield use `event: "while:on_field:<who>"` (`support`, `self`, `any`, or a member index); they're active only during those windows. Default 4 s.

## Marks

```yaml
mark: { hit: 162000001 } # damage dealt when the main triggers a Mark
mark: { hit: 112100000, tags: [cyclone] } # optional tags on the Mark hit: "a Mark that inflicts Cyclone" = hit:main:cyclone
```

Marks are **per element**: a hit applies and triggers Marks of its Trekker's element (Chixia's Ignis Marks can't be triggered by Umbra Mistique). A Mark is up after a support hit with `applies_mark` lands. A hit with `triggers_mark` consumes it and deals the mark hit, at most once per `mark_icd` seconds (team file, default 1.0). Emits event `mark:<member>`. Applying one emits `mark_applied:<who>` and also `mark_new:<who>` (no Mark of that element was up: "inflicts a Mark on a target without a Mark") or `mark_refresh:<who>` (one was: "repeatedly inflicts").

A main kit can have `procs:` of its own (same keys as potential procs), e.g. Mistique's Dark Burn after each Mark trigger: `{event: "mark:self", hit: 135000001, count: 10, offset: 0.067, interval: 0.5, mult: 0.1, restart: true}`. Supports can trigger Marks too when their kit has a `mark:` (Shia's skill and ult "trigger Lux Mark and summon a Thunderbolt"): they then compete with the main for them.

## Buffs granted by base skills

```yaml
buffs:
  - effect: 16290003 # Effect id, leveled by the skill level named in `level`
    level: ult
    event: cast:self:ult
    duration: { ref: "Buff,LevelUp,16290003,Time,10K" }
    target: self # self | main | team | enemy
```

A buff without `effect` or `attribute` is a **pure status**: no stat, only stacks other rules can count (e.g. minions out: `{name: dragon, event: "marker:self:dragon_up", duration: 7.067, max_stacks: 4}`). `while:status:a+b` counts several statuses together, and `while:status:a>=N` is only active (and only counts) at N stacks or more; both also work in proc `when`.

Buffs also take `name` (makes a status other rules can test with `while:status:<name>`), `max_stacks`, `add` (stacks added per event, e.g. 3 butterflies per cast), `every` (activate on every Nth event), `icd` (seconds between activations), `reset_on` (list of events that clear the stacks), `minions` (also reaches the owner's minions), and `requires` / `excludes` / `requires_all` (potential ids). `event: always` makes a buff always on: "vs elite or higher" is always on, as every enemy preset is a boss.

## ATK SPD

Stat 47 (ATK SPD) runs the main's auto string faster: its clock advances at `1 + ATK SPD`, so every offset in the string, the reload and an auto `dodge_cancel` scale together. Treat it like any other stat: give the potential's modifier an `event` and, for a support's buff, `target: main`. It does not change skill or ult locks, or minions (those use a pool's `speed`).

## Minion pools

For minions with their own lifetimes and attack loops (Mistique's Pumpka Phantoms), a kit section can have `minions:`:

```yaml
minions:
  phantom:
    summon: { event: "cast:self:skill", offset: 0.7, every: 3.0, count: 5 } # summon ticks; a new schedule cancels the old (restart: true)
    max: 4 # out at once
    duration: 15.0 # lifetime from its summon
    at_max: replace # a tick with `max` out: replace (the oldest vanishes) | refresh (all lifetimes reset)
    windup: 1.433 # first attack after the summon
    interval: 0.7 # then one attack per interval, cycling through `attacks`
    attacks:
      - { hit: 135900001, tags: [phantom, minion], triggers_mark: true }
      - { hit: 135900002, tags: [phantom, minion], triggers_mark: true }
```

Optional: `sacrifice_on` (event: all vanish and count as sacrificed), `resummon_on` (event: all vanish and as many are summoned again), `speed` (ATK SPD: interval / (1 + speed)), `reactions` (hits with `event` / `icd`: every minion out attacks on the event, each with its own ICD that starts on cooldown at its summon, e.g. Thread the Needle). Events: `summon:<who>:<pool>`, `vanish:<who>:<pool>` (lifetime over, replaced, sacrificed or re-summoned), `sacrifice:<who>:<pool>`, `minion_tick:<who>:<pool>` (every summon tick, also at max). The pool's name is a status counting the minions out (`while:status:phantom>=2`). A potential changes a pool with `minion_rules: {phantom: {at_max: refresh}}` (any of the keys above; values may be `{param: ...}` / `{ref: ...}`). A key ending in `_add` adds to a numeric key instead of replacing it, e.g. Nanoha's Wind Whispers `{clone: {duration_add: {param: Param1}}}` (+N s of clone lifetime). Minion-pool attacks with a non-minion DamageType (Nanoha's clones deal Ultimate DMG) use the owner's stat sheet like her own hits.

## Talents (dupes)

Each dupe unlocks the next talent group (`TalentGroup`, chained by `PreGroup`). A team member's `talents: N` (default 0) unlocks the first N groups. Their stat nodes (Talent Type 2) are read from data; the key talent (Type 1) is scripted and needs an entry. Talents belong to the Trekker, so they sit at the top level of the file and apply in both roles (a section can have its own `talents:`, whose entries win):

```yaml
char_id: 162
talents:
  1620116: # Buried Past
    buff_events: { starender: "hit:self:any&once" } # adds an event alternative to the named base buff
    buffs:
      - { attribute: 16296111, event: "while:status:starender" }
  1120464: # Today's Bond: needs kills, nothing against a single boss
    buffs: []
```

`buffs` take the same keys as base-skill buffs. An unlocked key talent without an entry is listed as not modelled; `buffs: []` means it's deliberately worth nothing. A buff whose `effect` or `attribute` id is itself a row reads that row at any level, as talent rows are single-level, so `level` doesn't matter for them.

`&once` on an event alternative lets it fire only the first time it matches in the fight ("Triggers once every 5 minutes" with a 2-minute fight); other alternatives fire normally.

## Potentials

Pure always-on stat potentials need no entry; they're read from data. An entry can have any of:

```yaml
potentials:
  516205: # Prism Warp
    add_hits:
      skill: [{ hit: 162310006, count: 9, offset: 0.8, tags: [glow_return] }]
    overrides:
      - { stat: 71, hit_tags: [longsword, glow] } # its Skill Crit Rate only on these hits
    note: "Glow returns modelled on skill Glows only."
```

| key | meaning |
| --- | --- |
| `add_hits` | `{action: [HitSpec...]}` extra hits on that action |
| `replace_hits` | `{action: [HitSpec...]}` replaces the action's hits (e.g. ult form swap) |
| `add_actions` | new actions; `followup: {after: skill, every: 2}` casts it after every 2nd cast of `after`, once that cast's lock ends. `delay: <seconds>` waits that much longer (e.g. the input gap before a recast); the main doesn't auto meanwhile unless `autos: true`. A main's cast can have `dodge_cancel: {at: <offset>, duration: <s>}`: the main dodges `at` s after the cast, which cuts the hits still to come, ends the cast after `duration` (instead of `lock`) and starts a `starts_cd` cooldown at the dodge. On a `followup`, the same key applies to the `after` action, and only in builds that have the followup. The dodge takes the place of the next periodic one (team assumption `dodge_cancel: false` turns it off). `followup: {event: "hit:self:glow", every: {param: Param1}}` casts it after every Nth matching event instead (once the main's lock ends) |
| `overrides` | patch the data-derived modifiers. Match with `index` (order from data) or `stat`. Set `hit_tags`, `target`, `event`, `duration`, `max_stacks`, `uptime`, `icd`, `stacks`, `as_stat`, `minions` (true/false: does it reach the owner's minions? default read from the text, see below), `pct: true` (the stat is a %: an ATK attribute that decodes as flat but whose text says "ATK by 39%"), `copies` (a list of settings: the modifier is split into one copy per entry, each with its own events/tags, e.g. per-minion stacks), `reset_on` (list of events that clear the stacks, e.g. a reload), `every` (activate on every Nth event, e.g. "for every 4 claw strikes"), or `drop: true` |
| `mark_tags` | hits with these tags can now trigger Marks |
| `reset_cd` | `{ult: skill}`: casting the ult makes the skill ready |
| `add_charges` | `{skill: 1}`: more stored uses of that action ("increases initial uses by 1") |
| `cd_scale` | `{skill: 0.5}`: that action's cooldown is multiplied by the value ("reduces the Cooldown by 50%") |
| `ult_cost_scale` | the ult's Energy cost is multiplied by the value ("requires 25% more Energy": `1.25`) |
| `cd_when` | `[{action: skill, scale: 0.5, when: "while:cast_within:self:ult:9.167"}]`: a cooldown is multiplied by `scale` if `when` holds as it starts. A cooldown already running doesn't change |
| `cd_reduce` | `{action: skill, seconds: <value>, times: <value>}`: each cast refunds `seconds × times` of its own cooldown |
| `minion_rules` | `{pool: {key: value}}`: changes a minion pool (see Minion pools) |
| `procs` | `[{event: "hit:main:skill_dmg", hit: <id>, icd: <value>, every: <value>, tags: [...]}]` extra hits fired by events; `every: N` fires on every Nth matching event. Proc hits take all `HitSpec` fields (`count`, `offset`, `triggers_mark`, `requires`, ...) and emit their own tag events |
| `note` | shown in the sheet's Notes column |

**Values** that the data has are written as `{ref: "<Param string>"}` (resolved at the potential's level) or `{param: Param3}` (the potential's own Param). Plain numbers are only for timings, counts and uptimes.

### Events

Several events can be joined with `|` (`"cast:self:skill|cast:self:recast"`). `hit:<who>:any` matches every hit. Add `&while:<condition>` to an event alternative to count it only while the condition holds, e.g. `cast:self:skill&while:status:berserk` (casting the skill while in Berserk); conditions are the `while:` ones (`status:<name>`, `on_field:<who>`, `broken`, `vul:<EET>`: the enemy has that element's VUL, i.e. an elemental DMG Taken debuff (EAT 35–40) is up, `in_action:<member>:<action>`: within that action's `lock` after its last cast, e.g. "while the main's Ultimate is active", `cast_within:<member>:<action>:<s>`, `mark:<EET>`: a Mark of that element is on the enemy, `squad:<EET>:<n>`: at least n Trekkers of that element in the squad, e.g. `while:squad:5:3`, `not:<condition>`: the opposite of any of these, e.g. `while:not:in_action:0:ult`). `while:broken` holds while the enemy's resilience bar is broken (see Enemy presets); with the bar off (`resilience: 0`) it falls back to the `unknown_trigger_uptime` assumption (on if > 0). "Hits a stunned target" counts as broken: bosses are stun-immune in this model. Usable in modifier events, `&while:broken` suffixes, proc `when` and `hold`. Add `&recent:<tag>:<seconds>` to an event to count it only if the member that emitted it also landed a `<tag>` hit (or `<bucket>_dmg`) within that many seconds, e.g. `hit:any:minion&recent:skill_dmg:12.25` (a minion hit whose summoner dealt Skill DMG recently). Works in kit and disc specs. `mark_applied:<who>` (a hit that inflicts a Mark lands), `timer:<s>` (at 0, s, 2s, ... of the fight: "after the battle begins ... once every 20 s"), `dodge:main` (one dodge every `dodge_interval` s on average, team assumption, default 10; only when the main has control, at least 3 s apart, each pausing autos `dodge_time` 0.333 s; `dodge_spam: {interval: 3, potentials: [ids]}` dodges faster in builds with one of those potentials; a main whose `auto` has `dodge_cancel: {at: <offset>, duration: <s>}` instead dodges at that point of every string, which then lasts `duration`), `hit_taken:main` (the main is hit, one every `hit_taken_interval` s, default 20, never while broken), `on_field_1s:<who>` (every second a support is on the battlefield), `on_field_5s:<who>` (every 5 s a support has been on the battlefield: "every 5s they are on the field"), `cast:<who>:<action>`, `hit:<who>:<tag>` (each tag of each landed hit, plus the damage bucket: `auto_dmg`, `skill_dmg`, `ult_dmg`, `mark_dmg`, ...), `damage:<who>` (once per landed hit: use it for "deals DMG" stacks and counts, as `hit:<who>:any` fires once for each tag as well), `mark:<who>`. Marks are per element and a member triggers or inflicts their own, so `mark:element5` is "when Lux Mark is triggered" and `mark_applied:element5` "when any Trekker inflicts Lux Mark". `<who>` is `self`, `main`, `any`, a member index, `support` (any support) or `class<N>` (members of `Character.Class` N, e.g. `hit:class2:skill_dmg` = Skill DMG by a Versatile Trekker). Targets also take `support`. Targets are `self`, `main`, `team`, `enemy`, `element:N` (Trekkers of EET N, e.g. `element:6` = "Umbra Trekkers"), or `class:N` (members of `Character.Class` N: 1 Vanguard, 2 Versatile, 3 Support). A modifier with `event: unknown` (data couldn't say when it applies) uses a constant `uptime × max_stacks` and is listed as assumed in the sheet.

# Disc spec files (`specs/discs/<disc id>.yaml`)

Many discs' melody/harmony are scripted: the row has no `EffectId`, only text and `ParamN` strings (`"15%"`, `"8"`). A disc spec says what those Params do; values are always read from the row (melody at the disc's C-level, harmony at Level 1). Scripted parts without a spec are listed in the Discs sheet's Notes as not modelled.

```yaml
melody: # also harmony1 / harmony2
  - { stat: 3, pct: true, value: Param1, target: team }
  - {
      stat: 6,
      value: Param4,
      target: main,
      event: "mark:main",
      duration: Param5,
    }
  - { stat: 57, value: Param3, times: 3, target: main } # times: a number or a Param
  - {
      stat: 21,
      value: Param2,
      target: team,
      event: "hit:main:skill_dmg",
      every: Param1,
      duration: Param3,
    }
overrides: # pin down data-derived parts the data can't explain
  - { part: melody, stat: 39, event: "hit:main:ult_dmg" }
```

**"The main <Element> Trekker":** in a part whose text says so, modifiers tied to the main (a `main` event or target) only work when the main has that element (Meowing Cat God does nothing for an Umbra main's casts). Set `main_element: <EET>` in an override when the text only implies it (Meowing Cat God's Blazing Armor harmony).

Entry keys: `stat` (EAT id), `value`, `times`, `pct`, `target`, `hit_tags`, `event`, `duration`, `max_stacks`, `every` (activate on every Nth event), `uptime`, `note`, and for disc-only statuses `name`, `per_stack`, `stacks_from`, `add`, `reset_on` (as in kit buffs). `stat: 0, value: 0` with a `name` is a pure status (e.g. Fleeting Glimmers' Tide Weave, Soaring Blue's Bright Tide), tested elsewhere with `while:status:<name>`. `event: always` makes an entry always on. An empty part (`melody: []`) marks a scripted part as deliberately not modelled (e.g. a defensive shield). Shields (EffectType 42) have no damage; when another part tests "if the main has a shield", track the shield as a pure status with the same trigger (`{stat: 0, value: 0, name: prelude_shield, target: main, event: "timer:20", duration: Param3}`). EffectType 34 ("restore N Energy at the start of battle") is read from data as starting Energy.

## Minions

Minion hits (HitDamage DamageType 7) take the summoner's stat sheet (base stats, disc stats and emblems), Minion DMG/Crit stats, enemy debuffs and modifiers that **reach minions**. In game, buffs scoped to "Trekkers" don't reach minions; "minions" or "friendly/all units" do. Each modifier's `minions` flag is read from its text (potential, disc part): it looks at what the sentence naming the stat increases, or at the whole text if the stat is a placeholder. Set `minions: true|false` in a kit override, a buff, a disc spec entry or a disc override when the text says it differently. The team assumption `minion_buffs: all` turns the rule off.

# Enemy presets (`specs/enemies/<id>.yaml`)

A team file picks one with `enemy: {preset: <id>}` (default `generic`); the build page has a dropdown. All keys are optional; a key the preset file sets wins over the `monster` data.

```yaml
label: "Lithe Beauty (Boss Blitz)"
monster: 6310280 # data: resilience (Toughness), break time, refill, DEF, RES per element
fight_length: 180 # used when the team file has no fight_length
res: 250 # instead of monster data (generic)
defense: 500
resilience: 250000000 # 0 = no bar
break_time: 10 # seconds broken per break
break_ratio: 1.5 # damage x while broken (unverified)
lock_delay: 1.3 # GUESS: seconds from refill to the resilience lock
lock_time: 4.7 # GUESS: seconds the bar can't be lowered
ability: # the boss's ability: disc-spec entry syntax; values may be {ref: ...}
  - {
      stat: 61,
      value: { ref: "EffectValue,NoLevel,631028020,EffectTypeParam1,HdPct" },
      target: enemy,
      event: "hit:any:skill_dmg",
      duration: 15,
      max_stacks: 4,
    }
```

**Enemy DEF reductions:** a modifier with `stat: 2` (DEF) and `target: enemy` lowers the enemy's DEF: effective DEF = max(0, (DEF + flat) × (1 + %)), then defAmend = 1 − 40·DEF / (32·DEF + 24000) (`docs/reference/damage-formula/2.def.c`). Ridge's Corrosive Vines (−30 per stack, ×5) and Root Grasp (−151) are written this way; data often decodes such lines onto the owner, so set `target: enemy` in an override.

Resilience per hit = the hit's damage without the break ratio × the hitter's `Attribute.ToughnessDamageAdjust`/10000 (minions use their owner's) × (1 + Resilience Break Efficiency, EAT 43). The hit that breaks the bar isn't boosted; damage while broken or locked doesn't lower the bar, and a hit bigger than what's left breaks it once (the excess is lost). Procs can remove a fraction of the bar (`resilience`).

# Team file extras

```yaml
enemy:
  preset: lithe_beauty # specs/enemies/<id>.yaml (default generic); any key below overrides the preset
  resilience: 0 # e.g. turn the bar off
  res: 250 # RES of the weak element(s) (docs/assumptions.md)
  weak: [Umbra] # optional: other elements use res_neutral
  res_neutral: 750
hold: # optional rotation timing: a ready action waits for a condition, at most max_wait s
  - {
      member: 0,
      action: ult,
      until: "while:cast_within:2:skill:3",
      only_if: "while:cd_within:2:skill:7",
      max_wait: 15,
    }
budget: [30, 20, 20] # per-member level budgets (build page / optimize)
budget_total: 60 # optional: a shared pool; `budget` then holds per-member caps
disc_level: 80 # optional: level of every disc's base stats, filler included (default 90)
members:
  - trekker: Firstlight Noya
    level: 80 # optional: Trekker level for base stats (default 90)
    bonus_stats: # optional flat extras (EAT), e.g. the build-level ATK/HP or a fixed emblem roll
      - { stat: 1, value: 2541 } # ATK (flat)
      - { stat: 6, value: 0.07 } # Crit Rate
      - { stat: 1, value: 0.05, pct: true }
```

`hold` conditions are any `while:` condition, plus `while:cast_within:<member>:<action>:<seconds>` (that member cast that action within the last N seconds), `while:cd_within:<member>:<action>:<seconds>` (its cooldown has N s or less left) and `while:mark:<element>` (a Mark of that element is on the enemy). `only_if` is checked when the action becomes ready: if false, it's cast at once ("wait for Cosette's skill if it shows 7 s or less, else fire now"). Mistique holds her ult for Cosette's skill so the ult's hits find Gloom (Full Frame Focus).
