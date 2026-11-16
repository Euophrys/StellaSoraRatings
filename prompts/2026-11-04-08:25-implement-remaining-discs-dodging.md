# Implement remaining discs dodging

2026-11-04 08:25 · 7 prompts

## 08:25

I think there's a team for every element now. Go through all the discs and implement the unimplemented ones if possible. For things related to dodging, you can assume one dodge per ten seconds. Ask if there's anything else with unclear uptime or functionality.

## 21:53

Yeah, potentials related to dodging can use 1 per 10 seconds too. Each dodge costs 10 frames of attacking uptime, but perhaps some like Mistique who have auto attacks that don't do much damage could just dodge every 3 seconds (the cooldown on dodge) and get benefits from it...

## 22:19

Hmm, with Chitose it also switches her auto attack to be the big final hit after dodging, right? Might make sense to her. In the Nazuna team, I think most of the damage comes from Gerie anyway, so treating Gerie like Nazuna's "minion" and dodging all the time like Mistique does might also make sense. You can't dodge when you have no control in skill animations or ults, but you're also immune in those times so you don't have to, and the 1 per 10s was from a real fight with that accounted for.

## 22:35

For Nanoha it's like, unintuitive why it would be good to dodge on cooldown with her. The others have reasons. For Chitose with Tremble, dodge pressed at 3,18; hits the boss at 4,13. Pressed dodge again at 4,19; hits at 5,14. The following hit can be skipped. Dodge at 14,00; hits 14,25; smaller hit 14,28. Dodge at 14,29; Hit at 15,24; dodge at 15,26; no smaller followup hit. I imagine you shouldn't do that but it won't come up with dodging every 3s anyway.

## 22:50

I wondered if maybe Nanoha could get "free" dodges. One cycle is from 17,19 to 20,01 or so. Another starts at 11,22; throws the final projectile at 13,02; dodge was a bit late and started 13,08; first projectile of the second chain happens 13,26. So the first took... 2,12? And with a dodge, it took... 2,04 even with the dodge being late. So dodging at the end of the auto attack chain seems strictly optimal even without the potential. Also, looks like I misremembered the dodge cooldown, it's only one second.

## 23:06

For Chitose, with the second hit of the big attack landing at 3,16 her first auto of the next chain lands at 4,09. 7,00 -> 7,23. vs 16,28; dodge at 16,29; first big hit at 17,24. Also, the mirror image still follows up if you dodge cancel and have that potential. By the way, for Nanoha, are you allowing the atk% buff from dodging to stack? It doesn't mention a cap, though I don't know if that implies no cap or a cap of 1.

## 23:15

Is energy based on damage done or hits done? I imagine the dodge loop wins out on damage even if it misses out on an ult or two since it's a sizeable increase and Chitose's ult never seemed that key anyway, but still curious
