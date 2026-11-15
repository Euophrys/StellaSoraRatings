# Stella Sora Ratings

This simulates in-game fights to calculate what the best potentials, discs, emblems, and teams are. It was built based off the following:

- [Hiro420's datamined game data](https://github.com/Hiro420/StellaSoraData)
- [AutumnVN's damage formula gist](https://gist.github.com/AutumnVN/91afd7a37a9743488419b70f07225950)
- The game's animation files, which are unencrypted
- Recordings of the game stepped through frame by frame for verification

There are the following things to consider when looking at the results.

- Dodges are coded to happen roughly once every 10 seconds.
- The boss never moves. DPS uptime is constant, and things like Leafia's turrets never get out of range.
- I don't own every character so most of the limiteds are taken from the game data and haven't been verified. Minion behaviour in particular is a mystery.
- Fights are assumed to be against a single boss. Enemies never die and AOE potentials are weak.
- The rotation is simple. They use their ultimates when they have enough energy and use their skills whenever the cooldown ends. There is capability to have skills held for certain things but it's complicated to verify that it's correct to do so.
- Some things are hard for the optimizer to find. It can't find Gerie's mark build on its own. Without Mark DMG emblems, it doesn't pick Nazuna's Touch of Nature potential, and without Touch of Nature, it doesn't pick Mark DMG emblems.
- Some trekkers are given special behaviour. For example, Chitose assumes you dodge cancel every auto attack when you have Tremble and Fall selected.
- See docs/assumptions.md for the full list.

What I do for manual verification is:

- Record with OBS, go into a fight, use each skill and ult without overlap while dashing around so there's no auto attacks
- Open that recording and step through frame by frame, writing down each time a damage number appears or what the thing on screen seems to be doing. This looks something like, for Leafia, `Skill. Used: 3,17. Damage: 4,14. Turret ready at 6,01. Turret shoots 6,08; 7,09; 8,10... Turret pulses at 8,01; 11,04; 14,07... Turret expires around 34,28.` where the first number is the seconds and the second number is the frames in that second.
- Paste that into Claude Code, and then Claude works it in.

## Platforms

It runs on Linux, macOS and Windows. On Linux and macOS, each batch of fights is split across all your CPU cores. That relies on process forking, which Windows doesn't have, so there it runs one fight at a time and jobs take several times longer. If you're on Windows and want full speed, run it in [WSL](https://learn.microsoft.com/windows/wsl/install) and follow the Linux steps.

## First-time setup

You need [Python 3.13 or newer](https://www.python.org/downloads/) and [git](https://git-scm.com/downloads). Run these from the repo root.

**1. Download the game data.** This clones only the English tables from Hiro420's repo into `data_src/`, which nothing works without:

```bash
git clone --filter=blob:none --sparse https://github.com/Hiro420/StellaSoraData.git data_src/StellaSoraData
git -C data_src/StellaSoraData sparse-checkout set EN
```

After a game patch, update it with `git -C data_src/StellaSoraData pull`.

**2. Create a virtual environment and install.**

Linux and macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

If `python3` is older than 3.13, call the newer one by name, e.g. `python3.13 -m venv .venv`.

Windows (PowerShell):

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

If PowerShell refuses to run the activate script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once. In Command Prompt, activate with `.venv\Scripts\activate.bat` instead.

## Start the server

From the repo root, activate the environment (`source .venv/bin/activate` on Linux and macOS, `.venv\Scripts\Activate.ps1` on Windows), then:

```bash
python -m ssr.web
```

This serves the build guide at <http://127.0.0.1:8765/> and opens it in your browser. Press `Ctrl+C` to stop it.

Options:

- `--port 9000`: use a different port
- `--no-open`: don't open the browser

Restart the server after changing anything in `specs/` or `src/`, or after pulling new game data, because it keeps what it loaded when it started. Saving a team from the build page overwrites its file in `teams/`, so keep a copy of any team file you've edited by hand.

## Other tools

The same simulator runs from the command line. With the environment active:

```bash
python -m ssr teams/<team>.yaml -o out/                             # full rating workbook: out/<team>.xlsx
python -m ssr teams/<team>.yaml --pinks <main> <support1> <support2> # best pink potential pairs
python -m ssr.compare teams/a.yaml teams/b.yaml --split 30,15,15    # compare team totals
python -m ssr.finder <trekker> --template teams/<t>.yaml --role main  # best teams for one Trekker
```

`SSR_WORKERS=<n>` limits how many CPU cores a run uses (in PowerShell: `$env:SSR_WORKERS=4`).

## License

The code and specs in this repo are under the [PolyForm Noncommercial License 1.0.0](LICENSE.md): use, change and share them freely for any noncommercial purpose, but not commercially. The game data, the damage formula gist and the game itself aren't part of this repo and aren't covered by it; they belong to their owners.

This is a fan project. It isn't affiliated with or endorsed by Yostar Games, which owns Stella Sora.
