# Amber dodge cancel timings

2026-11-06 19:56 · 11 prompts

## 19:56

Looking at dodge cancels for Amber. Skill starts at 38,12; next is usable at 40,22 (with the skill reusable potential). Skill used at 14,09; dodge pressed at 16,04; skill usable at about 16,13. So, a very minor gain, and a free dodge inbetween consecutive skill casts. Skill used at 40,03; dodge at 41,26; skill used at 42,06. From a 2,10 duration to a 2,03 + a dodge trigger. For auto attacks, dodging before the reload animation just puts the reload after the dodge, and the reload is so fast that interrupting it with a dodge is difficult, so let's go with no gain there. Of course, using the skill at 0 will refill it to 36 without a reload.

## 20:16

Good call. I tested again with the final skill. Skill used at 17,22; ammo goes from 36 to 35 at 20,03. Skill used at 38,00; dodge pressed at 39,25; ammo goes from 36 to 35 at 40,06. Slightly faster. Another thing I noticed, the cooldown starts immediately as the dodge happens, and the dodge can cut off a large portion of the last hit. For example, skill used at 32,11; third hit hits at 34,00; dodge pressed at 34,05 (could have been 0,05 faster minimum); skill used at 34,18; dodge used at 35,27; cooldown starts at 8 at 35,27. So the total skill duration for the two rounds gets reduced from like 4,20 with no cancels to 3,11 with (just looking at the numbers as written). At the cost of the third hit, a second is shaved off the skill cooldown. In this clip, against a neutral enemy, the first two parts deal 26k each (13k x2) and the last does about 8k (1000 x8), so it may be worth it.

## 20:22

Did we have precise timings for when amber's hits land in the third volley or was it estimated?

## 20:32

Skill used at 38,12; hits at 38,18; 38,24; 39,08; 39,13; the third volley is then 40,02 x2 ("full cut dodge"); 40,03 x2; 40,04 x2; 40,05 x2; so 40,06 would be the "earliest dodge that doesn't interrupt." The followup skill is then ready to use at 40,22. It's used at 41,03. Damage hits at 41,08; 41,24; 42,12 x2; 42,13 x2; 42,14 x2; 42,15 x2. Ammo ticks down 42,28. I'm unsure why it's missing two hits.

## 20:37

On the first usage, the first hits were 11855, and the third volley hit for 850. On the recast (there are attack buffs now), the first hits were 21534 (crit?) and 13091, with the third volley being 2106 and 3825 (crit).

## 21:07

There was no mark, just amber shooting. With a mark, the first hit does 19k + 14k from incineration, then 21k, 21k, 53k, and the volley is 1686 non-crit 4074 crit. (Flora's butterflies are active, since she's the one who applied the mark). The followup (which does not trigger a mark) is 10k, 8k, then the volley is 5716 non-crit and 11927 crit.

## 21:09

It's not that the recast doesn't trigger marks, it's that there was no mark to trigger.

## 21:24

Flora skill used, then immediate amber skills. Amber hits 21098, incineration hits 36076, amber crits 56794. 23503, 23503, volley of 1686 to 4074. Recast hits 10109, crits 24427, volley hits 7454~18012. Later, amber hits 23092, incineration hits 39486, amber hits 25657, 60744 crit, 61999 crit, 1977~4777 volley with a 16811 incineration. Recast, 12801, 30932 crit + 40623 incineration, 10408~25150 volley.

## 21:30

My guess for DMG Multiplier would be that it's added to the "text on the skill," like amber's skill says 119% x2 so maybe it's (119 + 65)% x2. No actual confirmation though, that's just my guess. And would give ridiculous numbers if the base was small.

## 21:40

Dominant Firepower, PTC, Grand Finale 6, Ardent Trigger 6, Soul-Hunting Spark 6 (unused), Bursting Spark 5 (unused), Fiery Rhythm 2, Overloaded Spark 2 (unused). Skill level is 8.

## 21:43

You can commit everything. I'll rerun optimizations later to identify the best build. Other things causing spikes are probably Chixia's tiger giving attack buffs or Flora's potential that gives ATK% when the main crits.
