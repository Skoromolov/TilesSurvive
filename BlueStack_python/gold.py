# ==========================================
# ЛОГИКА ЗОЛОТОДОБЫЧИ (стейт-машина)
# ==========================================

import time

from config import *
from utils import *


# ==========================================
# ПЕРЕМЕННЫЕ СОСТОЯНИЯ ЗОЛОТА
# ==========================================
last_gold_time = 0


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


# ==========================================
# ОПРЕДЕЛЕНИЕ СОСТОЯНИЯ ЗОЛОТОДОБЫЧИ
# ==========================================
def determine_gold_state(screen_cv, region):
    """Возвращает GoldState на основе текущего экрана (приоритет сверху-вниз)."""
    coords, _ = find_on_screen(get_template(RECONNECT_IMG), screen_cv, region)
    if coords:
        return GoldState.RECONNECT_POPUP

    coords, _ = find_on_screen(get_template(RECONNECT_REPEAT_IMG), screen_cv, region)
    if coords:
        return GoldState.RECONNECT_REPEAT_POPUP

    coords, _ = find_on_screen(get_template(GOLD_RETURN_BOYS_IMG), screen_cv, region)
    if coords:
        return GoldState.RETURN_CONFIRM_VISIBLE

    coords, _ = find_on_screen(get_template(GOLD_GO_IMG), screen_cv, region)
    if coords:
        return GoldState.GO_VISIBLE

    coords, _ = find_on_screen(get_template(GOLD_WORK_IMG), screen_cv, region)
    if coords:
        return GoldState.WORK_VISIBLE

    coords, _ = find_on_screen(get_template(GOLD_GRIND_IMG), screen_cv, region)
    if coords:
        return GoldState.GRIND_VISIBLE

    coords, _ = find_on_screen(get_template(GOLD_MY_RUDNIK_IMG), screen_cv, region)
    if coords:
        return GoldState.MY_RUDNIK_VISIBLE

    coords, _ = find_on_screen(get_template(GOLD_FIND_IMG), screen_cv, region)
    if coords:
        return GoldState.FIND_VISIBLE

    # rudnik_opened говорит что мы в табе рудника
    coords, _ = find_on_screen(get_template(GOLD_RUDNIK_OPENED_IMG), screen_cv, region)
    if coords:
        return GoldState.RUDNIK_TAB

    # rudnik.png — иконка в списке событий
    coords, _ = find_on_screen(get_template(GOLD_RUDNIK_IMG), screen_cv, region)
    if coords:
        return GoldState.EVENTS_OPEN

    # events.png на главном экране
    coords, _ = find_on_screen(get_template(EVENTS_IMG), screen_cv, region)
    if coords:
        return GoldState.MAIN_SCREEN

    # Если видны признаки поселения — тоже считаем MAIN_SCREEN
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
_unchanged_count = 0
_last_action_state = None

def process_gold(screen_cv, region, last_gold_state, window):
    """
    Обработать одно состояние золотодобычи; одно действие за вызов.
    Возвращает: новое состояние (GoldState)
    """
    global _unchanged_count, _last_action_state

    current_state = determine_gold_state(screen_cv, region)

    if current_state != last_gold_state:
        print(f"[GOLD] Состояние: {current_state.value}")
        _unchanged_count = 0
        _last_action_state = None

    # ---- RECONNECT ----
    if current_state == GoldState.RECONNECT_POPUP:
        handle_reconnect(screen_cv, region)
        return GoldState.UNKNOWN

    if current_state == GoldState.RECONNECT_REPEAT_POPUP:
        handle_reconnect_repeat(screen_cv, region)
        return GoldState.UNKNOWN

    # ---- WORKFLOW ----
    if current_state == GoldState.MAIN_SCREEN:
        find_and_click(EVENTS_IMG, screen_cv, region)
        return GoldState.EVENTS_OPEN

    if current_state == GoldState.EVENTS_OPEN:
        # Клик по иконке рудника; после этого ожидаем RUDNIK_TAB
        find_and_click(GOLD_RUDNIK_IMG, screen_cv, region)
        return GoldState.RUDNIK_TAB

    if current_state == GoldState.RUDNIK_TAB:
        # Нажимаем Find для поиска свободного рудника
        find_and_click(GOLD_FIND_IMG, screen_cv, region)
        return GoldState.FIND_VISIBLE

    if current_state == GoldState.FIND_VISIBLE:
        # Пока Find висит — ждём результата (он исчезает и появится grind / my_rudnik)
        # Ничего не кликаем, на следующей итерации увидим что появилось
        return GoldState.FIND_VISIBLE

    if current_state == GoldState.GRIND_VISIBLE:
        find_and_click(GOLD_GRIND_IMG, screen_cv, region)
        return GoldState.WORK_VISIBLE

    if current_state == GoldState.WORK_VISIBLE:
        find_and_click(GOLD_WORK_IMG, screen_cv, region)
        return GoldState.GO_VISIBLE

    if current_state == GoldState.GO_VISIBLE:
        find_and_click(GOLD_GO_IMG, screen_cv, region)
        update_gold_time()
        print("[GOLD] ✓ Золотодобыча завершена!")
        return GoldState.COMPLETED

    # ---- MY RUDNIK BRANCH ----
    if current_state == GoldState.MY_RUDNIK_VISIBLE:
        find_and_click(GOLD_RETURN_IMG, screen_cv, region)
        return GoldState.RETURN_CONFIRM_VISIBLE

    if current_state == GoldState.RETURN_CONFIRM_VISIBLE:
        find_and_click(GOLD_RETURN_BOYS_IMG, screen_cv, region)
        # После отзыва снова появится Find, идём к нему
        return GoldState.FIND_VISIBLE

    # ---- UNKNOWN / STUCK RECOVERY ----
    if current_state == GoldState.UNKNOWN:
        # Защита от застревания: если дважды подряд UNKNOWN — пробуем recovery
        if last_gold_state == GoldState.UNKNOWN and _unchanged_count >= 1:
            # Recovery: клик Back → если не помог Close → Village
            if _last_action_state != GoldState.UNKNOWN:
                _last_action_state = current_state
                find_and_click(BACK_IMG, screen_cv, region)
                return GoldState.UNKNOWN
            if _last_action_state == GoldState.UNKNOWN and _unchanged_count >= 2:
                find_and_click(CLOSE_IMG, screen_cv, region)
                _last_action_state = current_state
                return GoldState.UNKNOWN
            if _unchanged_count >= 3:
                find_and_click(VILLAGE_IMG, screen_cv, region)
                _last_action_state = None
                _unchanged_count = 0
                return GoldState.MAIN_SCREEN
        else:
            _unchanged_count += 1
            time.sleep(0.5)
            return GoldState.UNKNOWN

    return current_state


# ==========================================
# ЗАВЕРШЕНИЕ ЗОЛОТОДОБЫЧИ (возврат в поселение)
# ==========================================
def process_gold_exit(screen_cv, region, last_exit_state, window):
    """
    Обратный переход к MAIN_SCREEN после завершения добычи.
    Возвращает: новое состояние (GoldState.COMPLETED при успехе)
    """
    if last_exit_state is None:
        last_exit_state = GoldState.COMPLETED

    current_state = determine_gold_state(screen_cv, region)

    # Если уже на главной
    if current_state in (GoldState.MAIN_SCREEN,):
        return GoldState.COMPLETED

    # Если окно рудника — жмём Back пока не выйдем
    if current_state in (
        GoldState.GO_VISIBLE,
        GoldState.WORK_VISIBLE,
        GoldState.GRIND_VISIBLE,
        GoldState.FIND_VISIBLE,
        GoldState.RUDNIK_TAB,
        GoldState.EVENTS_OPEN,
        GoldState.MY_RUDNIK_VISIBLE,
        GoldState.RETURN_CONFIRM_VISIBLE,
    ):
        find_and_click(BACK_IMG, screen_cv, region)
        return current_state

    # Recovery
    if current_state in (GoldState.UNKNOWN,):
        find_and_click(BACK_IMG, screen_cv, region)
        time.sleep(0.3)
        return last_exit_state

    return current_state
