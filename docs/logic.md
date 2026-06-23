# Логика работы скрипта лечения, рейдов и золотодобычи

## Обзор

Скрипт автоматизирует лечение войск, участие в рейдах и добычу золота в игре через эмулятор BlueStacks. Использует компьютерное зрение (OpenCV) для распознавания интерфейса и автоматизацию действий через pyautogui.

---

## Структура проекта

```
.
├── main.py               # Точка входа, основной цикл
├── config.py             # Конфигурация, константы, Enum состояний
├── utils.py              # Общие утилиты (скриншоты, поиск, окно)
├── heal.py               # Логика лечения и быстрого лечения с карты
├── raid.py               # Логика рейдов
├── gold.py               # Логика золотодобычи
├── logic.md              # Эта документация
└── pictures/             # Изображения для распознавания
```

## Модули

| Файл | Описание |
|------|----------|
| `main.py` | Основной цикл, переключение режимов, управление состоянием |
| `config.py` | Константы изображений, параметры чувствительности, Enum состояний |
| `utils.py` | Работа с окном, скриншоты, поиск шаблонов, клик, reconnect |
| `heal.py` | Определение и обработка состояний лечения |
| `raid.py` | Определение и обработка состояний рейдов, навигация, скроллинг |
| `gold.py` | Определение и обработка состояний золотодобычи |

---

## Конфигурация режимов работы

| Переменная | Значение | Поведение |
|------------|----------|-----------|
| `FORCE_HEAL_ONLY = True` | Только лечение | Игнорирует рейды, лечение + помощь союзу + золото по таймеру |
| `FORCE_RAID_ONLY = True` | Только рейды | Игнорирует лечение и золото, только рейды |
| `FAST_HEAL_FROM_MAP_ENABLED = True` | Быстрое лечение с карты | Игнорирует рейды и обычное лечение, кликает ambulance |
| Все False | Автопереключение | HEAL ↔ GOLD ↔ RAID по таймерам и событиям |

---

## Ключевые параметры

| Параметр | Значение | Описание |
|----------|----------|----------|
| `CONFIDENCE_THRESHOLD` | 0.70 | Стандартный порог обнаружения элементов |
| `CONFIDENCE_HIGH` | 0.95 | Высокий порог (кнопка "+", RAID_HAVE_TO_CONNECT) |
| `CONFIDENCE_MEDIUM_THRESHOLD` | 0.80 | Средний порог |
| `MARCH_THRESHOLD` | 0.90 | Порог кнопки "Марш" |
| `NAVIGATION_THRESHOLD` | 0.90 | Порог навигационных элементов |
| `RAID_JOIN_TIMEOUT` | 120s | Таймаут возврата к лечению при неудаче в рейде |
| `RAID_SCROLL_THRESHOLD` | 2 | Максимум упоминаний "Атака" перед скроллом |
| `GOLD_INTERVAL` | 2700s | Интервал между золотыми заходами |
| `GOLD_MINING_DURATION` | 2700s | Длительность добычи перед отзывом |
| `GOLD_TIMEOUT` | 300s | Максимальное время одного золотого процесса |
| `GOLD_LEVEL` | 4 | Целевой уровень рудника 1–6 |

---

## Структура папок с изображениями

```
pictures/
├── common/      # mail, reconnect, village, wild_earth, close, back, souz, news, events, book, help_hands
├── heal/        # heal_town, heal_button, heal_wait, heal_help_hands, heal_free_button, fast_use,
│                # ambulance, ambulance_bottle_wide, heal_help_with_time_button
├── help/        # help_hands
├── raid/        # raid_plus, raid_march_button, ok, raid_active, raid_not_active, noFreeSpace,
│                # raid_connect, raid_connect_2, attack, raid_full
└── gold/        # rudnik, rudnik_opened, forward, no_free_rudnik, select_level, lvl_1..6, current_lvl_1..6,
                 # current_raid_lvl_icon, find, free_place, grind, join, go, moveOn, my_rudnik,
                 # return, return_boys, finish, confirm, summary_strength_text, hand, close
```

---

## Состояния

### `HealState`

| Состояние | Описание |
|-----------|----------|
| `UNKNOWN` | Неизвестное состояние |
| `MAIN_SCREEN` | Главный экран карты/поселения |
| `HEAL_ICON` | Видна иконка лечения |
| `HEAL_MENU_OPEN` | Меню лечения открыто |
| `HEAL_HELP` | Помощь в меню лечения |
| `HEAL_WAIT` | Ожидание лечения |
| `HEAL_TOWN` | Окно города лечения |
| `RECONNECT_POPUP` | Окно переподключения |
| `RECONNECT_REPEAT_POPUP` | Окно повторного переподключения |
| `FAST_USE_POPUP` | Окно быстрого использования |
| `CONFIRM_BUTTON_REQUIRED` | Требуется подтверждение |
| `MAIL` | Почта |
| `HELP_HANDS` | Помощь союзу |
| `AMBULANCE_ON_MAP` | Иконка ambulance на карте мира |
| `HEAL_HELP_WITH_TIME` | Кнопка лечения с таймером |

### `RaidState`

| Состояние | Описание |
|-----------|----------|
| `UNKNOWN` | Неизвестное состояние |
| `REID_WINDOW_ACTIVE` | Активное окно рейдов |
| `REID_TAB_NOT_ACTIVE` | Вкладка рейдов не активна |
| `PLUS_VISIBLE` | Видна кнопка "+" |
| `MARCH_VISIBLE` | Видна кнопка "Марш" |
| `RAID_IN_PROGRESS` | Рейд выполняется (есть "Атака") |
| `RAID_COMPLETED` | Рейд завершён |
| `NO_FREE_SPACE` | Нет мест в марше |
| `NO_REIDS` | Нет активных рейдов |
| `RECONNECT_POPUP` / `RECONNECT_REPEAT_POPUP` | Окна переподключения |
| `NAVIGATION_NEEDED` | Требуется полная навигация к окну рейдов |
| `NEEDS_SCROLL` | Требуется скролл списка рейдов |
| `RAID_FULL` | Рейд заполнен |

### `GoldState`

| Состояние | Описание |
|-----------|----------|
| `UNKNOWN` | Не удалось определить экран |
| `MAIN_SCREEN` | Главный экран |
| `EVENTS_MENU_OPEN` | Меню событий открыто |
| `EVENTS_RUDNIK_VISIBLE` | В меню событий виден рудник |
| `EVENTS_NEED_SCROLL` | Требуется скролл для поиска рудника |
| `FORWARD_POPUP_VISIBLE` | Попап "Вперёд" |
| `NO_FREE_RUDNIK` | Нет свободных рудников |
| `RUDNIK_TAB` | Открыта таба рудника |
| `SELECT_LEVEL_VISIBLE` | Виден виджет выбора уровня |
| `LEVEL_LIST_VISIBLE` | Открыт список уровней |
| `RAID_LEVEL_ICON_VISIBLE` | Видна иконка активной добычи |
| `FIND_VISIBLE` | Видна кнопка поиска |
| `GRIND_VISIBLE` | Кнопка начала добычи |
| `WORK_VISIBLE` | Кнопка "Работа" |
| `GO_VISIBLE` | Кнопка отправки отряда |
| `MY_RUDNIK_VISIBLE` | Отряд уже добывает |
| `RETURN_CONFIRM_VISIBLE` | Подтверждение отзыва |
| `RETURN_BUTTON_VISIBLE` | Видна кнопка отзыва |
| `FINISH_VISIBLE` / `CONFIRM_VISIBLE` | Подтверждения после отзыва |
| `SUMMARY_STRENGTH_TEXT_VISIBLE` | Попап "место занято" |
| `FREE_PLACE_VISIBLE` | Найдено свободное место |
| `COMPLETED` | Процесс завершён |

---

## Логика определения состояния лечения (`determine_heal_state`)

Приоритет (сверху вниз):

1. `RECONNECT_IMG` → `RECONNECT_POPUP`
2. `RECONNECT_REPEAT_IMG` → `RECONNECT_REPEAT_POPUP`
3. `FAST_USE_IMG` → `FAST_USE_POPUP`
4. `HEAL_BUTTON_IMG` / `HEAL_FREE_BUTTON_IMG` → `HEAL_MENU_OPEN`
5. `CONFIRM_BUTTON_IMG` → `CONFIRM_BUTTON_REQUIRED`
6. `MAIL_IMG` → `MAIL`
7. `HEAL_TOWN_IMG` → `HEAL_ICON`
8. `HELP_HANDS_IMG` → `HELP_HANDS`
9. `HEAL_HELP_HANDS_IMG` → `HEAL_HELP`
10. `HEAL_WAIT_IMG` → `HEAL_WAIT`
11. `WILD_EARTH_IMG` → `MAIN_SCREEN`
12. `VILLAGE_IMG` → `UNKNOWN`
13. Иначе → `UNKNOWN`

---

## Обработка состояний лечения (`process_heal`)

### `RECONNECT_POPUP` / `RECONNECT_REPEAT_POPUP`
```
→ Обработка переподключения → ожидание 3с → return None
```

### `MAIL`
```
→ Клик по почте → return None
```

### `CONFIRM_BUTTON_REQUIRED`
```
→ Клик по conferm_button.png → return None
```

### `HEAL_ICON`
```
→ Клик по heal_town.png → return HEAL_MENU_OPEN
```

### `HEAL_HELP`
```
→ Клик по heal_help_hands.png → return None
```

### `HEAL_MENU_OPEN`
```
→ Клик по heal_free_button.png; если найдена → return MAIN_SCREEN
→ Иначе клик по heal_button.png; если найдена → return MAIN_SCREEN
```

### `FAST_USE_POPUP`
```
→ Клик по close.png → return UNKNOWN
```

### `UNKNOWN`
```
→ Попытка клика по village.png → MAIN_SCREEN
→ Или back.png / close.png → UNKNOWN
→ Если нет ключевых иконок — клик по верхней части экрана
```

---

## Быстрое лечение с карты мира

### `determine_fast_heal_from_map_state`

Приоритет:
1. Reconnect
2. `HEAL_HELP_WITH_TIME_IMG` → `HEAL_HELP_WITH_TIME`
3. `HEAL_BUTTON_IMG` / `HEAL_FREE_BUTTON_IMG` → `HEAL_MENU_OPEN`
4. `AMBULANCE_ON_MAP_IMG` / `AMBULANCE_ON_MAP_WIDE_IMG` → `AMBULANCE_ON_MAP`
5. `HELP_HANDS_IMG` → `HELP_HANDS`
6. `WILD_EARTH_IMG` → `MAIN_SCREEN`
7. Иначе → `UNKNOWN`

### `process_fast_heal_from_map`

```
HEAL_HELP_WITH_TIME  → клик heal_help_with_time_button.png → HELP_HANDS
HEAL_MENU_OPEN       → heal_free_button.png / heal_button.png → MAIN_SCREEN
AMBULANCE_ON_MAP     → ambulance.png / ambulance_bottle_wide.png → HEAL_HELP_WITH_TIME
HELP_HANDS           → help_hands.png → AMBULANCE_ON_MAP
MAIN_SCREEN          → ждём ambulance
UNKNOWN              → ждём
```

---

## Логика определения состояния рейда (`determine_raid_state`)

Приоритет:
1. Reconnect
2. `RAID_FULL_IMG` → `RAID_FULL`
3. `RAID_NO_FREE_SPACE_IMG` → `NO_FREE_SPACE`
4. `RAID_NOT_ACTIVE_IMG` → `REID_TAB_NOT_ACTIVE`
5. `RAID_PLUS_IMG` (threshold 0.95) → `PLUS_VISIBLE`
6. `RAID_MARCH_IMG` → `MARCH_VISIBLE`
7. `count_attack_mentions()`:
   - > 2 → `NEEDS_SCROLL`
   - > 0 → `RAID_IN_PROGRESS`
   - == 0:
     - если не видны `raid_active`/`raid_not_active` → `NAVIGATION_NEEDED`
     - если `plus_found` → `NO_REIDS`
     - иначе → `RAID_COMPLETED`

---

## Обработка состояний рейда (`process_raid`)

### `RECONNECT_POPUP` / `RECONNECT_REPEAT_POPUP`
```
→ Обработка переподключения → return (None, last_join_time, raid_joined_at_least_once)
```

### `NAVIGATION_NEEDED`
```
→ navigate_to_reid_window() → return (None, ...)
```

### `REID_TAB_NOT_ACTIVE`
```
→ Клик по raid_not_active.png → REID_WINDOW_ACTIVE или None
```

### `NO_FREE_SPACE` / `RAID_FULL`
```
→ Клик по ok.png → RAID_COMPLETED, обновление last_join_time
```

### `NO_REIDS`
```
→ Если village.png видна → navigate_to_reid_window() → None
→ Иначе остаёмся в NO_REIDS, обновляем last_join_time
```

### `NEEDS_SCROLL`
```
→ check_and_scroll_for_attack() → RAID_IN_PROGRESS
```

### `RAID_IN_PROGRESS`
```
→ return (RAID_IN_PROGRESS, time.time(), ...)
```

### `PLUS_VISIBLE`
```
→ Клик raid_plus.png → ожидание 0.5с → скриншот
→ Клик raid_march_button.png:
   ├── Успешно → ожидание 0.5с → скриншот
│   ├── noFreeSpace.png найдена → ok.png → NO_FREE_SPACE
│   └── Иначе → RAID_IN_PROGRESS
```

### `MARCH_VISIBLE`
```
→ Аналогично PLUS_VISIBLE, но без предварительного клика по "+"
→ После клика "Марш" также проверяется ok.png (raid_full)
```

---

## Навигация к окну рейдов (`navigate_to_reid_window`)

Последовательность кликов:
1. **Союз** (`SOUZ_IMG`) → ожидание 0.3с
2. **Новости** (`NEWS_IMG`) → ожидание 0.3с
3. **Рейды** (`RAID_NOT_ACTIVE_IMG`) → ожидание 0.3с → завершение

---

## Скроллинг списка рейдов (`check_and_scroll_for_attack`)

1. Подсчитать упоминания "Атака".
2. Если `attack_count > RAID_SCROLL_THRESHOLD`:
   - Свайп вверх (скролл вниз) на 60% высоты экрана.
   - Ожидание 0.3с, новый скриншот, пересчёт атак.
   - Если всё ещё много атак → повторный свайп 70% от первой длины.

---

## Подсчёт упоминаний "Атака" (`count_attack_mentions`)

1. Загрузить шаблон `attack.png`.
2. `cv2.matchTemplate` с порогом 0.6.
3. Собрать уникальные точки (минимальное расстояние 15px).
4. Вернуть количество уникальных совпадений.

---

## Логика золотодобычи

### Триггер входа

```
HEAL
  ↓ GOLD_ENABLED
  ↓ should_do_gold()  или  gold_mission_should_recall()
  ↓ Да
MainMode.GOLD, reset_gold_context(), gold_start_time = now
```

### Основной flow

```
MAIN_SCREEN
  ↓ click EVENTS_IMG / BOOK_IMG
EVENTS_MENU_OPEN
  ↓ scroll_in_region('down') пока не найдётся GOLD_RUDNIK_IMG
EVENTS_RUDNIK_VISIBLE
  ↓ click GOLD_RUDNIK_IMG
FORWARD_POPUP_VISIBLE
  ↓ click GOLD_FORWARD_IMG
RUDNIK_TAB
  ↓ get_current_level()
  ↓ если != GOLD_LEVEL: click select_level.png → LEVEL_LIST_VISIBLE → scroll → click_moveon_for_target_level()
RUDNIK_TAB
  ↓ click find.png
FIND_VISIBLE
  ↓ click find.png пока не появится free_place.png
FREE_PLACE_VISIBLE
  ↓ click
GRIND_VISIBLE → WORK_VISIBLE → GO_VISIBLE
  ↓ click go.png
  ↓ проверка return.png / my_rudnik.png
  ↓ Да → start_gold_mission() → update_gold_time() → COMPLETED
```

### Активная добыча

```
MY_RUDNIK_VISIBLE / RAID_LEVEL_ICON_VISIBLE
  ↓ если recall_requested: click return.png → RETURN_CONFIRM_VISIBLE → return_boys.png → clear_gold_mission()
  ↓ иначе: click current_raid_lvl_icon.png → RUDNIK_TAB → get_current_level()
     ↓ если elapsed >= GOLD_MINING_DURATION: recall_requested = True
     ↓ иначе: update_gold_time() → COMPLETED
```

### Отсутствие свободных мест

```
NO_FREE_RUDNIK / LEVEL_LIST_VISIBLE при no_free_rudnik.png
  ↓ Пробуем GOLD_LEVEL +1, -1, +2, -2, ... в пределах 1..6
  ↓ Если нашли свободный уровень: click_moveon_for_target_level(alternative)
  ↓ После 10 попыток: COMPLETED
```

### Recovery при UNKNOWN

```
UNKNOWN
  ↓ Ожидание после moveOn / events (до 2.5с)
  ↓ Если открылось активное событие: swipe_horizontal('right')
  ↓ Иначе:
     1. back.png
     2. gold/close.png
     3. village.png → сброс stuck_count
```

---

## Основной цикл (`main`)

### Инициализация
```python
window, region = get_window_region()
last_heal_state = None
last_raid_state = None
last_gold_state = None
current_mode = MainMode.HEAL
raid_start_time = None
raid_joined_at_least_once = False
raid_terminal_since = None
gold_start_time = None
gold_exiting = False
```

### Цикл `while True`

1. Обновить окно и область. Если не найдено — `sleep(5)`.
2. Активировать окно через `SetForegroundWindow`.
3. Сделать скриншот.
4. Глобальная проверка reconnect (завершает программу).
5. Если `FAST_HEAL_FROM_MAP_ENABLED` — `process_fast_heal_from_map()`.
6. Если `FORCE_RAID_ONLY` — `process_raid()`.
7. Если режим HEAL:
   - Триггер GOLD (по таймеру или отзыву).
   - В автопереключении проверить `check_for_raid_button()`.
   - `check_and_click_help_button()`.
   - `process_heal()`.
8. Если режим GOLD:
   - Защитный таймаут `GOLD_TIMEOUT`.
   - `process_gold()`.
   - Если `COMPLETED` — возврат к HEAL.
9. Если режим RAID:
   - Таймаут `RAID_JOIN_TIMEOUT`.
   - `process_raid()`.
   - Защита от застревания в терминальном состоянии > 30с.
   - Если `RAID_COMPLETED` / `NO_REIDS` — возврат к HEAL.
10. Задержка: `GOLD_LOOP_DELAY` для GOLD, иначе 1 секунда.
11. Обработка исключений → log → `sleep(5)`.

---

## Переключение режимов

### HEAL → GOLD
- **Триггер:** `GOLD_ENABLED` и (`should_do_gold()` или `gold_mission_should_recall()`).
- **Действия:**
  ```python
  current_mode = MainMode.GOLD
  last_gold_state = None
  reset_gold_context()
  gold_start_time = time.time()
  ```

### GOLD → HEAL
- **Триггер:** `last_gold_state == GoldState.COMPLETED` или таймаут `GOLD_TIMEOUT`.
- **Действия:**
  ```python
  current_mode = MainMode.HEAL
  last_gold_state = None
  gold_start_time = None
  ```

### HEAL → RAID
- **Триггер:** Найдена `RAID_HAVE_TO_CONNECT_IMG` или `RAID_HAVE_TO_CONNECT_2_IMG`.
- **Действия:**
  ```python
  current_mode = MainMode.RAID
  raid_start_time = time.time()
  raid_joined_at_least_once = False
  last_join_time = time.time()
  raid_nav_grace_until = time.time() + 10
  last_raid_state = None
  ```

### RAID → HEAL
- **Триггер:** `RAID_COMPLETED`, `NO_REIDS` или таймаут `RAID_JOIN_TIMEOUT` без join.
- **Действия:**
  ```python
  current_mode = MainMode.HEAL
  last_raid_state = None
  raid_start_time = None
  raid_joined_at_least_once = False
  ```

---

## Утилиты

### `get_window_region()`
Получение области окна BlueStacks, активация если не активно.

### `prepare_template(template_path)`
Загрузка и подготовка шаблона для матчинга.

### `get_template(template_path)`
Получение шаблона с кэшированием.

### `take_screenshot(window, region)`
Создание скриншота области окна через win32 API с фолбэком на pyautogui.

### `find_on_screen(template, screen_cv, region, threshold)`
Поиск шаблона через `cv2.matchTemplate`, возврат центра + confidence.

### `find_all_on_screen(template, screen_cv, region, threshold)`
Поиск всех вхождений шаблона с фильтрацией по минимальному расстоянию.

### `find_and_click(template_path, screen_cv, region, threshold)`
Поиск и клик по элементу.

### `scroll_in_region(region, direction, step_ratio)`
Вертикальный drag для скролла списка.

### `swipe_horizontal(region, direction)`
Горизонтальный свайп по верхней части окна.

### `save_debug_screenshot(screen_cv, step_name)`
Сохранение отладочного скриншота.

### `handle_reconnect()` / `handle_reconnect_repeat()`
Обработка окон переподключения.

---

## Обработка ошибок

- Любое исключение в цикле → log → `sleep(5)` → продолжение.
- Окно BlueStacks не найдено → `sleep(5)` → повтор.
- Шаблон не найден → log + return False (не прерывает выполнение).
- RAID застрял в терминальном состоянии > 30с → клик по центру → HEAL.
- GOLD затянулся > `GOLD_TIMEOUT` → принудительный возврат к HEAL.

---

## Отладка

- Папка `debug_screenshots/` создаётся автоматически.
- `save_debug_screenshot()` сохраняет скриншоты с метками состояний.
- Детальный логгинг в консоль.

---

## Зависимости

```
numpy
opencv-python
pyautogui
pygetwindow
pywin32 (win32gui, win32ui, win32con)
datetime
os
pynput
```

Установка:
```bash
pip install numpy opencv-python pyautogui pygetwindow pywin32 pynput
```

---

## См. также

- `docs/GOLD_MODULE.md` — детальный flow золотодобычи.
- `docs/REFACTORING_SUMMARY.md` — почему код разделён на модули.
- `docs/GOLD_REFACTOR.md` — история рефакторинга gold.py.
- `docs/AGENTS.md` — инструкции для AI-ассистентов.
