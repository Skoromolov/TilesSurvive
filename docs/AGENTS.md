# AGENTS.md

## Entrypoint
- **Run**: `python main.py`
- Do **not** run `heal_and_raid.py` — that is the old monolithic backup. The refactored codebase entry point is `main.py`.

## Architecture
- `main.py` — main loop, mode switching (heal / raid / gold / fast heal from map)
- `config.py` — all image path constants, thresholds, enums (`MainMode`, `HealState`, `RaidState`, `GoldState`)
- `utils.py` — window capture, template caching, CV matching, click helpers, scroll/swipe
- `heal.py` — heal state machine (`determine_heal_state`, `process_heal`) + fast heal from map
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
- **Filenames must exactly match** constants defined in `config.py` (e.g. `conferm_button.png`, `raid_connect.png`, `forward.png`)
- Missing images cause silent runtime skips (`prepare_template` returns `None`), not crashes
- If you add a new UI element:
  1. Drop image into the correct `pictures/<folder>/`
  2. Add a constant in `config.py` using `FOLDER + FOLDER_<X> + 'filename.png'`
  3. Import it where needed

### Important gold assets
- `pictures/common/events.png` — primary calendar icon
- `pictures/common/book.png` — alternative calendar/events icon
- `pictures/gold/rudnik.png` — mine icon in the calendar list
- `pictures/gold/forward.png` — "Вперёд" button in the event popup
- `pictures/gold/no_free_rudnik.png` — "no free spots" message
- `pictures/gold/select_level.png` — current level widget / level list entry point
- `pictures/gold/lvl_1.png` … `lvl_6.png` — level text cards in the list
- `pictures/gold/current_lvl_1.png` … `current_lvl_6.png` — currently opened level badges
- `pictures/gold/moveOn.png` — "Перейти" button attached to a level card
- `pictures/gold/current_raid_lvl_icon.png` — active mining icon to open details
- `pictures/gold/find.png`, `free_place.png`, `grind.png`, `join.png` (work), `go.png` — search & deploy chain
- `pictures/gold/my_rudnik.png`, `return.png`, `return_boys.png`, `finish.png`, `confirm.png` — recall chain
- `pictures/gold/summary_strength_text.png` — "spot occupied" popup
- `pictures/gold/close.png` — close button inside gold UI popups

### Fast heal from map assets
- `pictures/heal/ambulance.png` — ambulance icon on the world map
- `pictures/heal/ambulance_bottle_wide.png` — wider variant for matching
- `pictures/heal/heal_help_with_time_button.png` — heal button with timer after ambulance click

## Code conventions
- Imports use `from config import *` and `from utils import *` (wildcard imports are intentional here)
- State machines rely on `cv2.matchTemplate` + hardcoded confidence thresholds in `config.py`
- `take_screenshot` falls back to `pyautogui.screenshot` if win32 capture fails
- Gold module uses a context dict `_gold_ctx` for transient state; reset it with `reset_gold_context()` on every GOLD entry

## Mode switches
- `HEAL_ENABLED` — enable/disable healing automation
- `FORCE_HEAL_ONLY` — only healing and gold (by timer)
- `FORCE_RAID_ONLY` — only raids
- `FAST_HEAL_FROM_MAP_ENABLED` — highest priority, ambulance-based fast heal on world map, ignores raids
- All false — auto-switch between HEAL, GOLD, RAID

## Modifying behavior
- Change mode switches in `config.py`: `HEAL_ENABLED`, `FORCE_HEAL_ONLY`, `FORCE_RAID_ONLY`, `FAST_HEAL_FROM_MAP_ENABLED`, `GOLD_ENABLED`
- Adjust confidence thresholds in `config.py` if CV matching is unreliable
- Change `GOLD_LEVEL`, `GOLD_INTERVAL`, `GOLD_MINING_DURATION` in `config.py` for gold behavior
- Debug screenshots are saved automatically to `debug_screenshots/`

## Important docs that already exist
- `docs/logic.md` — detailed state-machine logic for heal, raid, and gold modes
- `docs/GOLD_MODULE.md` — detailed flow for the gold-mining module
- `docs/REFACTORING_SUMMARY.md` — explains why `heal_and_raid.py` is legacy and how modules were split
- `docs/GOLD_REFACTOR.md` — notes on the gold state-machine refactor

## What not to do
- Do not delete `heal_and_raid.py` without checking `REFACTORING_SUMMARY.md` notes first
- Do not assume a test suite exists before making changes
- Do not run this on non-Windows systems; it will fail immediately on win32 imports
- Do not invent UI shortcuts (e.g. pressing Escape) or generic close/back images without explicit instruction or screenshot
- Do not update docs only — code and docs must stay synchronized
