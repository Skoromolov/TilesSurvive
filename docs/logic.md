# Логика работы скрипта лечения и рейдов

## Обзор

Скрипт автоматизирует лечение войск и участие в рейдах в игре через эмулятор BlueStacks. Использует компьютерное зрение (OpenCV) для распознавания интерфейса и автоматизацию действий через pyautogui.

## Структура проекта

```
.
├── main.py               # Точка входа, основной цикл
├── config.py             # Конфигурация, константы, настройки
├── utils.py              # Общие утилиты (скриншоты, поиск, окно)
├── heal.py               # Логика лечения
├── raid.py               # Логика рейдов
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

---

## Конфигурация режимов работы

Переменные в начале файла определяют режим работы:

| Переменная | Значение | Поведение |
|------------|----------|-----------|
| `FORCE_HEAL_ONLY = True` | Только лечение | Игнорирует рейды, только лечение и помощь союзу |
| `FORCE_RAID_ONLY = True` | Только рейды | Игнорирует лечение, только рейды |
| `FORCE_HEAL_ONLY = False`<br>`FORCE_RAID_ONLY = False` | Автопереключение | Автоматически переключается между лечением и рейдами |

---

## Ключевые параметры

| Параметр | Значение | Описание |
|----------|----------|----------|
| `CONFIDENCE_THRESHOLD` | 0.70 | Стандартный порог обнаружения элементов интерфейса |
| `CONFIDENCE_HIGH` | 0.95 | Высокий порог (для кнопки "+") |
| `MARCH_THRESHOLD` | 0.90 | Порог кнопки "Марш" |
| `NAVIGATION_THRESHOLD` | 0.90 | Порог навигационных элементов |
| `RAID_JOIN_TIMEOUT` | 120s (2 мин) | Таймаут возврата к лечению если не удалось присоединиться к рейду |
| `RAID_SCROLL_THRESHOLD` | 2 | Максимум упоминаний "Атака" перед выполнением скролла |

---

## Структура папок с изображениями

```
pictures/
├── common/      # Общие элементы: mail, reconnect, village, wild_earth, close, back, souz, news
├── heal/        # Элементы лечения: heal_town, heal_button, heal_wait, heal_help_hands, heal_free_button, fast_use
├── help/        # Элементы помощи: help_hands
└── raid/        # Элементы рейдов: raid_plus, raid_march_button, ok, raid_active, raid_not_active, noFreeSpace, raid_connect, raid_connect_2, attack
```

---

## Основные состояния

### Состояния лечения (`HealState`)

| Состояние | Описание |
|-----------|----------|
| `UNKNOWN` | Неизвестное состояние, ничего не найдено |
| `MAIN_SCREEN` | Главная страница поселения (видна `WILD_EARTH_IMG`) |
| `HEAL_ICON` | Видна иконка лечения (`HEAL_TOWN_IMG`) |
| `HEAL_MENU_OPEN` | Меню лечения открыто (видна `HEAL_BUTTON_IMG`) |
| `HEAL_HELP` | Видна иконка помощи (`HEAL_HELP_HANDS_IMG`) |
| `HEAL_ACTIVE` | Лечение активно (виден `HEAL_WAIT_IMG`) |
| `HEAL_WAIT` | Ожидание лечения |
| `HEAL_TOWN` | Видно окно города лечения |
| `RECONNECT_POPUP` | Появилось окно переподключения |
| `RECONNECT_REPEAT_POPUP` | Появилось окно повторного переподключения |
| `FAST_USE_POPUP` | Появилось окно "Быстрое использование" |
| `CONFIRM_BUTTON_REQUIRED` | Требуется кнопка подтверждения |
| `MAIL` | Видна почта |
| `HELP_HANDS` | Видна помощь руками |

### Состояния рейда (`RaidState`)

| Состояние | Описание |
|-----------|----------|
| `UNKNOWN` | Неизвестное состояние |
| `REID_WINDOW_ACTIVE` | Активное окно рейдов |
| `REID_TAB_NOT_ACTIVE` | Вкладка рейдов не активна |
| `PLUS_VISIBLE` | Видна кнопка "+" |
| `MARCH_VISIBLE` | Видна кнопка "Марш" |
| `RAID_IN_PROGRESS` | Рейд выполняется (есть упоминания "Атака") |
| `RAID_COMPLETED` | Рейд завершён |
| `NO_FREE_SPACE` | Нет мест в марше |
| `NO_REIDS` | Нет активных рейдов, ожидание |
| `RECONNECT_POPUP` | Окно переподключения |
| `RECONNECT_REPEAT_POPUP` | Окно повторного переподключения |
| `NAVIGATION_NEEDED` | Требуется полная навигация к окну рейдов |
| `NEEDS_SCROLL` | Требуется прокрутка списка рейдов |

---

## Логика определения состояния лечения (`determine_heal_state`)

Функция проверяет элементы в следующем порядке приоритета:

1. **Reconnect popup** (`RECONNECT_IMG`) → `HealState.RECONNECT_POPUP`
2. **Reconnect repeat popup** (`RECONNECT_REPEAT_IMG`) → `HealState.RECONNECT_REPEAT_POPUP`
3. **Fast use popup** (`FAST_USE_IMG`) → `HealState.FAST_USE_POPUP`
4. **Кнопка лечения** (`HEAL_BUTTON_IMG`) → `HealState.HEAL_MENU_OPEN`
5. **Кнопка подтверждения** (`CONFIRM_BUTTON_IMG`) → `HealState.CONFIRM_BUTTON_REQUIRED`
6. **Почта** (`MAIL_IMG`) → `HealState.MAIL`
7. **Иконка лечения в городе** (`HEAL_TOWN_IMG`) → `HealState.HEAL_ICON`
8. **Помощь руками** (`HELP_HANDS_IMG`) → `HealState.HELP_HANDS`
9. **Помощь в меню лечения** (`HEAL_HELP_HANDS_IMG`) → `HealState.HEAL_HELP`
10. **Ожидание лечения** (`HEAL_WAIT_IMG`) → `HealState.HEAL_WAIT`
11. **Дикие земли** (`WILD_EARTH_IMG`) → `HealState.MAIN_SCREEN`
12. **Поселение** (`VILLAGE_IMG`) → `HealState.UNKNOWN`
13. **Ничего не найдено** → `HealState.UNKNOWN`

---

## Обработка состояний лечения (`process_heal`)

### `RECONNECT_POPUP` / `RECONNECT_REPEAT_POPUP`
```
→ Обработка переподключения → ожидание 3с → возврат None
```

### `MAIL`
```
→ Клик по почте → возврат None
```

### `CONFIRM_BUTTON_REQUIRED`
```
→ Клик по кнопке подтверждения → возврат None
```

### `HEAL_ICON`
```
→ Клик по HEAL_TOWN_IMG → если успешно → возврат HEAL_MENU_OPEN
```

### `HEAL_HELP`
```
→ Клик по HEAL_HELP_HANDS_IMG → возврат None
```

### `HEAL_ACTIVE`
```
→ Поиск помощи (HEAL_HELP_HANDS_IMG):
   ├── Найдена → возврат None (переход к обработке помощи)
   └── Не найдена → возврат HEAL_ACTIVE (продолжаем ждать)
```

### `FAST_USE_POPUP`
```
→ Клик по CLOSE_IMG (крестик) → возврат HealState.UNKNOWN
```

### `HEAL_MENU_OPEN`
```
→ Клик по HEAL_BUTTON_IMG → если успешно → возврат HealState.MAIN_SCREEN
```

### `UNKNOWN`
```
→ Попытка клика по VILLAGE_IMG → если успешно → возврат HealState.MAIN_SCREEN
→ Или клик по BACK_IMG / CLOSE_IMG → возврат HealState.UNKNOWN
```

---

## Логика определения состояния рейда (`determine_raid_state`)

Функция проверяет элементы в следующем порядке:

1. **Reconnect popup** (`RECONNECT_IMG`) → `RaidState.RECONNECT_POPUP`
2. **Reconnect repeat popup** (`RECONNECT_REPEAT_IMG`) → `RaidState.RECONNECT_REPEAT_POPUP`
3. **No free space** (`RAID_NO_FREE_SPACE_IMG`) → `RaidState.NO_FREE_SPACE`
4. **Неактивная вкладка рейдов** (`RAID_NOT_ACTIVE_IMG`):
   - Если видна неактивная вкладка → `RaidState.REID_TAB_NOT_ACTIVE`
5. **Кнопка "+"** (`RAID_PLUS_IMG` с `CONFIDENCE_HIGH = 0.95`):
   - Если видна → `RaidState.PLUS_VISIBLE`
6. **Подсчёт упоминаний "Атака"** через `count_attack_mentions()`:
   - `attack_count > 2` → `RaidState.NEEDS_SCROLL`
   - `attack_count > 0` → `RaidState.RAID_IN_PROGRESS`
   - `attack_count == 0` + `plus_found` → `RaidState.NO_REIDS`
   - `attack_count == 0` + `!plus_found` → `RaidState.RAID_COMPLETED`

---

## Обработка состояний рейда (`process_raid`)

### `RECONNECT_POPUP` / `RECONNECT_REPEAT_POPUP`
```
→ Обработка переподключения → возврат параметров без изменений
```

### `NAVIGATION_NEEDED`
```
→ Вызов navigate_to_reid_window() → возврат None
```

### `REID_TAB_NOT_ACTIVE`
```
→ Клик по RAID_NOT_ACTIVE_IMG (неактивная вкладка):
   ├── Успешно → возврат RaidState.REID_WINDOW_ACTIVE
   └── Не успешно → возврат None
```

### `NO_FREE_SPACE`
```
→ Клик по RAID_OK_IMG → обновление last_join_time → возврат предыдущего состояния
```

### `NO_REIDS`
```
→ Проверка VILLAGE_IMG:
   ├── Видна → навигация к окну рейдов → возврат None
   └── Не видна → ожидание → обновление last_join_time → возврат предыдущего состояния
```

### `NEEDS_SCROLL`
```
→ Вызов check_and_scroll_for_attack() → возврат RaidState.RAID_IN_PROGRESS
```

### `RAID_IN_PROGRESS`
```
→ Возврат текущего состояния + обновление last_join_time
```

### `PLUS_VISIBLE`
```
→ Клик по RAID_PLUS_IMG → ожидание 0.5с → скриншот
→ Клик по RAID_MARCH_IMG:
   ├── Успешно → ожидание 0.5с → скриншот
   │   → Проверка RAID_NO_FREE_SPACE_IMG:
   │       ├── Найдена → обработка (клик OK) → возврат RaidState.NO_FREE_SPACE
   │       └── Не найдена → возврат RaidState.RAID_IN_PROGRESS
   └── Не успешно → возврат None
```

### `MARCH_VISIBLE`
```
→ Клик по RAID_MARCH_IMG → обработка как в PLUS_VISIBLE
```

---

## Навигация к окну рейдов (`navigate_to_reid_window`)

Последовательность кликов:
1. Клик по **Союз** (`SOUZ_IMG`) → ожидание 0.3с
2. Клик по **Новости** (`NEWS_IMG`) → ожидание 0.3с
3. Клик по **Рейды** (`RAID_NOT_ACTIVE_IMG`) → ожидание 0.3с → завершение

---

## Скроллинг списка рейдов (`check_and_scroll_for_attack`)

1. Подсчитать упоминания "Атака" через `count_attack_mentions()`
2. Если `attack_count > RAID_SCROLL_THRESHOLD (2)`:
   - Выполнить свайп вверх (для скролла вниз) на 60% высоты экрана
   - Ожидание 0.3с
   - Обновить скриншот и пересчитать атаки
   - Если всё ещё много атак → повторить свайп (70% от первой длины)

---

## Подсчёт упоминаний "Атака" (`count_attack_mentions`)

1. Загрузить шаблон `attack.png`
2. Выполнить `cv2.matchTemplate` с порогом 0.6
3. Собрать уникальные точки (минимальное расстояние 15px между точками)
4. Вернуть количество уникальных найденных совпадений

---

## Основной цикл (`main`)

### Инициализация
```python
window, region = get_window_region()
last_heal_state = None
last_raid_state = None
raid_nav_grace_until = time.time() + 1
current_mode = MainMode.HEAL
raid_start_time = None
raid_joined_at_least_once = False
last_join_time = time.time()
```

### Цикл (while True)

1. **Обновление окна и области** → если не найдено → sleep(5) → continue
2. **Активация окна BlueStacks** (`SetForegroundWindow`)
3. **Скриншот области**
4. **Глобальная проверка reconnect**:
   - `handle_reconnect()` → если найден → return None (завершение)
   - `handle_reconnect_repeat()` → если найден → return None (завершение)
5. **Принудительный режим RAID**:
   - Если `FORCE_RAID_ONLY` → только `process_raid()` → continue
6. **Режим HEAL**:
   - Если `FORCE_HEAL_ONLY`:
     - Поиск `HELP_HANDS_IMG` → клик
     - `process_heal()` → continue
   - Если автопереключение (`not FORCE_HEAL_ONLY`):
     - **Поиск кнопок присоединения к рейду:**
       - `RAID_HAVE_TO_CONNECT_IMG` (threshold=0.5):
         - Найдена → клик → `current_mode = MainMode.RAID` → сброс таймеров → continue
       - `RAID_HAVE_TO_CONNECT_2_IMG` (threshold=0.5):
         - Найдена → клик → `current_mode = MainMode.RAID` → сброс таймеров → continue
     - **Если кнопки не найдены:**
       - Поиск `HELP_HANDS_IMG` → клик
       - `process_heal()` → update `last_heal_state`
7. **Режим RAID**:
   - Расчёт `elapsed = current_time - last_join_time`
   - **Проверка таймаута** (`elapsed >= RAID_JOIN_TIMEOUT`):
     - Клик по `BACK_IMG` → ожидание
     - Проверка возврата (`WILD_EARTH_IMG` / `VILLAGE_IMG`)
     - `current_mode = MainMode.HEAL` → continue
   - `process_raid()` → update параметры
8. **sleep(0.5)** → следующая итерация
9. **Обработка исключений** → error log → sleep(5)

---

## Переключение режимов

### HEAL → RAID
- **Триггер:** Найдена `RAID_HAVE_TO_CONNECT_IMG` или `RAID_HAVE_TO_CONNECT_2_IMG`
- **Действия:**
  ```python
  current_mode = MainMode.RAID
  raid_start_time = time.time()
  raid_joined_at_least_once = False
  last_join_time = time.time()
  raid_nav_grace_until = time.time() + 10  # Grace period 10с
  ```

### RAID → HEAL
- **Триггер:** Прошло `RAID_JOIN_TIMEOUT` (120 секунд) без успешного присоединения
- **Действия:**
  ```python
  click_back_button()  # BACK_IMG
  current_mode = MainMode.HEAL
  ```

---

## Утилиты

### `get_window_region()`
Получение области окна BlueStacks, активация если не активно.

### `prepare_template(template_path)`
Загрузка и подготовка шаблона для матчинга (конвертация в BGR, uint8).

### `get_template(template_path)`
Получение шаблона с кэшированием.

### `take_screenshot(region)`
Создание скриншота области окна через win32 API (с фолбэком на pyautogui).

### `find_on_screen(template, screen_cv, region, threshold)`
Поиск шаблона на скриншоте через `cv2.matchTemplate`, возврат координат центра + уверенность.

### `find_and_click_cached(template_path, screen_cv, region, threshold)`
Поиск шаблона с кэшированием и клик по найденному элементу.

### `save_debug_screenshot(screen_cv, step_name)`
Сохранение отладочного скриншота с временной меткой.

### `handle_reconnect(screen_cv, region)`
Обработка окна переподключения: клик + ожидание 3с.

### `handle_reconnect_repeat(screen_cv, region)`
Обработка окна повторного переподключения: клик + ожидание 3с.

---

## Обработка ошибок

- Любое исключение в цикле → лог ошибки → `sleep(5)` → продолжение
- Окно BlueStacks не найдено → `sleep(5)` → повторная попытка
- Шаблон не найден → лог + возврат False (не прерывает выполнение)

---

## Отладка

- Папка `debug_screenshots/` создаётся автоматически
- Функция `save_debug_screenshot()` сохраняет скриншоты с метками времени
- Детальный логгинг состояний в консоль

---

## Зависимости

```python
numpy
opencv-python
pyautogui
time
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

## Золотодобыча (кратко)

Подробное описание — в `docs/GOLD_MODULE.md`. Краткая схема:

```
HEAL
  ↓  GOLD_ENABLED and (should_do_gold() or gold_mission_should_recall())
GOLD
  ↓
MAIN_SCREEN → EVENTS_OPEN → [swipe right] → RUDNIK_TAB
  ↓
get_current_level() != GOLD_LEVEL ?
  Да  → SELECT_LEVEL_VISIBLE → LEVEL_LIST_VISIBLE → click_level_go_button() → RUDNIK_TAB
  Нет → FIND_VISIBLE
  ↓
click find.png каждую секунду
  ↓
FREE_PLACE_VISIBLE → GRIND_VISIBLE → WORK_VISIBLE → GO_VISIBLE → COMPLETED
```

Если отряд уже добывает:

```
MY_RUDNIK_VISIBLE / RAID_LEVEL_ICON_VISIBLE
  ↓
click current_raid_lvl_icon.png → RUDNIK_TAB → get_current_level()
  ↓
if elapsed >= GOLD_MINING_DURATION:
    recall_requested = True → click return.png → return_boys.png → FIND_VISIBLE
else:
    update_gold_time() → COMPLETED
```

Основные функции:
- `determine_gold_state()` — приоритетная классификация экрана.
- `process_gold()` — одно действие за итерацию.
- `process_gold_exit()` — выход из меню рудника.
- `get_current_level()` / `get_list_level()` / `click_level_go_button()` — работа с уровнями.
