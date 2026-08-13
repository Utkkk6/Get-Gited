<div align="center">

# Get Gited

**One workspace. All your Git repos.**

`SIMPLE. SAFE. SYNCED.`

[English](README.md) · [Русский](README.ru.md)

[![CI](https://github.com/Utkkk6/Get-Gited/actions/workflows/ci.yml/badge.svg)](https://github.com/Utkkk6/Get-Gited/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Windows-first](https://img.shields.io/badge/windows-first-0078D6?logo=windows&logoColor=white)](#install)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](#license)

Dozens of folders. Some on GitHub. Some only on disk. Some ahead, behind, dirty, or not a Git repo at all.

I wrote Get Gited as the **workspace table** for that mess — then a preview, then a safe write. It is not a `git push` wrapper that fires blindly.

```text
scan → understand → preview → choose → execute → verify
```

never

```text
scan → YOLO git push
```

</div>

| It is | It is not |
| --- | --- |
| One view of every local project + GitHub match | A full Git client |
| Preview-first push / ff-only pull / private publish / clone | Dropbox-style file sync |
| A keyboard `[*]` picker (`gg`) and a Textual TUI | An Issues / PR manager |
| `BLOCKED` with a reason when a write would be unsafe | Auto-commit, force push, merge, or rebase |

```text
GET GITED                                          SIMPLE. SAFE. SYNCED.
One workspace. All your Git repos.
────────────────────────────────────────────────────────────────────────
mtime  ·  minimal  ·  guess off

  #  Sel  Project     GitHub            Status              Date        About
  1  [*]  ScreenNote  you/ScreenNote    REMOTE_AHEAD        2026-08-12  Capture the screen.
  2  [ ]  CLINQ       you/CLINQ         LOCAL_AHEAD         2026-08-11  Clinic queue app.
  3  [ ]  OldParser   you/OldParser     REMOTE_ONLY         —           —
  4  [ ]  NewTool     —                 LOCAL_ONLY          2026-08-10  Scratch CLI.

number  toggle   s1–s4  sort   u1–u5  ui   [Enter]  continue
q  back   e  exit   gg acpt --help  About consent
```

(No screenshot files in this repo yet. That is the real picker layout.)

## Install

Windows is the primary target. Paths like `C:\Users\...` and `D:\Code` are first-class.

| Need | Check |
| --- | --- |
| **Python 3.12+** | `py -0p` — **3.11 will not install this package** |
| **Git** | `git --version` (must be on `PATH`) |
| **[GitHub CLI](https://cli.github.com/) `gh`** | `gh --version`, then `gh auth login` |

From a clone, in **PowerShell**:

```powershell
cd "C:\Users\You\Desktop\Get Gited"
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .
gg --help
get-gited doctor
```

The prompt must show `(.venv)`. Until it does, Windows will not see `gg` / `get-gited`.

Without activating:

```powershell
.\.venv\Scripts\gg.exe --help
.\.venv\Scripts\get-gited.exe doctor
```

If `Activate.ps1` is blocked:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## PATH gotcha (editor terminal, venv, `gh`)

This is the #1 “it installed but `gg` is not recognized” case.

- An IDE’s integrated terminal often keeps the `PATH` it had when **that** session started. Installing into `.venv` does not magically update an old tab.
- `python` in that tab may still be the **system** interpreter, not `.venv`. Then `pip install -e .` lands somewhere else, and `gg` is missing.
- `gh` / Git installed via winget often need a **full editor restart** (or a new PowerShell window) before `PATH` updates.

Fix, in this order:

1. Close the terminal tab. Open a new one. Run `.\.venv\Scripts\Activate.ps1`. Confirm `(.venv)`.
2. `Get-Command python, gg, git, gh | Format-Table Name, Source`
3. `python -c "import sys; print(sys.executable)"` must point inside `.venv`.
4. Still stuck? Call the exe: `.\.venv\Scripts\gg.exe doctor`
5. After installing Git or `gh`, quit the editor completely and reopen, or open a fresh PowerShell outside it.

`gg` is a console-script alias of `get-gited` (`pyproject.toml` → `[project.scripts]`). No extra PATH hacking if the venv is actually active.

## First five minutes

```powershell
gg --help
gg doctor
gg status "C:\Users\You\Desktop"
gg "C:\Users\You\Desktop"          # picker: numbers, preview, confirm
get-gited sync "C:\Users\You\Desktop" --dry-run
get-gited                          # Textual TUI
```

Quote paths with spaces. Do not paste placeholders like `<your folders>` — PowerShell treats `<` as redirection.

`--help` and `-h` both work. `get-gited` with no subcommand opens the TUI.

## Short command (`gg`)

```powershell
gg                          # offer current folder, then sort + [*]
gg D:\Projects              # scan that path, then sort + [*]
gg -y                       # scan cwd, open the picker with every row
gg --yes --sort mtime
gg status D:\Projects
gg doctor
gg acpt --help
gg ui                       # list 5 looks
gg ui 2                     # select by number
gg ui cards                 # select by name
```

**`gg -y` is not execute-all.** It only skips “use this folder?” and opens the picker. Writes still need a selection and `[Enter]` on the preview.

`get-gited sync --yes` **is** execute-all: it runs the full planned queue with no picker. Different flag, different command.

## Keyboard

| Input | What happens |
| --- | --- |
| `1`, `2`, … | Toggle that row `[*]` / `[ ]` |
| `[Enter]` on the table | Preview planned ops for the selection |
| `[Enter]` on the preview | **Execute** |
| `q` | Back one screen (picker → sort → picker). Does **not** quit |
| `e` | Exit. Preview also accepts `e` |
| `s1`–`s4` | Sort while the table is open (`mtime`, `sync`, `presence`, `size`) |
| `u1`–`u5` | Live UI theme (`frame`, `minimal`, `hud`, `cards`, `poster`) |
| `i` | Toggle About-column file guesses (off by default) |

Five looks: **frame** (classic boxes), **minimal** (default, wide table), **hud** (double-line), **cards** (two lines per project), **poster** (stacked title). Leftover terminal width goes to **About** so the header is not clipped to `Ab...`.

About is a README excerpt, or `—`. Other project files are not read unless you grant consent:

```powershell
gg acpt --on     # allow pyproject.toml / package.json / Cargo.toml descriptions
gg acpt --off    # back to README or —
gg acpt --help
```

## Commands

| Command | What it does |
| --- | --- |
| `get-gited` | Workspace TUI |
| `get-gited doctor` | Python / Git / `gh` / auth / config — **does not scan projects** |
| `get-gited scan D:\Projects` | Discover local projects |
| `get-gited status D:\Projects` | Local + GitHub table |
| `get-gited status D:\Projects --sort mtime` | Same table, sorted |
| `get-gited sync D:\Projects` | TTY: sort + `[*]` picker, preview, confirm |
| `get-gited sync D:\Projects --dry-run` | Preview — **no writes** |
| `get-gited sync D:\Projects --yes` | Execute the **full** planned queue (no picker) |
| `gg` / `gg PATH` / `gg -y` | Short command — see above |
| `gg ui` / `gg ui 2` | Terminal look (5 themes) |
| `gg acpt` | About-column consent |

Pass one or more roots. If you skip them, Get Gited uses `[[roots]]` from config.

`git fetch` is **not** part of dry-run. Freshness is an explicit refresh.

## How to read the status table

| Status | Meaning |
| --- | --- |
| `SYNCED` | Local branch matches upstream |
| `SYNCED (UNCOMMITTED)` | In sync, but the working tree has uncommitted changes |
| `LOCAL_AHEAD` | Unpushed commits |
| `REMOTE_AHEAD` | Safe to fast-forward pull (if the tree is clean) |
| `DIVERGED` | Local and remote both moved — **blocked**, no auto merge/rebase |
| `NO_REMOTE` | Git repo, no remotes configured |
| `LOCAL_ONLY` | Local project, no exact GitHub match |
| `REMOTE_ONLY` | On GitHub, not cloned here |
| `NO_GIT` | Looks like a project, not a Git repository |
| `BLOCKED` | A write would be unsafe (secrets, clone collision, detached HEAD, …) |
| `ERROR` | Inspect failed for that row |
| `DUP` | Possible duplicate (same remote, name, or root commit) |

`UNCOMMITTED` is a badge on top of the primary status.

## Typical laptop loop

```text
ScreenNote   REMOTE AHEAD   → pull (ff-only)
CLINQ        LOCAL AHEAD    → push existing commits
OldParser    REMOTE ONLY    → clone into a chosen root
NewTool      LOCAL ONLY     → publish (private by default)
```

Always preview first:

```powershell
get-gited sync D:\Projects --dry-run
```

If the preview is right **and** you want the full queue with no picker:

```powershell
get-gited sync D:\Projects --yes
```

Without `--yes`, non-interactive `sync` prints the plan and stops. Interactive `gg` still needs `[Enter]` on the preview.

## Safety

Get Gited will **never** automatically:

- force-push
- `git reset --hard` / `git clean -fd`
- rewrite history
- merge diverged branches or rebase
- commit working-tree changes
- overwrite an existing clone destination
- replace an existing Git remote
- make a repository public unless you choose that
- print a detected secret in full

If a safe action is impossible, the row is `BLOCKED` (or `ERROR`) — not a clever automatic repair.

Dry-run does not change working trees, Git refs (including remote-tracking), GitHub, or config.

First publish runs a deterministic secret / large-file preflight.

## Configuration

Optional. Default path on Windows:

```text
%APPDATA%\get-gited\config.toml
```

Usually `C:\Users\<you>\AppData\Roaming\get-gited\config.toml`.

```toml
[[roots]]
path = "D:\\Projects"
profile = "personal"
default_visibility = "private"

[scan]
max_depth = 6

[ignore]
paths = ["D:\\Projects\\archive"]

[privacy]
infer_about = false

[ui]
theme = "minimal"
```

Never put tokens in this file. Auth is `gh`. Get Gited does not store GitHub tokens.

## Development

```powershell
python -m pip install -e ".[dev]"
pytest
ruff check .
ruff format --check .
mypy
python -m build
```

## License

MIT. The terms are in [`LICENSE`](LICENSE).

That file **is** the license. You do not apply to GitHub for one — you put `LICENSE` in the repository, and GitHub displays whatever is in the tree.
