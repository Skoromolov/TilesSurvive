# Рефакторинг gold.py: вынести параметры/состояние в модель данных

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Устранить дублирование, разделить данные (model) и логику (state-machine), сохранив порядок действий и семантику переходов `process_gold` + `main.py`.

**Architecture:**
- Ввести `GoldContext` (dataclass) вместо глобального `_gold_ctx` dict.
- Вынести таймеры/флаги персистентности (`last_gold_time`, `started_at`, `recall_requested`, `force_reclaim`, `current_mining_level`) в чёткий слой, общающийся с `state.py`.
- Убрать дублирующиеся ветки `GRIND_VISIBLE`, `SUMMARY/WORK/GO`, унифицировать цепочку захвата места.
- Все клики оставить в `process_gold`; helper-функции не должны решать, в какое состояние возвращаться — только возвращать результат действия.

**Tech Stack:** Python 3.13, OpenCV, pyautogui, существующие `config.py`, `utils.py`, `logger.py`, `state.py`.

---

## Текущие проблемы (найдено в `gold.py:823–1516`, `main.py:214–295`, `config.py:232–259`)

1. **Дублирование `GRIND_VISIBLE`**: обработка повторяется в двух местах (`gold.py:1044–1073` и `1088–1117`).
2. **Дублирование цепочки `SUMMARY/WORK/GO`**: `SUMMARY_STRENGTH_TEXT_VISIBLE` обрабатывается и в отдельной ветке (`gold.py:908–976`), и через `_rapid_capture_chain` (`gold.py:1084–1085`).
3. **Глобальный dict `_gold_ctx`**: поля не типизированы, рассинхрон легко не заметить. Ключи вида `'expected'`, `'started_at'`, `'force_reclaim'` дублируются строками.
4. **Персистентные таймеры перемешаны с волатильным контекстом**: `last_gold_time` — глобальная переменная модуля; `_gold_ctx['started_at']`/`recall_requested`/`force_reclaim` живут в dict, но пишутся в `state.py`.
5. **`_click_and_check_completion` объявлена дважды** (`gold.py:176` и `437`): вторая (более поздняя) перезаписывает первую, но обе версии различаются аргументами и логикой. Нужно оставить одну корректную.
6. **`process_gold_exit` не используется в `main.py`**: `main.py` вызывает `_return_to_main_screen`/`ensure_exit_to_main_screen` — либо задействовать единый exit helper, либо удалить мёртвый код.
7. **Дублирование логики `RETURN_BUTTON_VISIBLE` и `MY_RUDNIK_VISIBLE`**: обе проверяют `recall_requested`, кликают `return.png`, но `RETURN_BUTTON_VISIBLE` ещё и пытается `_complete_mission` при отсутствии recall — семантика разная, но общий кусок можно вынести.

---

## Task 1: Ввести `GoldContext` dataclass и единый слой persistence

**Objective:** Заменить `_gold_ctx` dict и глобальные переменные на типизированную модель.

**Files:**
- Modify: `gold.py:14–40` (заменить dict + global vars на dataclass)
- Create: `gold.py` внутри новый class `GoldContext`
- Modify: `state.py` (если нужно — оставить existing `LAST_GOLD_TIME_KEY`, `STARTED_AT_KEY`, `RECALL_REQUESTED_KEY`, `FORCE_RECLAIM_KEY`)

**Step 1: Определить dataclass**

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class GoldContext:
    expected: Optional[str] = None
    swipe_count: int = 0
    level_select_scroll_tries: int = 0
    stuck_count: int = 0
    stuck_last_action: Optional[str] = None
    events_clicked_at: Optional[float] = None
    moveon_clicked_at: Optional[float] = None
    current_mining_level: Optional[int] = None
    need_level_check: bool = False
    main_screen_tries: int = 0
    raid_icon_clicks: int = 0
    find_started_at: Optional[float] = None
    find_clicked_at: Optional[float] = None
    exit_attempts: int = 0

    # persistence (load/save via state.py)
    started_at: Optional[float] = None
    recall_requested: bool = False
    force_reclaim: bool = False

    def reset_transient(self):
        """Сброс волатильных полей при новом заходе в режим GOLD."""
        self.expected = None
        self.swipe_count = 0
        self.level_select_scroll_tries = 0
        self.stuck_count = 0
        self.stuck_last_action = None
        self.events_clicked_at = None
        self.moveon_clicked_at = None
        self.need_level_check = False
        self.main_screen_tries = 0
        self.raid_icon_clicks = 0
        self.find_started_at = None
        self.exit_attempts = 0
```

**Step 2: Заменить инициализацию**

```python
_saved_state = load_state()
last_gold_time = _saved_state.get(LAST_GOLD_TIME_KEY, time.time())
gold_first_run = True
_gold_ctx = GoldContext(
    recall_requested=_saved_state.get(RECALL_REQUESTED_KEY, False),
    started_at=_saved_state.get(STARTED_AT_KEY, None),
    force_reclaim=_saved_state.get(FORCE_RECLAIM_KEY, False),
)
```

**Step 3: Обновить все обращения `_gold_ctx['key']` → `_gold_ctx.key`** по файлу. Можно использовать поиск-замену, но каждое место проверить вручную.

**Step 4: Run compile check**

```bash
C:/Users/defaultuser0/AppData/Local/Programs/Python/Python313/python.exe -m py_compile gold.py
```

Expected: no syntax errors.

---

## Task 2: Удалить дублирующую `_click_and_check_completion`

**Objective:** Оставить одну реализацию helper’a, совместимую с `_rapid_capture_chain` и прочими ветками.

**Files:**
- Modify: `gold.py:176–210` (первая копия) и `gold.py:437–470` (вторая копия)

**Step 1: Удалить первое объявление `gold.py:176–210`**, оставить второе (`gold.py:437–470`).

**Step 2: Проверить все call sites**, что они передают нужные именованные аргументы (`post_click_delay`, `max_attempts`).

**Step 3: Run compile check**

```bash
C:/Users/defaultuser0/AppData/Local/Programs/Python/Python313/python.exe -m py_compile gold.py
```

---

## Task 3: Объединить дублирующиеся ветки `GRIND_VISIBLE` и `SUMMARY/WORK/GO`

**Objective:** Одна логика для каждого состояния; убрать повторы.

**Files:**
- Modify: `gold.py:978–1117`

### План реструктуризации `process_gold`

1. **Удалить** отдельную ветку `GRIND_VISIBLE` (`gold.py:1044–1073`) и оставить только ту, что ниже (`gold.py:1088–1117`), но переписать её через `_rapid_capture_chain`.
2. **Удалить** отдельную ветку `SUMMARY_STRENGTH_TEXT_VISIBLE`/`WORK_VISIBLE`/`GO_VISIBLE` (`gold.py:908–976`), т.к. `gold.py:1084–1085` уже делегирует в `_rapid_capture_chain`.
3. **Расширить `_rapid_capture_chain`** так, чтобы он корректно обрабатывал `SUMMARY_STRENGTH_TEXT_VISIBLE` с fallback на `WORK`/`GO` и закрытие при занятом месте.
4. **Сделать `GRIND_VISIBLE` → `FREE_PLACE_VISIBLE` / `SUMMARY` / `WORK` / `GO` единым входом в `_rapid_capture_chain(initial_state=GRIND_VISIBLE)`**, убрав ручные `find_and_click`.

**Step 1: Переписать ветку `GRIND_VISIBLE`**

```python
if current_state == GoldState.GRIND_VISIBLE:
    # grind.png — точка входа в цепочку захвата.
    # После клика может появиться free_place / summary / work / go — rapid chain разберётся.
    result, screen_after = _click_and_check_completion(
        GOLD_GRIND_IMG,
        "[GOLD] Нажимаем 'GRIND'.",
        window, screen_cv, region,
        post_click_delay=_GOLD_RAPID_POLL,
        max_attempts=3,
    )
    if result == 'completed':
        return _complete_mission("[GOLD] ✓ Золотодобыча запущена!")
    # Все остальные результаты (summary/go/wait/other) пусть обрабатывает rapid chain
    return _rapid_capture_chain(
        GoldState.SUMMARY_STRENGTH_TEXT_VISIBLE,
        screen_after or screen_cv,
        region,
        window,
    )
```

**Step 2: Удалить устаревшие ветки `SUMMARY_STRENGTH_TEXT_VISIBLE` и `GO_VISIBLE`/`WORK_VISIBLE` вне `_rapid_capture_chain`.**

**Step 3: Убедиться, что `_rapid_capture_chain` корректно обрабатывает `SUMMARY_STRENGTH_TEXT_VISIBLE`:**
- Сначала искать `GOLD_GO_IMG`.
- Если `GO` нет — искать `GOLD_WORK_IMG`.
- Если `WORK` нет — wait up to ~1 s, затем close to rudnik_tab.
- Если `result == 'summary'` → `_close_to_rudkin_tab`.
- Если `result == 'go'` → вернуть `SUMMARY_STRENGTH_TEXT_VISIBLE` для обработки GO на следующей итерации (или обработать внутри).

**Step 4: Run compile check**

```bash
C:/Users/defaultuser0/AppData/Local/Programs/Python/Python313/python.exe -m py_compile gold.py
```

---

## Task 4: Вынести общую логику recall в отдельный helper

**Objective:** `RETURN_BUTTON_VISIBLE` и `MY_RUDNIK_VISIBLE` оба кликают `return.png` при `recall_requested`; унифицировать.

**Files:**
- Modify: `gold.py:833–843` и `gold.py:1119–1180`

**Step 1: Создать helper `_try_recall(screen_cv, region, window=None)`**

```python
def _try_recall(screen_cv, region, window=None):
    """Если recall_requested — кликнуть return.png или my_rudnik.png -> return.png.
    Возвращает новое GoldState или None, если recall не требуется/невозможен.
    """
    return_coords, _ = find_on_screen(get_template(GOLD_RETURN_IMG), screen_cv, region)
    if return_coords:
        logger.info("[GOLD] Отряд занят добычей. Отзываем.")
        find_and_click(GOLD_RETURN_IMG, screen_cv, region)
        return GoldState.RETURN_CONFIRM_VISIBLE

    my_rudnik_coords, _ = find_on_screen(get_template(GOLD_MY_RUDNIK_IMG), screen_cv, region)
    if my_rudnik_coords:
        logger.info("[GOLD] Открываем детали рудника (my_rudnik.png) для отзыва.")
        find_and_click(GOLD_MY_RUDNIK_IMG, screen_cv, region)
        time.sleep(GOLD_ACTION_DELAY)
        return GoldState.UNKNOWN

    logger.info("[GOLD] recall_requested, но не видно ни return.png, ни my_rudnik.png. Ждём.")
    time.sleep(GOLD_ACTION_DELAY)
    return GoldState.UNKNOWN
```

**Step 2: В `RETURN_BUTTON_VISIBLE`**:

```python
if current_state == GoldState.RETURN_BUTTON_VISIBLE:
    if _gold_ctx.recall_requested:
        return _try_recall(screen_cv, region)
    current = get_current_level(screen_cv, region)
    if current:
        _gold_ctx.current_mining_level = current
    return _complete_mission("[GOLD] ✓ Золотодобыча запущена (return.png видна, отзыв не требуется).")
```

**Step 3: В `MY_RUDNIK_VISIBLE`/`RAID_LEVEL_ICON_VISIBLE`**:

```python
if current_state in (GoldState.MY_RUDNIK_VISIBLE, GoldState.RAID_LEVEL_ICON_VISIBLE):
    current = get_current_level(screen_cv, region)
    if current:
        _gold_ctx.current_mining_level = current

    needs_recall = _gold_ctx.recall_requested
    if not needs_recall:
        recall_status, _ = _check_recall_needed()
        needs_recall = recall_status == 'recall'

    if needs_recall:
        return _try_recall(screen_cv, region)

    # active mining, no recall -> complete
    started = _gold_ctx.started_at
    if started is not None:
        elapsed = int(time.time() - started)
        logger.info(f"[GOLD] Добыча активна ({elapsed//60} мин).")
    else:
        logger.info("[GOLD] Добыча активна, таймер синхронизирован.")

    if started is None:
        update_gold_time()
    return GoldState.COMPLETED
```

**Step 4: Run compile check**

```bash
C:/Users/defaultuser0/AppData/Local/Programs/Python/Python313/python.exe -m py_compile gold.py
```

---

## Task 5: Унифицировать persistence API (`update_gold_time`, `start_gold_mission`, `clear_gold_mission`)

**Objective:** Все обращения к `state.py` идут через чёткий интерфейс, чтобы `GoldContext` всегда синхронизирован с файлом.

**Files:**
- Modify: `gold.py:66–124`

**Step 1: Сделать функции методами или явно принимающими `GoldContext`**.

Оставим функциями, но пусть оперируют `_gold_ctx`:

```python
def update_gold_time():
    global last_gold_time
    last_gold_time = time.time()
    update_state(**{LAST_GOLD_TIME_KEY: last_gold_time})
    logger.info(f"[GOLD] Время обновлено: {time.ctime(last_gold_time)}")


def start_gold_mission():
    now = time.time()
    _gold_ctx.started_at = now
    _gold_ctx.current_mining_level = GOLD_LEVEL
    _gold_ctx.recall_requested = False
    update_state(**{STARTED_AT_KEY: now, RECALL_REQUESTED_KEY: False})
    logger.info(f"[GOLD] Отряд отправлен на уровень {GOLD_LEVEL} в {time.ctime()}")


def clear_gold_mission():
    _gold_ctx.started_at = None
    _gold_ctx.current_mining_level = None
    _gold_ctx.recall_requested = False
    update_state(**{STARTED_AT_KEY: None, RECALL_REQUESTED_KEY: False})
```

**Step 2: Удалить `global _gold_ctx` в тех функциях**, где он больше не нужен (dataclass mutable).

**Step 3: Run compile check**

```bash
C:/Users/defaultuser0/AppData/Local/Programs/Python/Python313/python.exe -m py_compile gold.py
```

---

## Task 6: Удалить или задействовать `process_gold_exit`

**Objective:** Убрать мёртвый код.

**Files:**
- Modify: `gold.py:1478–1516` и `main.py:258–295`

**Step 1: Проверить, используется ли `process_gold_exit` где-либо.**

```bash
grep -n "process_gold_exit" *.py
```

**Step 2: Если не используется — удалить весь блок `process_gold_exit`**. `main.py` уже вызывает `_return_to_main_screen`/`ensure_exit_to_main_screen`, что эквивалентно.

**Step 3: Run compile check**

```bash
C:/Users/defaultuser0/AppData/Local/Programs/Python/Python313/python.exe -m py_compile gold.py main.py
```

---

## Task 7: Унифицировать цепочку захвата места в `_rapid_capture_chain`

**Objective:** Одна функция обрабатывает все промежуточные состояния между `free_place` и `complete`, без дублирования.

**Files:**
- Modify: `gold.py:326–434`

**Step 1: Разделить внутренние состояния цепочки:**

- `FREE_PLACE_VISIBLE` → клик `free_place` → ждём `WORK`/`GO`/`completed`.
- `WORK_VISIBLE` / `SUMMARY_STRENGTH_TEXT_VISIBLE` → клик `work` → ждём `GO`/`completed`/`summary`.
- `GO_VISIBLE` → клик `go` → ждём `completed`/`summary`/`wait`.
- `MY_RUDNIK_VISIBLE` / `RETURN_BUTTON_VISIBLE` / `RAID_LEVEL_ICON_VISIBLE` → `completed`.

**Step 2: Сделать helper `_wait_for_state(window, region, targets, timeout=1.0, poll=0.05)`**, который делает polling и возвращает `(detected_state, screen)`.

```python
def _wait_for_state(window, region, targets, timeout=1.0, poll=0.05):
    """
    targets: dict {GoldState: img_path} или список (img_path, GoldState).
    Возвращает (state, screen) первого найденного или (None, screen).
    """
    start = time.time()
    while time.time() - start < timeout:
        screen = take_screenshot(window, region)
        if screen is None:
            time.sleep(poll)
            continue
        for img, state in targets:
            coords, _ = find_on_screen(get_template(img), screen, region)
            if coords:
                return state, screen
        time.sleep(poll)
    return None, screen if screen is not None else None
```

**Step 3: Переписать `_rapid_capture_chain` с использованием `_wait_for_state`:**

```python
def _rapid_capture_chain(initial_state, screen_cv, region, window):
    chain_start = time.time()
    screen = screen_cv
    last_state = initial_state

    while time.time() - chain_start < _GOLD_RAPID_CHAIN_TIMEOUT:
        current_state = determine_gold_state(screen, region)
        if current_state != last_state:
            logger.debug(f"[GOLD] Быстрая цепочка: {last_state.value} -> {current_state.value}")
            last_state = current_state

        if current_state in (GoldState.MY_RUDNIK_VISIBLE, GoldState.RETURN_BUTTON_VISIBLE, GoldState.RAID_LEVEL_ICON_VISIBLE):
            return _complete_mission("[GOLD] ✓ Золотодобыча уже активна.")

        if current_state == GoldState.GO_VISIBLE:
            result, screen = _click_and_check_completion(
                GOLD_GO_IMG, "[GOLD] Нажимаем 'Марш'.", window, screen, region,
                post_click_delay=_GOLD_RAPID_POLL, max_attempts=8,
            )
            if result == 'completed':
                return _complete_mission("[GOLD] ✓ Золотодобыча запущена через 'Марш'!")
            screen = _fresh_or_current(window, region, screen)
            continue

        if current_state in (GoldState.SUMMARY_STRENGTH_TEXT_VISIBLE, GoldState.WORK_VISIBLE):
            go_coords, _ = find_on_screen(get_template(GOLD_GO_IMG), screen, region)
            if go_coords:
                # go имеет приоритет — следующая итерация его обработает
                screen = _fresh_or_current(window, region, screen)
                continue
            work_coords, _ = find_on_screen(get_template(GOLD_WORK_IMG), screen, region)
            if not work_coords:
                if time.time() - chain_start > 1.5:
                    logger.info("[GOLD] В окне 'Общая сила' не появилась кнопка 'Добывать'. Закрываем.")
                    return _close_to_rudkin_tab(screen, region, window)
                screen = _fresh_or_current(window, region, screen)
                continue
            result, screen = _click_and_check_completion(
                GOLD_WORK_IMG, "[GOLD] Нажимаем 'Добывать'.", window, screen, region,
                post_click_delay=_GOLD_RAPID_POLL, max_attempts=8,
            )
            if result == 'completed':
                return _complete_mission("[GOLD] ✓ Золотодобыча запущена!")
            if result == 'summary':
                return _close_to_rudkin_tab(screen, region, window)
            screen = _fresh_or_current(window, region, screen)
            continue

        if current_state == GoldState.FREE_PLACE_VISIBLE:
            result, screen = _click_and_check_completion(
                GOLD_FREE_PLACE_IMG, "[GOLD] Нажимаем свободное место.", window, screen, region,
                post_click_delay=_GOLD_RAPID_POLL, max_attempts=3,
            )
            if result == 'completed':
                return _complete_mission("[GOLD] ✓ Золотодобыча запущена!")
            screen = _fresh_or_current(window, region, screen)
            if time.time() - chain_start > 1.0:
                logger.info("[GOLD] Свободное место не нажалось, продолжаем обычный цикл.")
                return GoldState.FREE_PLACE_VISIBLE
            continue

        if current_state == GoldState.GRIND_VISIBLE:
            result, screen = _click_and_check_completion(
                GOLD_GRIND_IMG, "[GOLD] Нажимаем 'GRIND'.", window, screen, region,
                post_click_delay=_GOLD_RAPID_POLL, max_attempts=3,
            )
            if result == 'completed':
                return _complete_mission("[GOLD] ✓ Золотодобыча запущена!")
            screen = _fresh_or_current(window, region, screen)
            continue

        # Вне цепочки — возвращаем управление
        return current_state

    logger.info("[GOLD] Быстрая цепочка превысила лимит времени. Возвращаем UNKNOWN.")
    return GoldState.UNKNOWN
```

**Step 4: Run compile check**

```bash
C:/Users/defaultuser0/AppData/Local/Programs/Python/Python313/python.exe -m py_compile gold.py
```

---

## Task 8: Убедиться, что `main.py` корректно использует новый `GoldContext`

**Objective:** `main.py` импортирует `_gold_ctx` и читает `.get('force_reclaim')`. После перехода на dataclass это сломается.

**Files:**
- Modify: `main.py:27–29`, `main.py:283–286`

**Step 1: Импорт оставить как есть**, т.к. `_gold_ctx` всё ещё существует как объект.

**Step 2: Заменить `_gold_ctx.get('force_reclaim')` → `_gold_ctx.force_reclaim`**.

```python
if last_gold_state == GoldState.COMPLETED:
    if _gold_ctx.force_reclaim:
        logger.info("[MAIN] Золотодобыча завершена, но нужно немедленно перезанять рудник. Продолжаем GOLD.")
        _gold_ctx.force_reclaim = False
        update_state(**{FORCE_RECLAIM_KEY: False})
        last_gold_state = None
        gold_start_time = time.time()
        continue
```

**Step 3: Проверить, что `reset_gold_context()` сбрасывает волатильные поля через `_gold_ctx.reset_transient()`**.

**Step 4: Run compile check**

```bash
C:/Users/defaultuser0/AppData/Local/Programs/Python/Python313/python.exe -m py_compile main.py gold.py
```

---

## Task 9: Полная проверка всех обращений к `_gold_ctx`

**Objective:** Гарантировать, что ни одно `_gold_ctx['...']` не осталось.

**Files:**
- Modify: `gold.py`, `main.py`

**Step 1: Поиск старых обращений**

```bash
grep -n "_gold_ctx\['" gold.py main.py
```

Expected: пустой вывод.

**Step 2: Поиск `.get(` на `_gold_ctx`**

```bash
grep -n "_gold_ctx\.get" gold.py main.py
```

Expected: пустой вывод (или только если намеренно оставили для default).

**Step 3: Run full compile suite**

```bash
C:/Users/defaultuser0/AppData/Local/Programs/Python/Python313/python.exe -m py_compile main.py heal.py raid.py gold.py config.py utils.py adventure.py logger.py state.py
```

Expected: all compiled successfully.

---

## Task 10: Обновить README/docs если меняется внешний интерфейс

**Objective:** Синхронизировать документацию с новой архитектурой.

**Files:**
- Read: `README.md`, `docs/gold-ui-calendar-flow.md` (или `references/gold-ui-calendar-flow.md` в skill)
- Modify: любые места, где упоминается `_gold_ctx` как dict

**Step 1: Поиск упоминаний `_gold_ctx`**

```bash
grep -R "_gold_ctx" README.md docs/ references/ 2>/dev/null || true
```

**Step 2: Обновить или добавить заметку**, что gold state теперь `GoldContext` dataclass.

**Step 3: Run docs sync check (если есть скрипт)**.

---

## Risks / Tradeoffs

- **Risk:** Переход с dict на dataclass сломает любой сторонний скрипт, импортирующий `_gold_ctx` и использующий dict-API. Поищем по всему репо.
- **Risk:** Объединение `SUMMARY/WORK/GO` в `_rapid_capture_chain` может изменить порядок кликов. После каждого изменения нужно trace через логи/ PlantUML flow.
- **Risk:** Удаление `process_gold_exit` — если где-то есть старый вызов. Проверить `grep`.
- **Tradeoff:** dataclass увеличивает бойлерплейт, но убирает опечатки в строковых ключах. Приемлемо.

## Open questions

1. Нужно ли добавить unit-тест на `GoldContext`? В проекте нет тестовой инфраструктуры, поэтому пока ограничимся `py_compile` + ручной trace.
2. Стоит ли вынести `GoldContext` в отдельный файл `models.py`? Пока оставить в `gold.py`, чтобы не плодить файлы. Если позже появятся другие dataclass модели — вынести.
3. Нужно ли сохранять `current_mining_level` в `state.py`? Сейчас нет — оставить как есть, чтобы не усложнять.

## Acceptance criteria

- [ ] `gold.py` компилируется без ошибок.
- [ ] `main.py` компилируется без ошибок.
- [ ] Все модули проекта (`main.py heal.py raid.py gold.py config.py utils.py adventure.py logger.py state.py`) компилируются.
- [ ] В `gold.py`/`main.py` не осталось `_gold_ctx['...']` или `_gold_ctx.get(...)`.
- [ ] Дублирующие ветки `GRIND_VISIBLE` и `SUMMARY/WORK/GO` удалены; осталась одна цепочка через `_rapid_capture_chain`.
- [ ] `_click_and_check_completion` существует в единственном экземпляре.
- [ ] `process_gold_exit` удалён (или задействован в `main.py`).
- [ ] `GoldContext` — dataclass с типизированными полями.
- [ ] Пользователь перезапускает бота `python -B main.py` после применения изменений.
