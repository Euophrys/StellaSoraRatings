# Chitose + Freesia + Teresa (2026-11-01)

All-Aqua team: Chitose main (Vanguard), Freesia (Versatile) and Teresa (Support). Team file `teams/chitose_freesia_teresa.yaml`, kits `specs/trekkers/144.yaml`, `125.yaml`, `127.yaml`.

## Setup

- Pinks (user): Chitose Cascade of Ruin + Against the Flow; Freesia Chill Forecast + Frost Warning; Teresa Surge: Infinite + Surge: Ripple. The pink search ranks the user's pairs first for Chitose (Serpent's Glide + Against the Flow next, 73%) and Teresa. All six of Freesia's pairs are within 3%: Localized Snowfall + Frost Warning 100%, the user's 99.0%. On a single boss Chill Forecast is only +10% Frost Bloom DMG, like Realm of Frost, and Localized Snowfall's value rests on a guess (one flower per skill cast in Berserk).
- Main discs: Sword Against Stream, Sunlit Blossom, Fleeting Glimmers (top 3 of the team's own disc rating; the best-trio search agrees).
- Enemy: RES 145, DEF 500 (same calibration as FL Noya).

## User timings and mechanics (30 fps)

- **Chitose auto:** 12 hits in a 5.03 s string (string start 3,01; first hit 3,13; next string's first hit 8,14).
- **Torrent Flash:** 2 stored uses (`Skill.SectionAmount`), cast at least 0.5 s apart (`UseInterval`; user saw 0.4–0.6 s gaps). One recharge timer refills uses one at a time and keeps its progress (at 2.5 uses, a cast leaves 1.5). Autos resume 0.37 s after a cast (44,24 → next auto hit 45,17).
- **Scale** replaces a Torrent Flash and spends a use: every 3rd cast, every 2nd with Cascade of Ruin. With Returning Tide, every cast after the first is a Scale against a boss (43,24 no serpent, the next three had one; a miss breaks the chain). The user's build has Flowing Circle (3 uses).
- **Chitose ult:** small hits every ~0.25 s from +0.8 s, big hit at +4.63 s, control back at +5.63 s.
- **Freesia skill:** field hit at +0.77 s, flowers burst at +2.17 s (8 hits with Chill Forecast), leaves at +3.37 s.
- **Freesia ult:** last ult hit at ~+1.3 s. Berserk autos start at +3.43 s; one string is ~2.7 s from first hit to recovery; she attacks continuously until leaving at +17 s.
- **Teresa skill:** plant hits at +0.97 s, domain ticks from +2.0 s every 1 s. The shield appears at the plant (+0.8 s) and lasts 8 s with Surge: Infinite (not broken; the user wasn't hit). On the field 10.5 s.
- **Teresa ult:** hits at +2.47 s, on the field 5.53 s.
- Bosses can't be Frozen.
- **Serpent's Glide** (user-tested): a Coiling Serpent with every auto strike, lasting 10+ s (longer than the skill CD), and Serpent potentials trigger on them.
- **Chill Forecast** (user-compared): no visible difference on a single boss; the extra flowers (3-line cone) only add reach. 8 bursts either way.

## Engine changes

- **Stored uses:** `SectionAmount` / `UseInterval` from data; the `charges` / `use_interval` action keys; the potential `add_charges` key (Flowing Circle).
- **Cooldown scaling:** the potential `cd_scale` key (Against the Flow −50%).
- **Hit multiplier:** `mult` on hits (Mirror Images at 50% / 60%).
- **Cast cycle:** `cycle: [n, i]`, `from_cast`, `upto_cast` on hits (Scale casts, Returning Tide).
- **Gated events:** `&while:<condition>` on event alternatives (e.g. a skill cast while in Berserk).
- **New events:** `mark_applied:<who>` and `on_field_5s:<who>`.
- **New who-tokens:** `support` and `class<N>`; `support` also works as a target.
- **Disc spec keys:** `name`, `per_stack`, `stacks_from`, `add`, `reset_on` and `event: always`; `stat: 0` pure statuses; empty parts (`melody: []`).

None of these change the existing teams. No specced Trekker there has stored uses, and the new keys and events default to no-ops. Tests: `tests/test_chitose_team.py` (14).

## Disc specs written

Sunlit Blossom, Sword Against Stream, The Clash of Blade and Axe, Fleeting Glimmers (Tide Weave wasn't in the EffectIds, and the Notes column didn't flag it), Summer Afternoon Rain (Teresa's shield counts, user), Soaring Blue and Delivered by the Breeze (stacks from Versatile Skill DMG: Freesia), Bedtime Story, United by Fate (0 Destiny Cards), Soda Shopping, Steam Syndrome, Dappled Sunlight, All That Was Beautiful, Rainy Tune and Traces of Starlight. A scan of the other Aqua and neutral discs found no more parts the decoder misses.

## Results

Team: 36.7M with the top-3 discs. Shares: Chitose skill 49%, auto 6%, ult 4%, Mark 2%; Freesia skill 21%, Berserk autos 9%; Teresa 8.5%.

| Disc                       | Main C1 / C6   | Support C1 / C6 |
| -------------------------- | -------------- | --------------- |
| Sword Against Stream       | 63.6% / 104.2% | 11.2% / 15.7%   |
| Sunlit Blossom             | 49.5% / 81.5%  | 12.8% / 17.4%   |
| Fleeting Glimmers          | 46.7% / 92.9%  | 2.1% / 6.2%     |
| Bedtime Story              | 37.9% / 70.2%  | 11.2% / 15.7%   |
| The Clash of Blade and Axe | 33.4% / 49.4%  | 10.8% / 15.3%   |

Top potentials (Lv6): Returning Tide 57.6%, Winter's Grip 49.6%, Flowing Circle 48.5%, Shortcut Seeker 21.4%, Azure Embrace 17.4%, Adamant Scales 17.1%, Crackling Zero 15.1%, Wave Breaker 14.7%.

Top emblem lines (Chitose, personal): Skill +3 17.2%, Skill DMG 10.6%, ATK% 9.7%, Crit Rate 9.0%, Aqua PEN 8.6%.

## Noya regression

`teams/fl_noya_skill.yaml` now gives My Guiding Star 76.6% / 125.8% (doc: 76.6% / 124.3%) and Ripples of Nostalgia 43.1% / 60.2% (doc: 40.5% / 57.4%). None of this session's changes reach that team: a clean copy of the last commit (392be81) gives exactly the same numbers (checked 2026-11-02). The drift comes from commits made after the Noya doc (written at 9d358e2/abdbe9b, 09:43 on 2026-11-01), so that doc's numbers are stale.

## Open questions (GUESS in the specs)

- Frost Warning's cooldown: 1 s assumed (none in the text).
- Mirror Image hit timing (+0.1 s after Chitose), and whether its Mark triggers deal the full Mark hit.
- Freesia's Berserk string period: 3.0 s (2.7 s observed + wind-up).
- Sword Against Stream harmony 1's "every 20 hits, once per 15 s" uses the every-Nth counter plus a cooldown.
