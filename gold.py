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
last_gold_time = 0
_gold_ctx = {
    'expected': None,          # подсказка для неоднозначных состояний
    'swipe_count': 0,
    'level_select_scroll_tries': 0,
    'stuck_count': 0,
    'stuck_last_action': None,
    'started_at': None,        # timestamp запуска добычи
    'current_mining_level': None,
    'recall_requested': False,
}


# ==========================================
# ТАЙМЕР / ПРОВЕРКА ПОРЫ
# ==========================================
def should_do_gold():
    """True если прошло GOLD_INTERVAL с последнего посещения."""
    global last_gold_time
    if not GOLD_ENABLED:
        return False
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


# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ УРОВНЕЙ
# ==========================================
def get_current_level(screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD):
    """Определить текущий открытый уровень рудника по current_lvl_X."""
    for level in range(1, 7):
        coords, conf = find_on_screen(get_template(GOLD_CURRENT_LEVEL_IMAGES[level]), screen_cv, region, threshold)
        if coords:
            print(f"[GOLD] Распознан текущий уровень: {level} (conf={conf:.3f})")
            return level
    return None


def get_list_level(screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD):
    """Найти уровень в списке выбора уровней. Возвращает (level, center_coords) или (None, None)."""
    for level in range(1, 7):
        template = get_template(GOLD_LEVEL_IMAGES[level])
        if template is None:
            continue
        coords, conf = find_on_screen(template, screen_cv, region, threshold)
        if coords:
            print(f"[GOLD] В списке найден уровень {level} (conf={conf:.3f})")
            return level, coords
    return None, None


def click_level_go_button(level_path, screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD):
    """
    Кликнуть по кнопке 'Перейти' внутри карточки lvl_X.png.
    Шаблон lvl_X содержит всю карточку; кнопка находится в нижней части.
    """
    template = get_template(level_path)
    if template is None:
        return False

    res = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    if max_val < threshold:
        return False

    h, w = template.shape[:2]
    click_x = region[0] + max_loc[0] + w / 2
    click_y = region[1] + max_loc[1] + h * 0.85
    pyautogui.click(click_x, click_y)
    print(f"[GOLD] Нажата 'Перейти' для целевого уровня ({click_x:.0f}, {click_y:.0f}) conf={max_val:.3f}")
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

    # 3. Цепочка добычи / марш
    coords, _ = find_on_screen(get_template(GOLD_GO_IMG), screen_cv, region)
    if coords:
        return GoldState.GO_VISIBLE

    coords, _ = find_on_screen(get_template(GOLD_WORK_IMG), screen_cv, region)
    if coords:
        return GoldState.WORK_VISIBLE

    coords, _ = find_on_screen(get_template(GOLD_GRIND_IMG), screen_cv, region)
    if coords:
        return GoldState.GRIND_VISIBLE

    # 4. Свободное место после поиска
    coords, _ = find_on_screen(get_template(GOLD_FREE_PLACE_IMG), screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
    if coords:
        return GoldState.FREE_PLACE_VISIBLE

    # 5. Открыта таба рудника (виджет уровня / select_level) — приоритет выше,
    #    чем у иконки активной добычи, чтобы случайный UI-указатель не мешал.
    current_level = get_current_level(screen_cv, region)
    if current_level is not None:
        return GoldState.RUDNIK_TAB

    coords, _ = find_on_screen(get_template(GOLD_RUDNIK_OPENED_IMG), screen_cv, region)
    if coords:
        return GoldState.RUDNIK_TAB

    # 6. Мой рудник (отряд уже добывает)
    coords, _ = find_on_screen(get_template(GOLD_MY_RUDNIK_IMG), screen_cv, region)
    if coords:
        return GoldState.MY_RUDNIK_VISIBLE

    # 7. Иконка активного уровня добычи (кликабельная).
    #    Используется как вспомогательный признак, только если не определились
    #    RUDNIK_TAB/MY_RUDNIK_VISIBLE.
    coords, _ = find_on_screen(get_template(GOLD_CURRENT_RAID_LEVEL_ICON_IMG), screen_cv, region)
    if coords:
        return GoldState.RAID_LEVEL_ICON_VISIBLE

    # 8. Список уровней
    coords, _ = find_on_screen(get_template(GOLD_SELECT_LEVEL_IMG), screen_cv, region)
    if coords:
        # Если мы целенаправленно открыли список — считаем это списком уровней
        if _gold_ctx.get('expected') == 'level_list':
            return GoldState.LEVEL_LIST_VISIBLE
        return GoldState.SELECT_LEVEL_VISIBLE

    # 9. Меню событий — иконка рудника
    coords, _ = find_on_screen(get_template(GOLD_RUDNIK_IMG), screen_cv, region)
    if coords:
        return GoldState.EVENTS_OPEN

    # 10. Главный экран / меню событий без видимого рудника
    coords, _ = find_on_screen(get_template(EVENTS_IMG), screen_cv, region)
    if coords:
        if _gold_ctx.get('expected') in ('events', 'events_scroll'):
            return GoldState.EVENTS_NEED_SCROLL
        return GoldState.MAIN_SCREEN

    # 11. Признаки поселения / карты
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

    # ---- RETURN CONFIRM ----
    if current_state == GoldState.RETURN_CONFIRM_VISIBLE:
        find_and_click(GOLD_RETURN_BOYS_IMG, screen_cv, region)
        clear_gold_mission()
        _gold_ctx['expected'] = 'find'
        print("[GOLD] Отряд отозван.")
        return GoldState.FIND_VISIBLE

    # ---- GO / WORK / GRIND ----
    if current_state == GoldState.GO_VISIBLE:
        find_and_click(GOLD_GO_IMG, screen_cv, region)
        start_gold_mission()
        update_gold_time()
        print("[GOLD] ✓ Золотодобыча запущена!")
        return GoldState.COMPLETED

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
        time.sleep(0.5)
        return GoldState.RUDNIK_TAB

    # ---- RUDNIK TAB (выбор / поиск уровня) ----
    if current_state == GoldState.RUDNIK_TAB:
        _gold_ctx['expected'] = 'rudnik_tab'
        current = get_current_level(screen_cv, region)

        if current is not None and current != GOLD_LEVEL:
            print(f"[GOLD] Уровень {current}, нужен {GOLD_LEVEL}. Открываем выбор уровня.")
            find_and_click(GOLD_SELECT_LEVEL_IMG, screen_cv, region)
            _gold_ctx['expected'] = 'level_list'
            _gold_ctx['level_select_scroll_tries'] = 0
            return GoldState.SELECT_LEVEL_VISIBLE

        # Уровень совпадает или не удалось распознать — начинаем поиск
        find_and_click(GOLD_FIND_IMG, screen_cv, region)
        _gold_ctx['expected'] = 'find'
        return GoldState.FIND_VISIBLE

    # ---- LEVEL LIST / SELECT LEVEL ----
    if current_state in (GoldState.SELECT_LEVEL_VISIBLE, GoldState.LEVEL_LIST_VISIBLE) \
            or _gold_ctx.get('expected') == 'level_list':
        target_path = GOLD_LEVEL_IMAGES[GOLD_LEVEL]
        found_level, _ = get_list_level(screen_cv, region)

        if found_level == GOLD_LEVEL:
            if click_level_go_button(target_path, screen_cv, region):
                _gold_ctx['expected'] = 'rudnik_tab'
                _gold_ctx['level_select_scroll_tries'] = 0
                return GoldState.RUDNIK_TAB

        # Прокрутка списка
        _gold_ctx['level_select_scroll_tries'] = _gold_ctx.get('level_select_scroll_tries', 0) + 1
        if _gold_ctx['level_select_scroll_tries'] > 10:
            print("[GOLD] Не удалось найти целевой уровень. Сброс.")
            _gold_ctx['expected'] = None
            _gold_ctx['level_select_scroll_tries'] = 0
            return GoldState.UNKNOWN

        direction = 'down'
        if found_level is not None and GOLD_LEVEL < found_level:
            direction = 'up'
        scroll_in_region(region, direction)
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
        _gold_ctx['expected'] = 'events'
        return GoldState.EVENTS_OPEN

    # ---- UNKNOWN / STUCK RECOVERY ----
    if current_state == GoldState.UNKNOWN:
        _gold_ctx['stuck_count'] = _gold_ctx.get('stuck_count', 0) + 1
        if _gold_ctx['stuck_count'] >= 2:
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
            return GoldState.UNKNOWN
        time.sleep(0.5)
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
        GoldState.FREE_PLACE_VISIBLE,
    ):
        find_and_click(BACK_IMG, screen_cv, region)
        return current_state

    if current_state in (GoldState.UNKNOWN,):
        find_and_click(BACK_IMG, screen_cv, region)
        time.sleep(0.3)
        return last_exit_state if last_exit_state is not None else GoldState.UNKNOWN

    return current_state
