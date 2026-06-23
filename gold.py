# ==========================================
# ЛОГИКА ЗОЛОТОДОБЫЧИ (стейт-машина)
# ==========================================

import time
import cv2

from config import *
from utils import *


# ==========================================
# ПЕРЕМЕННЫЕ СОСТОЯНИЯ ЗОЛОТА
# ==========================================
last_gold_time = time.time()
gold_first_run = True         # при первом запуске сразу идём в золото после heal/raid, не ждём GOLD_INTERVAL
_gold_ctx = {
    'expected': None,          # подсказка для неоднозначных состояний
    'swipe_count': 0,
    'level_select_scroll_tries': 0,
    'stuck_count': 0,
    'stuck_last_action': None,
    'events_clicked_at': None,
    'moveon_clicked_at': None,
    'recall_requested': False,
    'started_at': None,
    'current_mining_level': None,
    'need_level_check': False,
    'main_screen_tries': 0,
    'raid_icon_clicks': 0,
    'find_started_at': None,
    'exit_attempts': 0,
}


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
        print("[GOLD] Первый запуск скрипта — сразу запускаем золотодобычу.")
        return True
    elapsed = time.time() - last_gold_time
    if elapsed >= GOLD_INTERVAL:
        print(f"[GOLD] Прошло {int(elapsed)} сек с последнего рудника. Пора!")
        return True
    remaining = int(GOLD_INTERVAL - elapsed)
    m, s = divmod(remaining, 60)
    print(f"[GOLD] До рудника: {m:02d}:{s:02d}")
    return False


def update_gold_time():
    """Обновить время последнего посещения рудника."""
    global last_gold_time
    last_gold_time = time.time()
    print(f"[GOLD] Время обновлено: {time.ctime(last_gold_time)}")


def gold_mission_active():
    """Отряд отправлен добывать золото и ещё не отозван."""
    return _gold_ctx.get('started_at') is not None and not _gold_ctx['recall_requested']


def gold_mission_should_recall():
    """Пора отозвать отряд (45 минут прошли)."""
    if not gold_mission_active():
        return False
    elapsed = time.time() - _gold_ctx['started_at']
    if elapsed >= GOLD_MINING_DURATION:
        print(f"[GOLD] Добыча идёт {int(elapsed)} сек, порог {GOLD_MINING_DURATION} сек. Нужен отзыв.")
        _gold_ctx['recall_requested'] = True
        return True
    return False


def start_gold_mission():
    """Зафиксировать запуск добычи на целевом уровне."""
    _gold_ctx['started_at'] = time.time()
    _gold_ctx['current_mining_level'] = GOLD_LEVEL
    _gold_ctx['recall_requested'] = False
    print(f"[GOLD] Отряд отправлен на уровень {GOLD_LEVEL} в {time.ctime()}")


def clear_gold_mission():
    """Сбросить данные активной добычи."""
    _gold_ctx['started_at'] = None
    _gold_ctx['current_mining_level'] = None
    _gold_ctx['recall_requested'] = False


def reset_gold_context():
    """Сбросить вспомогательный контекст перед новым заходом в режим GOLD."""
    _gold_ctx['expected'] = None
    _gold_ctx['swipe_count'] = 0
    _gold_ctx['level_select_scroll_tries'] = 0
    _gold_ctx['stuck_count'] = 0
    _gold_ctx['stuck_last_action'] = None
    _gold_ctx['events_clicked_at'] = None
    _gold_ctx['moveon_clicked_at'] = None
    _gold_ctx['recall_requested'] = False
    _gold_ctx['need_level_check'] = False
    _gold_ctx['main_screen_tries'] = 0
    _gold_ctx['raid_icon_clicks'] = 0
    _gold_ctx['find_started_at'] = None
    _gold_ctx['exit_attempts'] = 0


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
        print(f"[GOLD] Распознан текущий уровень: {best_level} (conf={best_conf:.3f})")
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
        print(f"[GOLD] В списке найден уровень {best_level} (conf={best_conf:.3f})")
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


def click_moveon_for_target_level(screen_cv, region, target=GOLD_LEVEL, lvl_threshold=None, btn_threshold=0.70):
    """Найти ближайшую кнопку 'Перейти' к тексту целевого уровня и кликнуть по ней.

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
        print(f"[GOLD] lvl_{target}.png не найден на экране.")
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
            print(f"[GOLD] Кнопка 'Перейти' отсутствует как шаблон, клик под уровень {target} ({fallback_x:.0f}, {fallback_y:.0f}), conf={conf_lvl:.3f}")
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
                # Кнопка должна быть в той же карточке по вертикали и не слишком далеко по горизонтали.
                # Обычно она либо под текстом уровня, либо справа/слева от него.
                if vertical_gap < h_btn * 3 and horizontal_gap < max(w_btn, w_lvl) * 2.5:
                    score = conf_lvl_i + conf_btn - vertical_gap / 100.0
                    if score > best_score:
                        best_score = score
                        best_pair = (cx_btn, cy_btn, conf_btn, cx_lvl_i, cy_lvl_i, conf_lvl_i)

    if best_pair is None:
        if fallback_click:
            pyautogui.click(*fallback_click)
            print(f"[GOLD] Кнопка 'Перейти' не найдена рядом с уровнем {target}, клик под карточку ({fallback_x:.0f}, {fallback_y:.0f}), conf={conf_lvl:.3f}")
            return True
        print(f"[GOLD] Кнопка 'Перейти' у уровня {target} не найдена. "
              f"lvl_matches={len(lvl_matches)}, btn_matches={len(btn_matches) if btn_matches else 0}")
        return False

    cx_btn, cy_btn, conf_btn, cx_lvl, cy_lvl, conf_lvl = best_pair
    btn_top = cy_btn - h_btn / 2
    btn_bottom = cy_btn + h_btn / 2
    if btn_top < region_top + 20 or btn_bottom > region_bottom - 20:
        if fallback_click:
            pyautogui.click(*fallback_click)
            print(f"[GOLD] Кнопка 'Перейти' у уровня {target} частично за краем, клик под карточку ({fallback_x:.0f}, {fallback_y:.0f})")
            return True
        print(f"[GOLD] Кнопка 'Перейти' у уровня {target} частично за краем экрана. Скроллим.")
        return False

    pyautogui.click(cx_btn, cy_btn)
    print(f"[GOLD] Нажата 'Перейти' у уровня {target} ({cx_btn:.0f}, {cy_btn:.0f}), conf=({conf_lvl:.3f}/{conf_btn:.3f})")
    return True


# ==========================================
# ОПРЕДЕЛЕНИЕ СОСТОЯНИЯ ЗОЛОТОДОБЫЧИ
# ==========================================
def determine_gold_state(screen_cv, region):
    """Возвращает GoldState на основе текущего экрана (приоритет сверху-вниз)."""

    # 1. Reconnect
    coords, _ = find_on_screen(get_template(RECONNECT_IMG), screen_cv, region)
    if coords:
        return GoldState.RECONNECT_POPUP
    coords, _ = find_on_screen(get_template(RECONNECT_REPEAT_IMG), screen_cv, region)
    if coords:
        return GoldState.RECONNECT_REPEAT_POPUP

    # 2. Подтверждение отзыва отряда
    coords, _ = find_on_screen(get_template(GOLD_RETURN_BOYS_IMG), screen_cv, region)
    if coords:
        return GoldState.RETURN_CONFIRM_VISIBLE

    # 3. Кнопка "Завершить" после отзыва
    coords, _ = find_on_screen(get_template(GOLD_FINISH_IMG), screen_cv, region)
    if coords:
        return GoldState.FINISH_VISIBLE

    # 4. Подтверждение после завершения
    coords, _ = find_on_screen(get_template(GOLD_CONFIRM_IMG), screen_cv, region)
    if coords:
        return GoldState.CONFIRM_VISIBLE

    # 5. Попап "SummaryStrenghtText" — место занято
    coords, _ = find_on_screen(get_template(GOLD_SUMMARY_STRENGTH_TEXT_IMG), screen_cv, region)
    if coords:
        return GoldState.SUMMARY_STRENGTH_TEXT_VISIBLE

    # 6. Мой рудник / активная добыча — проверяем ДО return.png,
    #    т.к. return.png видна на экране добычи всегда (как кнопка отзыва)
    coords, _ = find_on_screen(get_template(GOLD_MY_RUDNIK_IMG), screen_cv, region)
    if coords:
        return GoldState.MY_RUDNIK_VISIBLE

    # 7. Иконка активного уровня добычи
    coords, _ = find_on_screen(get_template(GOLD_CURRENT_RAID_LEVEL_ICON_IMG), screen_cv, region)
    if coords:
        return GoldState.RAID_LEVEL_ICON_VISIBLE

    # 8. Кнопка "Отозвать" на экране рудника
    coords, _ = find_on_screen(get_template(GOLD_RETURN_IMG), screen_cv, region)
    if coords:
        return GoldState.RETURN_BUTTON_VISIBLE

    # 9. Цепочка добычи / марш
    coords, _ = find_on_screen(get_template(GOLD_GO_IMG), screen_cv, region)
    if coords:
        return GoldState.GO_VISIBLE
    coords, _ = find_on_screen(get_template(GOLD_WORK_IMG), screen_cv, region)
    if coords:
        return GoldState.WORK_VISIBLE
    coords, _ = find_on_screen(get_template(GOLD_GRIND_IMG), screen_cv, region)
    if coords:
        return GoldState.GRIND_VISIBLE

    # 10. Свободное место после поиска
    coords, _ = find_on_screen(get_template(GOLD_FREE_PLACE_IMG), screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
    if coords:
        return GoldState.FREE_PLACE_VISIBLE

    # 11. Список уровней (приоритет выше календаря, чтобы не перепутать с EVENTS_MENU_OPEN)
    select_visible, _ = find_on_screen(get_template(GOLD_SELECT_LEVEL_IMG), screen_cv, region)
    if select_visible:
        return GoldState.SELECT_LEVEL_VISIBLE
    found_level, _ = get_list_level(screen_cv, region, threshold=GOLD_LIST_LEVEL_CONFIDENCE_THRESHOLD)
    if found_level is not None:
        return GoldState.LEVEL_LIST_VISIBLE

    # 12. Открыта таба рудника — строго по rudnik_opened.png, current_lvl_X или find
    coords, _ = find_on_screen(get_template(GOLD_RUDNIK_OPENED_IMG), screen_cv, region)
    if coords:
        return GoldState.RUDNIK_TAB

    current_level = get_current_level(screen_cv, region)
    find_visible, _ = find_on_screen(get_template(GOLD_FIND_IMG), screen_cv, region)
    if current_level is not None or find_visible:
        # Проверим, нет ли сообщения об отсутствии свободных мест
        no_free_coords, _ = find_on_screen(get_template(GOLD_NO_FREE_RUDNIK_IMG), screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
        if no_free_coords:
            return GoldState.NO_FREE_RUDNIK
        return GoldState.RUDNIK_TAB

    # 13. Попап события с кнопкой "Вперёд"
    coords, _ = find_on_screen(get_template(GOLD_FORWARD_IMG), screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
    if coords:
        return GoldState.FORWARD_POPUP_VISIBLE

    # 14. Меню событий: видна иконка рудника → можно кликать
    coords, _ = find_on_screen(get_template(GOLD_RUDNIK_IMG), screen_cv, region)
    if coords:
        return GoldState.EVENTS_RUDNIK_VISIBLE

    # 15. Главный экран / поселение / карта — проверяем ДО back.png,
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

    # 16. Меню событий/календарь — back.png видна, но events.png НЕ видна.
    #     Если events.png видна — мы на главном экране (проверка выше).
    back_coords, back_conf = find_on_screen(get_template(BACK_IMG), screen_cv, region)

    if back_coords:
        # back в календаре — в верхней трети; в окне рейда back обычно внизу — не путаем.
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
        print(f"[GOLD] Состояние: {current_state.value}")
        save_debug_screenshot(screen_cv, f"gold_{current_state.value}")

    # ---- RECONNECT ----
    if current_state == GoldState.RECONNECT_POPUP:
        handle_reconnect(screen_cv, region)
        return GoldState.UNKNOWN
    if current_state == GoldState.RECONNECT_REPEAT_POPUP:
        handle_reconnect_repeat(screen_cv, region)
        return GoldState.UNKNOWN

    # ---- RETURN BUTTON ----
    if current_state == GoldState.RETURN_BUTTON_VISIBLE:
        if _gold_ctx.get('recall_requested'):
            print("[GOLD] Отряд занят добычей на этом уровне. Отзываем.")
            find_and_click(GOLD_RETURN_IMG, screen_cv, region)
            return GoldState.RETURN_CONFIRM_VISIBLE
        current = get_current_level(screen_cv, region)
        if current:
            _gold_ctx['current_mining_level'] = current
        start_gold_mission()
        update_gold_time()
        print("[GOLD] ✓ Золотодобыча запущена (return.png видна, отзыв не требуется).")
        return GoldState.COMPLETED

    # ---- RETURN CONFIRM ----
    if current_state == GoldState.RETURN_CONFIRM_VISIBLE:
        find_and_click(GOLD_RETURN_BOYS_IMG, screen_cv, region)
        clear_gold_mission()
        _gold_ctx['expected'] = 'rudnik_tab'
        _gold_ctx['need_level_check'] = True
        print("[GOLD] Отряд отозван.")
        return GoldState.RUDNIK_TAB

    # ---- FINISH BUTTON ----
    if current_state == GoldState.FINISH_VISIBLE:
        print("[GOLD] Нажимаем 'Завершить' после отзыва отряда.")
        find_and_click(GOLD_FINISH_IMG, screen_cv, region)
        _gold_ctx['need_level_check'] = True
        return GoldState.RUDNIK_TAB

    # ---- CONFIRM BUTTON ----
    if current_state == GoldState.CONFIRM_VISIBLE:
        print("[GOLD] Нажимаем 'Подтвердить'.")
        find_and_click(GOLD_CONFIRM_IMG, screen_cv, region)
        _gold_ctx['need_level_check'] = True
        return GoldState.RUDNIK_TAB

    # ---- SUMMARY STRENGTH TEXT POPUP ----
    if current_state == GoldState.SUMMARY_STRENGTH_TEXT_VISIBLE:
        join_coords, _ = find_on_screen(get_template(GOLD_WORK_IMG), screen_cv, region)
        if join_coords:
            print("[GOLD] Найдена кнопка присоединения/добычи. Нажимаем.")
            find_and_click(GOLD_WORK_IMG, screen_cv, region)
            return GoldState.WORK_VISIBLE
        print("[GOLD] Место занято (SummaryStrenghtText). Закрываем попап.")
        find_and_click(GOLD_CLOSE_IMG, screen_cv, region)
        _gold_ctx['expected'] = 'rudnik_tab'
        return GoldState.RUDNIK_TAB

    # ---- ПРОВЕРКА ЦЕЛЕВОГО УРОВНЯ ПЕРЕД ДОБЫЧЕЙ ----
    if _gold_ctx.get('need_level_check') and current_state in (
        GoldState.FIND_VISIBLE, GoldState.FREE_PLACE_VISIBLE,
        GoldState.GRIND_VISIBLE, GoldState.WORK_VISIBLE, GoldState.GO_VISIBLE
    ):
        current = get_current_level(screen_cv, region)
        if current is not None and current != GOLD_LEVEL:
            print(f"[GOLD] Уровень {current}, нужен {GOLD_LEVEL}. Открываем выбор уровня перед добычей.")
            find_and_click(GOLD_SELECT_LEVEL_IMG, screen_cv, region)
            _gold_ctx['expected'] = 'level_list'
            _gold_ctx['level_select_scroll_tries'] = 0
            time.sleep(GOLD_ACTION_DELAY)
            return GoldState.SELECT_LEVEL_VISIBLE
        elif current == GOLD_LEVEL:
            _gold_ctx['need_level_check'] = False
            print(f"[GOLD] Уровень проверен: {current}. Продолжаем добычу.")
        else:
            print("[GOLD] Текущий уровень не виден на экране добычи. Закрываем окно для проверки.")
            find_and_click(GOLD_CLOSE_IMG, screen_cv, region)
            return GoldState.UNKNOWN

    # ---- GO / WORK / GRIND ----
    if current_state == GoldState.GO_VISIBLE:
        find_and_click(GOLD_GO_IMG, screen_cv, region)
        time.sleep(0.2)

        screen_after = take_screenshot(window, region)
        return_coords, _ = find_on_screen(get_template(GOLD_RETURN_IMG), screen_after, region)
        my_rudnik_coords, _ = find_on_screen(get_template(GOLD_MY_RUDNIK_IMG), screen_after, region)
        find_coords, _ = find_on_screen(get_template(GOLD_FIND_IMG), screen_after, region)
        summary_coords, _ = find_on_screen(get_template(GOLD_SUMMARY_STRENGTH_TEXT_IMG), screen_after, region)

        if summary_coords:
            print("[GOLD] После 'Марш' появился попап SummaryStrenghtText. Обработаем его.")
            return GoldState.SUMMARY_STRENGTH_TEXT_VISIBLE

        if return_coords or my_rudnik_coords:
            if find_coords is None:
                start_gold_mission()
                update_gold_time()
                print("[GOLD] ✓ Золотодобыча запущена!")
                return GoldState.COMPLETED
            else:
                print("[GOLD] Кнопка поиска всё ещё видна — рудник не занят. Продолжаем поиск.")
        else:
            print("[GOLD] Рудник не занят (нет return.png / my_rudnik.png). Продолжаем поиск.")

        work_coords, _ = find_on_screen(get_template(GOLD_WORK_IMG), screen_after, region)
        go_coords, _ = find_on_screen(get_template(GOLD_GO_IMG), screen_after, region)
        if work_coords or go_coords:
            print("[GOLD] Застряли в попапе (видны work/go). Закрываем.")
            find_and_click(GOLD_CLOSE_IMG, screen_after, region)

        _gold_ctx['expected'] = 'rudnik_tab'
        return GoldState.RUDNIK_TAB

    if current_state == GoldState.WORK_VISIBLE:
        find_and_click(GOLD_WORK_IMG, screen_cv, region)
        time.sleep(0.2)
        return GoldState.GO_VISIBLE

    if current_state == GoldState.GRIND_VISIBLE:
        find_and_click(GOLD_GRIND_IMG, screen_cv, region)
        time.sleep(0.2)
        return GoldState.WORK_VISIBLE

    # ---- FREE PLACE ----
    if current_state == GoldState.FREE_PLACE_VISIBLE:
        find_and_click(GOLD_FREE_PLACE_IMG, screen_cv, region)
        return GoldState.GRIND_VISIBLE

    # ---- MY RUDNIK / ACTIVE MINING ----
    if current_state in (GoldState.MY_RUDNIK_VISIBLE, GoldState.RAID_LEVEL_ICON_VISIBLE):
        if _gold_ctx.get('recall_requested'):
            find_and_click(GOLD_RETURN_IMG, screen_cv, region)
            return GoldState.RETURN_CONFIRM_VISIBLE

        current = get_current_level(screen_cv, region)
        if current:
            _gold_ctx['current_mining_level'] = current
            started = _gold_ctx.get('started_at')
            if started is None:
                _gold_ctx['started_at'] = time.time()
                print("[GOLD] Активная добыча без известного старта. Синхронизация таймера.")

            if (time.time() - _gold_ctx['started_at']) >= GOLD_MINING_DURATION:
                print("[GOLD] 45 минут добычи истекли. Отзываем отряд.")
                _gold_ctx['recall_requested'] = True
                return GoldState.MY_RUDNIK_VISIBLE
            elapsed = int(time.time() - _gold_ctx['started_at'])
            print(f"[GOLD] Добыча ещё активна ({elapsed//60} мин). Завершаем проверку.")
            update_gold_time()
            return GoldState.COMPLETED

        _gold_ctx['raid_icon_clicks'] = _gold_ctx.get('raid_icon_clicks', 0) + 1
        if _gold_ctx['raid_icon_clicks'] > 3:
            print("[GOLD] Иконка current_raid_lvl_icon.png не открывает детали. Сброс.")
            _gold_ctx['raid_icon_clicks'] = 0
            return GoldState.UNKNOWN

        find_and_click(GOLD_CURRENT_RAID_LEVEL_ICON_IMG, screen_cv, region)
        time.sleep(GOLD_ACTION_DELAY)
        return GoldState.RUDNIK_TAB

    # ---- RUDNIK TAB (выбор / поиск уровня) ----
    if current_state == GoldState.RUDNIK_TAB:
        _gold_ctx['expected'] = 'rudnik_tab'
        _gold_ctx['raid_icon_clicks'] = 0
        _gold_ctx['find_started_at'] = None  # сброс таймаута поиска
        current = get_current_level(screen_cv, region)

        find_test, _ = find_on_screen(get_template(GOLD_FIND_IMG), screen_cv, region)
        select_test, _ = find_on_screen(get_template(GOLD_SELECT_LEVEL_IMG), screen_cv, region)

        # Если кнопка выбора уровня видна и текущий уровень не совпадает с целевым — открываем список
        if select_test is not None:
            if current is not None and current != GOLD_LEVEL:
                _gold_ctx['need_level_check'] = True
                print(f"[GOLD] Уровень {current}, нужен {GOLD_LEVEL}. Открываем выбор уровня.")
                find_and_click(GOLD_SELECT_LEVEL_IMG, screen_cv, region)
                _gold_ctx['expected'] = 'level_list'
                _gold_ctx['level_select_scroll_tries'] = 0
                time.sleep(GOLD_ACTION_DELAY)
                return GoldState.SELECT_LEVEL_VISIBLE
            elif current is None:
                print(f"[GOLD] Текущий уровень не распознан, но видна кнопка выбора уровня. Открываем список.")
                _gold_ctx['need_level_check'] = True
                find_and_click(GOLD_SELECT_LEVEL_IMG, screen_cv, region)
                _gold_ctx['expected'] = 'level_list'
                _gold_ctx['level_select_scroll_tries'] = 0
                time.sleep(GOLD_ACTION_DELAY)
                return GoldState.SELECT_LEVEL_VISIBLE

        if find_test is None:
            print("[GOLD] На вкладке рудника нет кнопки поиска. Закрываем попап.")
            find_and_click(GOLD_CLOSE_IMG, screen_cv, region)
            return GoldState.UNKNOWN

        if current == GOLD_LEVEL:
            _gold_ctx['need_level_check'] = False

        clicked_find, _ = find_and_click(GOLD_FIND_IMG, screen_cv, region)
        if clicked_find:
            _gold_ctx['expected'] = 'find'
            return GoldState.FIND_VISIBLE
        print("[GOLD] Кнопка поиска не найдена. Пробуем закрыть/вернуться.")
        return GoldState.UNKNOWN

    # ---- LEVEL LIST / SELECT LEVEL ----
    if current_state in (GoldState.SELECT_LEVEL_VISIBLE, GoldState.LEVEL_LIST_VISIBLE) \
            or _gold_ctx.get('expected') == 'level_list':
        target_path = GOLD_LEVEL_IMAGES[GOLD_LEVEL]

        # Если видно сообщение "нет свободных рудников", пробуем соседний уровень
        no_free_coords, no_free_conf = find_on_screen(get_template(GOLD_NO_FREE_RUDNIK_IMG), screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
        if no_free_coords:
            print(f"[GOLD] На целевом уровне нет свободных мест (conf={no_free_conf:.3f}). Пробуем другой уровень.")
            _gold_ctx['level_select_scroll_tries'] = _gold_ctx.get('level_select_scroll_tries', 0) + 1
            if _gold_ctx['level_select_scroll_tries'] > 10:
                print("[GOLD] Везде занято. Завершаем золотодобычу.")
                _gold_ctx['level_select_scroll_tries'] = 0
                update_gold_time()
                return GoldState.COMPLETED
            # Попробуем уровень выше или ниже по кругу
            alternative = GOLD_LEVEL + (1 if _gold_ctx['level_select_scroll_tries'] % 2 == 1 else -1) * ((_gold_ctx['level_select_scroll_tries'] + 1) // 2)
            alternative = max(1, min(6, alternative))
            if is_target_level_in_list(screen_cv, region, target=alternative):
                if click_moveon_for_target_level(screen_cv, region, target=alternative):
                    print(f"[GOLD] Пробуем уровень {alternative} вместо {GOLD_LEVEL}.")
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
                _gold_ctx['need_level_check'] = True
                time.sleep(GOLD_ACTION_DELAY)
                return GoldState.RUDNIK_TAB

        found_level, _ = get_list_level(screen_cv, region)

        _gold_ctx['level_select_scroll_tries'] = _gold_ctx.get('level_select_scroll_tries', 0) + 1
        if _gold_ctx['level_select_scroll_tries'] > 20:
            print("[GOLD] Не удалось найти целевой уровень. Сброс.")
            _gold_ctx['expected'] = None
            _gold_ctx['level_select_scroll_tries'] = 0
            return GoldState.UNKNOWN

        if found_level is not None:
            if GOLD_LEVEL < found_level:
                direction = 'up'
            else:
                direction = 'down'
        else:
            direction = 'up'

        scroll_in_region(region, direction, step_ratio=0.08)
        time.sleep(GOLD_ACTION_DELAY)
        return GoldState.LEVEL_LIST_VISIBLE

    # ---- NO FREE RUDNIK ----
    if current_state == GoldState.NO_FREE_RUDNIK:
        print("[GOLD] На текущем уровне нет свободных рудников. Пробуем открыть выбор уровня.")
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
            print(f"[GOLD] Поиск длится {int(elapsed_find)} сек — таймаут {GOLD_SEARCH_TIMEOUT} сек. Сброс.")
            _gold_ctx['find_started_at'] = None
            find_and_click(GOLD_CLOSE_IMG, screen_cv, region)
            return GoldState.UNKNOWN
        time.sleep(0.2)
        find_and_click(GOLD_FIND_IMG, screen_cv, region)
        return GoldState.FIND_VISIBLE

    # ---- EVENTS: RUDNIK VISIBLE ----
    if current_state == GoldState.EVENTS_RUDNIK_VISIBLE:
        _gold_ctx['expected'] = 'forward_popup'
        _gold_ctx['swipe_count'] = 0
        clicked, _ = find_and_click(GOLD_RUDNIK_IMG, screen_cv, region)
        if clicked:
            print("[GOLD] Нажали на иконку рудника в календаре. Ждём попап 'Вперёд'.")
            time.sleep(0.5)
            return GoldState.FORWARD_POPUP_VISIBLE
        return GoldState.EVENTS_MENU_OPEN

    # ---- EVENTS: FORWARD POPUP ----
    if current_state == GoldState.FORWARD_POPUP_VISIBLE:
        _gold_ctx['expected'] = 'rudnik_tab'
        clicked, _ = find_and_click(GOLD_FORWARD_IMG, screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
        if clicked:
            print("[GOLD] Нажали 'Вперёд'. Ждём открытия табы рудника.")
            time.sleep(0.5)
            return GoldState.RUDNIK_TAB
        print("[GOLD] Кнопка 'Вперёд' не найдена, пробуем закрыть попап.")
        find_and_click(GOLD_CLOSE_IMG, screen_cv, region)
        return GoldState.EVENTS_MENU_OPEN

    # ---- EVENTS: MENU OPEN, NEED SCROLL ----
    if current_state in (GoldState.EVENTS_MENU_OPEN, GoldState.EVENTS_NEED_SCROLL):
        _gold_ctx['expected'] = 'events_scroll'
        # Сначала проверим, не появился ли rudnik после предыдущего свайпа
        rudnik_coords, _ = find_on_screen(get_template(GOLD_RUDNIK_IMG), screen_cv, region)
        if rudnik_coords:
            _gold_ctx['swipe_count'] = 0
            return GoldState.EVENTS_RUDNIK_VISIBLE

        # Верхнее меню событий: свайпаем влево чтобы добраться к началу списка,
        # потом вправо для поиска события золотодобычи
        direction = 'left' if _gold_ctx.get('swipe_count', 0) < 3 else 'right'
        swipe_horizontal(region, direction)
        _gold_ctx['swipe_count'] = _gold_ctx.get('swipe_count', 0) + 1
        if _gold_ctx['swipe_count'] > 15:
            print("[GOLD] Не удалось найти иконку рудника в меню событий. Сброс.")
            _gold_ctx['swipe_count'] = 0
            _gold_ctx['expected'] = None
            return GoldState.UNKNOWN
        return GoldState.EVENTS_NEED_SCROLL

    # ---- MAIN SCREEN ----
    if current_state == GoldState.MAIN_SCREEN:
        # Проверим, не открыт ли уже календарь (rudnik виден)
        rudnik_coords, _ = find_on_screen(get_template(GOLD_RUDNIK_IMG), screen_cv, region)
        if rudnik_coords:
            print("[GOLD] Календарь уже открыт, rudnik виден.")
            _gold_ctx['expected'] = 'events'
            _gold_ctx['swipe_count'] = 0
            return GoldState.EVENTS_RUDNIK_VISIBLE

        # Счётчик попыток нажать события
        _gold_ctx['main_screen_tries'] = _gold_ctx.get('main_screen_tries', 0) + 1

        # Если видна info.png — это попап, кликаем в верхнюю часть экрана для закрытия
        info_coords, _ = find_on_screen(get_template(INFO_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if info_coords:
            print("[GOLD] Видна info.png — попап открыт. Клик в верхнюю часть экрана для закрытия.")
            click_x = region[0] + region[2] // 2
            click_y = region[1] + int(region[3] * 0.15)
            pyautogui.click(click_x, click_y)
            time.sleep(0.5)
            _gold_ctx['main_screen_tries'] = 0
            return GoldState.UNKNOWN

        # Если застряли на main_screen > 3 попыток — клик в верхнюю часть экрана
        if _gold_ctx['main_screen_tries'] > 3:
            print(f"[GOLD] Застряли на main_screen ({_gold_ctx['main_screen_tries']} попыток). Клик в верхнюю часть экрана.")
            click_x = region[0] + region[2] // 2
            click_y = region[1] + int(region[3] * 0.15)
            pyautogui.click(click_x, click_y)
            time.sleep(0.5)
            _gold_ctx['main_screen_tries'] = 0
            return GoldState.UNKNOWN

        clicked, _ = find_and_click(EVENTS_IMG, screen_cv, region)
        _gold_ctx['swipe_count'] = 0
        _gold_ctx['events_clicked_at'] = time.time()
        time.sleep(1.0)
        _gold_ctx['expected'] = 'events'
        return GoldState.EVENTS_MENU_OPEN

    # ---- UNKNOWN / STUCK RECOVERY ----
    if current_state == GoldState.UNKNOWN:
        print(f"[GOLD] UNKNOWN recovery start. stuck_count={_gold_ctx.get('stuck_count', 0)}, expected={_gold_ctx.get('expected')}", flush=True)
        clicked_at = _gold_ctx.get('moveon_clicked_at')
        if clicked_at and (time.time() - clicked_at) < 2.0:
            print("[GOLD] Ожидаем завершения перехода после клика 'Перейти'.")
            _gold_ctx['moveon_clicked_at'] = None
            time.sleep(GOLD_ACTION_DELAY)
            return GoldState.UNKNOWN

        clicked_events_at = _gold_ctx.get('events_clicked_at')
        if clicked_events_at and (time.time() - clicked_events_at) < 4.0:
            print("[GOLD] Ожидаем открытия календаря событий.")
            time.sleep(0.1)
            return GoldState.UNKNOWN

        # Если мы недавно открыли события, но оказались в активном событии — свайп по верхней карусели
        if _gold_ctx.get('expected') == 'events' and clicked_events_at \
                and (time.time() - clicked_events_at) < 5.0:
            print("[GOLD] Активное событие открылось вместо календаря. Пробуем свайп по верхней карусели.")
            swipe_horizontal(region, 'right')
            time.sleep(0.3)
            return GoldState.UNKNOWN

        _gold_ctx['stuck_count'] = _gold_ctx.get('stuck_count', 0) + 1
        action = _gold_ctx.get('stuck_last_action')
        if action != 'back':
            print("[GOLD] UNKNOWN recovery: try back", flush=True)
            find_and_click(BACK_IMG, screen_cv, region)
            _gold_ctx['stuck_last_action'] = 'back'
        elif action != 'close':
            print("[GOLD] UNKNOWN recovery: try close", flush=True)
            find_and_click(GOLD_CLOSE_IMG, screen_cv, region)
            _gold_ctx['stuck_last_action'] = 'close'
        else:
            print("[GOLD] UNKNOWN recovery: try village", flush=True)
            find_and_click(VILLAGE_IMG, screen_cv, region)
            _gold_ctx['stuck_last_action'] = None
            _gold_ctx['stuck_count'] = 0

        time.sleep(0.1)
        print("[GOLD] UNKNOWN recovery end", flush=True)
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
            time.sleep(0.3)
            return current_state
    elif attempts % 4 == 2:
        if find_and_click(BACK_IMG, screen_cv, region)[0]:
            time.sleep(0.3)
            return current_state
    elif attempts % 4 == 3:
        if find_and_click(GOLD_CLOSE_IMG, screen_cv, region)[0]:
            time.sleep(0.3)
            return current_state
    else:
        center_x = region[0] + region[2] // 2
        center_y = region[1] + region[3] // 2
        print(f"[GOLD EXIT] Клик по центру экрана ({center_x}, {center_y}) для сброса UI.")
        pyautogui.click(center_x, center_y)
        time.sleep(0.5)
        return current_state

    if current_state in (GoldState.UNKNOWN,):
        find_and_click(BACK_IMG, screen_cv, region)
        time.sleep(GOLD_ACTION_DELAY)
        return last_exit_state if last_exit_state is not None else GoldState.UNKNOWN

    return current_state
