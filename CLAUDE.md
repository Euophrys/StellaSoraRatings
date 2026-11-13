# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Computes team ratings for the game Stella Sora: how much each potential, disc and emblem line adds to a team's total damage, written to `.xlsx`. A local web page (the build guide) sits on the same simulator.

## Git

The user doesn't care deeply about git. Commit whenever it makes sense, and feel free to commit any uncommitted work you find. Stay on `main`: no feature branches or worktrees.

## Setup

Requires Python 3.13+. pytest isn't declared in `pyproject.toml`, so install it separately. There's no linter or formatter configured.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e . pytest
```

Game data is required by the code and most tests, and is gitignored. It's a sparse clone of the mined tables at `data_src/StellaSoraData` (only `EN`). Pull it after a game patch; don't try to decrypt the game archives locally.

```bash
git clone --filter=blob:none --sparse https://github.com/Hiro420/StellaSoraData.git data_src/StellaSoraData
git -C data_src/StellaSoraData sparse-checkout set EN
```

## Commands

Assuming the venv is active:

```bash
pytest                                  # full suite, about 3 min
pytest tests/test_sim.py -k <name>      # one test

python -m ssr teams/<team>.yaml -o out/ # full rating to out/<team>.xlsx (~10 s)
python -m ssr teams/<team>.yaml --pinks <main> <support1> <support2>  # pink pair search (~20 s)
python -m ssr.compare teams/a.yaml teams/b.yaml --split 30,15,15      # compare totals (~15 s per team)
python -m ssr.compare ... --split 30,15,15 --emblems purple           # + greedy emblems on top (~30 s per team)
python -m ssr.inspect trekker|hits|disc|scripted-discs|word ...       # dump game data for writing specs
python -m ssr.web [--port 9000] [--no-open]                           # build guide at http://127.0.0.1:8765/
```

Those times are on 16 CPU threads: every batch of simulations is spread over worker processes (`parallel.py`). `SSR_WORKERS=<n>` sets how many, and `SSR_WORKERS=1` keeps everything in one process (what the tests do, and what to use with a debugger or profiler). One simulation is 25-70 ms depending on the team.

Restart a running command or the web server if specs or code change: specs are read lazily and the workers are forked once, so a running job would mix old and new.

## Architecture

Three layers of input feed one simulator, and everything else is a loop over `simulate`.

**Inputs**

- **Game tables** (`data_src/`, via `data.py` `GameData`, `game.py`): all numbers. `refs.py` resolves Param reference strings such as `Effect,LevelUp,...`, and `effects.py` decodes potentials, discs and buffs into `Modifier`s.
- **Specs** (`specs/`, schema in `specs/README.md`): only what the tables can't say, such as hit counts, timings, tags, triggers and uptimes. `specs/trekkers/<char id>.yaml` is loaded by `kit.py`. `specs/discs/<disc id>.yaml` pins scripted disc parts. `specs/enemies/<id>.yaml` is loaded by `enemies.py`.
- **Team files** (`teams/*.yaml`, loaded by `team.py`): members, discs, pinks, enemy and fight assumptions. A `Build` is the immutable set of choices being evaluated on top of a team.

**Simulation:** `sim.py` `simulate(gd, team, build, ...)` runs the fight timeline, using an event system (`cast:`, `hit:`, `mark:`, `while:` and so on) to drive buffs, procs and marks, and `formula.py` for damage per hit. `resilience.py` handles the enemy's break bar. It returns a `SimResult` with totals, per-slot damage, cast counts, uptimes and `unknown_modifiers` (assumed uptimes).

**Consumers**

- `parallel.py`: `simulate_many(gd, team, calls)` runs a batch of `simulate` calls on forked worker processes and returns the results in call order. Every consumer below goes through it, so write new loops as one batch of calls rather than a `simulate` per iteration.
- `rate.py`: the pipeline of discs, emblems, reference build and potentials, each rated as the % gain between simulations. `report.py` writes the workbook, and `__main__.py` is the CLI.
- `builds.py` (pink search) and `compare.py` (cross-team totals under level budgets).
- `guide.py` is the analysis behind `web/`: a stdlib HTTP server, background jobs with progress and cancel, and a static frontend with no build step. `sharecode.py` handles the game's preset share codes.

## Modelling rules

- **Numbers come from the game data.** In specs, use `{ref: ...}` or `{param: ParamN}`; plain numbers are only for timings, counts and uptimes. Mark anything guessed with `# GUESS`.
- **The user's in-game measurements beat skill text and guesses.** They can frame-time actions, so ask for timings rather than guessing (`docs/team-exploration-guide.md` lists what to ask). Surface anything you can't model for them to decide; don't silently pick.
- **Unknown triggers default to 100% uptime at max stacks**, the biggest source of overvaluation. Check the Notes column of the Discs sheet and `unknown_modifiers`.
- **Add engine features generally**, not per team. Document them in `specs/README.md`, log modelling choices in `docs/assumptions.md`, and add tests.
- **Regression check:** after any change to `src/` or a disc spec, re-run `teams/fl_noya_skill.yaml` and compare with `docs/validation/2026-11-01-fl-noya-skill.md` (the calibrated team). Report any moves.

## Docs

- `docs/team-exploration-guide.md`: read and follow this when rating a new team. It has the workflow, data table lookup, pitfalls and sanity-sim snippets.
- `specs/README.md`: the full spec schema and event syntax.
- `docs/assumptions.md`: every modelling choice not read directly from data.
- `docs/validation/`: one write-up per team session, with results and open questions.
- `docs/2026-11-01-team-ratings-design.md`: the original design. `docs/reference/damage-formula/`: the source of the damage formula.
