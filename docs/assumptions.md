# Modelling assumptions

What the model still guesses, assumes or can't model. Anything the user has since measured in game, or the game data settles, has been removed (see the git history and `docs/validation/` for those). Each entry is either a **GUESS** (a number or rule picked without evidence), **unconfirmed** (read from text or data but not checked in game), **open** (the evidence disagrees or is missing) or **not modelled**. When a measurement settles one, delete it here.

## General defaults

- **Unknown triggers default to 100% uptime at max stacks** (`unknown_trigger_uptime`), the biggest source of overvaluation. Check the Notes column of the Discs sheet and `unknown_modifiers`.
- **Scripted effects** (a potential effect not in any `Trigger` 1 row or `BuffValue`) are applied by script with a condition the data doesn't give, so they're assumed until the kit spec names the event or an uptime.
- **Derivative DMG (EAT 68)** is its own emblem line that nothing feeds; what it applies to is unknown.
- **`dmgPlus`, `finalDmgPlus`, `perkIntensity`, talent amends** are not modelled (the gist formula doesn't use them).
- **EAT 42 ("Resilience")** lines are the Trekker's own superarmor: not modelled.
- **Disc parts with GUESS uptimes** are marked in their `specs/discs/<id>.yaml`.

## Fight simulation

- **`DEFAULT_BUSY` 1.5 s** between main casts is a GUESS (the shorter of it and the action's lock).
- **Support energy** gain is the main's gain × `Character.EnergyConvRatio` (0.75): GUESS.
- **Charge Efficiency (AttrType 37):** "(Main)" applies only while the trekker is the main, "(Support)" only while a support; each multiplies the energy gained from the main's hits by `1 + value`. Claude's reading, unconfirmed.
- **Energy from potentials** (procs with `energy`) is flat and goes only to the Trekker the text names: Claude's reading, unconfirmed (Charge Efficiency isn't applied). Not modelled: Energy on kill-only or projectile-blocking lines, and Fleeting Glimmers' support-ult refund.
- **Minion ATK SPD** (Chixia's Crimson Dragon: Chant, Laru's Heart's Trumpet) isn't modelled, because those summons run on fixed hit timelines. Other ATK SPD potentials use their data values untimed: Flurry Stance (Noya), Gale Rage and Sun Chaser (Nanoha), Speed Surge (Ann), Isn't It Awesome! (Teresa). The reload scaling with ATK SPD is a GUESS.
- **Confident Mode** was timed at +39.5% ATK SPD against 35% in the text, from a 29.97 fps video of a 60 fps game, so a reading can be a frame off. The string's base timing stays at 61 frames.
- **Harmony notes** are assumed at Lv1 (conservative: the user's Noya run had 5 harmonies at Lv2). Support-disc starting notes aren't counted on top. Harmony effects stay at Lv1 either way.
- **Stack timers:** nearly every buff row has `TimeSuperposition` 2 (refresh); the 72 rows with 1 and the one with 3 may differ and aren't modelled.
- **Chance-based debuffs** (Laceration, Shock: 35% per non-Auto hit) fire on every 3rd such hit; near-permanent in practice. A chance as a count (Cosette's Determined to Leave, 25% -> every 4th hit) keeps the rate but not the randomness.
- **Crits as a count:** "on a crit" effects assume a 50% Crit Rate (every 2nd event or `chance: 0.5`) in the frame-timed kits.
- **Rotation choices** not modelled: Allie casting her ult through her skill, Wide Blade Arc's Mark DMG conversion. Tilia only holds Fortify Stance with a stance pink; Chaton taps her skill unless the build has a Bouncing Bomb pink; Sparkla holds for Rapid Fire unless the build has a Jaws pink; Willow uses Bubble Machine unless the build has a Megaphone pink.
- **Summons that aren't minions** (hits with a non-minion DamageType) count; DamageType 7 pools are skipped except Caramel's Boombox and Ann's Bubble: Firenze's Shadow Clones, Donna's Doll, Snowish Laru's toys and Mistique's Lanterna Phantoms. Potentials that lengthen sub-action states (Chaton's Evil Eye, Freesia's Berserk, Donna's Agile, Sparkla's modes, Firefly's Artillery Form, Snowish Laru's Dame Laru) aren't modelled.
- **HP conditions** hold as the text reads: the Trekker's own (Flora's Fate of Nirvana above 50%, Firstlight Noya's Meeting You at Dawn above 20%) always; "below N% boss HP" for N% of the fight. "Vs elite or higher-tier" is always on (every preset is a boss).

## Resilience breaks

- **Resilience per hit is inferred** (no per-hit table found): the hit's damage without the break ratio × `Attribute.ToughnessDamageAdjust`/10000 × (1 + Resilience Break Efficiency, EAT 43). Evidence is Noya's ~22-25 s per break and Chitose's team breaking once on 239M.
- **Break ratio ×1.5** (`break_ratio`) is unverified; ×2.5 is the other reading (`docs/validation/2026-11-03-boss-blitz-breaks.md` compares them). The breaking hit isn't boosted.
- **Lock (GUESS):** after a break ends the bar can't be lowered from `lock_delay` 1.3 s for `lock_time` 4.7 s. **Open:** the second recorded lock lasted only ~0.3 s, and no rule in the data explains either.
- **Stun-applying potentials** (Flora 512642, Tilia 510741, Shia 515528, Mistique 513508, Cosette 514228) are assumed not to stun or break the boss (bosses are stun-immune).
- **`while:broken`** with the bar off falls back to `unknown_trigger_uptime`.
- **Duloos' "main takes +10% DMG"** is defensive and not modelled.

## Boss Blitz presets

- **Fight length 180 s** for every boss (not in the tables).
- **"N times within X s"** triggers are approximated as every Nth event, without the time window. That overrates teams that can't hit that rate in a burst: Devouring Dark Ring (20 hits / 3 s), Call Down the Thunder (20 support Skill hits / 5 s, 3 Mark DMG / 5 s), Focus (2 Marks / 6 s), Aqua Ring, Pyro Blight (3 Marks / 5 s), Blood Pact (3 Mark DMG / 5 s).
- **Alternating forms** (Reality Shift 15 s, Baron Stance 30 s) start with the form the text names first (GUESS: Illusion, Warrior). Not modelled: Reality Shift's form extensions, Baron Stance clearing debuffs at a switch and pausing during breaks.
- **Fervent Combat:** the +20 Energy per Frenzy removal isn't modelled (undervalues it).
- **The Count's Majesty:** a main Mark clears all Resistance stacks instead of one, so mains that trigger Marks less than once per 5 s are treated too kindly.
- **Armor-Piercing Wedge (GUESS):** the "+60% with a support on the battlefield" scales the squad DEF PEN of 50 (to 80), rather than being 60% Ignore DEF.
- **Not modelled:** Momentum (VUL per player minion on the field) and Stormy Zeal's trigger (Wind Puffs are the boss's adds), which uses the assumed `unknown_trigger_uptime`. Boss DMG boosts and the squad's DMG Taken are defensive.

## Emblems

- **Emblem "+N" on a potential not taken in the run** is assumed to give that potential at level N (real behaviour unknown). With a target it fights at target + N, capped at 9.
- **Emblem stat lines are offered in every slot**; `CharGemAttrValue` has three TypeId groups that look like per-slot pools (the third lacks element PEN and Charge Efficiency), but which group is which slot isn't confirmed.
- **Emblem themes (`ssr.themes`): who gets forced lines.** A member gets a theme's line (Mark / Auto / Skill / Ultimate DMG) only if they deal that damage bucket in one sim with all 4 pinks and every potential at Lv1 (everything the team could do); Crit Rate + Crit DMG goes to anyone with damage. A bucket that only appears at higher potential levels would be missed.

## Discs

- **Fly, O Caged Bird's Starlit Hope (GUESS, user will test):** one stack per second a Ventus Versatile support is on the field (`on_field_1s`).
- **Overloaded Spark** without the recast can halve more than one CD per ult in the sim; the user has no such build to test, so that case is a GUESS.
- **Downwind Journey** (user's read, not confirmable in game): Nanoha's autos, shurikens and clones count as projectiles; every tagged hit is assumed to pass through a wall while one stands, which makes it an upper bound.
- **Mirror Images' Aqua Marks** (Against the Flow) are full-value Mark hits (GUESS).
- **Surging Shield** lasts its full duration; boss hits breaking it aren't modelled. Tide Weave's support-ult Energy refund isn't modelled.
- **Frozen** (3 Chill stacks) isn't modelled separately; "Chill/Frozen" conditions test Chill.
- **Prayer of Raging Flame's ATK buff** is dropped (only stacks on multiple targets); its ult Ignis Mark still applies.

## Amber's recast

- **No-Mark recast** (13091 / 2106 for big / small, rows `103303004` / `103303003`) isn't modelled: in the 3 Amber teams every first cast triggers a Mark.
- **Row `103303002`** (29.7%) isn't seen in game. The marked clips' 1.356 and 1.230 ratios sit either side of the rows' 1.335.
- **Why the recast jump is above 1.65x** is open: buffs change between the casts (the sim's per-cycle ratio varies 1.41x-2.24x against the clips' 1.98x and 2.35x), which favours the separate multiplier without proving it. The first cast's ~11% rise after its first hit (sim 8-10%) has no traced source; the user's guess is Chixia's tiger or Flora's potential that gives ATK% on a crit.
- **Cutting the recast's volley with a dodge loses damage** (-1.8% to -6.3% in the sim), so the kit dodges after the last hit; the 1,13 dodge timing combines two clips rather than coming from one.

## Key talents

All from the game text, none checked in game. T5 on all three members (nodes plus key talents) comes to +75% to +207% across the teams; no in-game measurement backs that yet.

- **Not modelled:** Ann's The Watcher in the Rye (needs her ult to destroy a hostile projectile), Snowish Laru's Queen's Party (needs the shield from her ult form). Worth nothing here: Noya's Today's Bond and Canace's Imminent Dawn (kills), Canace's Yearning for Truth (normal and elite targets).
- **Readings of unclear text** (Claude's, unconfirmed):
  - Divine Punishment (Tilia) and Withered Flower Show (Flora) say "increases ATK" without saying whose; modelled on the squad (8.4% is the size of their other squad buffs).
  - Fate of Nirvana's Skill Crit Rate goes to the main.
  - Teresa's Sturdy Edge is always on, as Demonic Devour assumes.
  - Freesia's roar is the ult's first two hits ("growls furiously"), not the AoE hit after them.
  - Canace's Lost Youth lasts 6.533 s from the cast; her Flying Leaves are main-role and that kit is a stub. Hidden Past ("for each target hit") gives one stack per ult on a single target.
  - Ridge's Bountiful Harvest counts Ult DMG hits by anyone, Ridge included, then lasts the rest of the fight.
  - Mistique's Truth As You Wish covers every phantom hit during its 12 s, which slightly overrates it.
- **"Removed after casting her Ultimate"** (Chitose's Afterrain Clarity, Shia's Beyond the Horizon, GUESS): all of that ult's hits get the stacks, and they clear right after the last one.
- **Guiding Star** (Firstlight Noya): the text value (2.5 Energy/s at Lv6) is trusted, but the user's Lv2 clip had a 43.2 s ult gap against the sim's 40.0 s with it (43-44 s without). Variation from boss movement and dodging (3 s is 27 of 235 Energy) means one clip can't separate them: open. It doesn't test Lv6 either.

## Frame data

The roles are timed from the game's animation data (read from the plain Unity bundles; the Lua stays untouched). What Lua decides stays a GUESS.

- **Bullets fly 3 units to the boss** (GUESS; Ann's ult +0.97 s fits).
- **Counts the data can't give** (fans of bullets, Lua-driven summons, "multiple times") are marked in the specs. Notable: Shia's Snow Rabbit fan (2 of 18 bullets), Willow's Bubble Machine strike 3 (1 of 7 bubbles), Shia's skill Rabbits' fire rate, Willow's support bubbles (1/s).
- **Pink-only clips** (Laru's Lance Sweep, Snowish Laru's Whipping Gale, Caramel's Melody Return): the hits follow the longer clip but the lock doesn't.
- **Minions:** which attack the Lua picks is unknown. Caramel's Boombox and Ann's Bubble are timed from user measurements (Caramel 2026-11-14); the user can check others in game.
  - Caramel: Fallen Duet is 12 hits every 0.2 s + 1 at 3.42 (the split is a GUESS). Duet and cable hits don't trigger Marks (text silent; GUESS). "Near the Boombox" is assumed always near.
  - Ann: Dazzling Vortex's laser is assumed to come right after the birth clip (text: "within 5 s") without holding up the spits. Grand Debut's extra laser fires on every squad Ventus Mark trigger with no ICD (GUESS).

## Leafia

- **Markers are picked up** as they appear in every build (GUESS). They're given at once rather than about one attack after they spawn, which shifts which swings are crystals but not how many.
- **Field Echo's waves** come every 3 turret attacks: 9 s apart without Field Assault (GUESS).
- **Draw Zone Support:** the +50% Auto DMG is always on; the +10% "in the ult's range" lasts 20 s from the cast.
- **Support Calibration Marks:** each stack deals one Calibration hit 1 s later on average. Calibration Expansion's extra stacks from a Vanguard main aren't modelled, and Vanguard Calibration's "expire after 10 s" isn't forced on Co-Draw's longer turrets.
- **Leafia's tiers reach later turrets only**, modelled as tiers gained when a turret expires (GUESS).

## Wraith

User-timed 2026-11-17 (main).

- **Melee or ranged play is set by her pinks.** Storm-Piercing Surge or Wind-Splitting Bullet means ranged play: the gun string, and the skill's slashes miss. Otherwise she's played in melee with the sword string. A mixed pair counts as ranged, so Last Gasp of Gale does nothing in it.
- **Wind-Splitting Bullet is always held for all 3 uses** (user: that's how she's played): 4 + 8 + 12 shots, then a 9 s recharge. Rounds 2 and 3 are their own casts (`hold_2`, `hold_3`), so energy caps, Overheat Shot and Scorching Gale count each round. Discs and supports that react to "main casts skill" see one cast per hold, so they undercount in ranged play.
- **Her auto shots are "Wraith's shots"** for Storm-Piercing / Wind-Splitting / Scorching Gale (GUESS: the text doesn't limit it to the skill).
- **Tracewind Blink** fires with the gun string's 1st and 4th shots (user), never with the sword string (user).
- **Last Gasp of Gale:** one Whirlwind per cast, on the first sword hit within 4 s; its first tick is as it appears (GUESS).
