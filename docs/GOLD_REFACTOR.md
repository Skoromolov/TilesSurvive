# Рефакторинг gold.py — краткое описание изменений

## Проблема

Старый `process_gold()` был линейной цепочкой вызовов:
1. Скриншот → 2. Клик Events → 3. Скриншот → 4. Клик Рудник → 5. Найти → 6. grind/work/go.

Если игра показала рекламу, лаг или неожиданное окно в середине цепочки — весь золотой процесс падал с ошибкой либо зависал.

---

## Решение — стейт-машина по аналогии с `heal.py` и `raid.py`

### 1. Enum `GoldState` (`config.py`)

```
MAIN_SCREEN → EVENTS_MENU_OPEN → EVENTS_RUDNIK_VISIBLE → FORWARD_POPUP_VISIBLE → RUDNIK_TAB
                                                    ↓
                    SELECT_LEVEL_VISIBLE → LEVEL_LIST_VISIBLE
                                                    ↓
                                                RUDNIK_TAB
                                                    ↓
FIND_VISIBLE → FREE_PLACE_VISIBLE → GRIND_VISIBLE → WORK_VISIBLE → GO_VISIBLE
                                                    ↓
                         (return.png / my_rudnik.png) → COMPLETED

MY_RUDNIK_VISIBLE / RAID_LEVEL_ICON_VISIBLE
  ↓ recall_requested == True
RETURN_CONFIRM_VISIBLE → FINISH_VISIBLE / CONFIRM_VISIBLE → FIND_VISIBLE
```

Добавлены состояния:
- `EVENTS_MENU_OPEN` — календарь событий открыт, но `rudnik.png` ещё не виден.
- `EVENTS_RUDNIK_VISIBLE` — `rudnik.png` найден в календаре.
- `EVENTS_NEED_SCROLL` — календарь открыт, требуется скролл вниз для поиска рудника.
- `FORWARD_POPUP_VISIBLE` — попап события с кнопкой "Вперёд" (`forward.png`).
- `NO_FREE_RUDNIK` — на текущем уровне нет свободных мест.
- `RETURN_BUTTON_VISIBLE`, `RETURN_CONFIRM_VISIBLE`, `FINISH_VISIBLE`, `CONFIRM_VISIBLE` — цепочка отзыва отряда.
- `SUMMARY_STRENGTH_TEXT_VISIBLE` — попап "место занято".

### 2. `determine_gold_state(screen_cv, region)`

- Сканирует экран в строгом порядке приоритета (reconnect → return/finish/confirm → workflow → my_rudnik → current level → events → main screen).
- Возвращает **ровно одно** текущее состояние.
- Каждая итерация main-цикла получает свежий скриншот и переоценивает реальное состояние.

### 3. `process_gold(screen_cv, region, last_gold_state, window)`

- Принимает старое состояние.
- Делает **ровно один клик** за вызов.
- Возвращает новое состояние (`GoldState`).
- Recovery при `UNKNOWN`: ожидание переходов, свайп по верхней карусели, затем `back.png` → `gold/close.png` → `village.png`.

### 4. Вспомогательные функции (`gold.py`)

- `get_current_level()` — распознаёт `current_lvl_1..6.png` по максимальному confidence.
- `get_list_level()` — находит `lvl_1..6.png` в списке.
- `is_target_level_in_list()` — проверяет видимость целевого уровня.
- `click_moveon_for_target_level()` — кликает по ближайшей кнопке "Перейти" (`moveOn.png`) рядом с текстом уровня.
- `gold_mission_active()` / `gold_mission_should_recall()` — таймер 45-минутной добычи.
- `start_gold_mission()` / `clear_gold_mission()` — учёт активной добычи.
- `reset_gold_context()` — сброс `_gold_ctx` при входе в режим GOLD.

### 5. `utils.py`

- `find_all_on_screen()` — множественный матч для групповых элементов.
- `swipe_horizontal()` — горизонтальный свайп по верхней части окна.
- `scroll_in_region()` — вертикальный drag для списка уровней и календаря событий.

### 6. `main.py`

- Триггер `GOLD_ENABLED and (should_do_gold() or gold_mission_should_recall())` для автопереключения и `FORCE_HEAL_ONLY`.
- Вызов `reset_gold_context()` при каждом переключении в GOLD.
- `GOLD_TIMEOUT` 300 секунд — защита от зависания.
- Обработка `GoldState.COMPLETED` для возврата к HEAL.

---

## Ключевое отличие

- **Раньше**: один вызов `process_gold()` выполнял всю цепочку, не проверяя реальный экран между шагами.
- **Теперь**: каждые ~0.1–1 секунды делается скриншот, определяется реальное состояние, выполняется один клик. Если UI сбился — следующая итерация увидит реальное состояние и восстановит workflow.

---

## Добавленные/изменённые константы (`config.py`)

- `GOLD_LEVEL = 4` — целевой уровень рудника (1–6).
- `GOLD_MINING_DURATION = 2700` — 45 минут активной добычи.
- `GOLD_INTERVAL = 2700` — интервал между заходами.
- `GOLD_TIMEOUT = 300` — таймаут всего процесса.
- `GOLD_LEVEL_CONFIDENCE_THRESHOLD = 0.90` — распознавание текущего уровня.
- `GOLD_LIST_LEVEL_CONFIDENCE_THRESHOLD = 0.90` — поиск уровня в списке.
- `GOLD_LOOP_DELAY = 0.1` / `GOLD_ACTION_DELAY = 0.05` — тайминги итераций.
- Новые пути к изображениям: `forward.png`, `no_free_rudnik.png`, `moveOn.png`, `summary_strength_text.png`, `gold/close.png`.
- Расширен `GoldState` (25+ состояний).

---

## Файлы, затронутые изменениями

| Файл | Изменения |
|------|-----------|
| `config.py` | GOLD_LEVEL, GOLD_INTERVAL, GOLD_MINING_DURATION, GOLD_TIMEOUT, confidence thresholds, новые image-пути, расширен GoldState |
| `utils.py` | `find_all_on_screen`, `swipe_horizontal`, `scroll_in_region` |
| `gold.py` | Полностью переписан: стейт-машина, forward-попап, выбор уровня, отзыв отряда, recovery, no_free_rudnik |
| `main.py` | Триггеры GOLD, reset_gold_context(), защитный таймаут, возврат COMPLETED |
| `heal.py` | `FAST_HEAL_FROM_MAP_ENABLED`, ambulance, heal_help_with_time |
| `docs/GOLD_MODULE.md` | Актуальная документация по flow |
| `docs/logic.md` | Актуальная логика всех модулей |
| `README.md` | Описание нового flow, UML, конфигурации |
| `docs/AGENTS.md` | Инструкции для AI по новым ассетам и режимам |
