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
gold_first_run = True         # при первом запуске сразу идём в золото, не ждём GOLD_INTERVAL
_gold_ctx = {
    'expected': None,          # подсказка для неоднозначных состояний
    'swipe_count': 0,
    'level_select_scroll_tries': 0,
    'stuck_count': 0,
    'stuck_last_action': None,
    'events_clicked_at': None,
    'moveon_clicked_at': None,
    'recall_requested': False,
    'need_level_check': False, # флаг: нужно убедиться, что мы на целевом уровне
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
    return _gold_ctx['started_at'] is not None and not _gold_ctx['recall_requested']


def gold_mission_should_recall():
    """Пора отозвать отряд (45 минут прошли)."""
    if not gold_mission_active():
        return False
    elapsed = time.time() - _gold_ctx['started_at']
    if elapsed >= GOLD_MINING_DURATION:
        print(f"[GOLD] Добыча идёт {int(elapsed)} сек, порог {GOLD_MINING_DURATION} сек. Нужен отзыв.")
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
    _gold_ctx['raid_icon_clicks'] = 0
    _gold_ctx['need_level_check'] = False
    _gold_ctx['recall_requested'] = False

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


def is_target_level_in_list(screen_cv, region, target=GOLD_LEVEL, threshold=0.95):
    """Проверить, виден ли целевой уровень в списке. Используем высокий порог, чтобы
    исключить ложные совпадения lvl_X в других элементах интерфейса."""
    lvl_template = get_template(GOLD_LEVEL_IMAGES[target])
    if lvl_template is None:
        return False
    coords, conf = find_on_screen(lvl_template, screen_cv, region, threshold)
    return coords is not None


def click_moveon_for_target_level(screen_cv, region, target=GOLD_LEVEL, lvl_threshold=0.95, btn_threshold=0.70):
    """
    Найти кнопку 'Перейти' (moveOn.png), которая расположена под текстом целевого уровня,
    и кликнуть по ней. Обрабатывает дублирующиеся кнопки на экране.

    Логика: для каждой найденной кнопки 'Перейти' ищем текст целевого уровня
    непосредственно над ней. Так мы точно привязываем кнопку к карточке уровня.
    """

    btn_template = get_template(GOLD_MOVEON_IMG)
    if btn_template is None:
        return False
    h_btn, w_btn = btn_template.shape[:2]
    btn_matches = find_all_on_screen(btn_template, screen_cv, region, btn_threshold)
    if not btn_matches:
        print(f"[GOLD] moveOn.png не найден на экране (threshold={btn_threshold}).")
        return False

    # 2. Находим все вхождения текста целевого уровня
    lvl_template = get_template(GOLD_LEVEL_IMAGES[target])
    if lvl_template is None:
        return False
    h_lvl, w_lvl = lvl_template.shape[:2]
    lvl_matches = find_all_on_screen(lvl_template, screen_cv, region, lvl_threshold)
    if not lvl_matches:
        print(f"[GOLD] lvl_{target}.png не найден на экране.")
        return False

    # 3. Для каждой кнопки ищем текст уровня, расположенный прямо над ней
    best_pair = None
    best_score = -1.0
    for cx_btn, cy_btn, conf_btn in btn_matches:
        btn_top = cy_btn - h_btn / 2
        for cx_lvl, cy_lvl, conf_lvl in lvl_matches:
            lvl_bottom = cy_lvl + h_lvl / 2
            vertical_gap = btn_top - lvl_bottom
            horizontal_gap = abs(cx_btn - cx_lvl)
            # Текст должен быть над кнопкой, но не слишком высоко
            # и по горизонтали совпадать с кнопкой (текст может быть смещён
            # относительно центра карточки, поэтому допуск побольше)
            if 0 < vertical_gap < h_btn * 5 and horizontal_gap < w_btn * 0.55:
                score = conf_lvl + conf_btn
                if score > best_score:
                    best_score = score
                    best_pair = (cx_btn, cy_btn, conf_btn, cx_lvl, cy_lvl, conf_lvl)

    if best_pair is None:
        print(f"[GOLD] Кнопка 'Перейти' под уровнем {target} не найдена. "
              f"lvl_matches={len(lvl_matches)}, btn_matches={len(btn_matches)}")
        return False

    cx_btn, cy_btn, conf_btn, cx_lvl, cy_lvl, conf_lvl = best_pair
    btn_top = cy_btn - h_btn / 2
    btn_bottom = cy_btn + h_btn / 2
    region_top = region[1]
    region_bottom = region[1] + region[3]
    if btn_top < region_top + 20 or btn_bottom > region_bottom - 20:
        print(f"[GOLD] Кнопка 'Перейти' под уровнем {target} частично за краем экрана. Скроллим.")
        return False

    pyautogui.click(cx_btn, cy_btn)
    print(f"[GOLD] Нажата 'Перейти' под уровнем {target} ({cx_btn:.0f}, {cy_btn:.0f}), conf=({conf_lvl:.3f}/{conf_btn:.3f})")
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

    # 3. Кнопка "Завершить" после отзыва отряда / завершения добычи
    coords, _ = find_on_screen(get_template(GOLD_FINISH_IMG), screen_cv, region)
    if coords:
        return GoldState.FINISH_VISIBLE

    # 4. Подтверждение после "Завершить" (confirm)
    coords, _ = find_on_screen(get_template(GOLD_CONFIRM_IMG), screen_cv, region)
    if coords:
        return GoldState.CONFIRM_VISIBLE

    # 4.5 Попап "SummaryStrenghtText" — место занято
    coords, _ = find_on_screen(get_template(GOLD_SUMMARY_STRENGTH_TEXT_IMG), screen_cv, region)
    if coords:
        return GoldState.SUMMARY_STRENGTH_TEXT_VISIBLE

    # 5. Кнопка "Отозвать" на экране рудника — отряд уже добывает на этом уровне
    coords, _ = find_on_screen(get_template(GOLD_RETURN_IMG), screen_cv, region)
    if coords:
        return GoldState.RETURN_BUTTON_VISIBLE

    # 6. Цепочка добычи / марш
    coords, _ = find_on_screen(get_template(GOLD_GO_IMG), screen_cv, region)
    if coords:
        return GoldState.GO_VISIBLE

    coords, _ = find_on_screen(get_template(GOLD_WORK_IMG), screen_cv, region)
    if coords:
        return GoldState.WORK_VISIBLE

    coords, _ = find_on_screen(get_template(GOLD_GRIND_IMG), screen_cv, region)
    if coords:
        return GoldState.GRIND_VISIBLE

    # 7. Свободное место после поиска
    coords, _ = find_on_screen(get_template(GOLD_FREE_PLACE_IMG), screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
    if coords:
        return GoldState.FREE_PLACE_VISIBLE

    # 8. Открыта таба рудника (виджет уровня / select_level)
    current_level = get_current_level(screen_cv, region)
    if current_level is not None:
        return GoldState.RUDNIK_TAB

    coords, _ = find_on_screen(get_template(GOLD_RUDNIK_OPENED_IMG), screen_cv, region)
    if coords:
        return GoldState.RUDNIK_TAB

    # 9. Мой рудник (отряд уже добывает)
    coords, _ = find_on_screen(get_template(GOLD_MY_RUDNIK_IMG), screen_cv, region)
    if coords:
        return GoldState.MY_RUDNIK_VISIBLE

    # 10. Иконка активного уровня добычи (кликабельная)
    coords, _ = find_on_screen(get_template(GOLD_CURRENT_RAID_LEVEL_ICON_IMG), screen_cv, region)
    if coords:
        return GoldState.RAID_LEVEL_ICON_VISIBLE

    # 11. Список уровней
    coords, _ = find_on_screen(get_template(GOLD_SELECT_LEVEL_IMG), screen_cv, region)
    if coords:
        return GoldState.SELECT_LEVEL_VISIBLE

    # Если мы целенаправленно открыли список — любой видимый lvl_X значит список уровней
    if _gold_ctx.get('expected') == 'level_list':
        found_level, _ = get_list_level(screen_cv, region)
        if found_level is not None:
            return GoldState.LEVEL_LIST_VISIBLE

    # 12. Меню событий — иконка рудника
    coords, _ = find_on_screen(get_template(GOLD_RUDNIK_IMG), screen_cv, region)
    if coords:
        return GoldState.EVENTS_OPEN

    # 13. Главный экран / меню событий без видимого рудника
    coords, _ = find_on_screen(get_template(EVENTS_IMG), screen_cv, region)
    if coords:
        if _gold_ctx.get('expected') in ('events', 'events_scroll'):
            return GoldState.EVENTS_NEED_SCROLL
        return GoldState.MAIN_SCREEN

    # 14. Признаки поселения / карты
    coords, _ = find_on_screen(get_template(VILLAGE_IMG), screen_cv, region)
    if coords:
        return GoldState.MAIN_SCREEN

    coords, _ = find_on_screen(get_template(WILD_EARTH_IMG), screen_cv, region)
    if coords:
        return GoldState.MAIN_SCREEN

    return GoldState.UNKNOWN


# ==========================================
# ОБРАБОТКА СОСТОЯНИЙ ЗОЛОТОДОБЫЧИ
# ==========================================
def process_gold(screen_cv, region, last_gold_state, window):
    """
    Обработать одно состояние золотодобычи; одно действие за вызов.
    Возвращает: новое состояние (GoldState)
    """
    current_state = determine_gold_state(screen_cv, region)

    if current_state != last_gold_state:
        print(f"[GOLD] Состояние: {current_state.value}")

    # ---- RECONNECT ----
    if current_state == GoldState.RECONNECT_POPUP:
        handle_reconnect(screen_cv, region)
        return GoldState.UNKNOWN

    if current_state == GoldState.RECONNECT_REPEAT_POPUP:
        handle_reconnect_repeat(screen_cv, region)
        return GoldState.UNKNOWN

    # ---- RETURN BUTTON ----
    if current_state == GoldState.RETURN_BUTTON_VISIBLE:
        print("[GOLD] Отряд занят добычей на этом уровне. Отзываем.")
        find_and_click(GOLD_RETURN_IMG, screen_cv, region)
        _gold_ctx['recall_requested'] = True
        return GoldState.RETURN_CONFIRM_VISIBLE

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
        # Сначала ищем кнопку присоединения/атаки внутри попапа
        join_coords, _ = find_on_screen(get_template(GOLD_WORK_IMG), screen_cv, region)
        if join_coords:
            print("[GOLD] Найдена кнопка присоединения/добычи. Нажимаем.")
            find_and_click(GOLD_WORK_IMG, screen_cv, region)
            return GoldState.WORK_VISIBLE

        # Иначе просто закрываем попап
        print("[GOLD] Место занято (SummaryStrenghtText). Закрываем попап.")
        find_and_click(CLOSE_IMG, screen_cv, region)
        _gold_ctx['expected'] = 'rudnik_tab'
        return GoldState.RUDNIK_TAB

    # ---- ПРОВЕРКА ЦЕЛЕВОГО УРОВНЯ ПЕРЕД ДОБЫЧЕЙ ----
    # После отзыва/подтверждения обязательно проверяем, что мы на нужном уровне,
    # прежде чем нажимать find / free_place / grind / work / go.
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
            # Текущий уровень не виден на экране поиска/добычи — закрываем его, чтобы увидеть current_lvl_X
            print("[GOLD] Текущий уровень не виден на экране добычи. Закрываем окно для проверки.")
            find_and_click(CLOSE_IMG, screen_cv, region)
            return GoldState.UNKNOWN

    # ---- GO / WORK / GRIND ----
    if current_state == GoldState.GO_VISIBLE:
        find_and_click(GOLD_GO_IMG, screen_cv, region)
        time.sleep(GOLD_ACTION_DELAY)

        # Проверяем, что рудник действительно занят
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

        _gold_ctx['expected'] = 'rudnik_tab'
        return GoldState.RUDNIK_TAB

    if current_state == GoldState.WORK_VISIBLE:
        find_and_click(GOLD_WORK_IMG, screen_cv, region)
        return GoldState.GO_VISIBLE

    if current_state == GoldState.GRIND_VISIBLE:
        find_and_click(GOLD_GRIND_IMG, screen_cv, region)
        return GoldState.WORK_VISIBLE

    # ---- FREE PLACE ----
    if current_state == GoldState.FREE_PLACE_VISIBLE:
        find_and_click(GOLD_FREE_PLACE_IMG, screen_cv, region)
        return GoldState.GRIND_VISIBLE

    # ---- MY RUDNIK / ACTIVE MINING ----
    if current_state in (GoldState.MY_RUDNIK_VISIBLE, GoldState.RAID_LEVEL_ICON_VISIBLE):
        # Если требуется отзыв — нажимаем return
        if _gold_ctx.get('recall_requested'):
            find_and_click(GOLD_RETURN_IMG, screen_cv, region)
            return GoldState.RETURN_CONFIRM_VISIBLE

        # Сначала пробуем распознать уровень прямо на текущем экране
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

        # Уровень не распознался — открываем детали по иконке активного уровня
        _gold_ctx['raid_icon_clicks'] = _gold_ctx.get('raid_icon_clicks', 0) + 1
        if _gold_ctx['raid_icon_clicks'] > 3:
            print("[GOLD] Иконка current_raid_lvl_icon.png не открывает детали. "
                  "Проверьте шаблон (возможно, это курсор/указатель). Сброс.")
            _gold_ctx['raid_icon_clicks'] = 0
            return GoldState.UNKNOWN

        find_and_click(GOLD_CURRENT_RAID_LEVEL_ICON_IMG, screen_cv, region)
        time.sleep(GOLD_ACTION_DELAY)
        return GoldState.RUDNIK_TAB

    # ---- RUDNIK TAB (выбор / поиск уровня) ----
    if current_state == GoldState.RUDNIK_TAB:
        _gold_ctx['expected'] = 'rudnik_tab'
        current = get_current_level(screen_cv, region)

        if current is not None and current != GOLD_LEVEL:
            _gold_ctx['need_level_check'] = True
            print(f"[GOLD] Уровень {current}, нужен {GOLD_LEVEL}. Открываем выбор уровня.")
            find_and_click(GOLD_SELECT_LEVEL_IMG, screen_cv, region)
            _gold_ctx['expected'] = 'level_list'
            _gold_ctx['level_select_scroll_tries'] = 0
            time.sleep(GOLD_ACTION_DELAY)
            return GoldState.SELECT_LEVEL_VISIBLE

        # Уровень совпадает — сбрасываем флаг проверки
        if current == GOLD_LEVEL:
            _gold_ctx['need_level_check'] = False

        # Уровень совпадает или не удалось распознать — начинаем поиск
        find_and_click(GOLD_FIND_IMG, screen_cv, region)
        _gold_ctx['expected'] = 'find'
        return GoldState.FIND_VISIBLE

    # ---- LEVEL LIST / SELECT LEVEL ----
    if current_state in (GoldState.SELECT_LEVEL_VISIBLE, GoldState.LEVEL_LIST_VISIBLE) \
            or _gold_ctx.get('expected') == 'level_list':
        target_path = GOLD_LEVEL_IMAGES[GOLD_LEVEL]

        # 1. Если целевой уровень виден в списке — пробуем нажать 'Перейти' под ним
        if is_target_level_in_list(screen_cv, region, target=GOLD_LEVEL):
            if click_moveon_for_target_level(screen_cv, region, target=GOLD_LEVEL):
                _gold_ctx['expected'] = 'rudnik_tab'
                _gold_ctx['level_select_scroll_tries'] = 0
                _gold_ctx['moveon_clicked_at'] = time.time()
                time.sleep(GOLD_ACTION_DELAY)
                return GoldState.RUDNIK_TAB

        # 2. Иначе определяем направление по любому видимому уровню и скроллим
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

    # ---- FIND (поиск свободного рудника) ----
    if current_state == GoldState.FIND_VISIBLE:
        # Повторяем нажатие Find каждую секунду, пока не появится free_place
        find_and_click(GOLD_FIND_IMG, screen_cv, region)
        return GoldState.FIND_VISIBLE

    # ---- EVENTS_OPEN / EVENTS_NEED_SCROLL ----
    if current_state in (GoldState.EVENTS_OPEN, GoldState.EVENTS_NEED_SCROLL):
        _gold_ctx['expected'] = 'events'
        clicked, _ = find_and_click(GOLD_RUDNIK_IMG, screen_cv, region)
        if clicked:
            _gold_ctx['swipe_count'] = 0
            _gold_ctx['expected'] = 'rudnik_tab'
            return GoldState.RUDNIK_TAB

        # Рудник не влез на экран — свайп вправо по верхней части
        swipe_horizontal(region, 'right')
        _gold_ctx['swipe_count'] = _gold_ctx.get('swipe_count', 0) + 1
        _gold_ctx['expected'] = 'events_scroll'
        if _gold_ctx['swipe_count'] > 10:
            print("[GOLD] Не удалось найти иконку рудника в событиях. Сброс.")
            _gold_ctx['swipe_count'] = 0
            _gold_ctx['expected'] = None
            return GoldState.UNKNOWN
        return GoldState.EVENTS_NEED_SCROLL

    # ---- MAIN SCREEN ----
    if current_state == GoldState.MAIN_SCREEN:
        find_and_click(EVENTS_IMG, screen_cv, region)
        _gold_ctx['swipe_count'] = 0
        _gold_ctx['events_clicked_at'] = time.time()
        time.sleep(1.0)
        _gold_ctx['expected'] = 'events'
        return GoldState.EVENTS_OPEN

    # ---- UNKNOWN / STUCK RECOVERY ----
    if current_state == GoldState.UNKNOWN:
        # Если только что кликнули 'Перейти' — подождём, пока экран перейдёт в RUDNIK_TAB,
        # не нажимая back.png сразу.
        clicked_at = _gold_ctx.get('moveon_clicked_at')
        if clicked_at and (time.time() - clicked_at) < 2.0:
            print("[GOLD] Ожидаем завершения перехода после клика 'Перейти'.")
            _gold_ctx['moveon_clicked_at'] = None
            time.sleep(GOLD_ACTION_DELAY)
            return GoldState.UNKNOWN

        clicked_events_at = _gold_ctx.get('events_clicked_at')
        if clicked_events_at and (time.time() - clicked_events_at) < 2.5:
            print("[GOLD] Ожидаем открытия меню событий.")
            _gold_ctx['events_clicked_at'] = None
            time.sleep(GOLD_ACTION_DELAY)
            return GoldState.UNKNOWN

        _gold_ctx['stuck_count'] = _gold_ctx.get('stuck_count', 0) + 1
        action = _gold_ctx.get('stuck_last_action')
        if action != 'back':
            find_and_click(BACK_IMG, screen_cv, region)
            _gold_ctx['stuck_last_action'] = 'back'
        elif action != 'close':
            find_and_click(CLOSE_IMG, screen_cv, region)
            _gold_ctx['stuck_last_action'] = 'close'
        else:
            find_and_click(VILLAGE_IMG, screen_cv, region)
            _gold_ctx['stuck_last_action'] = None
            _gold_ctx['stuck_count'] = 0

        time.sleep(GOLD_ACTION_DELAY)
        return GoldState.UNKNOWN

    return current_state


# ==========================================
# ЗАВЕРШЕНИЕ ЗОЛОТОДОБЫЧИ (возврат в поселение)
# ==========================================
def process_gold_exit(screen_cv, region, last_exit_state, window):
    """
    Обратный переход к MAIN_SCREEN после завершения добычи.
    Возвращает: GoldState.COMPLETED при успехе.
    """
    current_state = determine_gold_state(screen_cv, region)

    if current_state in (GoldState.MAIN_SCREEN,):
        return GoldState.COMPLETED

    if current_state in (
        GoldState.GO_VISIBLE,
        GoldState.WORK_VISIBLE,
        GoldState.GRIND_VISIBLE,
        GoldState.FIND_VISIBLE,
        GoldState.RUDNIK_TAB,
        GoldState.SELECT_LEVEL_VISIBLE,
        GoldState.LEVEL_LIST_VISIBLE,
        GoldState.EVENTS_OPEN,
        GoldState.EVENTS_NEED_SCROLL,
        GoldState.MY_RUDNIK_VISIBLE,
        GoldState.RAID_LEVEL_ICON_VISIBLE,
        GoldState.RETURN_CONFIRM_VISIBLE,
        GoldState.RETURN_BUTTON_VISIBLE,
        GoldState.FINISH_VISIBLE,
        GoldState.CONFIRM_VISIBLE,
        GoldState.FREE_PLACE_VISIBLE,
    ):
        find_and_click(BACK_IMG, screen_cv, region)
        return current_state

    if current_state in (GoldState.UNKNOWN,):
        find_and_click(BACK_IMG, screen_cv, region)
        time.sleep(GOLD_ACTION_DELAY)
        return last_exit_state if last_exit_state is not None else GoldState.UNKNOWN

    return current_state
