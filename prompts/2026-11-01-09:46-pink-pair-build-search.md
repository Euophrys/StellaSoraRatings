# Pink pair build search

2026-11-01 09:46 · 2 prompts

## 09:46

We just did the initial implementation, comparing the results of FL Noya's skill build with the numbers for Maygi, and it was roughly in the right ballpark. The next step would be uncovering the builds to begin with, as the pinks were set for that experiment. There are 4 pinks per character, and you get two, so 4 choose 2 = 6 builds. There needs to be a step to evaluate which of those builds are good, with the expectation that it surfaces FL Noya's skill build (Lucent Blitz + Dawnflare) and auto attack build (Stardust Descent + Sinbreaker), presumably with the other 4 options being markedly worse than those two. Which I suppose just means running the tests on all six options.

## 09:48

I guess matters are complicated further by the supports each having their own 4 choose 2. Might be a long runtime to identify them unless the user pins certain ones as known.
