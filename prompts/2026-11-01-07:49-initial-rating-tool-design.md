# Initial rating tool design

2026-11-01 07:49 · 8 prompts

## 07:49

I saw a post on twitter showing the ratings for various skills and discs for a particular team in the gacha game Stella Sora. That's in example.jpeg. I'd like to be able to calculate a similar thing for other teams. The game data is in `~/.local/share/Steam/steamapps/common/Stella Sora`, and it's a unity game. There may also be files in the proton/wine directory, `~/.local/share/Steam/steamapps/compatdata/4813850/pfx/drive_c`. If the character data can be mined from the game files, skill levels and what they give and such, that would be ideal, if not, we can discuss a format and I can collect things manually.

## 07:58

The emblems are handled outside of a run, and the discs are set at the start of it. Within the run, you are frequently posed choices between 3 potentials, and that's where the potential ratings come in. Some assumptions will likely need to be made about the enemy monsters. For example, in Maygi's chart, it has Lux PEN on emblems at 8.65%, but the second line of it at 0.05%. A maxed lux pen on an emblem is something like 40, so the resistance of monsters might be around 45 or something. As for the damage of the different things, skills can be assumed to be used as soon as they come off cooldown, but the gap between skill usage and the next auto attack can vary based on animations, maybe 3 seconds as a baseline. Ultimates too, maybe more of a 5 second gap. I could be timed ingame to tune the numbers. And some characters have things that reset their skill cooldown, like Amber's potentials that let her use her skill twice in a row, or refreshes it after she uses an ultimate. Marks are generally triggered by the main character using a skill, but again there's some variation. Using Amber again, her skill has 3 separate hits, and each could trigger a mark if marks were constantly being applied at the time.

## 08:08

For C1/C6 on discs, the C is the number of duplicates of that disc you have. Each duplicate raises the stats and effect. It's never a choice between C1 and C6, but a weaker disc you have more dupes of can outperform a stronger disc you only have one copy of. Most fights in the game are around two minutes long. As a general rule, when starting the fight, the support skills get used first, as they often buff or apply marks, and then the main character skill gets used a second after. Then everything gets used when it's available. A pre-made sheet is likely the  best option. The game lets you set build reminders, so when the choice comes up, it will tell you which are recommended and what level to raise them to, and that's the most convenient way. The "level to raise them to" can just be the ratings, with 6 being S and 1 being C or something. By the way, in the run you can level the potentials to 6, the data if it goes to 9 is for the emblems which can roll +3 on a potential.

## 08:14

Yeah I suppose the ideal output is just a spreadsheet with each potential in rows, levels 1 to 9 as columns, and each cell being the % increase off a sensible baseline. Oh, another note, there are 4 pink-coloured potentials for each character, and you can only choose two of those. You can always get the two you want and they don't level in the run. So, the "skill / auto" build thing is generally just which two you're taking as the baseline. For Amber, these are "Dominant Firepower," "Bullet Storm," "Precise Temperature Control," and "Echo of Hospitality." So you can use those to figure out how the data labels them.

## 08:21

Yeah, let's try the FL Noya skill build and see how it compares. The pinks chosen for Noya are Lucent Blitz and Dawnflare. Firefly gets Radiance Blade: Twin Shadow and Radiance Blade: Firefly. Tilia gets Prefect Spiral and Renewed Spectrum. Supports typically don't auto attack, so just skill + ult damage, and whatever buffs they give to the main trekker. It might need to be an iterative process, picking the pinks, then calculating the discs, calculating the first two emblems (as they don't touch potentials), adding those in, calculating the potentials, then calculating the last emblem's +3 for each potential.  We'll see if the results approximate the rankings from Maygi.

## 08:30

For discs, there are 3 main discs, which have everything. The three support discs ONLY give their base stats, e.g. flat attack and flat hp, as well as some starting notes for the harmony skills. Their melody and harmony skills do not occur. Emblems are character specific and can't be moved between characters. I'm not at the highest level of ascension yet, but my current records have about 60 total potential levels, with 30 levels on the main trekker and 15 on each support. That will go up at the highest level, but for now, that's a good target. Referencing a finished run makes sense, maybe a three step process taking the highest one/two potentials from steps one and two and setting their level to 6 for the next step. One for the supports, two for the main? As for the target level, it's probably something that can be interpreted from the data after the fact.

## 08:41

To be specific on the emblems, Emblem 1 can only roll stats, Emblem 2 is character skills + stats, and Emblem 3 is potentials + stats. The game's damage formula is here: https://gist.github.com/AutumnVN/91afd7a37a9743488419b70f07225950, the raw md at https://gist.githubusercontent.com/AutumnVN/91afd7a37a9743488419b70f07225950/raw/7724e91b7cf694d5d64220b895d217127e017eb4/1.Stella_Sora_DEF_RES_PEN_VUL_and_your_damage.md. The ult energy costs here are 235 for FL Noya, 190 for Tilia, and 300 for Firefly (you can maybe check the data for those numbers to see if it's present). For the "baseline stat stick disc", look at a max level Eternal Brilliance's base hp and base atk values, and use that for the baseline.

## 08:45

The filler disc is probably C6 in Miyagi's data I'd assume, as these sorts of fillers are event "welfare" discs that are easy to max out. It is interesting that the second lux pen roll is only 0.05% if the enemy res is so high, but perhaps it's being compared to something, or there's lux pen in the build, or the curve is strange, who knows. Anyway, go ahead with a build plan.
