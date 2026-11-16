# Mistique chixia cosette team

2026-11-02 09:14 · 11 prompts

## 09:14

Team exploration, Mistique - Chixia - Cosette. Here are the timings, with X,Y meaning Seconds,Frame at 30 FPS. 

```text
MISTIQUE
Pinks used for test: Defiance Before Deletion, Extended Exposure

Auto attacks
Starts 35,12
Hits on 35,16; 35,29; 36,19; 37,01; 38,09
Next cycle first hits at 38,21

Skill
Used at 2,27 with no enemies around; cooldown starts immediately
Minion appears 3,18; 6,18; 9,18; 12,18
15,27 circles flash on all four minions (assuming Extended Exposure trigger)
30,22 death animation starts
31,18 all four explode
So, it seems Extended Exposure refreshes their duration to 15s
Used at 43,13; damage hits at 43,18

Ultimate
Used at 49,10
Hits at 50,13; 50,25; 50,29; 51,02; 51,05; 51,07; 51,10; 52,05; 54,10
Control regained at 50,22; first auto attack hits at 50,26

COSETTE
Pinks used for test: Eclipse Imprint, Phantom Mark

Skill
Used at 26,12
Hits at 27,11; 27,21; 28,01; 28,11; 28,25; 29,06; 29,16; 29,26; 30,10; 30,21; 31,01; 31,11; 31,25
Leaves the field at 33,23

Ultimate
Used at 38,28
Explosion at 40,05
Leaves at 43,04
```


## 09:47

1. Pumpka appears at 44,03. Swipe hits at 45,16. Headbutt hits at 46,05. The boss then moves. It walks to the boss, and starts a swipe at 47,13. It hits 47,18. Headbutt hits 48,10. Swipe hits 49,02. Headbutt htis 49,21. So they alternate. There's no Night Dash present in this build. 2. The last hit was the big one. The ult summons a ghost thing and the final hit is it exploding. 3. Yes, with Extended Exposure they last indefinitely if not killed. 4. First pumpka on screen at 3,00; second at 6,01. At 14,19 the death animation for pumpka 1 starts, because pumpka 5 is being summoned and appears at 15,03. This triggers the explosions etc. Pumpka 2 death animation starts at 21,01 and the rest die one by one. 5. At 49,12 Dark Burn is triggered, the mark dealing 1709. At 49,14 there's a 30 from it, another 30 at 50,00; Dark Burn is triggered again at 50,13 so things get complicated to track at that point. 6. A claw mark appears at 27,21. It vanishes entirely at about 28,16. Each attack from her skill leaves a claw mark, so roughly 1 second after the last hit and the claw marks are gone. 7. Nobody runs this build, but the timings are all the same. 8. Yes.

## 09:55

Another quick note: If Cosette's ult is used while her skill is going, it cancels the skill. I imagine the optimal play would be to wait until the skill ends to ult but might depend on how many ults you get in the 120s...

## 09:56

Another mechanics note that I'm not sure if it's covered. When a minion triggers a mark, the mark is triggerred using the summoner's stats. This is relevant since the pumpkas can trigger marks.

## 10:29

1. Mistique auto hits at 7,19; one pumpka starts spinning and hits at 7,27. That pumpka then headbutts, which lands at 8,22. None of Mistique's autos trigger a spin again until she hits at 10,26 which causes all four pumpka to spin, hitting at 11,05. Her hit at 14,03 causes three of the four pumpkas to spin, but the fourth dies so maybe it was just at the end of its life. I think there's an ICD that starts on cooldown when a pumpka spawns, but other than that, every pumpka does spin. It seems every final strike of Mistique's auto swing triggers them all, so the ICD is roughly the length of Mistique's auto string. 2&3. They all explode. Skill used at 3,25 and all 4 new pumpkas are immediately visible; skill hits 4,01 for 5595; explosions seem to hit at 4,08 but there's only one damage number of 11285; auto attack hits 4,25; pumpka swipe hits 5,07. 4. The first build I see with Mistique as main uses Defiance + Burst Shooting.

## 11:07

Looking in the spreadsheet, for Ink Sigil: Raid, the dragons are stationary turrets, while the tiger actively moves. So it probably has a low uptime on dragons and a constant uptime on tiger. Against a boss with neutral resistance, over 3 minutes with my Burst Shooting test build, the damage was 36.9% Mistique, 51.4% Chixia, 11.6% Cosette. Though it's probably worth noting that they would usually be fighting a boss that's Umbra weak and neutral to Fire. Also, trekkers can only trigger marks of their own element, so Mistique can't trigger the marks that Chixia applies.

## 11:12

In the reference damage formula doc, it implies a resist value of 250 = weak, 570 = raid, 750 = neutral, 2000 = resisted. Considering the numbers in Maygi's image for Lux PEN, I'd assume it should be the 250 number rather than the 570 number, and then 750 for off element trekkers.

## 12:11

Odd thing. For Mistique's emblems, Charge Efficieny (Main) on Emblem 1 is listed as -16.4% for green, -24.6% for blue, -21.9% gold, -13.2% for purple. But on Emblem 2, it's +8.7% green, +16.8% blue, +11.1% gold, +25.5% purple. Also, can we have a simultaneous total budget and individual caps? E.g. budget of 60, caps at 30/20/20, so the supports can cannibalize a bit.

## 12:28

The question I'd have is the pumpkas. They can trigger marks, and there's four of them smacking the boss, sometimes at staggered timings if they have to walk around. So they might consume the mark anyway. Oh, but there's the potential that makes them all explode when you use the ult, so that would allow the mark to always be saved for the ult.

## 12:33

I think a maximum wait makes sense. Try the finished build with a binary search for the optimal max wait time, then give mistique three emblem lines of charge efficiency and level 6 Quick Nightfall and do another binary search. Then we'd have the number for no efficiency and max efficiency and can pick based on that.

## 12:34

The player can only see the skill cooldowns in whole numbers, so giving someone a guidance like "wait if there's 3s left on cosette's skill" would be the end state.
