# Football Career Mode

A football management game built in Python. Pick a club from the top five European leagues, run it for up to seven seasons, and watch the matches play out as a simulation. There is no real-time gameplay: you make the decisions, and the engine plays the games.

Built by **Brooklyn Chigozie** and **Prosper** as a computer science project.

## Features

- **Five leagues:** Premier League, La Liga, Serie A, Bundesliga and Ligue 1 (first divisions only, no promotion or relegation)
- **Cups:** one domestic cup per league, plus the Champions League
- **Seven-season career:** the world keeps moving on its own, with AI transfers, player development, aging, retirement and new youngsters
- **Squad management:** formations, starting XI, injuries, suspensions, fitness and morale
- **Transfers:** search the market, make bids, sign free agents, list players and answer offers for your own
- **Finances and sponsorships:** wages, budgets, income and sponsor deals
- **Accounts and saves:** sign up, log in, and keep several save slots per user
- **Dark dashboard UI** built with PySide6 (Qt)

## Requirements

- Python 3.12 or newer (developed on 3.14 for Windows)
- The packages listed in `requirements.txt` (PySide6, pyqtgraph, bcrypt, pytest and others)

## Setup

### Windows (PowerShell)

```
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell refuses to run the activation script, run this once and try again:

```
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

In PyCharm you can skip the manual steps. Open the project, choose the `.venv` interpreter under **Settings > Project > Python Interpreter**, and use **View > Tool Windows > Terminal**, which activates the environment for you.

### macOS / Linux

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run the game

```
python main.py
```

## Run the tests

```
python -m pytest
```

The tests cover the match engine, game services, accounts and saves, and the UI.

## Build a Windows application

Install PyInstaller and build from the project folder:

```
python -m pip install --upgrade pyinstaller
python -m PyInstaller --noconfirm --windowed --name "Football-Career-Mode" --add-data "data;data" --add-data "ui/theme.qss;ui" main.py
```

The app appears in `dist\Football-Career-Mode\`. Run `Football-Career-Mode.exe` from there, and keep the whole folder together.

Notes:

- On macOS and Linux, use `:` instead of `;` in the `--add-data` values.
- Any non-Python file the game reads (themes, images, data) must be added with its own `--add-data` flag, or the built app will report a missing file.
- Build without `--windowed` first if you need to see error messages in a console.

## Project structure

```
Football-Career-Mode/
├── main.py            # application entry point
├── requirements.txt   # Python dependencies
├── data/              # game data (clubs, players)
├── docs/              # project documentation
├── engine/            # simulation: matches, schedules, lineups, tactics, economy, offseason
├── services/          # accounts, database, saves, importing, file paths
├── ui/                # PySide6 windows, screens, components and theme
├── scripts/           # helper scripts
├── tools/             # developer tools
├── tests/             # automated tests
└── userdata/          # local accounts and save games (created at runtime)
```

## How the code is organised

The project has three layers, and each one only depends on the layer below it:

```
ui  ->  services  ->  engine
```

- **engine** is pure Python simulation with no UI or database code, so it can be tested on its own.
- **services** handles persistence: the database, accounts, save slots and importing data.
- **ui** contains the screens and widgets. Screens read from the game state and call into the services and engine; they do not reach into engine internals.

Long-running actions, such as simulating a season, run on a background thread so the window never freezes.

## Data and saves

- Club and player data is loaded from the `data/` folder.
- Accounts and save games are stored locally in `userdata/`. Passwords are hashed and never stored in plain text.
- Deleting `userdata/` removes all local accounts and saves.

## Working on the project

- Create a branch for each task, for example `feature/ui-transfers`, and open a pull request.
- The other lead reviews each pull request before it is merged into `main`.
- Run `python -m pytest` before you push.
- Keep source files as normal text in Git. Do not track `.py` files with Git LFS.

## Troubleshooting

| Problem | Fix |
|---|---|
| `python3` is not found on Windows | Use `py` or `python` instead. `python3` is a Mac/Linux name. |
| `source .venv/bin/activate` fails on Windows | Use `.venv\Scripts\Activate.ps1` |
| `SyntaxError` mentioning `version https://git-lfs...` | Files were pulled as Git LFS placeholders. Run `git fetch origin` then `git reset --hard origin/main`, or ask for the files to be re-committed as normal text. |
| `PermissionError ... being used by another process` when deleting a save | A save database is still open. Close the connection before deleting the file. |
| `FileNotFoundError` for a `.qss`, image or data file in the built app | Add the file or folder with another `--add-data` flag and rebuild. |
| `pyinstaller` is not recognised | Run it as `python -m PyInstaller ...` |
| Editor shows red underlines on `from engine...` | Mark the project root as a Sources Root in PyCharm. |

## Known limitations

- No in-match substitutions or live tactics changes
- Cup draws are random
- No international breaks
- Real club and player names are used for study and portfolio purposes only. Logos and photos are not included, and the game should not be released commercially without licensing.

## Credits

Created by Brooklyn Chigozie and Prosper.
