# Build guide webpage design

2026-11-01 15:49 · 13 prompts

## 15:49

We need some human-usable way of generating readable build guides. Probably a webpage managed by python or something. Selecting the three characters (main + 2 supports), then either select the pinks or calculate them first, then once the pinks are entered, ranking each characters' potentials and levels (so they can tell if getting 0->1 for one potential is better the 3->4 for another etc). Maybe an optimize button that takes the spread like 30-15-15 and finds the absolute best choices.

## 15:55

Things I'd be thinking of are, "Which emblem rolls are most impactful?" before going into the run. Oh, the user should be able to set their discs and C values. Then, before a run, setting a preset to label what potentials to target. See preset.png for the ingame layout; you set target skill levels for things that show up as reminders in the run. Usually I'm just thinking "hmm, that seems good" or looking at what people have posted online, but those people are also largely going "hmm, that seems good." Data-driven builds are rare.

## 15:56

Yeah, I'm aware the optimize is slow. Go ahead with the visual

## 16:00

Ranking the lines that could roll. Maybe the layout should be like the preset grid, but instead of "next: +0.3%" it has a 2x3 grid of percents showing levels 1~6, with the current level having a focus border. Some potentials give +1% stat from 3->4 then 2% stat from 4->5 (like 1.5% per level, but rounded unfairly) so seeing them all could be useful.

## 16:09

I suppose a recalculate button, and the already selected levels would be flipped to negatives, showing what you lose from lowering it to that level...?

## 16:12

I think the total change looks the most convenient.

## 16:13

I think it's also intuitive to click on a level to set the skill to that level rather than only the +/- buttons. Sharing could be just screenshots, or rendered to static html, I suppose

## 16:15

Sounds good to me.

## 16:18

Each roll on an emblem gives you four random lines, so there's never empty slots, though there might be stats people don't care to add (like minion dmg on amber). The rest sound good. I don't think I'd use the CLI personally and it's mostly a tool for you when doing the explorations.

## 16:19

I think the chart of what % damage each line gives is sufficient. Going beyond that gets into weird probability math.

## 16:26

I don't know what happens if you have +potential on a potential you didn't pick. Let's assume you get it at that level. It doesn't cost budget. Emblems only roll the element that the trekker is for damage and pen and such. The rest I think are available to all. I don't see any difference in rolls between vanguards and supports or anything.

## 16:29

The emblem lines go green/blue/yellow/purple ingame. +1 skill level is yellow, +2 is purple, +3 is also purple. Not everything has a purple. Skills are like "Main Skill Level Up +2 levels". Potentials are named and only emblems on the character can roll that potential; emblems are rolled per-character and can't be transferred. Go ahead with the implementation plan.

## 16:35

Do you have any information on AttrType 37? Translated name, values? I haven't really been using git but you can commit if you want. Here's an example share code, an Amber Flora Chixia team in that order: AAAAZwAAAH4AAACNobDDAY6gNhhhiKGGw2wA
