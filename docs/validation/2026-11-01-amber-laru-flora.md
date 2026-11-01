# Amber + Snowish Laru + Flora (2026-11-01)

Run: `python -m ssr teams/amber_laru_flora.yaml -o out/` → `out/amber_laru_flora.xlsx` (~110 s). No Maygi chart to compare against. This is a first model, built from the data plus the user's timings:

- Amber skill (frame-timed): shots at +0.20 s, +0.83 s, +1.57 s; cast ends at +2.23 s. Without potentials: 1 big, 1 big, ~8 small hits (the text says x4 small). With Grand Finale: 2, 2, 10. With Precise Temperature Control the recast follows, and the 8 s skill CD starts only after the recast ends (~12.5 s cycle). Ult: 1 s.
- Amber autos (frame-timed): 12 shots in 2.03 s (0.185 s apart), then a 0.77 s reload: 2.8 s per magazine.
- Snowish Laru: on the field 14 s per skill (CD keeps ticking). Her ult isn't used in the reference video, so the kit leaves it out.
- Flora: 4 s on the field per skill or ult.

Enemy RES 145 / DEF 0 (same calibration as FL Noya). Skill levels 10.

## Build used

| Member       | Pinks (from the pink search)                      |
| ------------ | ------------------------------------------------- |
| Amber        | Precise Temperature Control + Echo of Hospitality |
| Snowish Laru | Fire Downpour + Special Ammo                      |
| Flora        | Ember of Tomorrow + Ember Rekindled               |

Main discs: Snowy Night Surprise, Mystic Brushstrokes, The Cat's Treasure (this team's own top 3 at C1).

Damage share: Laru 53% (shells 44%, Walnuts 9%), Amber 32% (skill incl. recast and Echo 16%, autos 7%, Incineration 5%, ult 4%), Flora 15%. Amber auto-attacks ~8 s of every ~12.5 s.

## Pink pairs (% of best, own discs)

`python -m ssr teams/amber_laru_flora.yaml --pinks Amber "Snowish Laru" Flora` (~280 s). The user confirmed these winners are the builds commonly used.

Amber, re-run after the skill/auto timing and CD changes: PTC + Echo 100%, Bullet Storm + PTC 96.1%, DF + PTC 94.3%, DF + Bullet Storm 93.8%, DF + Echo 93.4%, Bullet Storm + Echo 91.3%. The table below is the earlier run (Laru and Flora unaffected).

| Amber |  | Snowish Laru |  | Flora |  |
| --- | --- | --- | --- | --- | --- |
| PTC + Echo of Hospitality | 100.0% | Fire Downpour + Special Ammo | 100.0% | Ember of Tomorrow + Ember Rekindled | 100.0% |
| Dominant Firepower + PTC | 99.0% | Fire Downpour + Investiture | 94.4% | Ember of Tomorrow + Ashes of the Past | 90.2% |
| Bullet Storm + PTC | 95.5% | Fire Downpour + Promotion Time | 91.6% | Ember of Tomorrow + Spark of Ashes | 89.7% |
| Dominant Firepower + Bullet Storm | 82.8% | Promotion Time + Investiture | 86.8% | Ember Rekindled + Ashes | 86.2% |
| Dominant Firepower + Echo | 82.1% | Special Ammo + Investiture | 75.5% | Ember Rekindled + Spark | 85.3% |
| Bullet Storm + Echo | 79.8% | Special Ammo + Promotion Time | 75.5% | Ashes + Spark | 82.4% |

Precise Temperature Control (PTC) is in all top three Amber pairs; PTC + Echo vs PTC + Dominant Firepower is within 1 point, which is inside the noise of the auto-attack guesses.

## Discs (main C1 / C6)

| Disc | Main C1 | Main C6 | Support C1 | Notes |
| --- | --- | --- | --- | --- |
| Snowy Night Surprise | 56.3% | 104.8% | 11.1% | Hymn from Laru's Walnut hits (new spec) |
| Mystic Brushstrokes | 32.5% | 58.5% | 10.7% | triggers pinned (new spec) |
| The Cat's Treasure | 27.9% | 43.6% | 11.1% | new spec |
| Meowing Cat God | 25.9% | 41.7% | 10.7% | triggers pinned (new spec) |
| One Shot, One Down | 24.7% | 46.7% | 7.5% | 0 Destiny Cards; ATK ramp averaged |
| Fireworks | 23.1% | 33.8% | 11.1% | new spec |
| Voyage Blueprint | 18.8% | 35.1% | -1.3% | shield -> Ignis DMG 12 s, once per 20 s (user) |

## Potentials (Lv6 gain over the reference build)

Reference: Keen Accent, Grand Finale, Weakness Mark, Bursting Spark (Amber); Two-Gun Salute, Uplifting Shot (Laru); Guest Performer, Lethal Inferno (Flora).

Top: Two-Gun Salute 101%, Uplifting Shot 57%, Fairy Tale Rule 37%, Heart's Trumpet 31%, Guest Performer 22%, Lethal Inferno 10%, Grand Finale 10%, Celebration Resumed 8%, Keen Accent 7%, Soul-Hunting Spark 5%.

Laru's normals dominate because her shells are ~44% of the team's damage and her Skill DMG bucket is otherwise nearly empty. Two-Gun Salute is +117% Skill DMG at Lv6 (data: 29% at Lv1, 170% at Lv9) plus 2 shells.

## Model changes made for this team

Engine (general):

- **HitDamage DamageType 7 = Minion DMG** (EAT 66, crit 74/81), not Derivative DMG. Only summoners use it. Derivative DMG (EAT 68) is a separate stat that nothing feeds yet.
- **Negative "DMG Taken" goes on the owner** (defensive). It used to decode as an enemy debuff, which lowered team damage for 10 discs.
- **Disc effects are element-locked:** a disc's effects only reach Trekkers of its element. Neutral discs (EET 7) are unchanged. Before this, Fireworks rated +12.8% for FL Noya.
- Action `starts_cd` (Amber's recast starts the skill CD); disc specs take `icd`, and `event: always` in disc overrides.
- `a|b` event alternatives, `hit:<who>:any`, `reset_on` (stacks cleared by an event), `when` on procs (status-gated), buff `add` / `requires` / `excludes`, hit `requires_all`, data refs in override `icd` / `max_stacks`.

Kits: `specs/trekkers/103.yaml` (Amber), `158.yaml` (Snowish Laru), `126.yaml` (Flora). Discs: new specs for Fireworks, One Shot One Down, The Cat's Treasure, Fist of Courage, A Gift for the Journey, Joyful Gathering, Snowy Night Surprise, Mystic Brushstrokes, Meowing Cat God; trigger fixes for Sparkling Moment and A Moment in the Afternoon.

## Effect on the FL Noya calibration

Discs, main C1, before → after (Maygi in brackets):

- A Moment in the Afternoon 26.6% → 35.5% (21.9%). The −10% bug had been cancelling an over-assumed Shock debuff. Its kill-based harmony is now dropped.
- Sparkling Moment 22.0% → 24.4% (18.6%). Ult stacks now build per ult cast instead of starting at max.

Other Noya discs and potentials are unchanged within ~1 point.

## Update (Amber + Flora + Chixia session, same day)

Re-rated after these changes:

- the minion buff rule: buffs scoped to "Trekkers" don't reach minions;
- Heart's Edict flagged as a minion buff;
- PTC's recast starts 0.15 s after the skill's lock, with one auto shot in between;
- Laru retimed from a YouTube video: shells at +0.7 s then every 2 s, on the field 15.3 s, Walnuts living ~13.5 s and outlasting her next cast.

Results:

- Damage share: Laru 53%, Amber 32%, Flora 15%.
- Discs: Snowy Night Surprise 52.5%, Mystic Brushstrokes 30.5%, The Cat's Treasure 26.6% (same top 3).
- Potentials: Two-Gun Salute 83% (was 102% before the retime; with the 4-Walnut cap its extra Walnuts mostly replace older ones), Uplifting Shot 46%, Fairy Tale Rule 37%.

The video's build (Two-Gun Salute, Fairy Tale Rule, Uplifting Shot at Lv6) matches the model's top picks. See `2026-11-01-amber-flora-chixia.md` for the cross-team comparison.
