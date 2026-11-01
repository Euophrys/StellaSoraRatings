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
| `triggers_mark` | this hit can trigger a Mark already on the enemy (main only) |
| `applies_mark` | this hit puts a Mark on the enemy (supports) |
| `requires` | only lands if any of these potential ids is in the build |
| `excludes` | doesn't land if any of these potential ids is in the build |

Cooldown and ult energy cost come from `Skill.json`. Energy gained per hit is
`HitDamage.EnergyCharge`, capped per cast by `Skill.GetEnergyLimit`.

## Marks

```yaml
  mark: {hit: 162000001}   # damage dealt when the main triggers a Mark
```

A Mark is up after a support hit with `applies_mark` lands. A main hit with
`triggers_mark` consumes it and deals the mark hit, at most once per
`mark_icd` seconds (team file, default 1.0). Emits event `mark:<member>`.

## Buffs granted by base skills

```yaml
  buffs:
    - effect: 16290003        # Effect id, leveled by the skill level named in `level`
      level: ult
      event: cast:self:ult
      duration: {ref: "Buff,LevelUp,16290003,Time,10K"}
      target: self            # self | main | team | enemy
```

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
| `add_actions` | new actions; `followup: {after: skill, every: 2}` casts it after every 2nd cast of `after`, once that cast's lock ends |
| `overrides` | patch the data-derived modifiers. Match with `index` (order from data) or `stat`. Set `hit_tags`, `target`, `event`, `duration`, `max_stacks`, `uptime`, `stacks`, `as_stat`, or `drop: true` |
| `mark_tags` | hits with these tags can now trigger Marks |
| `reset_cd` | `{ult: skill}`: casting the ult makes the skill ready |
| `cd_reduce` | `{action: skill, seconds: <value>, times: <value>}`: each cast refunds `seconds × times` of its own cooldown |
| `procs` | `[{event: "hit:main:skill_dmg", hit: <id>, icd: <value>, tags: [...]}]` extra hits fired by events |
| `note` | shown in the sheet's Notes column |

**Values** that the data has are written as `{ref: "<Param string>"}` (resolved
at the potential's level) or `{param: Param3}` (the potential's own Param).
Plain numbers are only for timings, counts and uptimes.

### Events

`cast:<who>:<action>`, `hit:<who>:<tag>` (each tag of each landed hit, plus the
damage bucket: `auto_dmg`, `skill_dmg`, `ult_dmg`, `mark_dmg`, ...), `mark:<who>`.
`<who>` is `self`, `main`, `any`, or a member index. A modifier with
`event: unknown` (data couldn't say when it applies) uses a constant
`uptime × max_stacks` and is listed as assumed in the sheet.
