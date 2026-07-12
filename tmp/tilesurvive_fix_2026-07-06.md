# TileSurvive — план исправлений (2026-07-06, обновлён)

## Проблема 1: Бот не возвращается в поселение, остаётся в диких землях

### Уточнение пользователя
- `back.png` / `close.png` — это выход из случайных меню, не навигация в поселение.
- Кнопка "в поселение" (`VILLAGE_IMG`) — это переход в меню поселения, а не "возврат как таковой".
- После вызова `_is_at_main_screen_village()` возвращающего `False`, код должен инициировать переход в поселение.

### Корневая причина
- `_is_at_main_screen_village()` в `utils.py:241` проверяет только `WILD_EARTH_IMG`.
- `WILD_EARTH_IMG` виден и в диких землях (карта мира), и в поселении. Поэтому функция ошибочно возвращает `True`, когда бот на самом деле в диких землях.
- `ensure_exit_to_main_screen()` вначале пытается кликнуть `VILLAGE_IMG`, но если она не сматчилась (conf=0.219 < 0.7), дальше бьёт `back.png` — бесполезно на карте мира.
- Кнопка "в поселение" на карте мира (`VILLAGE_IMG`) не используется как явный переход.

### Исправление
- `utils.py:_is_at_main_screen_village()` — добавить проверку `VILLAGE_IMG` и других поселенческих маркеров (`souz.png`, `heal_town.png`, `events.png`, `mail.png`, `book.png`).
  - Если виден `VILLAGE_IMG` — значит мы НЕ в поселении (это кнопка "в поселение" на карте мира) — вернуть `False`.
  - Если виден `WILD_EARTH_IMG` И `VILLAGE_IMG` отсутствует — мы в поселении — вернуть `True`.
  - Использовать `souz.png`, `heal_town.png`, `events.png` как fallback-маркеры поселения.
- `ensure_exit_to_main_screen()` — если `_is_at_main_screen_village()` вернул `False`:
  1. Попытаться нажать `VILLAGE_IMG` (переход в меню поселения).
  2. Если не сработало — нажать `BACK_IMG` / `CLOSE_IMG` для закрытия случайных меню.
  3. Циклически перепроверять `_is_at_main_screen_village()` после каждого действия.
- `utils.py:get_window_region()` — обернуть `window.activate()` в try/except, чтобы Windows error 0 не ломала цикл.

## Проблема 2: Золото — поиск места не удался, бот вышел на карту мира

### Уточнение пользователя
- `GOLD_SEARCH_TIMEOUT` увеличен до 600 секунд — это принято.
- При `UNKNOWN` в `process_gold` должен быть возврат в `MainMode.DEFAULT` (через `COMPLETED`), чтобы другие процессы работали.
- `last_gold_time` обновляется при неудаче — это плохо, нужно исправить.

### Корневая причина
- `gold.py:847` — при "Везде занято. Завершаем золотодобычу." вызывается `update_gold_time()`. Это означает, что если на всех уровнях нет мест, бот считает золото "сделанным" и не будет искать 45 минут.
- `update_gold_time()` должна вызываться только при реальном успешном запуске добычи (уже есть в `_complete_mission`, line 115).

### Исправление
- `gold.py:847` — убрать `update_gold_time()` перед `return GoldState.COMPLETED` в блоке "Везде занято".
- Дополнительно проверить все остальные места, где может неявно обновляться `last_gold_time`:
  - `_complete_mission` — OK (успешный старт).
  - Другие `update_gold_time()` вызовы — только при подтверждённой добыче.

## Дополнительно: обработка ошибки Windows 0
- `utils.py:get_window_region()` — обернуть `window.activate()` в try/except, при `PyGetWindowException` продолжать работу (окно может быть уже активно или свёрнуто).

## Файлы для изменения
- `utils.py` — `_is_at_main_screen_village`, `ensure_exit_to_main_screen`, `get_window_region`.
- `gold.py` — убрать `update_gold_time()` при "Везде занято".
- `config.py` — убедиться, что `GOLD_SEARCH_TIMEOUT = 600` (уже сделано пользователем).

## Порядок действий
1. Исправить `_is_at_main_screen_village` и `ensure_exit_to_main_screen`.
2. Исправить `get_window_region`.
3. Убрать лишний `update_gold_time()` в `gold.py`.
4. `python -m py_compile` всех модулей.
5. Удалить `__pycache__`.
6. Пользователь перезапускает скрипт: `Ctrl+C → python -B main.py`.
