# Team finder design

2026-11-13 18:08 · 7 prompts

## 18:08

Use-case: A user wants to find the best team for a given character. Perhaps with a specific role (most likely main). Something that generates all the possible teams of characters in that element, with that character included, does an optimization pass on all of them, and shows the damage comparisons. Discs provided, that apply to all teams.

## 18:16

In the game, you start a run with 3 characters, and the build is set from that completed run. If you want to change the build you need to do another run. Like uma or czn or such. I think usually only two or so pink combinations even make sense. Like Nazuna has a pair for terra dmg and a pair for not-terra dmg.

## 18:17

How about we only let the optimizer pick in batches of 6 (fully levelling a potential), with 30 (5 potentials) on mains and 18 (3 potentials) on supports, and then use that for the rough calibration and take the top teams from there.

## 18:21

I think most teams won't have quick reference builds

## 18:22

Go ahead with the implementation plan

## 18:27

Output the data on the page in a nice table showing the damage numbers and members. See the table reference webp I put in the folder for an example. Those damage numbers look high, so I presume they're 180s fights against a specific boss, probably with strong discs, so they don't need to be similar to those numbers.

## 18:28

It's fine without images
