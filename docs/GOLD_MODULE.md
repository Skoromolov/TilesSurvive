# Логика модуля золотодобычи (gold.py)

## Обзор

Модуль автоматизирует событие "Золотодобыча" в игре. Запускается из режима лечения по таймеру `GOLD_INTERVAL` или когда активная добыча длится ≥ `GOLD_MINING_DURATION`.

---

## Конфигурация

В файле `config.py`:

```python
# Настройки золотодобычи
GOLD_ENABLED = True                              # Включить автоматизацию
GOLD_INTERVAL = 2700                             # Интервал между успешными заходами (45 мин)
GOLD_LEVEL = 4                                   # Целевой уровень рудника 1–6
GOLD_MINING_DURATION = 2700                      # 45 минут = 2700 сек; после этого отзываем отряд
GOLD_SEARCH_TIMEOUT = 60                         # Таймаут поиска рудника (сек)
GOLD_TIMEOUT = 300                               # Максимальное время всего процесса (сек)
GOLD_LEVEL_CONFIDENCE_THRESHOLD = 0.90           # Порог для current_lvl_X
GOLD_LIST_LEVEL_CONFIDENCE_THRESHOLD = 0.90      # Порог для lvl_X в списке
GOLD_LOOP_DELAY = 0.1                            # Задержка между итерациями GOLD
GOLD_ACTION_DELAY = 0.05                         # Пауза после клика внутри gold
```

Изображения должны лежать в `pictures/gold/`:

| Файл | Назначение |
|------|------------|
| `rudnik.png` | Иконка рудника в меню событий |
| `rudnik_opened.png` | Открытая таба рудника |
| `forward.png` | Кнопка "Вперёд" в попапе события |
| `no_free_rudnik.png` | Сообщение об отсутствии свободных мест |
| `select_level.png` | Виджет текущего уровня / вход в список уровней |
| `lvl_1.png` ... `lvl_6.png` | Карточки уровней в списке |
| `current_lvl_1.png` ... `current_lvl_6.png` | Индикаторы текущего открытого уровня |
| `current_raid_lvl_icon.png` | Иконка активной добычи для открытия деталей |
| `find.png` | Кнопка поиска рудника |
| `free_place.png` | Свободное место в результате поиска |
| `grind.png`, `join.png` (work), `go.png` | Цепочка запуска добычи |
| `my_rudnik.png`, `return.png`, `return_boys.png` | Отзыв активного отряда |
| `finish.png`, `confirm.png` | Подтверждения после отзыва |
| `summary_strength_text.png` | Попап "место занято" |
| `hand.png` | Резервный элемент UI |
| `close.png` | Кнопка закрытия попапов внутри золотодобычи |
| `moveOn.png` | Кнопка "Перейти" в карточке уровня |

---

## Состояния (`GoldState`)

| Состояние | Описание |
|-----------|----------|
| `UNKNOWN` | Не удалось определить экран |
| `MAIN_SCREEN` | Главный экран поселения/карты |
| `EVENTS_MENU_OPEN` | Меню событий/календарь открыто, рудник ещё не найден |
| `EVENTS_RUDNIK_VISIBLE` | В календаре видна иконка рудника |
| `EVENTS_NEED_SCROLL` | Календарь открыт, нужен скролл вниз для поиска rudnik.png |
| `FORWARD_POPUP_VISIBLE` | Попап события с кнопкой "Вперёд" |
| `NO_FREE_RUDNIK` | На текущем/выбранном уровне нет свободных мест |
| `RUDNIK_TAB` | Открыта таба рудника |
| `SELECT_LEVEL_VISIBLE` | Виден виджет `select_level.png` |
| `LEVEL_LIST_VISIBLE` | Открыт список уровней |
| `RAID_LEVEL_ICON_VISIBLE` | Видна иконка активной добычи |
| `FIND_VISIBLE` | Видна кнопка поиска |
| `GRIND_VISIBLE` | Кнопка начала добычи |
| `WORK_VISIBLE` | Кнопка "Работа" |
| `GO_VISIBLE` | Кнопка отправки отряда |
| `MY_RUDNIK_VISIBLE` | Отряд уже добывает |
| `RETURN_CONFIRM_VISIBLE` | Подтверждение отзыва отряда |
| `RETURN_BUTTON_VISIBLE` | Видна кнопка отзыва |
| `FINISH_VISIBLE` | Кнопка завершения после отзыва |
| `CONFIRM_VISIBLE` | Подтверждение после завершения |
| `SUMMARY_STRENGTH_TEXT_VISIBLE` | Попап "место занято" |
| `FREE_PLACE_VISIBLE` | Найдено свободное место |
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
    ↓ click EVENTS_IMG / BOOK_IMG
EVENTS_MENU_OPEN
    ↓ скролл вниз по центру списка, пока не найдётся GOLD_RUDNIK_IMG
EVENTS_RUDNIK_VISIBLE
    ↓ click GOLD_RUDNIK_IMG
FORWARD_POPUP_VISIBLE
    ↓ click GOLD_FORWARD_IMG
RUDNIK_TAB
    ↓ (проверка rudnik_opened.png / current_lvl / find / select_level)
```

### 3. Проверка и смена уровня

```
RUDNIK_TAB
    ↓ get_current_level()
Если current_lvl != GOLD_LEVEL:
    click select_level.png
        ↓
    SELECT_LEVEL_VISIBLE / LEVEL_LIST_VISIBLE
        ↓
    scroll_in_region() до появления lvl_GOLD_LEVEL.png
        ↓
    click_moveon_for_target_level() — клик по кнопке "Перейти" рядом с целевым уровнем
        ↓
    RUDNIK_TAB
```

### 4. Поиск и запуск добычи

```
RUDNIK_TAB
    ↓ click find.png
FIND_VISIBLE
    ↓ click find.png, пока не появится free_place.png
FREE_PLACE_VISIBLE
    ↓ click
GRIND_VISIBLE
    ↓ click
WORK_VISIBLE
    ↓ click
GO_VISIBLE
    ↓ click go.png
    ↓
Проверка return.png / my_rudnik.png
    ↓ Да
start_gold_mission() → update_gold_time() → COMPLETED
```

### 5. Ветка активной добычи

```
MY_RUDNIK_VISIBLE / RAID_LEVEL_ICON_VISIBLE
    ↓
Если recall_requested == True:
    click return.png → RETURN_CONFIRM_VISIBLE → return_boys.png
    ↓
    clear_gold_mission() → FIND_VISIBLE
Иначе:
    click current_raid_lvl_icon.png
    ↓
    RUDNIK_TAB → get_current_level()
    ↓
    Если elapsed >= GOLD_MINING_DURATION:
        recall_requested = True
    Иначе:
        update_gold_time() → COMPLETED
```

### 6. Отсутствие свободных мест

```
NO_FREE_RUDNIK
    ↓
Если видна select_level.png:
    Открыть список уровней
    Пробовать lvl_GOLD_LEVEL ± N по кругу
    Если уровень найден и свободен:
        click_moveon_for_target_level(alternative)
    Иначе после 10 попыток:
        COMPLETED
```

---

## Приоритет определения состояния (`determine_gold_state`)

1. Reconnect popup
2. `return_boys.png` → `RETURN_CONFIRM_VISIBLE`
3. `finish.png` → `FINISH_VISIBLE`
4. `confirm.png` → `CONFIRM_VISIBLE`
5. `summary_strength_text.png` → `SUMMARY_STRENGTH_TEXT_VISIBLE`
6. `return.png` → `RETURN_BUTTON_VISIBLE`
7. Цепочка `go.png` → `work.png` → `grind.png`
8. `free_place.png` → `FREE_PLACE_VISIBLE`
9. `my_rudnik.png` → `MY_RUDNIK_VISIBLE`
10. `current_raid_lvl_icon.png` → `RAID_LEVEL_ICON_VISIBLE`
11. `select_level.png` / `lvl_X.png` → `SELECT_LEVEL_VISIBLE` / `LEVEL_LIST_VISIBLE`
12. `rudnik_opened.png` / `current_lvl_X` / `find.png` → `RUDNIK_TAB`
13. `no_free_rudnik.png` → `NO_FREE_RUDNIK`
14. `forward.png` → `FORWARD_POPUP_VISIBLE`
15. `rudnik.png` → `EVENTS_RUDNIK_VISIBLE`
16. `back.png` без `events.png` → `EVENTS_MENU_OPEN`
17. `events.png` / `village.png` / `wild_earth.png` → `MAIN_SCREEN`
18. Иначе → `UNKNOWN`

---

## Функции модуля

### `should_do_gold()`
Проверить, прошло ли `GOLD_INTERVAL` с последнего посещения рудника. При первом запуске скрипта возвращает `True` сразу.

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
Распознать текущий открытый уровень по `current_lvl_1..6.png` (выбор по максимальному confidence).

### `get_list_level(screen_cv, region)`
Найти уровень в списке выбора по `lvl_1..6.png`.

### `is_target_level_in_list(screen_cv, region, target, threshold)`
Проверить, виден ли целевой уровень в списке.

### `click_moveon_for_target_level(screen_cv, region, target, ...)`
Найти ближайшую кнопку "Перейти" (`moveOn.png`) к тексту целевого уровня и кликнуть по ней. Проверяет, что кнопка не обрезана краем экрана.

### `determine_gold_state(screen_cv, region)`
Вернуть текущее состояние золотодобычи на основе приоритетной проверки изображений.

### `process_gold(screen_cv, region, last_gold_state, window)`
Выполнить ровно одно действие для текущего состояния и вернуть новое состояние.

### `process_gold_exit(screen_cv, region, last_exit_state, window)`
Последовательно нажимать `village.png`, `back.png`, `gold/close.png` или кликать по центру, пока не вернёмся на `MAIN_SCREEN`.

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

## Recovery при UNKNOWN

Если `determine_gold_state` вернул `UNKNOWN`, `process_gold` выполняет последовательность:
1. Ожидание завершения перехода после клика "Перейти" / открытия календаря.
2. Если ожидали календарь, но открылось активное событие — свайп по верхней карусели вправо.
3. Иначе: `back.png` → `gold/close.png` → `village.png`.

---

## Логирование

Пример успешного запуска:

```
[GOLD] Первый запуск скрипта — сразу запускаем золотодобычу.
[MAIN] Переключение в режим GOLD
[GOLD] Состояние: main_screen
[GOLD] Состояние: events_menu_open
[SCROLL] down: (640,468) -> (640,252)
[GOLD] Состояние: events_rudnik_visible
[GOLD] Состояние: forward_popup_visible
[GOLD] Состояние: rudnik_tab
[GOLD] Распознан текущий уровень: 4 (conf=0.912)
[GOLD] Состояние: rudnik_tab
[GOLD] Состояние: find_visible
[GOLD] Состояние: free_place_visible
[GOLD] Состояние: grind_visible
[GOLD] Состояние: work_visible
[GOLD] Состояние: go_visible
[GOLD] Отряд отправлен на уровень 4 в Mon Jun 22 14:00:00 2026
[GOLD] ✓ Золотодобыча запущена!
[MAIN] Золотодобыча завершена, возврат к лечению
```

---

## Ошибки

### "Кнопка Events не найдена"
- Проверьте, что вы в поселении.
- Убедитесь, что `events.png` / `book.png` соответствует иконке событий.

### "Рудник не найден в событиях"
- Проверьте `rudnik.png`.
- Убедитесь, что событие "Золотодобыча" активно и доступно в календаре.

### "Не удалось найти целевой уровень"
- Проверьте `select_level.png`, `lvl_1.png`...`lvl_6.png`, `moveOn.png`.
- При необходимости измените направление `scroll_in_region()` в `gold.py`.

### "Превышен таймаут поиска"
- Увеличьте `GOLD_SEARCH_TIMEOUT`.
- Проверьте `find.png` и `free_place.png`.

### "Не отзывается отряд"
- Проверьте `my_rudnik.png`, `return.png`, `return_boys.png`, `finish.png`, `confirm.png`.
- Убедитесь, что `current_raid_lvl_icon.png` открывает экран с `current_lvl_X.png`.

### "Нет свободных рудников"
- Проверьте `no_free_rudnik.png`.
- При необходимости уменьшите/увеличьте `GOLD_LEVEL`.
