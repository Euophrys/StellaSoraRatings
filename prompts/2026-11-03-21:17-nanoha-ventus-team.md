# Nanoha ventus team

2026-11-03 21:17 · 13 prompts

## 21:17

Just did the Noya Ventus team, let's add in the standard banner Ventus Vanguard, Nanoha. Here are her timings: 

```text
NANOHA
Pinks: Whirling Blade / Bloom Dance
Wind Whispers level 3 is present, increasing clone duration by 3 seconds
No Gale Rage, Sun Chaser, or Blossom Shower (unclear if intentional or just missed due to RNG)

Autos:
Hits on 2,28; 2,29; 3,12; 3,13; 4,00 x2, 4,02.
Next chain first hits on 5,06

Skill:
Used at 9,29; cooldown starts immediately
First shuriken visible at 10,04; hits at 10,12 with travel time
Second appears at 10,21
First starts returning at 10,23; reaches Nanoha and disappears at 11,06
Throws the final one at 13,15
First autoattack hits at 13,29; cooldown reads 6

I couldn't really get a good answer for what distance counts for the Distant Prayer potential, let's just give it a 50% uptime.

Ultimate:
Used at 49,02
One clone appears at 49,04 and the other at 49,05
Nanoha's first autoattack hits at 49,22
Despite appearing 1 frame apart, the clones are in sync
Projectiles leave the clones' hands at 51,01
The closer one hits at 51,04 and triggers Blossom
Clone attack cycle: 51,01; 51,12; 52,01; same 2-2-3 projectiles as Nanoha herself
They leave at 1:18,20
```


## 21:27

Quick note that while the Nanoha clones feel like minions, they don't benefit from minion dmg and just use her stats.

## 21:45

1. The shuriken thrown at 10,04 hits at 10,12 (contact); 10,17; 10,21; 10,26; and then it MIGHT hit at 11,02 (not sure if it's the second shuriken doing it). Now that I've looked a lot closer at the footage, she throws the two shurikens, and then goes back to autoattacking. Each shuriken gets thrown 8 times, for a total of 16. 10,04 shuriken, 10,21 shuriken, 11,02 auto attack. She continuously autoattacks as they bounce back and forth. 2. Their next attack after the numbers given is 53,10. The other two I'll have to make another build with those potentials to check.

## 21:49

I think the final throw at 13,15 was me seeing her autoattack with no noise around and considering the skill done. They do last until 2s remaining on the skill, or if she runs away from them, can even stay out until the skill's cooldown finishes.It looks like they do hit on the way back, though it's a bit hard to tell if it's actually hitting or just doing the 0.15s tick. Well, I guess the ticks are its hits anyway.

## 21:52

The travel distance of the shurikens is about 4x the size of the boss, so not all those hits are landing. They fly through and past, then return.

## 22:02

At the 10,04 throw, she's standing at close to max distance. The shuriken goes through the boss and at its max distance the inner edge is still touching the boss. So that was probably the perfect case. Though there's some further complications with how, if the boss is moving towards Nanoha and she's moving away from it, the shuriken will keep moving towards her and have more uptime... Well, an approximation is fine. At a 37,03 throw, the boss is about in the middle of the range, tick at 37,08; 37,13; [out of range at the other side for the 37,18 tick]; 37,23; 37,28; then it's back to Nanoha at 38,03. So it hit 4 out of its 6 possible ticks.

## 22:21

Growth Tempest is hits. Blossom Flurry is 3 shurikens per strike; it replaces her auto attacks with the three shurikens. Together, each Blossom Flurry auto attack triggers a Growth Tempest, and Blossom Flurry can be maintained indefinitely since its duration is the same as the skill cooldown. Non-Whirling Blades seems to be one hit out, one hit back. Blossom Shower, skill used at 37,13; clone shurikens appear at 37,20; hit at 38,03.

## 22:28

In video 1, her first hit on the boss was at 2,28. Her ult was ready at 1:19,12. In the second video, her first hit was at 5,21. Her ult was ready at 1:20,19. So roughly the same. Ok, going frame by frame, I can see that she does indeed keep auto attacking on top of the shurikens rather than being replaced. This also makes Growth Tempest trigger twice per auto attack sometimes.

## 22:34

For ease of typing and calculation I leave out the minute when jotting these timings down, but I can see how it would be confusing in this case. The "49,02" cast was ready at 1:19,12 but I waited for the boss to be in a good position for clear recording, and was cast at 1:49,02. I went into a boss intending to never attack to see what the passive generation might be, but there is no passive generation, all energy comes from hits.

## 22:40

There is a literal dodge mechanic. She dodges at 13,06 and recovers at 13,17 or so, so 10 frames "lost" per dodge used. I counted 10 dodges used before the ult is charged, so a bit over 3 seconds, plus some downtime with the boss moving and having to chase it, so 60s against a stationary passive target might be correct.

## 22:52

Run an optimize pass with 60 total, 30/20/20 limits

## 2026-11-04 07:44

Since Canace is such a low share, let's try it with Nazuna or Tilia instead (keeping Ann). Those two are seen as good in any team. Swap Canace out for them and run two more optimizations and then compare the totals between the three teams.

## 2026-11-04 08:00

Yeah Nazuna should be using Bold Assertion and Feel the Beat.
