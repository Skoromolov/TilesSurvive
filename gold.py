# ==========================================
# ЛОГИКА ЗОЛОТОДОБЫЧИ (стейт-машина)
# ==========================================

import time
import cv2

from config import *
from utils import *
from logger import logger  # Импортируем логгер
from state import load_state, update_state, LAST_GOLD_TIME_KEY, STARTED_AT_KEY, RECALL_REQUESTED_KEY


# ==========================================
# ПЕРЕМЕННЫЕ СОСТОЯНИЙ ЗОЛОТА
# ==========================================
# Загружаем сохранённое состояние, чтобы таймеры переживали перезапуск скрипта.
_saved_state = load_state()
last_gold_time = _saved_state.get(LAST_GOLD_TIME_KEY, time.time())
_gold_ctx = {
    'expected': None,          # подсказка для неоднозначных состояний
    'swipe_count': 0,
    'level_select_scroll_tries': 0,
    'stuck_count': 0,
    'stuck_last_action': None,
    'events_clicked_at': None,
    'moveon_clicked_at': None,
    'recall_requested': _saved_state.get(RECALL_REQUESTED_KEY, False),
    'started_at': _saved_state.get(STARTED_AT_KEY, None),
    'current_mining_level': None,
    'need_level_check': False,
    'main_screen_tries': 0,
    'raid_icon_clicks': 0,
    'find_started_at': None,
    'exit_attempts': 0,
}
gold_first_run = True         # при первом запуске сразу идём в золото после heal/raid, не ждём GOLD_INTERVAL



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
    logger.debug(f"[GOLD] До рудника: {m:02d}:{s:02d}")
    return False


def update_gold_time():
    """Обновить время последнего посещения рудника."""
    global last_gold_time
    last_gold_time = time.time()
    logger.info(f"[GOLD] Время обновлено: {time.ctime(last_gold_time)}")


def gold_mission_active():
    """Отряд отправлен добывать золото и ещё не отозван."""
    return _gold_ctx.get('started_at') is not None and not _gold_ctx['recall_requested']


def gold_mission_should_recall():
    """Пора отозвать отряд (45 минут прошли)."""
    recall_status, _ = _check_recall_needed()
    return recall_status == 'recall'


def update_gold_time():
    """Обновить время последнего посещения рудника и сохранить в файл."""
    global last_gold_time
    last_gold_time = time.time()
    update_state(**{LAST_GOLD_TIME_KEY: last_gold_time})
    logger.info(f"[GOLD] Время обновлено: {time.ctime(last_gold_time)}")


def start_gold_mission():
    """Зафиксировать запуск добычи на целевом уровне и сохранить таймер."""
    now = time.time()
    _gold_ctx['started_at'] = now
    _gold_ctx['current_mining_level'] = GOLD_LEVEL
    _gold_ctx['recall_requested'] = False
    update_state(**{STARTED_AT_KEY: now, RECALL_REQUESTED_KEY: False})
    logger.info(f"[GOLD] Отряд отправлен на уровень {GOLD_LEVEL} в {time.ctime()}")


def clear_gold_mission():
    """Сбросить данные активной добычи и сохранить в файл."""
    _gold_ctx['started_at'] = None
    _gold_ctx['current_mining_level'] = None
    _gold_ctx['recall_requested'] = False
    update_state(**{STARTED_AT_KEY: None, RECALL_REQUESTED_KEY: False})


def reset_gold_context():
    """Сбросить вспомогательный контекст перед новым заходом в режим GOLD."""
    _gold_ctx['expected'] = None
    _gold_ctx['swipe_count'] = 0
    _gold_ctx['level_select_scroll_tries'] = 0
    _gold_ctx['stuck_count'] = 0
    _gold_ctx['stuck_last_action'] = None
    _gold_ctx['events_clicked_at'] = None
    _gold_ctx['moveon_clicked_at'] = None
    # recall_requested и started_at не сбрасываем — они хранятся в файле состояния
    _gold_ctx['need_level_check'] = False
    _gold_ctx['main_screen_tries'] = 0
    _gold_ctx['raid_icon_clicks'] = 0
    _gold_ctx['find_started_at'] = None
    _gold_ctx['exit_attempts'] = 0


# ==========================================
# ХЕЛПЕРЫ ДЛЯ УСТРАНЕНИЯ ДУБЛИРОВАНИЯ
# ==========================================
def _complete_mission(log_msg="[GOLD] ✓ Золотодобыча запущена!"):
    """Зафиксировать успешный запуск и вернуть COMPLETED."""
    start_gold_mission()
    update_gold_time()
    logger.info(log_msg)
    return GoldState.COMPLETED


def _check_mining_result(screen_after, region):
    """
    Проверить результат отправки отряда на скриншоте.
    Возвращает:
        ('completed', None) — отряд отправлен (return.png / my_rudnik.png видны)
        ('summary', None) — открылось окно 'Общая сила' с кнопкой 'Добывать'
        ('go', None)       — открылось окно отправки отряда с кнопкой 'Марш'
        ('unknown', None)  — окно закрылось, состояние не определено
    """
    if screen_after is None:
        return 'unknown', None
    return_coords, _ = find_on_screen(get_template(GOLD_RETURN_IMG), screen_after, region)
    my_rudnik_coords, _ = find_on_screen(get_template(GOLD_MY_RUDNIK_IMG), screen_after, region)
    if return_coords or my_rudnik_coords:
        return 'completed', None

    # Окно с кнопкой 'Марш' (GO) имеет приоритет — по нему нужно нажать GO
    go_coords, _ = find_on_screen(get_template(GOLD_GO_IMG), screen_after, region)
    if go_coords:
        return 'go', None

    # Окно с кнопкой 'Добывать' — занятое место
    work_coords, _ = find_on_screen(get_template(GOLD_WORK_IMG), screen_after, region)
    if work_coords:
        return 'summary', None

    # Если summary text остался, но ни work ни go не видны — значит это непонятный попап
    summary_coords, _ = find_on_screen(get_template(GOLD_SUMMARY_STRENGTH_TEXT_IMG), screen_after, region)
    if summary_coords:
        return 'summary', None

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
                time.sleep(GOLD_ACTION_DELAY / 2)
                current_screen = take_screenshot(window, region)
                if current_screen is None:
                    current_screen = screen_cv
            else:
                time.sleep(GOLD_ACTION_DELAY / 2)

    if current is not None and current != GOLD_LEVEL:
        logger.info(f"{log_prefix} Уровень {current}, нужен {GOLD_LEVEL}. Открываем выбор уровня.")
        _gold_ctx['need_level_check'] = True
        find_and_click(GOLD_SELECT_LEVEL_IMG, current_screen, region)
        _gold_ctx['expected'] = 'level_list'
        _gold_ctx['level_select_scroll_tries'] = 0
        time.sleep(GOLD_ACTION_DELAY)
        return GoldState.SELECT_LEVEL_VISIBLE

    if current == GOLD_LEVEL:
        _gold_ctx['need_level_check'] = False
        logger.info(f"{log_prefix} Уровень проверен: {current}. Продолжаем добычу.")
        return None

    # Уровень не распознан — пробуем открыть выбор уровня
    select_coords, _ = find_on_screen(get_template(GOLD_SELECT_LEVEL_IMG), current_screen, region)
    if select_coords:
        logger.info(f"{log_prefix} Текущий уровень не виден после {max_attempts} попыток. Открываем выбор уровня.")
        _gold_ctx['need_level_check'] = True
        find_and_click(GOLD_SELECT_LEVEL_IMG, current_screen, region)
        _gold_ctx['expected'] = 'level_list'
        _gold_ctx['level_select_scroll_tries'] = 0
        time.sleep(GOLD_ACTION_DELAY)
        return GoldState.SELECT_LEVEL_VISIBLE

    return None


def _click_top_screen(region, reset_main_tries=False):
    """Клик в верхнюю часть экрана для закрытия попапа/сброса UI."""
    click_x = region[0] + region[2] // 2
    click_y = region[1] + int(region[3] * 0.15)
    pyautogui.click(click_x, click_y)
    time.sleep(GOLD_ACTION_DELAY)
    if reset_main_tries:
        _gold_ctx['main_screen_tries'] = 0


def _check_recall_needed():
    """
    Проверить, нужен ли отзыв отряда.
    Возвращает:
        ('recall', reason) — нужен отзыв
        ('sync', remaining_seconds) — started_at утерян, синхронизирован таймер
        ('active', elapsed_seconds) — добыча активна, отзыв не нужен
    """
    now = time.time()
    started = _gold_ctx.get('started_at')

    if started is not None:
        elapsed = now - started
        if elapsed >= GOLD_MINING_DURATION:
            logger.info(f"[GOLD] Добыча идёт {int(elapsed)} сек, порог {GOLD_MINING_DURATION} сек. Нужен отзыв.")
            _gold_ctx['recall_requested'] = True
            update_state(**{RECALL_REQUESTED_KEY: True})
            return 'recall', int(elapsed)
        return 'active', int(elapsed)

    # Fallback: started_at утерян — ориентируемся на last_gold_time
    elapsed_since_last_gold = now - last_gold_time
    if elapsed_since_last_gold >= GOLD_MINING_DURATION:
        logger.info(f"[GOLD] started_at утерян, но с последнего золота прошло {int(elapsed_since_last_gold)} сек. Нужен отзыв.")
        _gold_ctx['recall_requested'] = True
        update_state(**{RECALL_REQUESTED_KEY: True})
        return 'recall', int(elapsed_since_last_gold)

    # Синхронизируем таймер, но не обновляем last_gold_time,
    # чтобы следующая проверка recall не зациклилась на "только что синхронизировано".
    _gold_ctx['started_at'] = now
    update_state(**{STARTED_AT_KEY: now})
    remaining = int(GOLD_MINING_DURATION - elapsed_since_last_gold)
    logger.info(f"[GOLD] Активная добыча без известного старта. Синхронизация таймера. До recall по last_gold_time: {remaining} сек.")
    return 'sync', remaining


def _take_result_screenshot(window, region, delay=None):
    """Сделать скриншот после клика и подождать GOLD_ACTION_DELAY."""
    if delay is None:
        delay = GOLD_ACTION_DELAY
    time.sleep(delay)
    screen_after = take_screenshot(window, region)
    if screen_after is None:
        logger.warning("[GOLD] Не удалось получить скриншот результата, берём старый кадр.")
    return screen_after


def _click_and_check_completion(button_img, log_msg, window, screen_cv, region, post_click_delay=None, max_attempts=1):
    """
    Нажать кнопку отправки отряда и проверить результат.
    Возвращает:
        ('completed', None) — отряд отправлен
        ('summary', None) — открылось окно 'Общая сила' (место занято)
        ('other', screen_after) — другое состояние, нужна дальнейшая проверка
    """
    logger.info(log_msg)
    clicked, _ = find_and_click(button_img, screen_cv, region)
    if not clicked:
        return 'other', screen_cv

    for attempt in range(1, max_attempts + 1):
        screen_after = _take_result_screenshot(window, region, delay=post_click_delay)
        if screen_after is None:
            continue
        result, _ = _check_mining_result(screen_after, region)
        if result == 'completed':
            return 'completed', None
        if result == 'summary':
            return 'summary', None
        # Если не завершено и не summary, возможно появится GO/MARCH позже.
        # Повторяем скриншот до max_attempts.
        if attempt < max_attempts:
            logger.debug(f"[GOLD] Попытка {attempt}: результат не определён, ждём ещё.")
    return 'other', screen_after if screen_after is not None else screen_cv


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
        _gold_ctx['expected'] = 'rudnik_tab'
        _gold_ctx['need_level_check'] = True  # после закрытия попапа уровень может измениться
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
        logger.debug(f"[GOLD] Распознан текущий уровень: {best_level} (conf={best_conf:.3f})")
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
        logger.debug(f"[GOLD] В списке найден уровень {best_level} (conf={best_conf:.3f})")
        return best_level, best_coords
    return None, None


def is_target_level_in_list(screen_cv, region, target=GOLD_LEVEL, threshold=None):
    """Проверить, виден ли целевой уровень в списке."""
    if threshold is None:
        threshold = GOLD_LIST_LEVEL_CONFIDENCE_THRESHOLD
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
        logger.debug(f"[GOLD] lvl_{target}.png не найден на экране.")
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
            logger.debug(f"[GOLD] Кнопка 'Перейти' отсутствует как шаблон, клик под уровень {target} ({fallback_x:.0f}, {fallback_y:.0f}), conf={conf_lvl:.3f}")
            return True
        return False

    h_btn, w_btn = btn_template.shape[:2]
    btn_matches = find_all_on_screen(btn_template, screen_cv, region, btn_threshold)

    best_pair = None
    best_score = -1.0
    if btn_matches:
        for cx_btn, cy_btn, conf_btn in btn_matches:
            for cx_lvl_i, cy_lvl_i, conf_lvl_i in lvl_matches:
                vertical_gap = abs(cy_btn - cy_lvl_i)
                horizontal_gap = abs(cx_btn - cx_lvl_i)
                # Кнопка "Перейти" — большая (254x50), карточка уровня ~270px высотой.
                # Увеличили допустимый vertical_gap до h_btn * 6 (было 3).
                if vertical_gap < h_btn * 6 and horizontal_gap < max(w_btn, w_lvl) * 3:
                    score = conf_lvl_i + conf_btn - vertical_gap / 100.0
                    if score > best_score:
                        best_score = score
                        best_pair = (cx_btn, cy_btn, conf_btn, cx_lvl_i, cy_lvl_i, conf_lvl_i)

    if best_pair is None:
        logger.debug(f"[GOLD] Кнопка 'Перейти' не найдена рядом с уровнем {target}. "
              f"lvl_matches={len(lvl_matches)}, btn_matches={len(btn_matches) if btn_matches else 0}. "
              f"Возможно уровень {target} за пределами экрана — нужен скролл.")
        return False

    cx_btn, cy_btn, conf_btn, cx_lvl, cy_lvl, conf_lvl = best_pair
    btn_top = cy_btn - h_btn / 2
    btn_bottom = cy_btn + h_btn / 2
    if btn_top < region_top + 20 or btn_bottom > region_bottom - 20:
        if fallback_click:
            pyautogui.click(*fallback_click)
            logger.debug(f"[GOLD] Кнопка 'Перейти' у уровня {target} частично за краем, клик под карточку ({fallback_x:.0f}, {fallback_y:.0f})")
            return True
        logger.debug(f"[GOLD] Кнопка 'Перейти' у уровня {target} частично за краем экрана. Скроллим.")
        return False

    pyautogui.click(cx_btn, cy_btn)
    logger.debug(f"[GOLD] Нажата 'Перейти' у уровня {target} ({cx_btn:.0f}, {cy_btn:.0f}), conf=({conf_lvl:.3f}/{conf_btn:.3f})")
    return True


# ==========================================
# ОПРЕДЕЛЕНИЕ СОСТОЯНИЯ ЗОЛОТОДОБЫЧИ
# ==========================================
def determine_gold_state(screen_cv, region):
    """Возвращает GoldState на основе текущего экрана (приоритет сверху-вниз)."""

    # 1. Reconnect
    # coords, _ = find_on_screen(get_template(RECONNECT_IMG), screen_cv, region)
    # if coords:
    #     return GoldState.RECONNECT_POPUP
    # coords, _ = find_on_screen(get_template(RECONNECT_REPEAT_IMG), screen_cv, region)
    # if coords:
    #     return GoldState.RECONNECT_REPEAT_POPUP

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
    if _gold_ctx.get('expected') != 'events':
        find_visible, _ = find_on_screen(get_template(GOLD_FIND_IMG), screen_cv, region)
        select_visible, _ = find_on_screen(get_template(GOLD_SELECT_LEVEL_IMG), screen_cv, region)

        # Если find.png видна и мы уже нажимали find (expected='find') — продолжаем поиск
        if find_visible and _gold_ctx.get('expected') == 'find':
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
        found_level, _ = get_list_level(screen_cv, region, threshold=GOLD_LIST_LEVEL_CONFIDENCE_THRESHOLD)
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
    heal_town_coords, _ = find_on_screen(get_template(HEAL_TOWN_IMG), screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
    if heal_town_coords:
        return GoldState.MAIN_SCREEN
    help_hands_coords, _ = find_on_screen(get_template(HELP_HANDS_IMG), screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
    if help_hands_coords:
        return GoldState.MAIN_SCREEN
    souz_coords, _ = find_on_screen(get_template(SOUZ_IMG), screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
    if souz_coords:
        return GoldState.MAIN_SCREEN
    mail_coords, _ = find_on_screen(get_template(MAIL_IMG), screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
    if mail_coords:
        return GoldState.MAIN_SCREEN

    # Если видна info.png — это попап, нужно кликнуть в верхнюю часть экрана
    info_coords, _ = find_on_screen(get_template(INFO_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if info_coords:
        return GoldState.MAIN_SCREEN

    # 16. Меню событий/календарь — calendar.png, calendar_opened.png или back.png видна.
    #     Если events.png видна — мы на главном экране (проверка выше).
    #     Пропускаем если expected='rudnik_tab' — мы в процессе перехода на табу рудника
    if _gold_ctx.get('expected') not in ('rudnik_tab', 'forward_popup'):
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
        if _gold_ctx.get('expected') == 'events':
            return GoldState.EVENTS_MENU_OPEN
        # Иначе: back в календаре — в верхней трети; в окне рейда back обычно внизу
        back_rel_y = (back_coords[1] - region[1]) / region[3] if region[3] else 0
        if back_rel_y < 0.35:
            return GoldState.EVENTS_MENU_OPEN
        # Иначе это похоже на back внизу экрана (рейд, попап и т.п.) — не считаем календарём

    return GoldState.UNKNOWN


# ==========================================
# ОБРАБОТКА СОСТОЯНИЙ ЗОЛОТОДОБЫЧИ
# ==========================================
def process_gold(screen_cv, region, last_gold_state, window):
    """Обработать одно состояние золотодобычи; одно действие за вызов."""
    current_state = determine_gold_state(screen_cv, region)

    if current_state != last_gold_state:
        logger.debug(f"[GOLD] Состояние: {current_state.value}")
        save_debug_screenshot(screen_cv, f"gold_{current_state.value}")

    # ---- RETURN BUTTON ----
    if current_state == GoldState.RETURN_BUTTON_VISIBLE:
        if _gold_ctx.get('recall_requested'):
            logger.info("[GOLD] Отряд занят добычей на этом уровне. Отзываем.")
            clicked, _ = find_and_click(GOLD_RETURN_IMG, screen_cv, region)
            if clicked:
                return GoldState.RETURN_CONFIRM_VISIBLE
        current = get_current_level(screen_cv, region)
        if current:
            _gold_ctx['current_mining_level'] = current
        return _complete_mission("[GOLD] ✓ Золотодобыча запущена (return.png видна, отзыв не требуется).")

    # ---- RETURN CONFIRM ----
    if current_state == GoldState.RETURN_CONFIRM_VISIBLE:
        find_and_click(GOLD_RETURN_BOYS_IMG, screen_cv, region)
        clear_gold_mission()
        _gold_ctx['expected'] = 'rudnik_tab'
        _gold_ctx['need_level_check'] = True
        logger.info("[GOLD] Отряд отозван.")
        return GoldState.RUDNIK_TAB

    # ---- FINISH BUTTON ----
    if current_state == GoldState.FINISH_VISIBLE:
        logger.info("[GOLD] Нажимаем 'Завершить' после отзыва/выбивания отряда.")
        find_and_click(GOLD_FINISH_IMG, screen_cv, region)
        # Добыча завершена — сбрасываем миссию, чтобы заново искать и сесть на это же место.
        clear_gold_mission()
        _gold_ctx['need_level_check'] = True
        _gold_ctx['expected'] = 'rudnik_tab'
        return GoldState.RUDNIK_TAB

    # ---- ADVICE / 45-MIN POPUP ----
    if current_state == GoldState.ADVICE_VISIBLE:
        # Попап "СОВЕТ" с ограничением отзыва раньше 45 минут (для уровней 5-6).
        # Подтверждаем его и синхронизируем таймеры, чтобы не пытаться отозвать сразу снова.
        if _gold_ctx.get('recall_requested'):
            logger.info("[GOLD] Попап 'СОВЕТ': отзыв пока невозможен. Подтверждаем.")
            # Сначала пробуем оранжевую кнопку, потом стандартную confirm.png
            clicked, _ = find_and_click(GOLD_CONFIRM_ORANGE_IMG, screen_cv, region)
            if not clicked:
                find_and_click(GOLD_CONFIRM_IMG, screen_cv, region)
            # Синхронизируем таймер: считаем, что добыча началась сейчас,
            # и через GOLD_MINING_DURATION снова попробуем отозвать.
            start_gold_mission()
            update_gold_time()
            _gold_ctx['recall_requested'] = False
            logger.info("[GOLD] Таймеры синхронизированы после попапа 'СОВЕТ'. Возвращаемся в основной цикл.")
            return GoldState.COMPLETED
        logger.info("[GOLD] Нажимаем 'Подтвердить' в попапе 'СОВЕТ'.")
        clicked, _ = find_and_click(GOLD_CONFIRM_ORANGE_IMG, screen_cv, region)
        if not clicked:
            find_and_click(GOLD_CONFIRM_IMG, screen_cv, region)
        _gold_ctx['need_level_check'] = True
        return GoldState.RUDNIK_TAB

    # ---- CONFIRM BUTTON ----
    if current_state == GoldState.CONFIRM_VISIBLE:
        # Если бот пытался отозвать отряд, а игра показала попап "СОВЕТ" с
        # текстом "Чтобы отозвать отряд, необходимо добывать ... в течение 45 мин",
        # подтверждаем его и выходим в HEAL. Отряд ещё не может быть отозван.
        if _gold_ctx.get('recall_requested'):
            logger.info("[GOLD] Подтверждаем попап 'СОВЕТ' (отзыв пока невозможен).")
            find_and_click(GOLD_CONFIRM_IMG, screen_cv, region)
            # Возвращаемся в main, не сбрасывая last_gold_time — отряд продолжает добыву,
            # и через реальные 45 минут с момента старта бот снова попробует отозвать.
            return GoldState.COMPLETED
        logger.info("[GOLD] Нажимаем 'Подтвердить'.")
        find_and_click(GOLD_CONFIRM_IMG, screen_cv, region)
        _gold_ctx['need_level_check'] = True
        return GoldState.RUDNIK_TAB

    # ---- SUMMARY STRENGTH TEXT POPUP ----
    if current_state == GoldState.SUMMARY_STRENGTH_TEXT_VISIBLE:
        # Это может быть либо попап с кнопкой 'Добывать' (work.png),
        # либо уже окно отправки отряда с кнопкой 'Марш' (go.png).
        go_coords, _ = find_on_screen(get_template(GOLD_GO_IMG), screen_cv, region)
        if go_coords:
            logger.info("[GOLD] Открыто окно отправки отряда (кнопка 'Марш'). Нажимаем.")
            result, _ = _click_and_check_completion(
                GOLD_GO_IMG,
                "[GOLD] Нажимаем 'Марш' для отправки отряда.",
                window, screen_cv, region,
                post_click_delay=2.0,
                max_attempts=3
            )
            if result == 'completed':
                return _complete_mission("[GOLD] ✓ Золотодобыча запущена через 'Марш'!")
            if result in ('summary', 'go'):
                logger.info("[GOLD] После 'Марш' всё ещё открыто окно отправки/общей силы.")
                return GoldState.SUMMARY_STRENGTH_TEXT_VISIBLE
            return GoldState.UNKNOWN

        # Сначала пытаемся нажать "Добывать" (join.png / work.png).
        join_coords, _ = find_on_screen(get_template(GOLD_WORK_IMG), screen_cv, region)
        if join_coords:
            result, screen_after = _click_and_check_completion(
                GOLD_WORK_IMG,
                "[GOLD] Нажимаем 'Добывать' для отправки отряда.",
                window, screen_cv, region,
                post_click_delay=1.0,
                max_attempts=2
            )
            if result == 'completed':
                return _complete_mission("[GOLD] ✓ Золотодобыча запущена!")
            if result == 'go':
                logger.info("[GOLD] После 'Добывать' открылось окно с 'Марш'. Обработаем его.")
                return GoldState.SUMMARY_STRENGTH_TEXT_VISIBLE
            if result == 'summary':
                logger.info("[GOLD] После 'Добывать' окно осталось — место занято. Закрываем попап.")
                return _close_to_rudkin_tab(screen_after, region, window)
            # result == 'unknown': проверим, не открылось ли GO-окно на всякий случай
            screen_for_go = screen_after if screen_after is not None else screen_cv
            go_coords, _ = find_on_screen(get_template(GOLD_GO_IMG), screen_for_go, region)
            if go_coords:
                logger.info("[GOLD] После 'Добывать' обнаружено окно с 'Марш'. Обработаем его.")
                return GoldState.SUMMARY_STRENGTH_TEXT_VISIBLE

            # Если клик 'Добывать' не сработал (окно не закрылось), не уходим в UNKNOWN —
            # явно проверяем, осталось ли окно, чтобы избежать зацикливания.
            screen_for_check = screen_after if screen_after is not None else screen_cv
            still_summary, _ = find_on_screen(get_template(GOLD_SUMMARY_STRENGTH_TEXT_IMG), screen_for_check, region)
            if still_summary:
                logger.info("[GOLD] После 'Добывать' окно 'Общая сила' всё ещё открыто. Повторим попытку.")
                return GoldState.SUMMARY_STRENGTH_TEXT_VISIBLE

            logger.info("[GOLD] После 'Добывать' окно 'Общая сила' закрылось. Переопределяем состояние.")
            return GoldState.UNKNOWN

        logger.info("[GOLD] В окне 'Общая сила' нет кнопки 'Добывать'/'Марш'. Закрываем попап.")
        return _close_to_rudkin_tab(screen_cv, region, window)

    # ---- GO / WORK / GRIND ----
    if current_state == GoldState.GO_VISIBLE:
        result, screen_after = _click_and_check_completion(
            GOLD_GO_IMG,
            "[GOLD] Нажимаем 'GO' для отправки отряда.",
            window, screen_cv, region,
            post_click_delay=2.0,
            max_attempts=3
        )
        if result == 'completed':
            return _complete_mission("[GOLD] ✓ Золотодобыча запущена!")
        if result in ('summary', 'go'):
            logger.info("[GOLD] После 'GO' всё ещё открыто окно отправки/общей силы. Обработаем его.")
            return GoldState.SUMMARY_STRENGTH_TEXT_VISIBLE

        # GO нажали, но результата нет — проверяем, не застряли ли в попапе
        screen_for_check = screen_after if screen_after is not None else screen_cv
        work_coords, _ = find_on_screen(get_template(GOLD_WORK_IMG), screen_for_check, region)
        go_coords, _ = find_on_screen(get_template(GOLD_GO_IMG), screen_for_check, region)
        if work_coords or go_coords:
            logger.info("[GOLD] Застряли в попапе (видны work/go). Закрываем.")
            find_and_click(GOLD_CLOSE_IMG, screen_for_check, region)
            time.sleep(GOLD_ACTION_DELAY)
            # После закрытия попапа проверяем, не вернулись ли в rudnik_tab
            screen_after_close = _take_result_screenshot(window, region)
            if screen_after_close is not None:
                find_after, _ = find_on_screen(get_template(GOLD_FIND_IMG), screen_after_close, region)
                select_after, _ = find_on_screen(get_template(GOLD_SELECT_LEVEL_IMG), screen_after_close, region)
                if find_after or select_after:
                    logger.info("[GOLD] После закрытия попапа вернулись в rudnik_tab. Продолжаем поиск.")
                    _gold_ctx['expected'] = 'rudnik_tab'
                    _gold_ctx['need_level_check'] = True
                    _gold_ctx['find_started_at'] = None
                    return GoldState.RUDNIK_TAB

        _gold_ctx['expected'] = 'rudnik_tab'
        _gold_ctx['need_level_check'] = True
        return GoldState.RUDNIK_TAB

    if current_state == GoldState.WORK_VISIBLE:
        result, _ = _click_and_check_completion(
            GOLD_WORK_IMG,
            "[GOLD] Нажимаем 'WORK' для отправки отряда.",
            window, screen_cv, region,
            post_click_delay=0.2,
            max_attempts=1
        )
        if result == 'completed':
            return _complete_mission("[GOLD] ✓ Золотодобыча запущена!")
        if result == 'summary':
            logger.info("[GOLD] После 'WORK' открылось окно 'Общая сила'. Обработаем его.")
            return GoldState.SUMMARY_STRENGTH_TEXT_VISIBLE
        if result == 'go':
            logger.info("[GOLD] После 'WORK' открылось окно с 'Марш'. Обработаем его.")
            return GoldState.GO_VISIBLE

        return GoldState.GO_VISIBLE

    if current_state == GoldState.GRIND_VISIBLE:
        result, screen_after = _click_and_check_completion(
            GOLD_GRIND_IMG,
            "[GOLD] Нажимаем 'GRIND'.",
            window, screen_cv, region,
            post_click_delay=0.2,
            max_attempts=1
        )
        if result == 'completed':
            return _complete_mission("[GOLD] ✓ Золотодобыча запущена!")
        if result == 'summary':
            logger.info("[GOLD] После 'GRIND' открылось окно 'Общая сила'.")
            return GoldState.SUMMARY_STRENGTH_TEXT_VISIBLE
        if result == 'go':
            logger.info("[GOLD] После 'GRIND' открылось окно с 'Марш'. Обработаем его.")
            return GoldState.GO_VISIBLE

        screen_for_check = screen_after if screen_after is not None else screen_cv
        free_coords, _ = find_on_screen(get_template(GOLD_FREE_PLACE_IMG), screen_for_check, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
        if free_coords:
            logger.info("[GOLD] После 'GRIND' найдено свободное место.")
            return GoldState.FREE_PLACE_VISIBLE

        _gold_ctx['expected'] = 'rudnik_tab'
        _gold_ctx['need_level_check'] = True
        return GoldState.RUDNIK_TAB

    # ---- FREE PLACE ----
    if current_state == GoldState.FREE_PLACE_VISIBLE:
        level_state = _ensure_target_level(screen_cv, region, window=window)
        if level_state is not None:
            return level_state

        result, screen_after = _click_and_check_completion(
            GOLD_FREE_PLACE_IMG,
            "[GOLD] Нажимаем свободное место.",
            window, screen_cv, region,
            post_click_delay=1.0,
            max_attempts=1
        )
        if result == 'completed':
            return _complete_mission("[GOLD] ✓ Золотодобыча запущена!")
        if result == 'go':
            logger.info("[GOLD] После 'FREE_PLACE' открылось окно с 'Марш'. Обработаем его.")
            return GoldState.SUMMARY_STRENGTH_TEXT_VISIBLE
        if result == 'summary':
            logger.info("[GOLD] После 'FREE_PLACE' открылось окно 'Общая сила'.")
            return GoldState.SUMMARY_STRENGTH_TEXT_VISIBLE

        screen_for_check = screen_after if screen_after is not None else screen_cv
        # Если после нажатия ничего не изменилось — возможно, клик не прошёл
        still_free, _ = find_on_screen(get_template(GOLD_FREE_PLACE_IMG), screen_for_check, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
        if still_free:
            logger.info("[GOLD] Свободное место всё ещё видно. Попробуем кликнуть ещё раз в следующей итерации.")
            _gold_ctx['expected'] = 'free_place'
            return GoldState.FREE_PLACE_VISIBLE

        # Проверим, не открылось ли GO-окно
        go_coords, _ = find_on_screen(get_template(GOLD_GO_IMG), screen_for_check, region)
        if go_coords:
            logger.info("[GOLD] После 'FREE_PLACE' открылось окно с 'Марш' (быстрая проверка). Обработаем его.")
            return GoldState.GO_VISIBLE

        logger.info("[GOLD] После 'FREE_PLACE' не появилось окна отправки. Продолжаем.")
        return GoldState.UNKNOWN

    # ---- MY RUDNIK / ACTIVE MINING ----
    if current_state in (GoldState.MY_RUDNIK_VISIBLE, GoldState.RAID_LEVEL_ICON_VISIBLE):
        current = get_current_level(screen_cv, region)
        if current:
            _gold_ctx['current_mining_level'] = current

        needs_recall = _gold_ctx.get('recall_requested', False)
        if not needs_recall:
            recall_status, recall_value = _check_recall_needed()
            needs_recall = recall_status == 'recall'

        if needs_recall:
            return_coords, _ = find_on_screen(get_template(GOLD_RETURN_IMG), screen_cv, region)
            if return_coords:
                logger.info("[GOLD] Отряд занят добычей. Отзываем.")
                find_and_click(GOLD_RETURN_IMG, screen_cv, region)
                return GoldState.RETURN_CONFIRM_VISIBLE
            # return.png не видна — открываем детали нашего рудника
            my_rudnik_coords, _ = find_on_screen(get_template(GOLD_MY_RUDNIK_IMG), screen_cv, region)
            if my_rudnik_coords:
                logger.info("[GOLD] Открываем детали рудника (my_rudnik.png).")
                find_and_click(GOLD_MY_RUDNIK_IMG, screen_cv, region)
                time.sleep(GOLD_ACTION_DELAY)
                return GoldState.UNKNOWN
            logger.info("[GOLD] recall_requested, но не видно ни return.png, ни my_rudnik.png. Ждём.")
            time.sleep(GOLD_ACTION_DELAY)
            return GoldState.UNKNOWN

        # Добыча активна, отзыв не требуется — выходим
        started = _gold_ctx.get('started_at')
        if started is not None:
            elapsed = int(time.time() - started)
            logger.info(f"[GOLD] Добыча активна ({elapsed//60} мин).")
        else:
            logger.info("[GOLD] Добыча активна, таймер синхронизирован.")

        # Обновляем last_gold_time, чтобы should_do_gold() не лез в золото раньше
        # следующего GOLD_INTERVAL. Отзыв всё равно контролируется started_at.
        update_gold_time()
        return GoldState.COMPLETED

    # ---- RUDNIK TAB (выбор / поиск уровня) ----
    if current_state == GoldState.RUDNIK_TAB:
        _gold_ctx['expected'] = 'rudnik_tab'
        _gold_ctx['raid_icon_clicks'] = 0
        _gold_ctx['find_started_at'] = None  # сброс таймаута поиска

        level_state = _ensure_target_level(screen_cv, region, window=window)
        if level_state is not None:
            return level_state

        # Целевой уровень подтверждён — ищем свободный рудник
        logger.info(f"[GOLD] Уровень {GOLD_LEVEL} — целевой. Ищем свободный рудник.")
        clicked_find, _ = find_and_click(GOLD_FIND_IMG, screen_cv, region)
        if clicked_find:
            _gold_ctx['expected'] = 'find'
            return GoldState.FIND_VISIBLE
        logger.info("[GOLD] Кнопка поиска не найдена. Ждём.")
        return GoldState.RUDNIK_TAB

    # ---- LEVEL LIST / SELECT LEVEL ----
    if current_state in (GoldState.SELECT_LEVEL_VISIBLE, GoldState.LEVEL_LIST_VISIBLE) \
            or _gold_ctx.get('expected') == 'level_list':
        target_path = GOLD_LEVEL_IMAGES[GOLD_LEVEL]

        # Если видно сообщение "нет свободных рудников", пробуем соседний уровень
        no_free_coords, no_free_conf = find_on_screen(get_template(GOLD_NO_FREE_RUDNIK_IMG), screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
        if no_free_coords:
            logger.info(f"[GOLD] На целевом уровне нет свободных мест (conf={no_free_conf:.3f}). Пробуем другой уровень.")
            _gold_ctx['level_select_scroll_tries'] = _gold_ctx.get('level_select_scroll_tries', 0) + 1
            if _gold_ctx['level_select_scroll_tries'] > 10:
                logger.info("[GOLD] Везде занято. Завершаем золотодобычу.")
                _gold_ctx['level_select_scroll_tries'] = 0
                # Не обновляем last_gold_time: золото не запущено, поэтому должно перезапуститься быстро
                return GoldState.COMPLETED
            # Попробуем уровень выше или ниже по кругу
            alternative = GOLD_LEVEL + (1 if _gold_ctx['level_select_scroll_tries'] % 2 == 1 else -1) * ((_gold_ctx['level_select_scroll_tries'] + 1) // 2)
            alternative = max(1, min(6, alternative))
            if is_target_level_in_list(screen_cv, region, target=alternative):
                if click_moveon_for_target_level(screen_cv, region, target=alternative):
                    logger.info(f"[GOLD] Пробуем уровень {alternative} вместо {GOLD_LEVEL}.")
                    _gold_ctx['expected'] = 'rudnik_tab'
                    _gold_ctx['need_level_check'] = True
                    time.sleep(GOLD_ACTION_DELAY)
                    return GoldState.RUDNIK_TAB
            scroll_in_region(region, 'down' if alternative >= GOLD_LEVEL else 'up', step_ratio=0.08)
            time.sleep(GOLD_ACTION_DELAY)
            return GoldState.LEVEL_LIST_VISIBLE

        if is_target_level_in_list(screen_cv, region, target=GOLD_LEVEL):
            if click_moveon_for_target_level(screen_cv, region, target=GOLD_LEVEL):
                _gold_ctx['expected'] = 'rudnik_tab'
                _gold_ctx['level_select_scroll_tries'] = 0
                _gold_ctx['moveon_clicked_at'] = time.time()
                # Уровень только что выбран явно — повторная проверка не нужна,
                # иначе нераспознанный current_lvl_X снова откроет этот список.
                _gold_ctx['need_level_check'] = False
                time.sleep(GOLD_ACTION_DELAY)  # Ждём загрузки табы рудника после "Перейти"
                return GoldState.RUDNIK_TAB
            # Кнопка "Перейти" не найдена рядом с уровнем — скроллим чтобы уровкть кнопку
            logger.info(f"[GOLD] Уровень {GOLD_LEVEL} виден, но кнопка 'Перейти' не найдена. Скроллим.")
            found_level, _ = get_list_level(screen_cv, region)
            scroll_in_region(region, _get_scroll_direction(found_level), step_ratio=0.15)
            time.sleep(GOLD_ACTION_DELAY)
            return GoldState.LEVEL_LIST_VISIBLE

        found_level, _ = get_list_level(screen_cv, region)

        _gold_ctx['level_select_scroll_tries'] = _gold_ctx.get('level_select_scroll_tries', 0) + 1
        if _gold_ctx['level_select_scroll_tries'] > 20:
            logger.info("[GOLD] Не удалось найти целевой уровень. Сброс.")
            _gold_ctx['expected'] = None
            _gold_ctx['level_select_scroll_tries'] = 0
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
        _gold_ctx['expected'] = 'level_list'
        _gold_ctx['level_select_scroll_tries'] = 0
        time.sleep(GOLD_ACTION_DELAY)
        return GoldState.SELECT_LEVEL_VISIBLE

    # ---- FIND (поиск свободного рудника) ----
    if current_state == GoldState.FIND_VISIBLE:
        # Таймаут поиска: если ищем дольше GOLD_SEARCH_TIMEOUT — выходим
        find_started = _gold_ctx.get('find_started_at')
        if find_started is None:
            _gold_ctx['find_started_at'] = time.time()
            find_started = _gold_ctx['find_started_at']
        elapsed_find = time.time() - find_started
        if elapsed_find > GOLD_SEARCH_TIMEOUT:
            logger.info(f"[GOLD] Поиск длится {int(elapsed_find)} сек — таймаут {GOLD_SEARCH_TIMEOUT} сек. Сброс.")
            _gold_ctx['find_started_at'] = None
            find_and_click(GOLD_CLOSE_IMG, screen_cv, region)
            return GoldState.UNKNOWN

        # Rate-limit: не жмём find.png чаще чем раз в 1.5 сек, иначе игра
        # не успевает обновить экран и свободное место занимают другие игроки.
        last_find_click = _gold_ctx.get('find_clicked_at', 0)
        if time.time() - last_find_click >= 1.5:
            find_and_click(GOLD_FIND_IMG, screen_cv, region)
            _gold_ctx['find_clicked_at'] = time.time()
        else:
            time.sleep(GOLD_ACTION_DELAY)
        return GoldState.FIND_VISIBLE

    # ---- EVENTS: RUDNIK VISIBLE ----
    if current_state == GoldState.EVENTS_RUDNIK_VISIBLE:
        _gold_ctx['expected'] = 'forward_popup'
        _gold_ctx['swipe_count'] = 0
        gold_coords, gold_conf, gold_template = find_event_gold_in_calendar(screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if gold_coords:
            # Клик по иконке event_gold.png часто не открывает попап.
            # Кликабельная область строки — правее иконки, по тексту/карточке события.
            # Смещаем клик вправо на ~2.5 ширины иконки и немного вниз, чтобы попасть в середину строки.
            template = get_template(gold_template) if gold_template else None
            icon_w = template.shape[1] if template is not None else 60
            icon_h = template.shape[0] if template is not None else 60
            click_x = gold_coords[0] + icon_w * 2.5
            click_y = gold_coords[1] + icon_h * 0.2
            logger.info(f"[GOLD] Нажимаем на строку события золотодобычи ({gold_template}, conf={gold_conf:.3f}) по ({click_x:.0f}, {click_y:.0f}).")
            pyautogui.click(click_x, click_y)
            time.sleep(GOLD_ACTION_DELAY)
            # Проверяем, открылся ли попап с кнопкой 'Вперёд', на свежем скриншоте
            screen_after = take_screenshot(window, region)
            if screen_after is not None:
                # forward.png matches at conf~0.55-0.65 on the actual popup, below MEDIUM_THRESHOLD
                forward_coords, forward_conf = find_on_screen(get_template(GOLD_FORWARD_IMG), screen_after, region, threshold=0.55)
                logger.debug(f"[GOLD] Проверка попапа 'Вперёд': conf={forward_conf:.3f}, threshold=0.55")
                if forward_coords:
                    logger.info(f"[GOLD] Попап 'Вперёд' открылся (conf={forward_conf:.3f}).")
                    return GoldState.FORWARD_POPUP_VISIBLE
                logger.info("[GOLD] Попап 'Вперёд' не открылся после первого клика, пробуем ещё раз.")
                pyautogui.click(click_x, click_y)
                time.sleep(GOLD_ACTION_DELAY)
                screen_after2 = take_screenshot(window, region)
                if screen_after2 is not None:
                    forward_coords2, forward_conf2 = find_on_screen(get_template(GOLD_FORWARD_IMG), screen_after2, region, threshold=0.55)
                    logger.debug(f"[GOLD] Проверка попапа 'Вперёд' (2): conf={forward_conf2:.3f}, threshold=0.55")
                    if forward_coords2:
                        logger.info(f"[GOLD] Попап 'Вперёд' открылся со второй попытки (conf={forward_conf2:.3f}).")
                        return GoldState.FORWARD_POPUP_VISIBLE
            logger.info("[GOLD] Не удалось открыть попап события, продолжаем искать/скроллить.")
            return GoldState.EVENTS_NEED_SCROLL
        return GoldState.EVENTS_MENU_OPEN

    # ---- EVENTS: FORWARD POPUP ----
    if current_state == GoldState.FORWARD_POPUP_VISIBLE:
        _gold_ctx['expected'] = 'rudnik_tab'
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
        _gold_ctx['expected'] = 'events_scroll'

        # Если events.png открыло сразу табу рудника (например, последнее событие),
        # не свайпаем по карусели, а переходим к выбору уровня.
        rudnik_opened_coords, _ = find_on_screen(get_template(GOLD_RUDNIK_OPENED_IMG), screen_cv, region)
        find_coords, _ = find_on_screen(get_template(GOLD_FIND_IMG), screen_cv, region)
        select_coords, _ = find_on_screen(get_template(GOLD_SELECT_LEVEL_IMG), screen_cv, region)
        if rudnik_opened_coords or find_coords or select_coords:
            logger.info("[GOLD] Событие золотодобычи уже открыто (rudnik_tab). Пропускаем свайпы.")
            _gold_ctx['swipe_count'] = 0
            _gold_ctx['expected'] = 'rudnik_tab'
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
            _gold_ctx['swipe_count'] = 0
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
        swipe_count = _gold_ctx.get('swipe_count', 0)
        if swipe_count < 5:
            # Пролистываем влево к началу списка
            swipe_horizontal(region, 'left')
        else:
            # Ищем золотодобычу, свайпая вправо
            swipe_horizontal(region, 'right')
        _gold_ctx['swipe_count'] = swipe_count + 1
        if _gold_ctx['swipe_count'] > 20:
            logger.info("[GOLD] Не удалось найти иконку золотодобычи в меню событий. Сброс.")
            _gold_ctx['swipe_count'] = 0
            _gold_ctx['expected'] = None
            return GoldState.UNKNOWN
        return GoldState.EVENTS_NEED_SCROLL

    # ---- MAIN SCREEN ----
    if current_state == GoldState.MAIN_SCREEN:
        # Проверим, не открыт ли уже календарь (event_gold или rudnik виден)
        gold_coords, _, _ = find_event_gold_in_calendar(screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if gold_coords:
            logger.info("[GOLD] Календарь уже открыт, событие золотодобычи видно.")
            _gold_ctx['expected'] = 'events'
            _gold_ctx['swipe_count'] = 0
            return GoldState.EVENTS_RUDNIK_VISIBLE

        # Счётчик попыток нажать события
        _gold_ctx['main_screen_tries'] = _gold_ctx.get('main_screen_tries', 0) + 1

        # Если видна info.png — это попап, кликаем в верхнюю часть экрана для закрытия
        info_coords, _ = find_on_screen(get_template(INFO_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if info_coords:
            logger.info("[GOLD] Видна info.png — попап открыт. Клик в верхнюю часть экрана для закрытия.")
            _click_top_screen(region, reset_main_tries=True)
            return GoldState.UNKNOWN

        # Если застряли на main_screen > 3 попыток — клик в верхнюю часть экрана
        if _gold_ctx['main_screen_tries'] > 3:
            logger.info(f"[GOLD] Застряли на main_screen ({_gold_ctx['main_screen_tries']} попыток). Клик в верхнюю часть экрана.")
            _click_top_screen(region, reset_main_tries=True)
            return GoldState.UNKNOWN

        clicked, _ = find_and_click(EVENTS_IMG, screen_cv, region)
        if not clicked:
            # Если events.png не найден — пробуем calendar.png (иконка календаря в меню событий)
            logger.info("[GOLD] events.png не найден, пробуем calendar.png")
            find_and_click(CALENDAR_IMG, screen_cv, region)
        _gold_ctx['swipe_count'] = 0
        _gold_ctx['events_clicked_at'] = time.time()
        time.sleep(GOLD_ACTION_DELAY)
        _gold_ctx['expected'] = 'events'
        return GoldState.EVENTS_MENU_OPEN

    # ---- UNKNOWN / STUCK RECOVERY ----
    if current_state == GoldState.UNKNOWN:
        logger.debug(f"[GOLD] UNKNOWN recovery start. stuck_count={_gold_ctx.get('stuck_count', 0)}, expected={_gold_ctx.get('expected')}")
        clicked_at = _gold_ctx.get('moveon_clicked_at')
        if clicked_at and (time.time() - clicked_at) < 2.0:
            logger.debug("[GOLD] Ожидаем завершения перехода после клика 'Перейти'.")
            _gold_ctx['moveon_clicked_at'] = None
            time.sleep(GOLD_ACTION_DELAY)
            return GoldState.UNKNOWN

        clicked_events_at = _gold_ctx.get('events_clicked_at')
        if clicked_events_at and (time.time() - clicked_events_at) < 4.0:
            logger.debug("[GOLD] Ожидаем открытия календаря событий.")
            time.sleep(GOLD_ACTION_DELAY)
            return GoldState.UNKNOWN

        # Если мы недавно открыли события, но оказались в активном событии — свайп по верхней карусели
        if _gold_ctx.get('expected') == 'events' and clicked_events_at \
                and (time.time() - clicked_events_at) < 5.0:
            logger.debug("[GOLD] Активное событие открылось вместо календаря. Пробуем свайп по верхней карусели.")
            swipe_horizontal(region, 'right')
            time.sleep(GOLD_ACTION_DELAY)
            return GoldState.UNKNOWN

        _gold_ctx['stuck_count'] = _gold_ctx.get('stuck_count', 0) + 1
        action = _gold_ctx.get('stuck_last_action')
        if action != 'back':
            logger.debug("[GOLD] UNKNOWN recovery: try back")
            find_and_click(BACK_IMG, screen_cv, region)
            _gold_ctx['stuck_last_action'] = 'back'
        elif action != 'close':
            logger.debug("[GOLD] UNKNOWN recovery: try close")
            find_and_click(GOLD_CLOSE_IMG, screen_cv, region)
            _gold_ctx['stuck_last_action'] = 'close'
        else:
            logger.debug("[GOLD] UNKNOWN recovery: try village")
            find_and_click(VILLAGE_IMG, screen_cv, region)
            _gold_ctx['stuck_last_action'] = None
            _gold_ctx['stuck_count'] = 0

        time.sleep(GOLD_ACTION_DELAY)
        logger.debug("[GOLD] UNKNOWN recovery end")
        return GoldState.UNKNOWN

    return current_state


# ==========================================
# ЗАВЕРШЕНИЕ ЗОЛОТОДОБЫЧИ (возврат в поселение)
# ==========================================
def process_gold_exit(screen_cv, region, last_exit_state, window):
    """Обратный переход к MAIN_SCREEN после завершения добычи."""
    current_state = determine_gold_state(screen_cv, region)

    if current_state in (GoldState.MAIN_SCREEN,):
        return GoldState.COMPLETED

    _gold_ctx['exit_attempts'] = _gold_ctx.get('exit_attempts', 0) + 1
    attempts = _gold_ctx['exit_attempts']

    if attempts % 4 == 1:
        if find_and_click(VILLAGE_IMG, screen_cv, region)[0]:
            time.sleep(GOLD_ACTION_DELAY)
            return current_state
    elif attempts % 4 == 2:
        if find_and_click(BACK_IMG, screen_cv, region)[0]:
            time.sleep(GOLD_ACTION_DELAY)
            return current_state
    elif attempts % 4 == 3:
        if find_and_click(GOLD_CLOSE_IMG, screen_cv, region)[0]:
            time.sleep(GOLD_ACTION_DELAY)
            return current_state
    else:
        center_x = region[0] + region[2] // 2
        center_y = region[1] + region[3] // 2
        logger.debug(f"[GOLD EXIT] Клик по центру экрана центp экрана ({center_x}, {center_y}) для сброса UI.")
        pyautogui.click(center_x, center_y)
        time.sleep(GOLD_ACTION_DELAY)
        return current_state

    if current_state in (GoldState.UNKNOWN,):
        find_and_click(BACK_IMG, screen_cv, region)
        time.sleep(GOLD_ACTION_DELAY)
        return last_exit_state if last_exit_state is not None else GoldState.UNKNOWN

    return current_state


# ==========================================
# ОБРАБОТКА РЕЖИMA GOLD В MAIN.LOOP
# ==========================================
def handle_gold_mode(screen_cv, region, window, last_gold_state, gold_start_time, gold_exit_state, gold_exiting):
    """
    Обрабатывает режим GOLD: определяет состояние и выполняет соответствующие действия.

    Returns:
        tuple: (next_mode, new_last_gold_state, new_gold_start_time, new_gold_exit_state, new_gold_exiting)
        где next_mode - MainMode.HEAL или MainMode.GOLD
    """
    # Защитный таймаут
    if gold_start_time and (time.time() - gold_start_time) >= GOLD_TIMEOUT:
        logger.info(f"[ТАЙМЕР] Золото затянулось > {GOLD_TIMEOUT} сек. Возвращаемся к лечению.")
        return MainMode.HEAL, None, None, False

    # Если ещё стартуем и не определён state
    if last_gold_state is None:
        current_gold_state = determine_gold_state(screen_cv, region)
        logger.info(f"[MAIN] GOLD: стартовое состояние {current_gold_state.value}")
        last_gold_state = current_gold_state

    # Обработать одно состояние
    if not gold_exiting:
        current_gold_state = determine_gold_state(screen_cv, region)
        if current_gold_state != last_gold_state:
            if current_gold_state.value:
                logger.info(f"[MAIN] GOLD: {current_gold_state.value}")
            else:
                logger.info(f"[MAIN] GOLD: {current_gold_state}")
        last_gold_state = process_gold(screen_cv, region, last_gold_state, window)

    # Если добыча завершена — выходим
    if last_gold_state == GoldState.COMPLETED:
        logger.info("[MAIN] Золотодобыча завершена, возврат к лечению")
        return MainMode.HEAL, None, None, False

    # Если не выходим, остаемся в режиме GOLD
    return MainMode.GOLD, last_gold_state, gold_start_time, gold_exit_state, gold_exiting