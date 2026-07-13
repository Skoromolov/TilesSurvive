# ==========================================
# ЛОГИКА ЗОЛОТОДОБЫЧИ (стейт-машина)
# ==========================================

import time
import cv2
from dataclasses import dataclass
from typing import Optional

from config import *
from utils import *
from logger import logger  # Импортируем логгер
from state import load_state, update_state, LAST_GOLD_TIME_KEY, STARTED_AT_KEY, RECALL_REQUESTED_KEY, FORCE_RECLAIM_KEY

_GOLD_RAPID_POLL = 0.05
_GOLD_RAPID_CHAIN_TIMEOUT = 10.0

# ==========================================
# МОДЕЛЬ СОСТОЯНИЯ ЗОЛОТА
# ==========================================
@dataclass
class GoldContext:
    """Контекст золотодобычи: волатильные поля + persistent таймеры/флаги."""
    # волатильные поля (сбрасываются при новом заходе в режим GOLD)
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
    last_action_time: Optional[float] = None
    exit_attempts: int = 0

    # persistent поля (синхронизируются с state.py)
    started_at: Optional[float] = None
    recall_requested: bool = False
    force_reclaim: bool = False

    def reset_transient(self):
        """Сбросить волатильные поля перед новым заходом в режим GOLD."""
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
        self.last_action_time = None
        self.exit_attempts = 0


# Загружаем сохранённое состояние, чтобы таймеры переживали перезапуск скрипта.
_saved_state = load_state()
last_gold_time = _saved_state.get(LAST_GOLD_TIME_KEY, time.time())
gold_first_run = True         # при первом запуске сразу идём в золото после heal/raid, не ждём GOLD_INTERVAL
_gold_ctx = GoldContext(
    recall_requested=_saved_state.get(RECALL_REQUESTED_KEY, False),
    started_at=_saved_state.get(STARTED_AT_KEY, None),
    force_reclaim=_saved_state.get(FORCE_RECLAIM_KEY, False),
)

_GOLD_RAPID_POLL = 0.2
_GOLD_RAPID_CHAIN_TIMEOUT = 6.0

# ==========================================
# ТАЙМЕР / ПРОВЕРКА ПОРЫ
# ==========================================

def should_do_gold():
    """True если прошло GOLD_INTERVAL с последнего посещения."""
    global last_gold_time, gold_first_run
    if not GOLD_ENABLED:
        return False
    if gold_first_run:
        gold_first_run = False
        logger.info("[GOLD] Первый запуск скрипта — сразу запускаем золотодобычу.")
        return True
    elapsed = time.time() - last_gold_time
    if elapsed >= GOLD_INTERVAL:
        logger.info(f"[GOLD] Прошло {int(elapsed)} сек с последнего рудника. Пора!")
        return True
    remaining = int(GOLD_INTERVAL - elapsed)
    m, s = divmod(remaining, 60)
    logger.info(f"[GOLD] До рудника: {m:02d}:{s:02d}")
    return False


def update_gold_time():
    """Обновить время последнего посещения рудника и сохранить в файл."""
    global last_gold_time
    last_gold_time = time.time()
    update_state(**{LAST_GOLD_TIME_KEY: last_gold_time})
    logger.info(f"[GOLD] Время обновлено: {time.ctime(last_gold_time)}")


def gold_mission_active():
    """Отряд отправлен добывать золото и ещё не отозван."""
    return _gold_ctx.started_at is not None and not _gold_ctx.recall_requested


def gold_mission_should_recall():
    """Пора отозвать отряд (45 минут прошли)."""
    recall_status, _ = _check_recall_needed()
    return recall_status == 'recall'


def gold_mission_should_reclaim():
    """Нужно немедленно перезанять освободившееся место после отзыва/завершения."""
    return _gold_ctx.force_reclaim


def start_gold_mission():
    """Зафиксировать запуск добычи на целевом уровне и сохранить таймер."""
    now = time.time()
    _gold_ctx.started_at = now
    _gold_ctx.current_mining_level = GOLD_LEVEL
    _gold_ctx.recall_requested = False
    update_state(**{STARTED_AT_KEY: now, RECALL_REQUESTED_KEY: False})
    logger.info(f"[GOLD] Отряд отправлен на уровень {GOLD_LEVEL} в {time.ctime()}")


def clear_gold_mission():
    """Сбросить данные активной добычи и сохранить в файл."""
    _gold_ctx.started_at = None
    _gold_ctx.current_mining_level = None
    _gold_ctx.recall_requested = False
    update_state(**{STARTED_AT_KEY: None, RECALL_REQUESTED_KEY: False})


def reset_gold_context():
    """Сбросить вспомогательный контекст перед новым заходом в режим GOLD."""
    _gold_ctx.expected = None
    _gold_ctx.swipe_count = 0
    _gold_ctx.level_select_scroll_tries = 0
    _gold_ctx.stuck_count = 0
    _gold_ctx.stuck_last_action = None
    _gold_ctx.events_clicked_at = None
    _gold_ctx.moveon_clicked_at = None
    # recall_requested и started_at не сбрасываем — они хранятся в файле состояния
    _gold_ctx.need_level_check = False
    _gold_ctx.main_screen_tries = 0
    _gold_ctx.raid_icon_clicks = 0
    _gold_ctx.find_started_at = None
    _gold_ctx.exit_attempts = 0


# ==========================================
# ХЕЛПЕРЫ ДЛЯ УСТРАНЕНИЯ ДУБЛИРОВАНИЯ
# ==========================================
def _complete_mission(log_msg="[GOLD] ✓ Золотодобыча запущена!"):
    """Зафиксировать успешный запуск и вернуть COMPLETED."""
    # Сначала записываем таймер, потом лог — чтобы в логе была точная метка,
    # но главное: если обновление состояния упадёт, мы это заметим до COMPLETED.
    start_gold_mission()
    update_gold_time()
    _gold_ctx.force_reclaim = False
    update_state(**{FORCE_RECLAIM_KEY: False})
    logger.info(log_msg)
    return GoldState.COMPLETED


def _check_mining_result(screen_after, region):
    """
    Проверить результат отправки отряда на скриншоте.
    Возвращает:
        ('completed', None) — отряд отправлен (return.png / my_rudnik.png видны)
        ('go', None)       — открылось окно отправки отряда с кнопкой 'Марш'
        ('summary', None)  — открылось окно 'Общая сила' с кнопкой 'Добывать' (место занято)
        ('wait', None)     — на экране ещё остаточный текст 'Общая сила', нужно подождать анимацию
        ('unknown', None)  — окно закрылось, состояние не определено
    """
    if screen_after is None:
        return 'unknown', None

    # Сначала ищем с основным порогом
    return_coords, _ = find_on_screen(get_template(GOLD_RETURN_IMG), screen_after, region, threshold=CONFIDENCE_THRESHOLD)
    my_rudnik_coords, _ = find_on_screen(get_template(GOLD_MY_RUDNIK_IMG), screen_after, region, threshold=CONFIDENCE_THRESHOLD)
    if return_coords or my_rudnik_coords:
        return 'completed', None

    # Окно с кнопкой 'Марш' (GO) имеет приоритет — по нему нужно нажать GO
    go_coords, _ = find_on_screen(get_template(GOLD_GO_IMG), screen_after, region, threshold=CONFIDENCE_THRESHOLD)
    if go_coords:
        return 'go', None

    # Окно с кнопкой 'Добывать' (work/join) — это НЕ признак занятого места.
    # На свободном месте после free_place открывается окно 'Общая сила' с кнопкой 'Добывать',
    # а после неё появляется 'Марш'. Поэтому WORK здесь означает промежуточный экран.
    # Если виден GO — переходим к нему. Если остался только summary text — ждём анимацию.

    # Если summary text остался, но ни go ни return/my_rudnik не видны — значит анимация ещё идёт
    summary_coords, _ = find_on_screen(get_template(GOLD_SUMMARY_STRENGTH_TEXT_IMG), screen_after, region, threshold=CONFIDENCE_THRESHOLD)
    if summary_coords:
        return 'wait', None

    return 'unknown', None


def _ensure_target_level(screen_cv, region, window=None, log_prefix="[GOLD]"):
    """
    Проверить текущий уровень рудника.
    Если уровень не целевой — открыть выбор уровня и вернуть SELECT_LEVEL_VISIBLE.
    Если целевой — сбросить need_level_check и вернуть None.
    Если уровень не распознан и есть select_level.png — тоже открываем выбор.
    """
    current_screen = screen_cv
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        current = get_current_level(current_screen, region)
        if current is not None:
            break
        if attempt < max_attempts:
            # Делаем свежий скриншот между попытками, иначе 3 попытки на одном кадре бесполезны
            if window is not None:
                time.sleep(GOLD_ACTION_DELAY)
                current_screen = take_screenshot(window, region)
                if current_screen is None:
                    current_screen = screen_cv
            else:
                time.sleep(GOLD_ACTION_DELAY)

    if current is not None and current != GOLD_LEVEL:
        logger.info(f"{log_prefix} Уровень {current}, нужен {GOLD_LEVEL}. Открываем выбор уровня.")
        _gold_ctx.need_level_check = True
        find_and_click(GOLD_SELECT_LEVEL_IMG, current_screen, region)
        _gold_ctx.expected = 'level_list'
        _gold_ctx.level_select_scroll_tries = 0
        time.sleep(GOLD_ACTION_DELAY)
        return GoldState.SELECT_LEVEL_VISIBLE

    if current == GOLD_LEVEL:
        _gold_ctx.need_level_check = False
        logger.info(f"{log_prefix} Уровень проверен: {current}. Продолжаем добычу.")
        return None

    # Уровень не распознан — пробуем открыть выбор уровня
    select_coords, _ = find_on_screen(get_template(GOLD_SELECT_LEVEL_IMG), current_screen, region)
    if select_coords:
        logger.info(f"{log_prefix} Текущий уровень не виден после {max_attempts} попыток. Открываем выбор уровня.")
        _gold_ctx.need_level_check = True
        find_and_click(GOLD_SELECT_LEVEL_IMG, current_screen, region)
        _gold_ctx.expected = 'level_list'
        _gold_ctx.level_select_scroll_tries = 0
        time.sleep(GOLD_ACTION_DELAY)
        return GoldState.SELECT_LEVEL_VISIBLE

    return None


def _click_top_screen(region, reset_main_tries=False):
    """Клик в верхнюю часть экрана для закрытия попапа/сброса UI."""
    click_top_screen_safe(region)
    if reset_main_tries:
        _gold_ctx.main_screen_tries = 0

def _check_recall_needed():
    """
    Проверить, нужен ли отзыв отряда.
    Возвращает:
        ('recall', reason) — нужен отзыв
        ('sync', remaining_seconds) — started_at утерян, синхронизирован таймер
        ('active', elapsed_seconds) — добыча активна, отзыв не нужен
    """
    now = time.time()
    started = _gold_ctx.started_at

    if started is not None:
        elapsed = now - started
        if elapsed >= GOLD_MINING_DURATION:
            logger.info(f"[GOLD] Добыча идёт {int(elapsed)} сек, порог {GOLD_MINING_DURATION} сек. Нужен отзыв.")
            _gold_ctx.recall_requested = True
            update_state(**{RECALL_REQUESTED_KEY: True})
            return 'recall', int(elapsed)
        return 'active', int(elapsed)

    # Fallback: started_at утерян — ориентируемся на last_gold_time
    elapsed_since_last_gold = now - last_gold_time
    if elapsed_since_last_gold >= GOLD_MINING_DURATION:
        logger.info(f"[GOLD] started_at утерян, но с последнего золота прошло {int(elapsed_since_last_gold)} сек. Нужен отзыв.")
        _gold_ctx.recall_requested = True
        update_state(**{RECALL_REQUESTED_KEY: True})
        return 'recall', int(elapsed_since_last_gold)

    # Синхронизируем таймер, но не обновляем last_gold_time,
    # чтобы следующая проверка recall не зациклилась на "только что синхронизировано".
    _gold_ctx.started_at = now
    update_state(**{STARTED_AT_KEY: now})
    remaining = int(GOLD_MINING_DURATION - elapsed_since_last_gold)
    logger.info(f"[GOLD] Активная добыча без известного старта. Синхронизация таймера. До recall по last_gold_time: {remaining} сек.")
    return 'sync', remaining





def _take_result_screenshot(window, region, delay=None):
    """Сделать скриншот после клика и подождать минимальное время."""
    if delay is None:
        delay = _GOLD_RAPID_POLL
    if delay > 0:
        time.sleep(delay)
    screen_after = take_screenshot(window, region)
    return screen_after


def _fresh_or_current(window, region, current):
    """Получить свежий скриншот, не заменяя numpy-array на старый при сбое."""
    fresh = take_screenshot(window, region)
    return fresh if fresh is not None else current


def _rapid_capture_chain(initial_state, screen_cv, region, window):
    """
    Быстрая цепочка захвата свободного места.
    Выполняет клики free_place → 'Добывать' → 'Марш' → complete в одном вызове,
    используя polling с интервалом 0.05 сек, вместо разбросанных sleep 0.2-0.5 сек.
    """
    chain_start = time.time()
    screen = screen_cv
    last_state = initial_state
    _rapid_capture_chain._work_click_attempts = 0

    while time.time() - chain_start < _GOLD_RAPID_CHAIN_TIMEOUT:
        current_state = determine_gold_state(screen, region)
        if current_state != last_state:
            logger.info(f"[GOLD] Быстрая цепочка: {last_state.value} -> {current_state.value}")
            last_state = current_state

        # ---- GO / МАРШ ----
        if current_state == GoldState.GO_VISIBLE:
            if screen is None:
                screen = _fresh_or_current(window, region, screen)
                if screen is None:
                    return GoldState.UNKNOWN
                continue
            result, screen = _click_and_check_completion(
                GOLD_GO_IMG,
                "[GOLD] Нажимаем 'Марш' (быстрая цепочка).",
                window, screen, region,
                post_click_delay=_GOLD_RAPID_POLL,
                max_attempts=3
            )
            if result == 'completed':
                return _complete_mission("[GOLD] ✓ Золотодобыча запущена через 'Марш'!")
            # После клика GO делаем дополнительные попытки найти признаки активной добычи,
            # т.к. UI может обновляться с задержкой. Если нашли — completed, иначе продолжаем.
            confirmed_active = False
            for attempt in range(1, 8):
                screen = _fresh_or_current(window, region, screen)
                if screen is None:
                    break
                post_state = determine_gold_state(screen, region)
                if post_state in (GoldState.MY_RUDNIK_VISIBLE, GoldState.RETURN_BUTTON_VISIBLE, GoldState.RAID_LEVEL_ICON_VISIBLE):
                    logger.info(f"[GOLD] GO клик обработан: обнаружена активная добыча ({post_state.value}).")
                    confirmed_active = True
                    break
                if post_state == GoldState.GO_VISIBLE:
                    # GO всё ещё виден — возможно клик не сработал, повторим на следующей итерации
                    break
                if post_state == GoldState.WORK_VISIBLE:
                    # Вернулись к WORK — GO не сработал, повторим
                    break
                if post_state != GoldState.UNKNOWN:
                    logger.info(f"[GOLD] GO клик: неожиданное состояние {post_state.value}, продолжаем цепочку.")
                    break
                # UNKNOWN — подождём ещё немного
                time.sleep(_GOLD_RAPID_POLL)
            if confirmed_active:
                return _complete_mission("[GOLD] ✓ Золотодобыча запущена через 'Марш'!")
            _gold_ctx.last_action_time = time.time()
            continue

        # ---- SUMMARY / WORK ----
        if current_state in (GoldState.SUMMARY_STRENGTH_TEXT_VISIBLE, GoldState.WORK_VISIBLE):
            # Защита от потери скриншота в цепочке
            if screen is None:
                screen = _fresh_or_current(window, region, screen)
                if screen is None:
                    logger.warning("[GOLD] Нет скриншота в цепочке SUMMARY/WORK. Возвращаем UNKNOWN.")
                    return GoldState.UNKNOWN
                continue

            # Если одновременно видна кнопка Марш — сразу её
            go_coords, go_conf = find_on_screen(get_template(GOLD_GO_IMG), screen, region)
            logger.info(f"[GOLD] SUMMARY/WORK: GO conf={go_conf:.3f} at {go_coords}")
            if go_coords:
                result, screen = _click_and_check_completion(
                    GOLD_GO_IMG,
                    "[GOLD] Нажимаем 'Марш' из окна 'Общая сила'.",
                    window, screen, region,
                    post_click_delay=_GOLD_RAPID_POLL,
                    max_attempts=6
                )
                if result == 'completed':
                    return _complete_mission("[GOLD] ✓ Золотодобыча запущена через 'Марш'!")
                _gold_ctx.last_action_time = time.time()  # обновить таймер от последнего клика
                screen = _fresh_or_current(window, region, screen)
                continue

            work_coords, work_conf = find_on_screen(get_template(GOLD_WORK_IMG), screen, region)
            logger.info(f"[GOLD] SUMMARY/WORK: WORK conf={work_conf:.3f} at {work_coords}")
            if not work_coords:
                # Кнопка Добывать ещё не появилась — короткий poll
                screen = _fresh_or_current(window, region, screen)
                action_age = time.time() - (_gold_ctx.last_action_time or chain_start)
                if action_age > 3.0:
                    logger.info("[GOLD] В окне 'Общая сила' не появилась кнопка 'Добывать'. Закрываем.")
                    return _close_to_rudkin_tab(screen, region, window)
                continue

            # После нажатия WORK ожидаем появления GO или completed.
            # Если WORK всё ещё виден — возможно клик не сработал, повторяем ограниченное число раз.
            work_click_attempts = getattr(_rapid_capture_chain, '_work_click_attempts', 0)
            result, screen = _click_and_check_completion(
                GOLD_WORK_IMG,
                "[GOLD] Нажимаем 'Добывать' (быстрая цепочка).",
                window, screen, region,
                post_click_delay=_GOLD_RAPID_POLL,
                max_attempts=10
            )
            _gold_ctx.last_action_time = time.time()  # обновить таймер от последнего клика
            if result == 'completed':
                _rapid_capture_chain._work_click_attempts = 0
                # Перед завершением ещё раз убедимся, что реально виден признак активной добычи,
                # чтобы не стартовать таймер по ложному совпадению.
                screen = _fresh_or_current(window, region, screen)
                if screen is not None:
                    verify_state = determine_gold_state(screen, region)
                    if verify_state not in (GoldState.MY_RUDNIK_VISIBLE, GoldState.RETURN_BUTTON_VISIBLE, GoldState.RAID_LEVEL_ICON_VISIBLE):
                        logger.warning(f"[GOLD] WORK вернул completed, но активная добыча не подтверждена ({verify_state.value}). Продолжаем цепочку.")
                        result = 'other'
                    else:
                        logger.info(f"[GOLD] WORK: активная добыча подтверждена ({verify_state.value}).")
                return _complete_mission("[GOLD] ✓ Золотодобыча запущена!")
            if result == 'go':
                _rapid_capture_chain._work_click_attempts = 0
                # Открылся диалог 'Марш' — следующая итерация его обработает
                screen = _fresh_or_current(window, region, screen)
                continue
            if result in ('wait', 'other'):
                work_click_attempts += 1
                _rapid_capture_chain._work_click_attempts = work_click_attempts
                screen = _fresh_or_current(window, region, screen)
                if work_click_attempts >= 3:
                    logger.info("[GOLD] WORK не привёл к GO/complete после 3 попыток. Закрываем окно.")
                    _rapid_capture_chain._work_click_attempts = 0
                    return _close_to_rudkin_tab(screen, region, window)
                continue
            screen = _fresh_or_current(window, region, screen)
            continue

        # ---- FREE PLACE ----
        if current_state == GoldState.FREE_PLACE_VISIBLE:
            if screen is None:
                screen = _fresh_or_current(window, region, screen)
                if screen is None:
                    return GoldState.UNKNOWN
                continue
            result, screen = _click_and_check_completion(
                GOLD_FREE_PLACE_IMG,
                "[GOLD] Нажимаем свободное место (быстрая цепочка).",
                window, screen, region,
                post_click_delay=_GOLD_RAPID_POLL,
                max_attempts=10
            )
            if result == 'completed':
                return _complete_mission("[GOLD] ✓ Золотодобыча запущена!")
            if result in ('go', 'wait', 'other'):
                screen = _fresh_or_current(window, region, screen)
                continue
            # 'summary' больше не возвращается; всё ещё free — poll ещё раз
            screen = _fresh_or_current(window, region, screen)
            if time.time() - chain_start > 1.0:
                logger.info("[GOLD] Свободное место не нажалось, продолжаем обычный цикл.")
                return GoldState.FREE_PLACE_VISIBLE
            continue

        # ---- GRIND (вход в цепочку захвата) ----
        if current_state == GoldState.GRIND_VISIBLE:
            if screen is None:
                screen = _fresh_or_current(window, region, screen)
                if screen is None:
                    return GoldState.UNKNOWN
                continue
            result, screen = _click_and_check_completion(
                GOLD_GRIND_IMG,
                "[GOLD] Нажимаем 'GRIND' (быстрая цепочка).",
                window, screen, region,
                post_click_delay=_GOLD_RAPID_POLL,
                max_attempts=10,
            )
            if result == 'completed':
                return _complete_mission("[GOLD] ✓ Золотодобыча запущена!")
            screen = _fresh_or_current(window, region, screen)
            continue

        # ---- Активная добыча — уже отправлено ----
        if current_state in (GoldState.MY_RUDNIK_VISIBLE, GoldState.RETURN_BUTTON_VISIBLE, GoldState.RAID_LEVEL_ICON_VISIBLE):
            return _complete_mission("[GOLD] ✓ Золотодобыча уже активна.")

        # Состояние вне цепочки — передаём управление обратно в основной процесс
        return current_state

    logger.info("[GOLD] Быстрая цепочка превысила лимит времени. Возвращаем UNKNOWN.")
    return GoldState.UNKNOWN


def _click_and_check_completion(button_img, log_msg, window, screen_cv, region, post_click_delay=0.05, max_attempts=3):
    """
    Нажать кнопку отправки отряда и проверить результат.
    Возвращает:
        ('completed', None) — отряд отправлен (return.png / my_rudnik.png)
        ('go', screen_after) — открылось окно с кнопкой 'Марш'
        ('wait', screen_after) — остаточный текст 'Общая сила', нужно подождать анимацию
        ('other', screen_after) — другое состояние, нужна дальнейшая проверка
    """
    logger.info(log_msg)
    clicked, _ = find_and_click(button_img, screen_cv, region)
    if not clicked:
        return 'other', screen_cv

    for attempt in range(1, max_attempts + 1):
        screen_after = _take_result_screenshot(window, region, delay=post_click_delay)
        if screen_after is None:
            if attempt == max_attempts:
                return 'other', screen_cv
            continue
        result, _ = _check_mining_result(screen_after, region)
        if result != 'unknown':
            logger.info(f"[GOLD] Попытка {attempt}: результат после клика = {result}")
            if result == 'completed':
                return 'completed', None
            if result == 'go':
                return 'go', screen_after
            if result == 'wait':
                if attempt == max_attempts:
                    return 'wait', screen_after
                continue
            return 'other', screen_after
    return 'other', screen_after if screen_after is not None else screen_cv




def _try_recall(screen_cv, region, window=None):
    """Попытаться отозвать активный отряд, если recall_requested.
    Возвращает новое GoldState или None, если recall не требуется.
    """
    # return.png должен быть в нижней части экрана (кнопка отзыва),
    # чтобы не путать с иконками верхней панели/событий.
    return_coords, return_conf = find_on_screen(get_template(GOLD_RETURN_IMG), screen_cv, region)
    if return_coords:
        logger.info(f"[GOLD] Отряд занят добычей. Отзываем (return.png conf={return_conf:.3f}).")
        find_and_click(GOLD_RETURN_IMG, screen_cv, region)
        return GoldState.RETURN_CONFIRM_VISIBLE

    # Если уже открыты детали рудника — кнопка отзыва внутри попапа
    return_rudnik_coords, return_rudnik_conf = find_on_screen(get_template(GOLD_RETURN_RUDNIK_BUTTON_IMG), screen_cv, region)
    if return_rudnik_coords:
        logger.info(f"[GOLD] Отряд занят добычей. Отзываем через кнопку деталей рудника (conf={return_rudnik_conf:.3f}).")
        find_and_click(GOLD_RETURN_RUDNIK_BUTTON_IMG, screen_cv, region)
        return GoldState.RETURN_CONFIRM_VISIBLE

    # Fallback: открыть детали рудника через my_rudnik.png, если она в нижней части
    my_rudnik_coords, my_rudnik_conf = find_on_screen(get_template(GOLD_MY_RUDNIK_IMG), screen_cv, region)
    if my_rudnik_coords:
        logger.info(f"[GOLD] Открываем детали рудника (my_rudnik.png conf={my_rudnik_conf:.3f}) для отзыва.")
        find_and_click(GOLD_MY_RUDNIK_IMG, screen_cv, region)
        time.sleep(_GOLD_RAPID_POLL)
        return GoldState.UNKNOWN

    logger.info("[GOLD] recall_requested, но не видно корректной кнопки отзыва. Ждём.")
    return GoldState.UNKNOWN

def _close_to_rudkin_tab(screen_cv, region, window):
    """Закрыть попап и вернуться к rudnik_tab."""
    find_and_click(GOLD_CLOSE_IMG, screen_cv, region)

    time.sleep(GOLD_ACTION_DELAY)
    # Verify we are back at rudnik_tab by checking for find or select_level
    screen_after = take_screenshot(window, region)
    if screen_after is None:
        logger.warning("[GOLD] Не удалось получить скриншот после закрытия попапа.")
        return GoldState.UNKNOWN
    find_visible, _ = find_on_screen(get_template(GOLD_FIND_IMG), screen_after, region)
    select_visible, _ = find_on_screen(get_template(GOLD_SELECT_LEVEL_IMG), screen_after, region)
    if find_visible or select_visible:
        _gold_ctx.expected = 'rudnik_tab'
        _gold_ctx.need_level_check = True  # после закрытия попапа уровень может измениться
        return GoldState.RUDNIK_TAB
    else:
        # If not sure, return UNKNOWN to let recovery handle it
        return GoldState.UNKNOWN


def _get_scroll_direction(found_level):
    """Определить направление скролла списка уровней к целевому GOLD_LEVEL."""
    if found_level is not None:
        return 'up' if GOLD_LEVEL < found_level else 'down'
    return 'down'


# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ УРОВНЕЙ
# ==========================================
def get_current_level(screen_cv, region, threshold=GOLD_LEVEL_CONFIDENCE_THRESHOLD):
    """Определить текущий открытый уровень рудника по current_lvl_X."""
    best_level = None
    best_conf = 0.0
    for level in range(1, 7):
        coords, conf = find_on_screen(
            get_template(GOLD_CURRENT_LEVEL_IMAGES[level]), screen_cv, region, threshold
        )
        if coords and conf > best_conf:
            best_conf = conf
            best_level = level
    if best_level:
        logger.info(f"[GOLD] Распознан текущий уровень: {best_level} (conf={best_conf:.3f})")
    return best_level


def get_list_level(screen_cv, region, threshold=GOLD_LIST_LEVEL_CONFIDENCE_THRESHOLD):
    """Найти уровень в списке выбора уровней. Возвращает (level, center_coords) или (None, None)."""
    best_level = None
    best_coords = None
    best_conf = 0.0
    for level in range(1, 7):
        template = get_template(GOLD_LEVEL_IMAGES[level])
        if template is None:
            continue
        coords, conf = find_on_screen(template, screen_cv, region, threshold)
        if coords and conf > best_conf:
            best_conf = conf
            best_level = level
            best_coords = coords
    if best_level:
        logger.info(f"[GOLD] В списке найден уровень {best_level} (conf={best_conf:.3f})")
        return best_level, best_coords
    return None, None


def is_target_level_in_list(screen_cv, region, target=GOLD_LEVEL, threshold=GOLD_LIST_LEVEL_CONFIDENCE_THRESHOLD):
    """Проверить, виден ли целевой уровень в списке."""
    lvl_template = get_template(GOLD_LEVEL_IMAGES[target])
    if lvl_template is None:
        return False
    coords, conf = find_on_screen(lvl_template, screen_cv, region, threshold)
    return coords is not None


def find_event_gold_in_calendar(screen_cv, region, threshold=CONFIDENCE_THRESHOLD):
    """Найти событие золотодобычи в календаре.

    Ищет только event_gold.png — маленькую иконку в строке календаря.
    rudnik.png НЕ используется здесь, т.к. rudnik.png — это элемент верхней
    карусели активного события, а не строка календаря; клик по нему не
    открывает попап "Вперёд".
    Возвращает (coords, conf, template_path) или (None, 0.0, None).
    """
    coords, conf = find_on_screen(get_template(EVENT_GOLD_IMG), screen_cv, region, threshold=threshold)
    if coords:
        return coords, conf, EVENT_GOLD_IMG
    return None, 0.0, None


def click_moveon_for_target_level(screen_cv, region, target=GOLD_LEVEL, lvl_threshold=None, btn_threshold=0.70):
    """Найть ближайшую кнопку 'Перейти' к тексту целевого уровня и кликнуть по ней.

    Если кнопка moveOn.png не найдена, но текст уровня виден, кликает в нижнюю часть
    карточки уровня — это fallback для UI, где кнопка не выделяется как отдельный шаблон.
    """
    if lvl_threshold is None:
        lvl_threshold = GOLD_LIST_LEVEL_CONFIDENCE_THRESHOLD

    lvl_template = get_template(GOLD_LEVEL_IMAGES[target])
    if lvl_template is None:
        return False
    h_lvl, w_lvl = lvl_template.shape[:2]
    lvl_matches = find_all_on_screen(lvl_template, screen_cv, region, lvl_threshold)
    if not lvl_matches:
        logger.info(f"[GOLD] lvl_{target}.png не найден на экране.")
        return False

    btn_template = get_template(GOLD_MOVEON_IMG)
    fallback_click = None
    best_lvl_match = max(lvl_matches, key=lambda m: m[2])  # по максимальному confidence
    cx_lvl, cy_lvl, conf_lvl = best_lvl_match

    # Fallback: клик под текстом уровня, если moveOn.png не найдена или не подходит
    fallback_x = cx_lvl
    fallback_y = cy_lvl + h_lvl * 1.8
    region_top = region[1]
    region_bottom = region[1] + region[3]
    if region_top + 30 < fallback_y < region_bottom - 30:
        fallback_click = (fallback_x, fallback_y)

    if btn_template is None:
        if fallback_click:
            pyautogui.click(*fallback_click)
            logger.info(f"[GOLD] Кнопка 'Перейти' отсутствует как шаблон, клик под уровень {target} ({fallback_x:.0f}, {fallback_y:.0f}), conf={conf_lvl:.3f}")
            return True
        return False

    h_btn, w_btn = btn_template.shape[:2]
    btn_matches = find_all_on_screen(btn_template, screen_cv, region, btn_threshold)

    best_pair = None
    best_score = -1.0
    if btn_matches:
        for cx_btn, cy_btn, conf_btn in btn_matches:
            for cx_lvl_i, cy_lvl_i, conf_lvl_i in lvl_matches:
                vertical_gap = cy_btn - cy_lvl_i
                horizontal_gap = abs(cx_btn - cx_lvl_i)
                # Кнопка "Перейти" находится ПОД текстом уровня (не выше).
                # Карточка уровня ~270px, кнопка 50px; допускаем gap до h_btn * 5.
                if 0 < vertical_gap < h_btn * 5 and horizontal_gap < max(w_btn, w_lvl) * 1.5:
                    score = conf_lvl_i + conf_btn - vertical_gap / 100.0
                    if score > best_score:
                        best_score = score
                        best_pair = (cx_btn, cy_btn, conf_btn, cx_lvl_i, cy_lvl_i, conf_lvl_i)

    if best_pair is None:
        logger.info(f"[GOLD] Кнопка 'Перейти' не найдена рядом с уровнем {target}. "
              f"lvl_matches={len(lvl_matches)}, btn_matches={len(btn_matches) if btn_matches else 0}. "
              f"Возможно уровень {target} за пределами экрана — нужен скролл.")
        return False

    cx_btn, cy_btn, conf_btn, cx_lvl, cy_lvl, conf_lvl = best_pair
    btn_top = cy_btn - h_btn / 2
    btn_bottom = cy_btn + h_btn / 2
    if btn_top < region_top + 20 or btn_bottom > region_bottom - 20:
        if fallback_click:
            pyautogui.click(*fallback_click)
            logger.info(f"[GOLD] Кнопка 'Перейти' у уровня {target} частично за краем, клик под карточку ({fallback_x:.0f}, {fallback_y:.0f})")
            return True
        logger.info(f"[GOLD] Кнопка 'Перейти' у уровня {target} частично за краем экрана. Скроллим.")
        return False

    pyautogui.click(cx_btn, cy_btn)
    logger.info(f"[GOLD] Нажата 'Перейти' у уровня {target} ({cx_btn:.0f}, {cy_btn:.0f}), conf=({conf_lvl:.3f}/{conf_btn:.3f})")
    return True


# ==========================================
# ОПРЕДЕЛЕНИЕ СОСТОЯНИЯ ЗОЛОТОДОБЫЧИ
# ==========================================
def determine_gold_state(screen_cv, region):
    """Возвращает GoldState на основе текущего экрана (приоритет сверху-вниз)."""

    # 2. Подтверждение отзыва отряда
    coords, _ = find_on_screen(get_template(GOLD_RETURN_BOYS_IMG), screen_cv, region)
    if coords:
        return GoldState.RETURN_CONFIRM_VISIBLE

    # 3. Кнопка "Завершить" после отзыва
    coords, _ = find_on_screen(get_template(GOLD_FINISH_IMG), screen_cv, region)
    if coords:
        return GoldState.FINISH_VISIBLE

    # 4. Подтверждение после завершения / попап "СОВЕТ"
    # Сначала проверяем оранжевую кнопку подтверждения в попапе "СОВЕТ" —
    # она имеет приоритет, т.к. это блокирующий попап.
    coords, _ = find_on_screen(get_template(GOLD_ADVICE_IMG), screen_cv, region)
    if coords:
        return GoldState.ADVICE_VISIBLE

    coords, _ = find_on_screen(get_template(GOLD_CONFIRM_IMG), screen_cv, region)
    if coords:
        return GoldState.CONFIRM_VISIBLE

    # 5. Окно отправки отряда / кнопка "Марш" (имеет приоритет над summary,
    #    т.к. на этом экране тоже виден текст "Общая сила ваших отрядов")
    coords, _ = find_on_screen(get_template(GOLD_GO_IMG), screen_cv, region)
    if coords:
        return GoldState.GO_VISIBLE

    # 6. Попап "SummaryStrenghtText" — место занято (кнопка "Добывать")
    coords, _ = find_on_screen(get_template(GOLD_SUMMARY_STRENGTH_TEXT_IMG), screen_cv, region)
    if coords:
        return GoldState.SUMMARY_STRENGTH_TEXT_VISIBLE

    # 7. Мой рудник / активная добыча — проверяем ДО return.png,
    #    т.к. return.png видна на экране добычи всегда (как кнопка отзыва)
    coords, _ = find_on_screen(get_template(GOLD_MY_RUDNIK_IMG), screen_cv, region)
    if coords:
        return GoldState.MY_RUDNIK_VISIBLE

    # 8. Иконка активного уровня добычи
    coords, _ = find_on_screen(get_template(GOLD_CURRENT_RAID_LEVEL_ICON_IMG), screen_cv, region)
    if coords:
        return GoldState.RAID_LEVEL_ICON_VISIBLE

    # 9. Кнопка "Отозвать" на экране рудника
    coords, _ = find_on_screen(get_template(GOLD_RETURN_IMG), screen_cv, region)
    if coords:
        return GoldState.RETURN_BUTTON_VISIBLE

    # 10. Цепочка добычи / марш (work/grind если go уже проверили выше)
    coords, _ = find_on_screen(get_template(GOLD_WORK_IMG), screen_cv, region)
    if coords:
        return GoldState.WORK_VISIBLE

    coords, _ = find_on_screen(get_template(GOLD_GRIND_IMG), screen_cv, region)
    if coords:
        # grind.png (кирка) ложно срабатывает на табе рудника, где видна кнопка
        # "Место добычи". Если на том же экране есть find.png или select_level.png —
        # это таба рудника, а не цепочка добычи.
        find_visible, _ = find_on_screen(get_template(GOLD_FIND_IMG), screen_cv, region)
        select_visible, _ = find_on_screen(get_template(GOLD_SELECT_LEVEL_IMG), screen_cv, region)
        if not (find_visible or select_visible):
            return GoldState.GRIND_VISIBLE

    # 10. Свободное место после поиска
    coords, _ = find_on_screen(get_template(GOLD_FREE_PLACE_IMG), screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
    if coords:
        return GoldState.FREE_PLACE_VISIBLE

    # 11. Открыта таба рудника.
    #     rudnik_opened.png может ложно сработать на верхней карусели событий,
    #     когда открыт попап чужого рудника. Поэтому RUDNIK_TAB определяем
    #     только если видна кнопка поиска (find.png) или выбора уровня (select_level.png).
    #     НО: если мы только что нажали events.png (expected='events') — пропускаем,
    #     т.к. select_level.png может ложно сработать на календаре событий.
    if _gold_ctx.expected != 'events':
        find_visible, _ = find_on_screen(get_template(GOLD_FIND_IMG), screen_cv, region)
        select_visible, _ = find_on_screen(get_template(GOLD_SELECT_LEVEL_IMG), screen_cv, region)

        # Если find.png видна и мы уже нажимали find (expected='find') — продолжаем поиск
        if find_visible and _gold_ctx.expected == 'find':
            return GoldState.FIND_VISIBLE

        # Реальная таба рудника: есть find.png или select_level.png
        if find_visible or select_visible:
            current_level = get_current_level(screen_cv, region)
            if current_level is not None:
                # find не виден, но уровень распознан — проверяем no_free_rudnik
                no_free_coords, _ = find_on_screen(get_template(GOLD_NO_FREE_RUDNIK_IMG), screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
                if no_free_coords:
                    return GoldState.NO_FREE_RUDNIK
            return GoldState.RUDNIK_TAB

        # Список уровней — только если мы не на табе рудника
        found_level, _ = get_list_level(screen_cv, region, threshold=GOLD_LEVEL_CONFIDENCE_THRESHOLD)
        if found_level is not None:
            return GoldState.LEVEL_LIST_VISIBLE

    # 13. Попап события с кнопкой "Вперёд"
    coords, _ = find_on_screen(get_template(GOLD_FORWARD_IMG), screen_cv, region, threshold=0.55)
    if coords:
        return GoldState.FORWARD_POPUP_VISIBLE

    # 14. Активное событие открылось вместо календаря: в верхней карусели виден rudnik.png,
    #     а calendar_opened.png не виден. Нужно кликнуть по вкладке рудника, чтобы перейти к золотодобыче.
    rudnik_coords, _ = find_on_screen(get_template(GOLD_RUDNIK_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if rudnik_coords:
        rudnik_rel_y = (rudnik_coords[1] - region[1]) / region[3] if region[3] else 1.0
        calendar_opened_coords, _ = find_on_screen(get_template(CALENDAR_OPENED_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if rudnik_rel_y < 0.30 and not calendar_opened_coords:
            return GoldState.EVENTS_MENU_OPEN

    # 15. Меню событий: видна иконка золотодобычи в строке календаря → можно кликать
    gold_coords, _, _ = find_event_gold_in_calendar(screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if gold_coords:
        return GoldState.EVENTS_RUDNIK_VISIBLE



    # 16. Меню событий/календарь — calendar.png, calendar_opened.png или back.png видна.
    #     Если events.png видна — мы на главном экране (проверка выше).
    #     Пропускаем если expected='rudnik_tab' — мы в процессе перехода на табу рудника
    if _gold_ctx.expected not in ('rudnik_tab', 'forward_popup'):
        # calendar.png — иконка календаря в меню событий (меню открыто, календарь ещё не нажат)
        calendar_coords, calendar_conf = find_on_screen(get_template(CALENDAR_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if calendar_coords:
            return GoldState.EVENTS_MENU_OPEN

        # calendar_opened.png — календарь открыт, нужно свайпать для поиска события
        calendar_opened_coords, _ = find_on_screen(get_template(CALENDAR_OPENED_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if calendar_opened_coords:
            return GoldState.EVENTS_NEED_SCROLL

    back_coords, back_conf = find_on_screen(get_template(BACK_IMG), screen_cv, region)

    if back_coords:
        # Если мы только что нажали events.png — значит мы в меню событий
        if _gold_ctx.expected == 'events':
            return GoldState.EVENTS_MENU_OPEN
        # Иначе: back в календаре — в верхней трети; в окне рейда back обычно внизу
        back_rel_y = (back_coords[1] - region[1]) / region[3] if region[3] else 0
        if back_rel_y < 0.35:
            return GoldState.EVENTS_MENU_OPEN
        # Иначе это похоже на back внизу экрана (рейд, попап и т.п.) — не считаем календарём

    # 16. Главный экран / поселение / карта — проверяем ДО back.png,
    #     чтобы ложное срабатывание back.png не перебивало главный экран.
    events_coords, _ = find_on_screen(get_template(EVENTS_IMG), screen_cv, region)
    if events_coords:
        return GoldState.MAIN_SCREEN

    village_coords, _ = find_on_screen(get_template(VILLAGE_IMG), screen_cv, region)
    if village_coords:
        return GoldState.MAIN_SCREEN

    wild_coords, _ = find_on_screen(get_template(WILD_EARTH_IMG), screen_cv, region)
    if wild_coords:
        return GoldState.MAIN_SCREEN

    # Fallback: heal_town.png, help_hands.png, souz.png — видны на главном экране
    souz_coords, _ = find_on_screen(get_template(SOUZ_IMG), screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
    if souz_coords:
        return GoldState.MAIN_SCREEN

    # Если видна info.png — это попап, нужно кликнуть в верхнюю часть экрана
    info_coords, _ = find_on_screen(get_template(INFO_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if info_coords:
        return GoldState.MAIN_SCREEN

    return GoldState.UNKNOWN


# ==========================================
# ОБРАБОТКА СОСТОЯНИЙ ЗОЛОТОДОБЫЧИ
# ==========================================
def process_gold(screen_cv, region, last_gold_state, window):
    """Обработать одно состояние золотодобычи; одно действие за вызов."""
    global _gold_ctx
    current_state = determine_gold_state(screen_cv, region)

    if current_state != last_gold_state:
        logger.info(f"[GOLD] Состояние: {current_state.value}")
        # Сохраняем скриншот только при критических переходах — не на каждую смену
        critical_transitions = (
            GoldState.RETURN_CONFIRM_VISIBLE, GoldState.FINISH_VISIBLE,
            GoldState.FREE_PLACE_VISIBLE, GoldState.COMPLETED,
            GoldState.FORWARD_POPUP_VISIBLE,
        )
        if current_state in critical_transitions or last_gold_state == GoldState.UNKNOWN:
            save_debug_screenshot(screen_cv, f"gold_{current_state.value}")

    # ---- RETURN BUTTON ----
    if current_state == GoldState.RETURN_BUTTON_VISIBLE:
        if _gold_ctx.recall_requested:
            return _try_recall(screen_cv, region, window)
        current = get_current_level(screen_cv, region)
        if current:
            _gold_ctx.current_mining_level = current
        return _complete_mission("[GOLD] ✓ Золотодобыча запущена (return.png видна, отзыв не требуется).")

    # ---- RETURN CONFIRM ----
    if current_state == GoldState.RETURN_CONFIRM_VISIBLE:
        clicked, _ = find_and_click(GOLD_RETURN_BOYS_IMG, screen_cv, region)
        if not clicked:
            logger.warning("[GOLD] Кнопка подтверждения отзыва не найдена, пробуем fallback confirm.png")
            find_and_click(GOLD_CONFIRM_IMG, screen_cv, region)
        clear_gold_mission()
        _gold_ctx.recall_requested = False
        _gold_ctx.expected = 'rudnik_tab'
        _gold_ctx.need_level_check = True
        _gold_ctx.force_reclaim = True
        update_state(**{FORCE_RECLAIM_KEY: True, RECALL_REQUESTED_KEY: False})
        logger.info("[GOLD] Отряд отозван.")
        return GoldState.RUDNIK_TAB

    # ---- FINISH BUTTON ----
    if current_state == GoldState.FINISH_VISIBLE:
        logger.info("[GOLD] Нажимаем 'Завершить' после отзыва/выбивания отряда.")
        find_and_click(GOLD_FINISH_IMG, screen_cv, region)
        # Добыча завершена — сбрасываем миссию, чтобы заново искать и сесть на это же место.
        clear_gold_mission()
        _gold_ctx.need_level_check = True
        _gold_ctx.expected = 'rudnik_tab'
        _gold_ctx.force_reclaim = True
        update_state(**{FORCE_RECLAIM_KEY: True})
        return GoldState.RUDNIK_TAB

    # ---- ADVICE / 45-MIN POPUP ----
    if current_state == GoldState.ADVICE_VISIBLE:
        # Попап "СОВЕТ" с ограничением отзыва раньше 45 минут (для уровней 5-6).
        # Подтверждаем его и синхронизируем таймеры, чтобы не пытаться отозвать сразу снова.
        if _gold_ctx.recall_requested:
            logger.info("[GOLD] Попап 'СОВЕТ': отзыв пока невозможен. Подтверждаем.")
            # Сначала пробуем оранжевую кнопку, потом стандартную confirm.png
            clicked, _ = find_and_click(GOLD_CONFIRM_ORANGE_IMG, screen_cv, region)
            if not clicked:
                find_and_click(GOLD_CONFIRM_IMG, screen_cv, region)
            # Синхронизируем таймер: считаем, что добыча началась сейчас,
            # и через GOLD_MINING_DURATION снова попробуем отозвать.
            start_gold_mission()
            update_gold_time()
            _gold_ctx.recall_requested = False
            logger.info("[GOLD] Таймеры синхронизированы после попапа 'СОВЕТ'. Возвращаемся в основной цикл.")
            return GoldState.COMPLETED
        logger.info("[GOLD] Нажимаем 'Подтвердить' в попапе 'СОВЕТ'.")
        clicked, _ = find_and_click(GOLD_CONFIRM_ORANGE_IMG, screen_cv, region)
        if not clicked:
            find_and_click(GOLD_CONFIRM_IMG, screen_cv, region)
        _gold_ctx.need_level_check = True
        return GoldState.RUDNIK_TAB

    # ---- CONFIRM BUTTON ----
    if current_state == GoldState.CONFIRM_VISIBLE:
        if _gold_ctx.recall_requested:
            logger.info("[GOLD] Подтверждаем попап 'СОВЕТ' (отзыв пока невозможен).")
            find_and_click(GOLD_CONFIRM_IMG, screen_cv, region)
            # Не выходим из GOLD — остаёмся на руднике, чтобы сразу перезанять место.
            _gold_ctx.recall_requested = False
            _gold_ctx.force_reclaim = True
            _gold_ctx.expected = 'rudnik_tab'
            _gold_ctx.need_level_check = True
            update_state(**{RECALL_REQUESTED_KEY: False, FORCE_RECLAIM_KEY: True})
            return GoldState.RUDNIK_TAB
        logger.info("[GOLD] Нажимаем 'Подтвердить'.")
        find_and_click(GOLD_CONFIRM_IMG, screen_cv, region)
        _gold_ctx.need_level_check = True
        return GoldState.RUDNIK_TAB

    # ---- SUMMARY / WORK / GO / GRIND ----
    if current_state in (GoldState.SUMMARY_STRENGTH_TEXT_VISIBLE, GoldState.WORK_VISIBLE,
                         GoldState.GO_VISIBLE, GoldState.GRIND_VISIBLE):
        return _rapid_capture_chain(current_state, screen_cv, region, window)

    # ---- FREE PLACE ----
    if current_state == GoldState.FREE_PLACE_VISIBLE:
        level_state = _ensure_target_level(screen_cv, region, window=window)
        if level_state is not None:
            return level_state
        return _rapid_capture_chain(current_state, screen_cv, region, window)

    # ---- MY RUDNIK / ACTIVE MINING ----
    if current_state in (GoldState.MY_RUDNIK_VISIBLE, GoldState.RAID_LEVEL_ICON_VISIBLE):
        current = get_current_level(screen_cv, region)
        if current:
            _gold_ctx.current_mining_level = current

        needs_recall = _gold_ctx.recall_requested
        if not needs_recall:
            recall_status, recall_value = _check_recall_needed()
            needs_recall = recall_status == 'recall'

        if needs_recall:
            return _try_recall(screen_cv, region, window)

        # Добыча активна, отзыв не требуется. Если мы уже сидим на руднике
        # (RAID_LEVEL_ICON_VISIBLE / MY_RUDNIK_VISIBLE) и _gold_ctx.started_at
        # не задан — значит бот зашёл в золото, но миссия не запущена как завершённая.
        # Вместо мгновенного выхода пытаемся открыть детали рудника, чтобы увидеть
        # WORK/GRIND/GO и реально запустить добычу.
        if _gold_ctx.started_at is None:
            my_rudnik_coords, _ = find_on_screen(get_template(GOLD_MY_RUDNIK_IMG), screen_cv, region)
            if my_rudnik_coords:
                logger.info("[GOLD] Миссия не зафиксирована, но видна кнопка 'Мой рудник'. Открываем детали для запуска.")
                find_and_click(GOLD_MY_RUDNIK_IMG, screen_cv, region)
                time.sleep(GOLD_ACTION_DELAY)
                return GoldState.UNKNOWN
            # Если my_rudnik.png не видна — возможно, это уже открытое окно рудника
            # с кнопкой WORK/GRIND. Пропускаем в UNKNOWN, чтобы determine_* увидел их.
            work_coords, _ = find_on_screen(get_template(GOLD_WORK_IMG), screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
            grind_coords, _ = find_on_screen(get_template(GOLD_GRIND_IMG), screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
            if work_coords or grind_coords:
                logger.info("[GOLD] Миссия не зафиксирована, но видны кнопки WORK/GRIND. Продолжаем обработку.")
                return GoldState.UNKNOWN

        # Добыча активна, отзыв не требуется — выходим
        started = _gold_ctx.started_at
        if started is not None:
            elapsed = int(time.time() - started)
            logger.info(f"[GOLD] Добыча активна ({elapsed//60} мин).")
        else:
            logger.info("[GOLD] Добыча активна, таймер синхронизирован.")

        # Обновляем last_gold_time только если недавно запустили добычу.
        # При обычной проверке активной добычи не трогаем таймер, иначе
        # should_do_gold() постоянно сбрасывается и бот не перезапускает добычу.
        if started is None:
            update_gold_time()
        return GoldState.COMPLETED

    # ---- RUDNIK TAB (выбор / поиск уровня) ----
    if current_state == GoldState.RUDNIK_TAB:
        _gold_ctx.expected = 'rudnik_tab'
        _gold_ctx.raid_icon_clicks = 0
        _gold_ctx.find_started_at = None  # сброс таймаута поиска

        level_state = None

        # Early-exit: если уровень уже проверен и совпадает с GOLD_LEVEL — пропускаем 3-pass scan
        if not _gold_ctx.need_level_check and _gold_ctx.current_mining_level == GOLD_LEVEL:
            _gold_ctx.need_level_check = False
        else:
            level_state = _ensure_target_level(screen_cv, region, window=window)

        if level_state is not None:
            return level_state

        # Целевой уровень подтверждён — ищем свободный рудник
        logger.info(f"[GOLD] Уровень {GOLD_LEVEL} — целевой. Ищем свободный рудник.")
        clicked_find, _ = find_and_click(GOLD_FIND_IMG, screen_cv, region)
        if clicked_find:
            _gold_ctx.expected = 'find'
            return GoldState.FIND_VISIBLE
        logger.info("[GOLD] Кнопка поиска не найдена. Ждём.")
        return GoldState.RUDNIK_TAB

    # ---- LEVEL LIST / SELECT LEVEL ----
    if current_state in (GoldState.SELECT_LEVEL_VISIBLE, GoldState.LEVEL_LIST_VISIBLE) \
            or _gold_ctx.expected == 'level_list':
        target_path = GOLD_LEVEL_IMAGES[GOLD_LEVEL]

        # Если видно сообщение "нет свободных рудников", пробуем соседний уровень
        no_free_coords, no_free_conf = find_on_screen(get_template(GOLD_NO_FREE_RUDNIK_IMG), screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
        if no_free_coords:
            logger.info(f"[GOLD] На целевом уровне нет свободных мест (conf={no_free_conf:.3f}). Пробуем другой уровень.")
            _gold_ctx.level_select_scroll_tries = _gold_ctx.level_select_scroll_tries + 1
            if _gold_ctx.level_select_scroll_tries > 10:
                logger.info("[GOLD] Везде занято. Завершаем золотодобычу.")
                _gold_ctx.level_select_scroll_tries = 0
                # Не обновляем last_gold_time: золото не запущено, поэтому должно перезапуститься быстро
                return GoldState.COMPLETED
            # Попробуем уровень выше или ниже по кругу
            alternative = GOLD_LEVEL + (1 if _gold_ctx.level_select_scroll_tries % 2 == 1 else -1) * ((_gold_ctx.level_select_scroll_tries + 1) // 2)
            alternative = max(1, min(6, alternative))
            if is_target_level_in_list(screen_cv, region, target=alternative):
                if click_moveon_for_target_level(screen_cv, region, target=alternative):
                    logger.info(f"[GOLD] Пробуем уровень {alternative} вместо {GOLD_LEVEL}.")
                    _gold_ctx.expected = 'rudnik_tab'
                    _gold_ctx.need_level_check = True
                    time.sleep(GOLD_ACTION_DELAY)
                    return GoldState.RUDNIK_TAB
            scroll_in_region(region, 'down' if alternative >= GOLD_LEVEL else 'up', step_ratio=0.08)
            time.sleep(GOLD_ACTION_DELAY)
            return GoldState.LEVEL_LIST_VISIBLE

        if is_target_level_in_list(screen_cv, region, target=GOLD_LEVEL):
            if click_moveon_for_target_level(screen_cv, region, target=GOLD_LEVEL):
                _gold_ctx.expected = 'rudnik_tab'
                _gold_ctx.level_select_scroll_tries = 0
                _gold_ctx.moveon_clicked_at = time.time()
                # Уровень только что выбран явно — повторная проверка не нужна,
                # иначе нераспознанный current_lvl_X снова откроет этот список.
                _gold_ctx.need_level_check = False
                time.sleep(GOLD_ACTION_DELAY)  # Ждём загрузки табы рудника после "Перейти"
                return GoldState.RUDNIK_TAB
            # Кнопка "Перейти" не найдена рядом с уровнем — скроллим чтобы уровкть кнопку
            logger.info(f"[GOLD] Уровень {GOLD_LEVEL} виден, но кнопка 'Перейти' не найдена. Скроллим.")
            found_level, _ = get_list_level(screen_cv, region)
            scroll_in_region(region, _get_scroll_direction(found_level), step_ratio=0.15)
            time.sleep(GOLD_ACTION_DELAY)
            return GoldState.LEVEL_LIST_VISIBLE

        found_level, _ = get_list_level(screen_cv, region)

        _gold_ctx.level_select_scroll_tries = _gold_ctx.level_select_scroll_tries + 1
        if _gold_ctx.level_select_scroll_tries > 20:
            logger.info("[GOLD] Не удалось найти целевой уровень. Сброс.")
            _gold_ctx.expected = None
            _gold_ctx.level_select_scroll_tries = 0
            return GoldState.UNKNOWN

        scroll_in_region(region, _get_scroll_direction(found_level), step_ratio=0.08)
        time.sleep(GOLD_ACTION_DELAY)
        return GoldState.LEVEL_LIST_VISIBLE

    # ---- NO FREE RUDNIK ----
    if current_state == GoldState.NO_FREE_RUDNIK:
        logger.info("[GOLD] На текущем уровне нет свободных рудников. Пробуем открыть выбор уровня.")
        # Если видна кнопка выбора уровня — кликнем
        select_coords, _ = find_on_screen(get_template(GOLD_SELECT_LEVEL_IMG), screen_cv, region)
        if select_coords is None:
            # Возможно, мы на экране добычи — уходим через back
            find_and_click(BACK_IMG, screen_cv, region)
            return GoldState.UNKNOWN
        find_and_click(GOLD_SELECT_LEVEL_IMG, screen_cv, region)
        _gold_ctx.expected = 'level_list'
        _gold_ctx.level_select_scroll_tries = 0
        time.sleep(GOLD_ACTION_DELAY)
        return GoldState.SELECT_LEVEL_VISIBLE

    # ---- FIND (поиск свободного рудника) ----
    if current_state == GoldState.FIND_VISIBLE:
        # Таймаут поиска: если ищем дольше GOLD_SEARCH_TIMEOUT — выходим
        find_started = _gold_ctx.find_started_at
        if find_started is None:
            _gold_ctx.find_started_at = time.time()
            find_started = _gold_ctx.find_started_at
        elapsed_find = time.time() - find_started
        if elapsed_find > GOLD_SEARCH_TIMEOUT:
            logger.info(f"[GOLD] Поиск длится {int(elapsed_find)} сек — таймаут {GOLD_SEARCH_TIMEOUT} сек. Сброс.")
            _gold_ctx.find_started_at = None
            find_and_click(GOLD_CLOSE_IMG, screen_cv, region)
            return GoldState.UNKNOWN

        last_find_click = _gold_ctx.find_clicked_at or 0
        if time.time() - last_find_click >= 0.5:
            logger.info(f"[GOLD] Поиск свободного рудника ({int(elapsed_find)} сек)...")
            find_and_click(GOLD_FIND_IMG, screen_cv, region)
            _gold_ctx.find_clicked_at = time.time()
        else:
            time.sleep(_GOLD_RAPID_POLL)
        return GoldState.FIND_VISIBLE

    # ---- EVENTS: RUDNIK VISIBLE ----
    if current_state == GoldState.EVENTS_RUDNIK_VISIBLE:
        _gold_ctx.expected = 'forward_popup'
        _gold_ctx.swipe_count = 0
        clicked, _ = find_and_click(EVENT_GOLD_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if clicked:
            logger.info(f"[GOLD] Нажимаем на строку события золотодобычи.")
            # pyautogui.click(click_x, click_y)
            time.sleep(GOLD_ACTION_DELAY)
            # Проверяем, открылся ли попап с кнопкой 'Вперёд', на свежем скриншоте
            screen_after = take_screenshot(window, region)
            if screen_after is not None:
                clicked, _ = find_and_click(GOLD_FORWARD_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
                if clicked:
                    logger.info(f"[GOLD] Попап 'Вперёд' открылся")
                    return GoldState.FORWARD_POPUP_VISIBLE
                logger.info("[GOLD] Попап 'Вперёд' не открылся после первого клика, пробуем ещё раз.")
                time.sleep(GOLD_ACTION_DELAY)
            logger.info("[GOLD] Не удалось открыть попап события, продолжаем искать/скроллить.")
            return GoldState.EVENTS_NEED_SCROLL
        return GoldState.EVENTS_MENU_OPEN

    # ---- EVENTS: FORWARD POPUP ----
    if current_state == GoldState.FORWARD_POPUP_VISIBLE:
        _gold_ctx.expected = 'rudnik_tab'
        # Делаем свежий скриншот перед кликом, т.к. попап мог появиться после предыдущего шага
        screen_now = take_screenshot(window, region) if window else screen_cv
        clicked, _ = find_and_click(GOLD_FORWARD_IMG, screen_now, region, threshold=0.55)
        if clicked:
            logger.info("[GOLD] Нажали 'Вперёд'. Ждём открытия табы рудника.")
            time.sleep(GOLD_ACTION_DELAY)
            return GoldState.RUDNIK_TAB
        logger.info("[GOLD] Кнопка 'Вперёд' не найдена, пробуем закрыть попап.")
        find_and_click(GOLD_CLOSE_IMG, screen_now, region)
        return GoldState.EVENTS_MENU_OPEN

    # ---- EVENTS: MENU OPEN, NEED SCROLL ----
    if current_state in (GoldState.EVENTS_MENU_OPEN, GoldState.EVENTS_NEED_SCROLL):
        _gold_ctx.expected = 'events_scroll'

        # Если events.png открыло сразу табу рудника (например, последнее событие),
        # не свайпаем по карусели, а переходим к выбору уровня.
        rudnik_opened_coords, _ = find_on_screen(get_template(GOLD_RUDNIK_OPENED_IMG), screen_cv, region)
        find_coords, _ = find_on_screen(get_template(GOLD_FIND_IMG), screen_cv, region)
        select_coords, _ = find_on_screen(get_template(GOLD_SELECT_LEVEL_IMG), screen_cv, region)
        if rudnik_opened_coords or find_coords or select_coords:
            logger.info("[GOLD] Событие золотодобычи уже открыто (rudnik_tab). Пропускаем свайпы.")
            _gold_ctx.swipe_count = 0
            _gold_ctx.expected = 'rudnik_tab'
            return GoldState.RUDNIK_TAB

        # Если events.png открыло активное событие (не календарь), в верхней карусели
        # будет виден rudnik.png. Кликаем по нему, чтобы переключиться на вкладку рудника.
        rudnik_coords, rudnik_conf = find_on_screen(get_template(GOLD_RUDNIK_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if rudnik_coords:
            rudnik_rel_y = (rudnik_coords[1] - region[1]) / region[3] if region[3] else 1.0
            calendar_opened_coords, _ = find_on_screen(get_template(CALENDAR_OPENED_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
            if rudnik_rel_y < 0.30 and not calendar_opened_coords:
                logger.info(f"[GOLD] Открыто активное событие, переключаемся на вкладку рудника (rudnik.png conf={rudnik_conf:.3f}).")
                pyautogui.click(rudnik_coords[0], rudnik_coords[1])
                time.sleep(GOLD_ACTION_DELAY)
                return GoldState.EVENTS_MENU_OPEN

        # Сначала проверим, не появилась ли иконка золотодобычи после предыдущего свайпа
        gold_coords, _, _ = find_event_gold_in_calendar(screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if gold_coords:
            _gold_ctx.swipe_count = 0
            return GoldState.EVENTS_RUDNIK_VISIBLE

        # Если календарь ещё не открыт (calendar_opened.png не виден) — нажимаем calendar.png
        calendar_opened_coords, _ = find_on_screen(get_template(CALENDAR_OPENED_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if not calendar_opened_coords:
            calendar_coords, _ = find_on_screen(get_template(CALENDAR_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
            if calendar_coords:
                logger.info("[GOLD] Нажимаем calendar.png чтобы открыть календарь событий.")
                find_and_click(CALENDAR_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
                time.sleep(GOLD_ACTION_DELAY)
                return GoldState.EVENTS_MENU_OPEN
            # calendar.png не найден — пробуем свайпать
            logger.info("[GOLD] calendar.png не найден, пробуем свайпать для поиска.")

        # Календарь открыт — свайпаем для поиска события золотодобычи
        swipe_count = _gold_ctx.swipe_count
        if swipe_count < 5:
            # Пролистываем влево к началу списка
            swipe_horizontal(region, 'left')
        else:
            # Ищем золотодобычу, свайпая вправо
            swipe_horizontal(region, 'right')
        _gold_ctx.swipe_count = swipe_count + 1
        if _gold_ctx.swipe_count > 20:
            logger.info("[GOLD] Не удалось найти иконку золотодобычи в меню событий. Сброс.")
            _gold_ctx.swipe_count = 0
            _gold_ctx.expected = None
            return GoldState.UNKNOWN
        return GoldState.EVENTS_NEED_SCROLL

    # ---- MAIN SCREEN ----
    if current_state == GoldState.MAIN_SCREEN:
        # Проверим, не открыт ли уже календарь (event_gold или rudnik виден)
        gold_coords, _, _ = find_event_gold_in_calendar(screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if gold_coords:
            logger.info("[GOLD] Календарь уже открыт, событие золотодобычи видно.")
            _gold_ctx.expected = 'events'
            _gold_ctx.swipe_count = 0
            return GoldState.EVENTS_RUDNIK_VISIBLE

        # Счётчик попыток нажать события
        _gold_ctx.main_screen_tries = _gold_ctx.main_screen_tries + 1

        # Если видна info.png — это попап, кликаем в верхнюю часть экрана для закрытия
        info_coords, _ = find_on_screen(get_template(INFO_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if info_coords:
            logger.info("[GOLD] Видна info.png — попап открыт. Клик в верхнюю часть экрана для закрытия.")
            _click_top_screen(region, reset_main_tries=True)
            return GoldState.UNKNOWN

        # Застревание на main_screen решается только через events.png / calendar.png.
        # Универсальный клик вверх больше не используется здесь — он попадает в магазин/события.
        clicked, _ = find_and_click(EVENTS_IMG, screen_cv, region)
        if not clicked:
            # Если events.png не найден — пробуем calendar.png (иконка календаря в меню событий)
            logger.info("[GOLD] events.png не найден, пробуем calendar.png")
            find_and_click(CALENDAR_IMG, screen_cv, region)
        _gold_ctx.swipe_count = 0
        _gold_ctx.events_clicked_at = time.time()
        time.sleep(GOLD_ACTION_DELAY)
        _gold_ctx.expected = 'events'
        return GoldState.EVENTS_MENU_OPEN

    # ---- UNKNOWN / STUCK RECOVERY ----
    if current_state == GoldState.UNKNOWN:
        logger.info(f"[GOLD] UNKNOWN recovery start. stuck_count={_gold_ctx.stuck_count}, expected={_gold_ctx.expected}")
        clicked_at = _gold_ctx.moveon_clicked_at
        if clicked_at and (time.time() - clicked_at) < 2.0:
            logger.info("[GOLD] Ожидаем завершения перехода после клика 'Перейти'.")
            _gold_ctx.moveon_clicked_at = None
            time.sleep(GOLD_ACTION_DELAY)
            return GoldState.UNKNOWN

        clicked_events_at = _gold_ctx.events_clicked_at
        if clicked_events_at and (time.time() - clicked_events_at) < 3.0:
            logger.info("[GOLD] Ожидаем открытия календаря событий.")
            time.sleep(GOLD_ACTION_DELAY)
            return GoldState.UNKNOWN

        # Если мы недавно открыли события, но оказались в активном событии — свайп по верхней карусели
        if _gold_ctx.expected == 'events' and clicked_events_at \
                and (time.time() - clicked_events_at) < 5.0:
            logger.info("[GOLD] Активное событие открылось вместо календаря. Пробуем свайп по верхней карусели.")
            swipe_horizontal(region, 'right')
            time.sleep(GOLD_ACTION_DELAY)
            return GoldState.UNKNOWN

        # Если мы в процессе поиска/захвата рудника — back/close только мешают,
        # закрывая экран поиска. Вместо этого делаем свежий скриншот и определяем состояние.
        # if _gold_ctx.expected in ('find', 'rudnik_tab'):
            # logger.info("[GOLD] UNKNOWN в контексте поиска рудника: пропускаем recovery back/close, ждём свежий кадр.")
            # _gold_ctx.stuck_count = 0
            # _gold_ctx.stuck_last_action = None
            # time.sleep(_GOLD_RAPID_POLL)
            # return GoldState.UNKNOWN

        _gold_ctx.stuck_count = _gold_ctx.stuck_count + 1
        action = _gold_ctx.stuck_last_action
        if action != 'back':
            logger.info("[GOLD] UNKNOWN recovery: try back")
            find_and_click(BACK_IMG, screen_cv, region)
            _gold_ctx.stuck_last_action = 'back'
        elif action != 'close':
            logger.info("[GOLD] UNKNOWN recovery: try close")
            find_and_click(GOLD_CLOSE_IMG, screen_cv, region)
            _gold_ctx.stuck_last_action = 'close'
        else:
            logger.info("[GOLD] UNKNOWN recovery: try village")
            find_and_click(VILLAGE_IMG, screen_cv, region)
            _gold_ctx.stuck_last_action = None
            _gold_ctx.stuck_count = 0

        time.sleep(GOLD_ACTION_DELAY)
        logger.info("[GOLD] UNKNOWN recovery end")
        return GoldState.UNKNOWN

    return current_state
