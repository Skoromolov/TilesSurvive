# Модуль persistent state
import json
import os
from pathlib import Path

from config import FOLDER

# Папка для данных — та же, где и pictures, logs и т.д.
STATE_DIR = Path(FOLDER) / "data"
STATE_FILE = STATE_DIR / "bot_state.json"

# Ключи, которые сохраняются между перезапусками
LAST_GOLD_TIME_KEY = "last_gold_time"
STARTED_AT_KEY = "gold_started_at"
RECALL_REQUESTED_KEY = "gold_recall_requested"


def _ensure_state_dir():
    """Создать папку data, если её нет."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def load_state(defaults=None):
    """Загрузить сохранённое состояние из JSON."""
    if defaults is None:
        defaults = {}
    _ensure_state_dir()
    if not STATE_FILE.exists():
        return dict(defaults)
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return dict(defaults)
        merged = dict(defaults)
        merged.update(data)
        return merged
    except (json.JSONDecodeError, OSError):
        return dict(defaults)


def save_state(data):
    """Сохранить состояние в JSON-файл."""
    _ensure_state_dir()
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError as e:
        from logger import logger
        logger.warning(f"[STATE] Не удалось сохранить состояние: {e}")


def update_state(**kwargs):
    """Обновить указанные ключи в состоянии."""
    state = load_state()
    state.update(kwargs)
    save_state(state)
