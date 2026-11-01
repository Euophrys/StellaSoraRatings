# Kit spec files (`specs/trekkers/<char id>.yaml`)

One file per Trekker. It says what the game tables can't: how many times each
hit lands, timing, which hits trigger or apply Marks, and what potentials *do*
beyond adding a stat. **Every number the game data has is read from the data**;
these files only carry semantics (counts, timings, tags, triggers, uptimes).
Anything guessed is marked `# GUESS` so you can correct it with in-game timings.

A file has a `main:` section (used when the Trekker is the main) and a
`support:` section (used when they're a support). Supports never auto attack.

## Actions

```yaml
main:
  actions:
    auto:                 # the full auto-attack string, looped while the main isn't locked
      duration: 3.0       # seconds for one full string            # GUESS
      hits:
        - {hit: 162100001, count: 2, tags: [greatsword]}
    skill:
      lock: 5.0           # main can't auto for this long after casting (default 3.0)
      hits:
        - {hit: 162310001, count: 5, interval: 0.15, tags: [longsword], triggers_mark: true}
    ult:
      lock: 4.0           # default 5.0
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
| `when` | procs only: fires only while a condition holds, e.g. `"while:status:butterfly"` |

A hit with `hit: 0` is a **marker**: it deals no damage and only emits
`marker:<who>:<tag>` for each tag at its time. Use it for things that happen on a
schedule without dealing damage (a summon becoming ready, a stack every 2 s):

```yaml
        - {hit: 0, offset: 3.967, tags: [tiger_up]}                       # Tiger is ready
        - {hit: 0, count: 3, offset: 2.8, interval: 2.0, tags: [tiger_tick]}   # a stack every 2 s
```

Cooldown and ult energy cost come from `Skill.json`. Energy gained per hit is
`HitDamage.EnergyCharge`, capped per cast by `Skill.GetEnergyLimit`.

A support kit can leave out `ult` (the support never casts it).

## On the battlefield (supports)

```yaml
support:
  on_field: {skill: 4.0, ult: 4.0}   # seconds a support stays on the battlefield after casting
```

Supports appear to cast and then leave. Effects that only work while a support
is on the battlefield use `event: "while:on_field:<who>"` (`support`, `self`,
`any`, or a member index); they're active only during those windows. Default 4 s.

## Marks

```yaml
  mark: {hit: 162000001}   # damage dealt when the main triggers a Mark
```

A Mark is up after a support hit with `applies_mark` lands. A hit with
`triggers_mark` consumes it and deals the mark hit, at most once per
`mark_icd` seconds (team file, default 1.0). Emits event `mark:<member>`.
Supports can trigger Marks too when their kit has a `mark:` (Shia's skill and ult
"trigger Lux Mark and summon a Thunderbolt"): they then compete with the main for them.

## Buffs granted by base skills

```yaml
  buffs:
    - effect: 16290003        # Effect id, leveled by the skill level named in `level`
      level: ult
      event: cast:self:ult
      duration: {ref: "Buff,LevelUp,16290003,Time,10K"}
      target: self            # self | main | team | enemy
```

A buff without `effect` or `attribute` is a **pure status**: no stat, only stacks
other rules can count (e.g. minions out: `{name: dragon, event: "marker:self:dragon_up", duration: 7.067, max_stacks: 4}`).
`while:status:a+b` counts several statuses together, and `while:status:a>=N` is only
active (and only counts) at N stacks or more; both also work in proc `when`.

Buffs also take `name` (makes a status other rules can test with `while:status:<name>`), `max_stacks`,
`add` (stacks added per event, e.g. 3 butterflies per cast), and `requires` / `excludes` (potential ids).

## Talents (dupes)

Each dupe unlocks the next talent group (`TalentGroup`, chained by `PreGroup`). A team
member's `talents: N` (default 0) unlocks the first N groups. Their stat nodes (Talent
Type 2) are read from data; the key talent (Type 1) is scripted and needs an entry:

```yaml
  talents:
    1620116:   # Buried Past
      buff_events: {starender: "hit:self:any&once"}   # adds an event alternative to the named base buff
      buffs:
        - {attribute: 16296111, level: ult, event: "while:status:starender"}
```

`buffs` take the same keys as base-skill buffs. An unlocked key talent without an entry is
listed as not modelled.

`&once` on an event alternative lets it fire only the first time it matches in the fight
("Triggers once every 5 minutes" with a 2-minute fight); other alternatives fire normally.

## Potentials

Pure always-on stat potentials need no entry; they're read from data. An entry
can have any of:

```yaml
  potentials:
    516205:   # Prism Warp
      add_hits:
        skill: [{hit: 162310006, count: 9, offset: 0.8, tags: [glow_return]}]
      overrides:
        - {stat: 71, hit_tags: [longsword, glow]}   # its Skill Crit Rate only on these hits
      note: "Glow returns modelled on skill Glows only."
```

| key | meaning |
| --- | --- |
| `add_hits` | `{action: [HitSpec...]}` extra hits on that action |
| `replace_hits` | `{action: [HitSpec...]}` replaces the action's hits (e.g. ult form swap) |
| `add_actions` | new actions; `followup: {after: skill, every: 2}` casts it after every 2nd cast of `after`, once that cast's lock ends. `delay: <seconds>` waits that much longer (e.g. the input gap before a recast); the main doesn't auto meanwhile unless `autos: true`. `followup: {event: "hit:self:glow", every: {param: Param1}}` casts it after every Nth matching event instead (once the main's lock ends) |
| `overrides` | patch the data-derived modifiers. Match with `index` (order from data) or `stat`. Set `hit_tags`, `target`, `event`, `duration`, `max_stacks`, `uptime`, `icd`, `stacks`, `as_stat`, `minions` (true/false: does it reach the owner's minions? default read from the text, see below), `copies` (a list of settings: the modifier is split into one copy per entry, each with its own events/tags, e.g. per-minion stacks), `reset_on` (list of events that clear the stacks, e.g. a reload), or `drop: true` |
| `mark_tags` | hits with these tags can now trigger Marks |
| `reset_cd` | `{ult: skill}`: casting the ult makes the skill ready |
| `cd_reduce` | `{action: skill, seconds: <value>, times: <value>}`: each cast refunds `seconds × times` of its own cooldown |
| `procs` | `[{event: "hit:main:skill_dmg", hit: <id>, icd: <value>, every: <value>, tags: [...]}]` extra hits fired by events; `every: N` fires on every Nth matching event. Proc hits take all `HitSpec` fields (`count`, `offset`, `triggers_mark`, `requires`, ...) and emit their own tag events |
| `note` | shown in the sheet's Notes column |

**Values** that the data has are written as `{ref: "<Param string>"}` (resolved
at the potential's level) or `{param: Param3}` (the potential's own Param).
Plain numbers are only for timings, counts and uptimes.

### Events

Several events can be joined with `|` (`"cast:self:skill|cast:self:recast"`). `hit:<who>:any` matches every hit.
Add `&recent:<tag>:<seconds>` to an event to count it only if the member that emitted it also landed a `<tag>` hit (or `<bucket>_dmg`) within that many seconds, e.g. `hit:any:minion&recent:skill_dmg:12.25` (a minion hit whose summoner dealt Skill DMG recently). Works in kit and disc specs.
`cast:<who>:<action>`, `hit:<who>:<tag>` (each tag of each landed hit, plus the
damage bucket: `auto_dmg`, `skill_dmg`, `ult_dmg`, `mark_dmg`, ...), `mark:<who>`.
`<who>` is `self`, `main`, `any`, or a member index. Targets are `self`, `main`, `team`, `enemy`, or `class:N` (members of `Character.Class` N: 1 Vanguard, 2 Versatile, 3 Support). A modifier with
`event: unknown` (data couldn't say when it applies) uses a constant
`uptime × max_stacks` and is listed as assumed in the sheet.

# Disc spec files (`specs/discs/<disc id>.yaml`)

Many discs' melody/harmony are scripted: the row has no `EffectId`, only text and
`ParamN` strings (`"15%"`, `"8"`). A disc spec says what those Params do; values are
always read from the row (melody at the disc's C-level, harmony at Level 1).
Scripted parts without a spec are listed in the Discs sheet's Notes as not modelled.

```yaml
melody:            # also harmony1 / harmony2
  - {stat: 3, pct: true, value: Param1, target: team}
  - {stat: 6, value: Param4, target: main, event: "mark:main", duration: Param5}
  - {stat: 57, value: Param3, times: 3, target: main}               # times: a number or a Param
  - {stat: 21, value: Param2, target: team, event: "hit:main:skill_dmg", every: Param1, duration: Param3}
overrides:         # pin down data-derived parts the data can't explain
  - {part: melody, stat: 39, event: "hit:main:ult_dmg"}
```

Entry keys: `stat` (EAT id), `value`, `times`, `pct`, `target`, `hit_tags`, `event`,
`duration`, `max_stacks`, `every` (activate on every Nth event), `uptime`, `note`.

## Minions

Minion hits (HitDamage DamageType 7) take the summoner's stat sheet (base stats, disc stats and emblems), Minion DMG/Crit
stats, enemy debuffs and modifiers that **reach minions**. In game, buffs scoped to "Trekkers" don't reach minions;
"minions" or "friendly/all units" do. Each modifier's `minions` flag is read from its text (potential, disc part):
it looks at what the sentence naming the stat increases, or at the whole text if the stat is a placeholder. Set
`minions: true|false` in a kit override, a buff, a disc spec entry or a disc override when the text says it
differently. The team assumption `minion_buffs: all` turns the rule off.
