# Heal and Raid Bot

Автоматизированный бот для лечения войск и участия в рейдах в игре через эмулятор BlueStacks.

## Описание

Скрипт автоматически:
- **Лечит войска** — находит и нажимает кнопки лечения, использует бесплатные лечение
- **Участвует в рейдах** — присоединяется к активным рейдам, управляет маршами
- **Добывает золото** — автоматизирует событие "Золотодобыча":
  - открывает меню событий и свайпит вправо, пока не найдёт рудник;
  - переключается на заданный уровень 1–6;
  - ищет свободное место, начинает добычу и отправляет отряд;
  - если отряд уже добывает, проверяет уровень и отзывает его через 45 минут для перезапуска.
- **Помогает союзу** — кликает по кнопкам помощи когда доступны
- **Собирает почту** — забирает награды из почты
- **Обрабатывает ошибки** — переподключение при разрывах соединения

## Требования

- **Python 3.8+**
- **Эмулятор BlueStacks** (или аналогичный с именем окна "BlueStacks App Player")
- **Windows** (используются win32 API для захвата экрана)

## Установка зависимостей

```bash
pip install -r requirements.txt
```

Или вручную:
```bash
pip install numpy opencv-python pyautogui pygetwindow pywin32 pynput
```

## Структура проекта

```
.
├── main.py                      # Точка входа, основной цикл
├── config.py                    # Конфигурация, константы, настройки
├── utils.py                     # Общие утилиты (скриншоты, поиск, окно)
├── heal.py                      # Логика лечения (стейт-машина)
├── raid.py                      # Логика рейдов (стейт-машина)
├── gold.py                      # Логика золотодобычи (стейт-машина)
├── heal_and_raid_backup.txt     # Устаревший монолитный файл (не запускать)
├── requirements.txt             # Зависимости
├── README.md                    # Этот файл
├── docs/                        # Документация
│   ├── logic.md                 # Подробная документация по логике работы
│   ├── GOLD_MODULE.md           # Документация по модулю золота
│   ├── REFACTORING_SUMMARY.md   # Резюме разделения на модули
│   ├── GOLD_REFACTOR.md         # Краткое описание рефакторинга gold.py
│   └── AGENTS.md                # Инструкции для AI-ассистентов
├── archive/                     # Архив старых скриптов
│   ├── addReid.py
│   ├── heal.py
│   └── heal_help.py
├── pictures/                    # Изображения для распознавания
│   ├── common/                  # Общие элементы интерфейса
│   ├── heal/                    # Элементы лечения
│   ├── help/                    # Элементы помощи союзу
│   ├── raid/                    # Элементы рейдов
│   └── gold/                    # Элементы золотодобычи (см. pictures/gold/README.md)
└── waterbass/                   # Папка с данными (csv, xlsx, скриншоты)
```

## Настройка

### Режимы работы

В файле `config.py` настройте режим работы:

```python
# Только лечение (игнорирует рейды)
FORCE_HEAL_ONLY = True
FORCE_RAID_ONLY = False
FAST_HEAL_FROM_MAP_ENABLED = False

# Только рейды (игнорирует лечение)
FORCE_HEAL_ONLY = False
FORCE_RAID_ONLY = True
FAST_HEAL_FROM_MAP_ENABLED = False

# Быстрое лечение с карты мира (высший приоритет)
FORCE_HEAL_ONLY = False
FORCE_RAID_ONLY = False
FAST_HEAL_FROM_MAP_ENABLED = True

# Автопереключение между лечением и рейдами (по умолчанию)
FORCE_HEAL_ONLY = False
FORCE_RAID_ONLY = False
FAST_HEAL_FROM_MAP_ENABLED = False
```

### Золотодобыча

```python
GOLD_ENABLED = True               # Включить автоматизацию золотодобычи
GOLD_INTERVAL = 1800              # 30 минут между проверками (сек)
GOLD_LEVEL = 3                    # Уровень рудника 1–6, на котором работаем
GOLD_MINING_DURATION = 2700       # 45 минут = 2700 сек; после этого отзываем отряд
GOLD_SEARCH_TIMEOUT = 60          # Таймаут поиска рудника (сек)
GOLD_TIMEOUT = 300                # Максимальное время всего процесса (сек)
```

### Чувствительность распознавания

Основные параметры в файле `config.py`:

| Параметр | Значение | Описание |
|----------|----------|----------|
| `CONFIDENCE_THRESHOLD` | 0.70 | Стандартный порог обнаружения |
| `CONFIDENCE_HIGH` | 0.95 | Высокий порог для критических элементов |
| `MARCH_THRESHOLD` | 0.90 | Порог кнопки "Марш" |
| `NAVIGATION_THRESHOLD` | 0.90 | Порог навигационных элементов |
| `RAID_JOIN_TIMEOUT` | 120 | Секунды ожидания рейда перед возвратом к лечению |
| `GOLD_INTERVAL` | 1800 | Секунды между проверками рудника |
| `GOLD_LEVEL` | 1 | Целевой уровень рудника (1–6) |
| `GOLD_MINING_DURATION` | 2700 | Длительность добычи перед отзывом (45 мин) |
| `GOLD_TIMEOUT` | 300 | Максимальное время золотодобычи (5 мин) |

### Подготовка изображений

1. Сделайте скриншоты элементов интерфейса игры
2. Сохраните их в соответствующие папки:
   - `pictures/common/` — общие элементы (кнопки навигации, почта, события, поселение и т.д.)
   - `pictures/heal/` — элементы меню лечения
   - `pictures/help/` — элементы помощи союзу
   - `pictures/raid/` — элементы рейдов
   - `pictures/gold/` — элементы золотодобычи (см. `pictures/gold/README.md`)

**Важно:** Имена файлов должны совпадать с теми, что указаны в коде (см. раздел "КОНСТАНТЫ ИЗОБРАЖЕНИЙ"). Для золотодобычи также требуются:
`events.png`, `select_level.png`, `lvl_1.png`...`lvl_6.png`, `current_lvl_1.png`...`current_lvl_6.png`,
`current_raid_lvl_icon.png`, `free_place.png`. Дополнительно могут понадобиться `hand.png`, `confirm.png`, `finish.png`.

## Запуск

```bash
python main.py
```

### Предварительные шаги

1. **Запустите BlueStacks** и откройте игру
2. **Убедитесь, что окно называется** "BlueStacks App Player" (или измените `BLUESTACKS_WINDOW_TITLE` в `config.py`)
3. **Запустите скрипт** — он автоматически активирует окно BlueStacks

> **Не запускайте** `heal_and_raid.py` — это устаревший монолитный файл, сохранённый для истории.

### Работа скрипта

#### Режим лечения

Скрипт автоматически:
- Находит и открывает меню лечения
- Использует бесплатные лечения
- Обрабатывает окна ожидания
- Помогает союзу когда доступно
- Собирает почту с наградами

```plantuml
@startuml
skinparam backgroundColor #FEFEFE
title Режим лечения (HealState machine)

start

while (true) is (каждую секунду)
  :Скриншот окна;

  if (RECONNECT popup?) then (да)
    :handle_reconnect();
  elseif (FAST_USE popup?) then (да)
    :Нажать close.png;
  elseif (MAIL icon?) then (да)
    :Открыть/закрыть почту;
  elseif (HEAL icon?) then (да)
    :Нажать heal_town.png;
  elseif (HELP HANDS?) then (да)
    :Нажать help_hands.png;
  elseif (HEAL menu open?) then (да)
    if (free heal?) then (да)
      :Нажать free_heal.png;
    else (нет)
      :Нажать heal.png;
    endif
  elseif (CONFIRM button?) then (да)
    :Нажать confirm.png;
  elseif (UNKNOWN?) then (да)
    :Нажать village.png -> back.png -> close.png;
    :Если нет ключевых иконок — клик вверх экрана;
  endif
endwhile

stop

@enduml
```

#### Режим рейдов

Скрипт автоматически:
- Ищет доступные рейды
- Присоединяется к рейдам при возможности
- Управляет маршами
- Обрабатывает отсутствие свободных мест
- Прокручивает список рейдов при необходимости

```plantuml
@startuml
skinparam backgroundColor #FEFEFE
title Режим рейдов (RaidState machine)

start

while (true) is (до RAID_COMPLETED / NO_REIDS)
  :Скриншот окна;

  if (RECONNECT popup?) then (да)
    :handle_reconnect();
  elseif (NAVIGATION_NEEDED?) then (да)
    :Союз -> Новости -> Рейды;
  elseif (REID tab not active?) then (да)
    :Нажать raid_not_active.png;
  elseif (RAID_FULL / NO_FREE_SPACE?) then (да)
    :Нажать ok.png;
  elseif (PLUS_VISIBLE?) then (да)
    :Нажать raid_plus.png;
    if (MARCH visible?) then (да)
      :Нажать raid_march.png;
    endif
  elseif (MARCH_VISIBLE?) then (да)
    :Нажать raid_march.png;
    :Проверить NO_FREE_SPACE -> OK;
  elseif (NEEDS_SCROLL?) then (да)
    :Скролл списка рейдов;
  elseif (RAID_IN_PROGRESS?) then (да)
    :Ждать;
  elseif (NO_REIDS?) then (да)
    :Вернуться к HEAL;
    stop
  elseif (RAID_COMPLETED?) then (да)
    :Вернуться к HEAL;
    stop
  endif
endwhile

stop

@enduml
```

#### Автопереключение

В режиме автопереключения:
- Скрипт проверяет доступность рейдов во время лечения
- При нахождении рейда → переключается в режим рейдов
- Если за 2 минуты не удалось присоединиться → возвращается к лечению
- Цикл повторяется

```plantuml
@startuml
skinparam backgroundColor #FEFEFE
title Автопереключение режимов

start

:current_mode = HEAL;

while (true) is (цикл)
  :Скриншот;

  if (FAST_HEAL_FROM_MAP?) then (да)
    :process_fast_heal_from_map();
  elseif (FORCE_RAID_ONLY?) then (да)
    :process_raid();
  elseif (FORCE_HEAL_ONLY?) then (да)
    if (should_do_gold?) then (да)
      :current_mode = GOLD;
    else (нет)
      :process_heal();
    endif
  else (авто)
    if (current_mode == HEAL?) then (да)
      if (GOLD_ENABLED и пора?) then (да)
        :current_mode = GOLD;
      elseif (raid button найдена?) then (да)
        :current_mode = RAID;
      else (нет)
        :process_heal();
      endif
    elseif (current_mode == GOLD?) then (да)
      :process_gold();
      if (COMPLETED?) then (да)
        :current_mode = HEAL;
      elseif (TIMEOUT?) then (да)
        :current_mode = HEAL;
      endif
    elseif (current_mode == RAID?) then (да)
      :process_raid();
      if (RAID_COMPLETED / NO_REIDS?) then (да)
        :current_mode = HEAL;
      elseif (RAID_JOIN_TIMEOUT без join?) then (да)
        :current_mode = HEAL;
      endif
    endif
  endif
endwhile

stop

@enduml
```

#### Золотодобыча

В режиме лечения (если `GOLD_ENABLED = True`):
- **При первом запуске скрипта** сразу переключается в режим GOLD.
- **После успешного старта добычи** ждёт `GOLD_INTERVAL` (по умолчанию **30 минут**), затем снова идёт искать место.
- **Активная добыча** длится `GOLD_MINING_DURATION` (по умолчанию **45 минут**), после чего отряд отзывается и бот ищет новое место.
- Выполняет процесс:
  1. Открывает события (`events.png`) и свайпит вправо по верхней полосе, пока не найдёт рудник (`rudnik.png` / `rudnik_opened.png`).
  2. Проверяет текущий уровень (`current_lvl_X`).
  3. При необходимости открывает выбор уровня (`select_level.png`), скроллит список `lvl_X.png` и нажимает «Перейти» в карточке целевого уровня.
  4. Нажимает «Поиск» (`find.png`), пока не появится `free_place.png`.
  5. grind → work → go — отправляет отряд.
  6. Проверяет, что рудник занят (`return.png` / `my_rudnik.png`). Если `return.png` видна **без** запроса отзыва — считает запуск успешным и выходит в HEAL.
- Если отряд уже добывает (`my_rudnik.png` / `current_raid_lvl_icon.png`) и прошло 45 минут, открывает детали, определяет уровень и отзывает отряд.
- Возвращается к лечению (с таймаутом защиты `GOLD_TIMEOUT`).

> Золотодобыча реализована как **стейт-машина** (`determine_gold_state` + `process_gold`), аналогично лечению и рейдам. Это делает процесс устойчивым к неожиданным всплывающим окнам и лагам интерфейса — каждая итерация снимает актуальный скриншот и действует исходя из реального состояния экрана.

##### Схема процесса золотодобычи (PlantUML)

```plantuml
@startuml
skinparam backgroundColor #FEFEFE
title Процесс золотодобычи (GoldState machine)

start

if (GOLD_ENABLED?) then (нет)
  :Остаёмся в HEAL;
  stop
endif

if (Первый запуск?) then (да)
  :Сразу перейти в GOLD;
else (нет)
  if (Прошло GOLD_INTERVAL\n30 минут?) then (нет)
    :Ожидание;
    stop
  endif
endif

:main_screen;
:Нажать events.png;
:Ждать открытия меню событий;

while (rudnik.png /\nrudnik_opened.png?) is (нет)
  :Свайп вправо по верхней полосе;
endwhile (да)

:rudnik_tab;
:Определить current_lvl_X;

if (Уровень == GOLD_LEVEL?) then (нет)
  :Нажать select_level.png;
  while (Целевой lvl_X?) is (нет)
    :Скролл списка уровней;
  endwhile
  :Нажать Перейти\n(moveOn.png в карточке уровня);
endif

repeat
  :Нажать find.png;
  :Искать free_place.png;
repeat while (free_place.png?) is (нет) not (да)

:grind.png → work/join.png → go.png;

if (return.png / my_rudnik.png\nпосле Марш?) then (да)
  :Запуск засчитан;
  :start_gold_mission();
  :update_gold_time();
  :Вернуться в HEAL;
  stop
else (нет)
  if (SummaryStrenghtText popup?) then (да)
    if (join.png в попапе?) then (да)
      :Нажать join.png;
      :Повторить work → go;
    else (нет)
      :Нажать pictures/gold/close.png;
    endif
  else (нет)
    :Нажать pictures/gold/close.png;
  endif
  :Вернуться в rudnik_tab;
endif

while (Отряд добывает?) is (да)
  :Проверить current_raid_lvl_icon\nи current_lvl_X;
  if (Прошло 45 минут?) then (да)
    :recall_requested = true;
    :Отозвать отряд (return.png → confirm → finish);
    :Искать новое место;
  else (нет)
    :Вернуться в HEAL;
  endif
endwhile (нет)

stop

@enduml
```

## Обработка ошибок

- **Переподключение** — автоматическое при разрывах соединения
- **Окно не найдено** — повторная попытка каждые 5 секунд
- **Элемент не найден** — продолжение работы без действия

## Отладка

Скриншоты сохраняются в папку `debug_screenshots/` с временными метками:
```
debug_screenshots/
├── 20250101_120000_heal_icon.png
├── 20250101_120015_raid_state.png
└── ...
```

Используйте функцию `save_debug_screenshot()` для сохранения состояний интерфейса.

## Логирование

Скрипт выводит детальный лог в консоль:
```
[СИСТЕМА] Запуск объединенного скрипта лечения и рейдов
[СИСТЕМА] Определено окно BlueStacks: region=(100, 100, 1280, 720)
[MAIN] Режим HEAL: last_heal_state=None, current_state=MAIN_SCREEN
[PROCESS_HEAL] Лечение: main_screen
[RAID] Вкладка рейдов НЕ активна (conf=0.923). Требуется клик для активации.
```

## Структура кода

### Основные функции

| Функция | Модуль | Описание |
|---------|--------|----------|
| `main()` | `main.py` | Основной цикл работы |
| `process_heal()` | `heal.py` | Обработка состояния лечения |
| `determine_heal_state()` | `heal.py` | Определение текущего состояния лечения |
| `process_raid()` | `raid.py` | Обработка состояния рейда |
| `determine_raid_state()` | `raid.py` | Определение текущего состояния рейда |
| `process_gold()` | `gold.py` | Обработка одного шага золотодобычи |
| `determine_gold_state()` | `gold.py` | Определение текущего состояния золотодобычи |
| `process_gold_exit()` | `gold.py` | Возврат из рудника в поселение |
| `navigate_to_reid_window()` | `raid.py` | Навигация к окну рейдов |
| `find_and_click()` | `utils.py` | Поиск элемента и клик по нему |
| `take_screenshot()` | `utils.py` | Создание скриншота области окна |

### Утилиты

| Функция | Описание |
|---------|----------|
| `get_window_region()` | Получение области окна BlueStacks |
| `prepare_template()` | Подготовка шаблона для распознавания |
| `find_on_screen()` | Поиск шаблона на экране |
| `find_all_on_screen()` | Поиск всех вхождений шаблона |
| `swipe_horizontal()` | Горизонтальный свайп в области окна |
| `scroll_in_region()` | Вертикальный скролл в области окна |
| `count_attack_mentions()` | Подсчёт активных рейдов |
| `check_and_scroll_for_attack()` | Скроллинг списка рейдов |
| `should_do_gold()` | Проверка таймера золотодобычи |
| `gold_mission_should_recall()` | Проверка 45-минутного таймера добычи |
| `handle_reconnect()` | Обработка переподключения |
| `save_debug_screenshot()` | Сохранение отладочных скриншотов |

## Архитектура (стейт-машины)

Все три режима работают по единому паттерну:
1. **Скриншот** → 2. **Определить состояние** (`determine_*_state`) → 3. **Одно действие** (`process_*`) → 4. **Вернуться в цикл**

Это гарантирует, что даже при неожиданных всплывающих окнах или лагах, следующая итерация всегда опирается на реальный текущий экран, а не на предполагаемый.

## Известные ограничения

- **Только Windows** — используются win32 API для захвата экрана
- **Только BlueStacks** — имя окна жёстко задано (можно изменить)
- **Разрешение** — шаблоны привязаны к конкретному разрешению экрана
- **Язык игры** — шаблоны зависят от языка интерфейса

## Документация по разделам

| Файл | Что описывает |
|------|---------------|
| `docs/logic.md` | Детальная логика стейт-машин heal и raid |
| `docs/GOLD_MODULE.md` | Детальный flow процесса золотодобычи |
| `docs/REFACTORING_SUMMARY.md` | Почему `heal_and_raid_backup.txt` устарел и как код разделён на модули |
| `docs/GOLD_REFACTOR.md` | Краткое описание рефакторинга gold.py в стейт-машину |
| `docs/AGENTS.md` | Инструкции для AI-ассистентов по работе с репозиторием |

## Возможные улучшения

- [x] Рефакторинг `gold.py` в стейт-машину (устойчивость к лагам UI)
- [x] Разделение монолита на модули `heal.py`, `raid.py`, `gold.py`
- [x] Выбор уровня рудника 1–6 и отзыв отряда через 45 минут
- [ ] Добавить поддержку разных разрешений экрана
- [ ] Поддержка других эмуляторов (Nox, LDPlayer)
- [ ] Веб-интерфейс для мониторинга
- [ ] Конфигурационный файл (JSON/YAML)
- [ ] Уведомления при важных событиях

## Лицензия

Используется по вашему усмотрению.

## Предупреждение

Используйте на свой страх и риск. Авторы не несут ответствен за возможные последствия использования скрипта в онлайн-играх. Проверьте правила игры относительно использования ботов и автоматизации.
