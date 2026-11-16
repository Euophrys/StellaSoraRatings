# Three minute team comparison

2026-11-02 17:29 · 11 prompts

## 17:29

Can you run a 3 minute long simulation for each of the current teams and then put the results in a table comparing their damage numbers?

## 18:11

Running the 3 minute boss battle mode ingame, though with lower levels and worse discs than these have, my FL Noya T0, Shia, Tilia team did 1,620,206,678 damage, with Noya being 99% of it. This included 4 or 5 resilience breaks which are not currently modelled in this simulation. Chitose / Freesia / Teresa did 238,667,612 damage, with Chitose at 91.6% and Freesia at 6.4%. Only one resilience break. So yeah, Noya is very far ahead of others.

## 2026-11-03 08:25

The resilience break counts make me think we should be simulating that. Certain attacks deal different amounts of damage to resilience, some having a 150% multiplier on resilience damage, and when the resilience is broken the enemy takes, from what I can gather, 150% increased damage (2.5x?). For example, if Chitose's dragons deal more resilience damage, and lead to two or three breaks instead of just one, that build might be stronger. Cosette also has a potential that gives her a 30% chance to reduce resilience by 0.4+% on skill hits. Most of the information is in the damage formula reference, except I don't know the absolute value of resilience on enemies.

## 2026-11-03 08:43

Let's see... Recording a fight real quick, the first hit lands at 2,14. The boss's health bar is not on screen at that point. The first break happens at 27,17. The break ends at 37,17 and the resilience bar refills to full. Some damage is done to it, then a lock icon appears at 38,26. (An animation plays from 42,23 to 46,29 where time is essentially stopped.) The lock disappears at about 47,22 and damage can be done again. (Another animation from 50,24 to 55,08) The boss is broken at 1:12,24. It recovers at 1:22,24. Strangely, the resilience bar fills to half and locks, and the lock ends at 1:23,02. (Animation from 1:38,20 to 1:43,09) The boss breaks again at 1:49,23, recovers at 1:59,23 and refills to full. No lock is seen, and it soon vanishes for an add phase, so I stop recording there. This is probably one of those cases where all the information is hidden away in a discord rather than discussed online... maybe Japanese sites have some details...

## 2026-11-03 08:47

The animations do pause the three minute timer. Additionally, DPS uptime was relatively constant throughout this. The animations noted were Tilia's ult, Noya's ult, and Shia's ult, in order. The bar seemed to be depleting much slower when it refilled to half, so perhaps it was a visual glitch of some sort. The locks didn't seem tied to any mechanic, but maybe there's some failsafe to prevent you from stunlocking it permanently.

## 2026-11-03 08:49

Yes, search the data. This mode is titled "Boss Blitz" in English, and the boss name was "Lithe Beauty."

## 2026-11-03 08:54

There are two bosses a week, and you need to use two unique teams. Chitose's team fights "Count of the Duloos". I suppose the ideal would be a dropdown to select the enemy, with "Generic" as an option, and the effects could be modelled. I wasn't sure if 150% meant x1.5 or +150% (x2.5). While you were there, did you see anything about the boss's def and resist values?

## 2026-11-03 08:59

The technique score has a cap so it can generally just be assumed to be filled by a competent player, no need to model it. So, Cosette's 0.4% resilience damage 30% of the time, would be 1m resilience damage per trigger, or about 4m per skill use... and a break leads to a 10 second window of 1.5x damage...

## 2026-11-03 09:04

There's no dark-weak boss this week, so Mistique is on the bench for this mode. But the calibration should be fine with the data we have.

## 2026-11-03 09:29

It's probably not really overvaluing Chitose and is instead closer to undervaluing Noya. My units and discs are from levels 70 to 80 rather than maxed, and builds are done via an RNG method so they can't be perfect every time. I wouldn't worry about it too much. Generic should have the 250m bar. As for my run's build... Noya level 80, skills 7/11/1/7, 93 lux pen and 7% crit rate from emblem. Shia level 70, skills 1/1/1/1, emblem not relevant. Tilia level 70, skills 1/1/5/5, emblem not relevant. Discs, Summer Sanctuary C6 level 80, Eternal Brilliance C6 level 80, My Guiding Star C1 level 80. Noya potentials, Lucent Blitz / Dawnflare / Prism Warp 6 / Legion's End 6 / Resolve: Blitz 4 / Searing Sun 3 / Veteran's Gift 2 / Guiding Star 2. Shia, Bunny Torrent / Rabbit Flip / Moonfall 2 / Howl to the Moon 3 / Silent Tide 2 / Wave to Oblivion 1. Tilia, Renewed Spectrum / Perfect Spiral / Enemy Counter 6 / Banner of Glory 4 / Blinding Beam 4 / Knight's Seal 2. All harmony skills level 2, except Infinite Sunshine is level 1. We don't currently model notes. The build itself is level 30, which gives ATK+2541 and HP+23720. In the three minute run, Noya did 1.6B damage, Shia did 12M, and Tilia did 3.7M. Of course there are a lot of variations in the fight itself, with movement, what attacks land, etc.

## 2026-11-03 09:31

Sounds good, go ahead.
