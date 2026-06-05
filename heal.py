# ==========================================
# ЛОГИКА ЛЕЧЕНИЯ
# ==========================================

from config import *
from utils import *


# ==========================================
# ОПРЕДЕЛЕНИЕ СОСТОЯНИЯ ЛЕЧЕНИЯ
# ==========================================
def determine_heal_state(screen_cv, region):
    """
    Определить текущее состояние лечения.
    Возвращает: HealState
    """
    # Проверка в порядке приоритета
    coords, _ = find_on_screen(get_template(RECONNECT_IMG), screen_cv, region)
    if coords:
        return HealState.RECONNECT_POPUP

    coords, _ = find_on_screen(get_template(RECONNECT_REPEAT_IMG), screen_cv, region)
    if coords:
        return HealState.RECONNECT_REPEAT_POPUP

    coords, _ = find_on_screen(get_template(FAST_USE_IMG), screen_cv, region)
    if coords:
        return HealState.FAST_USE_POPUP

    coords, _ = find_on_screen(get_template(HEAL_BUTTON_IMG), screen_cv, region)
    if coords:
        return HealState.HEAL_MENU_OPEN

    coords, _ = find_on_screen(get_template(CONFIRM_BUTTON_IMG), screen_cv, region)
    if coords:
        return HealState.CONFIRM_BUTTON_REQUIRED

    coords, _ = find_on_screen(get_template(MAIL_IMG), screen_cv, region)
    if coords:
        return HealState.MAIL

    coords, _ = find_on_screen(get_template(HEAL_TOWN_IMG), screen_cv, region)
    if coords:
        return HealState.HEAL_ICON

    coords, _ = find_on_screen(get_template(HELP_HANDS_IMG), screen_cv, region)
    if coords:
        return HealState.HELP_HANDS

    coords, _ = find_on_screen(get_template(HEAL_HELP_HANDS_IMG), screen_cv, region)
    if coords:
        return HealState.HEAL_HELP

    coords, _ = find_on_screen(get_template(HEAL_WAIT_IMG), screen_cv, region)
    if coords:
        return HealState.HEAL_WAIT

    coords, _ = find_on_screen(get_template(WILD_EARTH_IMG), screen_cv, region)
    if coords:
        return HealState.MAIN_SCREEN

    coords, _ = find_on_screen(get_template(VILLAGE_IMG), screen_cv, region)
    if coords:
        return HealState.UNKNOWN

    return HealState.UNKNOWN


# ==========================================
# ОБРАБОТКА СОСТОЯНИЙ ЛЕЧЕНИЯ
# ==========================================
def process_heal(screen_cv, region, last_heal_state):
    """
    Обработать текущее состояние лечения.
    Возвращает: новое состояние (HealState или None)
    """
    current_state = determine_heal_state(screen_cv, region)

    if current_state != last_heal_state:
        print(f"[HEAL] Состояние: {current_state.value}")

    # Обработка каждого состояния
    if current_state == HealState.RECONNECT_POPUP:
        handle_reconnect(screen_cv, region)
        return None

    if current_state == HealState.RECONNECT_REPEAT_POPUP:
        handle_reconnect_repeat(screen_cv, region)
        return None

    if current_state == HealState.MAIL:
        find_and_click(MAIL_IMG, screen_cv, region)
        return None

    if current_state == HealState.CONFIRM_BUTTON_REQUIRED:
        find_and_click(CONFIRM_BUTTON_IMG, screen_cv, region)
        return None

    if current_state == HealState.HEAL_ICON:
        found, _ = find_and_click(HEAL_TOWN_IMG, screen_cv, region)
        if found:
            return HealState.HEAL_MENU_OPEN
        return None

    if current_state == HealState.HEAL_HELP:
        found, _ = find_and_click(HEAL_HELP_HANDS_IMG, screen_cv, region)
        if found:
            return None

    if current_state == HealState.HEAL_ACTIVE:
        found, _ = find_and_click(HEAL_HELP_HANDS_IMG, screen_cv, region)
        if found:
            return None
        return HealState.HEAL_ACTIVE

    if current_state == HealState.FAST_USE_POPUP:
        found, _ = find_and_click(CLOSE_IMG, screen_cv, region)
        if found:
            return HealState.UNKNOWN

    if current_state == HealState.HEAL_MENU_OPEN:
        found, _ = find_and_click(HEAL_BUTTON_IMG, screen_cv, region)
        if found:
            return HealState.MAIN_SCREEN

    if current_state == HealState.UNKNOWN:
        found, _ = find_and_click(VILLAGE_IMG, screen_cv, region)
        if found:
            return HealState.MAIN_SCREEN
        found, _ = find_and_click(BACK_IMG, screen_cv, region)
        if found:
            return HealState.UNKNOWN
        found, _ = find_and_click(CLOSE_IMG, screen_cv, region)
        if found:
            return HealState.UNKNOWN

    return HealState.UNKNOWN


# ==========================================
# ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ ЛЕЧЕНИЯ
# ==========================================
def check_and_click_help_button(screen_cv, region):
    """
    Проверить и кликнуть кнопку помощи союзу.
    Возвращает: True если найдена и нажата
    """
    found, _ = find_and_click(HELP_HANDS_IMG, screen_cv, region, CONFIDENCE_THRESHOLD)
    if found:
        print("[HEAL] ✓ Кнопка помощи найдена и нажата!")
    return found
