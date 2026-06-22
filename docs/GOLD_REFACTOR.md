# Рефакторинг gold.py — краткое описание изменений

## Проблема
Старый `process_gold()` был линейной цепочкой вызовов:
1. Скриншот → 2. Клик Events → 3. Скриншот → 4. Клик Рудник → 5. Найти → 6. grind/work/go

Если игра показала рекламу, лаг или неожиданное окно в середине цепочки — весь золотой процесс падал с ошибкой либо зависал.

## Решение — стейт-машина по аналогии с `heal.py` и `raid.py`

### 1. Enum `GoldState` (`config.py`)

```
MAIN_SCREEN → EVENTS_OPEN → EVENTS_NEED_SCROLL → RUDNIK_TAB
                                                ↓
                    SELECT_LEVEL_VISIBLE → LEVEL_LIST_VISIBLE
                                                ↓
                                            RUDNIK_TAB
                                                ↓
FIND_VISIBLE → FREE_PLACE_VISIBLE → GRIND_VISIBLE → WORK_VISIBLE → GO_VISIBLE → COMPLETED

MY_RUDNIK_VISIBLE / RAID_LEVEL_ICON_VISIBLE → RETURN_CONFIRM_VISIBLE → FIND_VISIBLE
```

Добавлены состояния:
- `EVENTS_NEED_SCROLL` — меню событий открыто, но рудник не влезает.
- `SELECT_LEVEL_VISIBLE`, `LEVEL_LIST_VISIBLE` — выбор уровня 1–6.
- `RAID_LEVEL_ICON_VISIBLE` — иконка активной добычи.
- `FREE_PLACE_VISIBLE` — свободное место после поиска.

### 2. `determine_gold_state(screen_cv, region)`
- Сканирует экран в порядке приоритета (reconnect → workflow → my_rudnik → current level → events → поселение).
- Возвращает **ровно одно** текущее состояние.
- Каждая итерация main-цикла получает свежий скриншот и переоценивает реальное состояние.

### 3. `process_gold(screen_cv, region, last_gold_state, window)`
- Принимает старое состояние.
- Делает **ровно один клик** за вызов.
- Возвращает новое состояние (`GoldState`).
- Recovery: при `UNKNOWN` клики Back → Close → Village.

### 4. Вспомогательные функции (`gold.py`)
- `get_current_level()` — распознаёт `current_lvl_1..6.png`.
- `get_list_level()` — находит `lvl_1..6.png` в списке.
- `click_level_go_button()` — кликает в нижнюю часть карточки целевого уровня.
- `gold_mission_active()` / `gold_mission_should_recall()` — таймер 45-минутной добычи.
- `start_gold_mission()` / `clear_gold_mission()` — учёт активной добычи.
- `reset_gold_context()` — сброс `_gold_ctx` при входе в режим GOLD.

### 5. `utils.py`
- `find_all_on_screen()` — множественный матч для групповых элементов.
- `swipe_horizontal()` — свайп по верхней части окна (для листания событий).
- `scroll_in_region()` — вертикальный drag для списка уровней.

### 6. `main.py`
- Триггер `GOLD_ENABLED and (should_do_gold() or gold_mission_should_recall())` для автопереключения и `FORCE_HEAL_ONLY`.
- Вызов `reset_gold_context()` при каждом переключении в GOLD.
- `GOLD_TIMEOUT` увеличен до 300 секунд из-за более сложного флоу.

## Ключевое отличие
- **Раньше**: один вызов `process_gold()` выполнял всю цепочку, не проверяя реальный экран между шагами.
- **Теперь**: каждые ~1 секунду делается скриншот, определяется реальное состояние, выполняется один клик. Если UI сбился — следующая итерация увидит реальное состояние и восстановит workflow.

## Добавленные/изменённые константы (`config.py`)
- `GOLD_LEVEL = 1` — целевой уровень рудника (1–6).
- `GOLD_MINING_DURATION = 2700` — 45 минут активной добычи.
- `GOLD_TIMEOUT = 300` — таймаут всего процесса.
- Новые пути к изображениям золотодобычи.
- Расширен `GoldState` (17 состояний).

## Файлы затронутые изменениями

| Файл | Изменения |
|------|-----------|
| `config.py` | + `GOLD_LEVEL`, `GOLD_MINING_DURATION`, новые image-пути, расширен `GoldState` |
| `utils.py` | + `find_all_on_screen`, `swipe_horizontal`, `scroll_in_region` |
| `gold.py` | полностью переписан: новая стейт-машина, выбор уровня, отзыв отряда по таймеру |
| `main.py` | триггер по `gold_mission_should_recall`, `reset_gold_context()` |
| `docs/GOLD_MODULE.md` | актуальная документация по флоу |
| `README.md` | описание нового флоу и конфигурации |
