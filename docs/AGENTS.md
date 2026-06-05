# AGENTS.md

## Entrypoint
- **Run**: `python main.py`
- Do **not** run `heal_and_raid.py` — that is the old monolithic backup. The refactored codebase entry point is `main.py`.

## Architecture
- `main.py` — main loop, mode switching (heal / raid / gold)
- `config.py` — all image path constants, thresholds, enums (`MainMode`, `HealState`, `RaidState`)
- `utils.py` — window capture, template caching, CV matching, click helpers
- `heal.py` — heal state machine (`determine_heal_state`, `process_heal`)
- `raid.py` — raid state machine + navigation + scrolling logic
- `gold.py` — gold state machine (`determine_gold_state`, `process_gold`, `process_gold_exit`)

## Platform / Runtime constraints
- **Windows only** — uses `win32gui`, `win32ui`, `pygetwindow`, `pyautogui`
- Requires **BlueStacks App Player** window to be open; title is `BLUESTACKS_WINDOW_TITLE` in `config.py`
- No tests, no CI, no build tool: there is no `pyproject.toml`, `setup.py`, `Makefile`, or test suite
- `.vscode/settings.json` references pytest, but zero test files exist

## Dependencies
```bash
pip install numpy opencv-python pyautogui pygetwindow pywin32 pynput
```

## Image assets
- Templates live under `pictures/` in subfolders: `common/`, `heal/`, `help/`, `raid/`, `gold/`
- **Filenames must exactly match** constants defined in `config.py` (e.g. `conferm_button.png`, `raid_connect.png`)
- Missing images cause silent runtime skips (`prepare_template` returns `None`), not crashes
- If you add a new UI element:
  1. Drop image into the correct `pictures/<folder>/`
  2. Add a constant in `config.py` using `FOLDER + FOLDER_<X> + 'filename.png'`
  3. Import it where needed

## Code conventions
- Imports use `from config import *` and `from utils import *` (wildcard imports are intentional here)
- State machines rely on `cv2.matchTemplate` + hardcoded confidence thresholds in `config.py`
- `take_screenshot` falls back to `pyautogui.screenshot` if win32 capture fails

## Important docs that already exist
- `logic.md` — detailed state-machine logic for heal and raid modes
- `GOLD_MODULE.md` — detailed flow for the gold-mining module
- `REFACTORING_SUMMARY.md` — explains why `heal_and_raid.py` is legacy and how modules were split

## Modifying behavior
- Change mode switches in `config.py`: `FORCE_HEAL_ONLY`, `FORCE_RAID_ONLY`, `GOLD_ENABLED`
- Adjust confidence thresholds in `config.py` if CV matching is unreliable
- Debug screenshots are saved automatically to `debug_screenshots/`

## What not to do
- Do not delete `heal_and_raid.py` without checking `REFACTORING_SUMMARY.md` notes first
- Do not assume a test suite exists before making changes
- Do not run this on non-Windows systems; it will fail immediately on win32 imports
