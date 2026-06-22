# Логика модуля золотодобычи (gold.py)

## Обзор

Модуль автоматизирует событие "Золотодобыча" в игре. Запускается из режима лечения по таймеру `GOLD_INTERVAL` или когда активная добыча длится ≥ `GOLD_MINING_DURATION` (45 минут).

---

## Конфигурация

В файле `config.py`:

```python
# Настройки золотодобычи
GOLD_ENABLED = True             # Включить автоматизацию
GOLD_INTERVAL = 3600              # Интервал между проверками (сек)
GOLD_LEVEL = 3                      # Целевой уровень рудника 1–6
GOLD_MINING_DURATION = 2700         # 45 минут = 2700 сек; после этого отзываем отряд
GOLD_SEARCH_TIMEOUT = 60            # Таймаут поиска рудника (сек)
GOLD_TIMEOUT = 300                # Максимальное время всего процесса (сек)
```

Изображения должны лежать в `pictures/gold/`:
- `rudnik.png` — иконка рудника в меню событий
- `rudnik_opened.png` — открытая таба рудника
- `select_level.png` — виджет текущего уровня / вход в список уровней
- `lvl_1.png` ... `lvl_6.png` — карточки уровней в списке
- `current_lvl_1.png` ... `current_lvl_6.png` — индикаторы текущего открытого уровня
- `current_raid_lvl_icon.png` — иконка активной добычи для открытия деталей
- `find.png` — кнопка поиска рудника
- `free_place.png` — свободное место в результате поиска
- `grind.png`, `work.png`, `go.png` — цепочка запуска добычи
- `my_rudnik.png`, `return.png`, `return_boys.png` — отзыв активного отряда
- `hand.png`, `confirm.png`, `finish.png` — резервные элементы UI (не обязательны)

---

## Состояния (`GoldState`)

| Состояние | Описание |
|-----------|----------|
| `UNKNOWN` | Не удалось определить экран |
| `MAIN_SCREEN` | Главный экран поселения/карты |
| `EVENTS_OPEN` | Меню событий открыто, рудник виден |
| `EVENTS_NEED_SCROLL` | Меню событий открыто, нужен свайп вправо |
| `RUDNIK_TAB` | Открыта таба рудника, виден текущий уровень |
| `SELECT_LEVEL_VISIBLE` | Виден виджет `select_level.png` |
| `LEVEL_LIST_VISIBLE` | Открыт список уровней |
| `RAID_LEVEL_ICON_VISIBLE` | Видна иконка активной добычи |
| `FIND_VISIBLE` | Видна кнопка поиска |
| `FREE_PLACE_VISIBLE` | Найдено свободное место |
| `GRIND_VISIBLE` | Кнопка начала добычи |
| `WORK_VISIBLE` | Кнопка "Работа" |
| `GO_VISIBLE` | Кнопка отправки отряда |
| `MY_RUDNIK_VISIBLE` | Отряд уже добывает |
| `RETURN_CONFIRM_VISIBLE` | Подтверждение отзыва отряда |
| `RECONNECT_POPUP` / `RECONNECT_REPEAT_POPUP` | Окна переподключения |
| `COMPLETED` | Процесс завершён, возврат к лечению |

---

## Основной процесс

### 1. Триггер входа

```
Режим HEAL
    ↓
GOLD_ENABLED == True
    ↓
should_do_gold()  (прошёл GOLD_INTERVAL)
   ИЛИ
   gold_mission_should_recall()  (45 мин активной добычи истекли)
    ↓ Да
Переключение в MainMode.GOLD, reset_gold_context()
```

### 2. Навигация к руднику

```
MAIN_SCREEN
    ↓ click EVENTS_IMG
EVENTS_OPEN
    ↓ click GOLD_RUDNIK_IMG
RUDNIK_TAB
    ↓ (если не влез — свайп вправо по верхней части, повтор)
```

### 3. Проверка и смена уровня

```
RUDNIK_TAB
    ↓ get_current_level()
Если current_lvl != GOLD_LEVEL:
    click select_level.png
        ↓
    LEVEL_LIST_VISIBLE
        ↓
    scroll_in_region() до появления lvl_GOLD_LEVEL.png
        ↓
    click_level_go_button() — клик в нижней части карточки уровня
        ↓
    RUDNIK_TAB
```

### 4. Поиск и запуск добычи

```
RUDNIK_TAB
    ↓ click find.png
FIND_VISIBLE
    ↓ каждую секунду click find.png, пока не появится free_place.png
FREE_PLACE_VISIBLE
    ↓ click
GRIND_VISIBLE
    ↓ click
WORK_VISIBLE
    ↓ click
GO_VISIBLE
    ↓ click go.png
COMPLETED
```

### 5. Ветка активной добычи

```
MY_RUDNIK_VISIBLE или RAID_LEVEL_ICON_VISIBLE
    ↓
Если recall_requested == True:
    click return.png → RETURN_CONFIRM_VISIBLE → return_boys.png
    ↓
    clear_gold_mission() → FIND_VISIBLE
Иначе:
    click current_raid_lvl_icon.png (если видна)
    ↓
    RUDNIK_TAB → get_current_level()
    ↓
    Если elapsed >= GOLD_MINING_DURATION:
        recall_requested = True
    Иначе:
        update_gold_time() → COMPLETED
```

---

## Функции модуля

### `should_do_gold()`
Проверить, прошло ли `GOLD_INTERVAL` с последнего посещения рудника.

### `update_gold_time()`
Обновить `last_gold_time`.

### `gold_mission_active()`
True, если отряд отправлен добывать и ещё не отозван.

### `gold_mission_should_recall()`
True, если активная добыча длится ≥ `GOLD_MINING_DURATION`.

### `start_gold_mission()`
Зафиксировать факт запуска добычи на `GOLD_LEVEL`.

### `clear_gold_mission()`
Сбросить данные активной добычи.

### `reset_gold_context()`
Сбросить вспомогательный контекст (`_gold_ctx`) перед новым заходом в режим GOLD.

### `get_current_level(screen_cv, region)`
Распознать текущий открытый уровень по `current_lvl_1..6.png`.

### `get_list_level(screen_cv, region)`
Найти уровень в списке выбора по `lvl_1..6.png`.

### `click_level_go_button(level_path, screen_cv, region)`
Кликнуть в нижнюю часть карточки уровня, где находится кнопка "Перейти".

### `determine_gold_state(screen_cv, region)`
Вернуть текущее состояние золотодобычи на основе приоритетной проверки изображений.

### `process_gold(screen_cv, region, last_gold_state, window)`
Выполнить ровно одно действие для текущего состояния и вернуть новое состояние.

### `process_gold_exit(screen_cv, region, last_exit_state, window)`
Последовательно нажимать `BACK_IMG`, пока не вернёмся на `MAIN_SCREEN`.

---

## Интеграция в main.py

```python
# В режиме HEAL
if GOLD_ENABLED and (should_do_gold() or gold_mission_should_recall()):
    print("[MAIN] Переключение в режим GOLD")
    current_mode = MainMode.GOLD
    last_gold_state = None
    reset_gold_context()
    gold_start_time = time.time()
    continue
```

В режиме GOLD:
- Каждую итерацию вызывается `process_gold()`.
- Если `last_gold_state == GoldState.COMPLETED` — возврат к `MainMode.HEAL`.
- Если процесс затянулся > `GOLD_TIMEOUT` — принудительный возврат к HEAL.

---

## Логирование

Пример успешного запуска:

```
[GOLD] Прошло 3650 сек с последнего рудника. Пора!
[MAIN] Переключение в режим GOLD
[GOLD] Состояние: main_screen
[GOLD] Состояние: events_open
[SWIPE] right: (960,180) -> (320,180)
[GOLD] Состояние: rudnik_tab
[GOLD] Распознан текущий уровень: 3 (conf=0.912)
[GOLD] Состояние: select_level_visible
[SCROLL] down: (640,468) -> (640,252)
[GOLD] В списке найден уровень 1 (conf=0.881)
[GOLD] Нажата 'Перейти' для целевого уровня (640, 520) conf=0.881
[GOLD] Состояние: rudnik_tab
[GOLD] Состояние: find_visible
[GOLD] Состояние: free_place_visible
[GOLD] Состояние: grind_visible
[GOLD] Состояние: work_visible
[GOLD] Состояние: go_visible
[GOLD] Отряд отправлен на уровень 1 в Mon Jun 22 14:00:00 2026
[GOLD] ✓ Золотодобыча запущена!
[MAIN] Золотодобыча завершена, возврат к лечению
```

---

## Ошибки

### "Кнопка Events не найдена"
- Проверьте, что вы в поселении.
- Убедитесь, что `events.png` соответствует иконке в правом верхнем углу.

### "Рудник не найден в событиях"
- Увеличьте число свайпов или проверьте `rudnik.png`.
- Проверьте, что событие "Золотодобыча" активно.

### "Не удалось найти целевой уровень"
- Проверьте `select_level.png` и `lvl_1.png`...`lvl_6.png`.
- При необходимости измените направление `scroll_in_region()` в `gold.py`.

### "Превышен таймаут поиска"
- Увеличьте `GOLD_SEARCH_TIMEOUT`.
- Проверьте `find.png` и `free_place.png`.

### "Не отзывается отряд"
- Проверьте `my_rudnik.png`, `return.png`, `return_boys.png`.
- Убедитесь, что `current_raid_lvl_icon.png` открывает экран с `current_lvl_X.png`.
