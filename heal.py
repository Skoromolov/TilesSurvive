# ==========================================
# ЛОГИКА ЛЕЧЕНИЯ
# ==========================================

from config import *
from utils import *
from adventure import process_adventure_state
from logger import logger  # Импортируем логгер


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

    coords, _ = find_on_screen(get_template(FAST_USE_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if coords:
        return HealState.FAST_USE_POPUP

    coords, _ = find_on_screen(get_template(HEAL_BUTTON_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if coords:
        return HealState.HEAL_MENU_OPEN

    coords, _ = find_on_screen(get_template(HEAL_FREE_BUTTON_IMG), screen_cv, region, threshold=NAVIGATION_THRESHOLD)
    if coords:
        return HealState.HEAL_MENU_OPEN

    coords, _ = find_on_screen(get_template(CONFIRM_BUTTON_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if coords:
        return HealState.CONFIRM_BUTTON_REQUIRED

    coords, _ = find_on_screen(get_template(MAIL_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if coords:
        return HealState.MAIL

    coords, _ = find_on_screen(get_template(HEAL_TOWN_IMG), screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
    if coords:
        return HealState.HEAL_ICON

    coords, _ = find_on_screen(get_template(HELP_HANDS_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if coords:
        return HealState.HELP_HANDS

    coords, _ = find_on_screen(get_template(HEAL_HELP_HANDS_IMG), screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
    if coords:
        return HealState.HEAL_HELP

    coords, _ = find_on_screen(get_template(HEAL_WAIT_IMG), screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
    if coords:
        return HealState.HEAL_WAIT

    coords, _ = find_on_screen(get_template(BOOK_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if coords:
        return HealState.BOOK

    coords, _ = find_on_screen(get_template(ADVENTURE_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if coords:
        return HealState.ADVENTURE

    coords, _ = find_on_screen(get_template(ADVENTURE_GET_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if coords:
        return HealState.ADVENTURE_GET

    coords, _ = find_on_screen(get_template(WILD_EARTH_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if coords:
        return HealState.MAIN_SCREEN

    coords, _ = find_on_screen(get_template(VILLAGE_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if coords:
        return HealState.UNKNOWN

    return HealState.UNKNOWN


# ==========================================
# ОБРАБОТКА СОСТОЯНИЙ ЛЕЧЕНИЯ
# ==========================================
def process_heal(screen_cv, region, last_heal_state, window=None):
    """
    Обработать текущее состояние лечения.
    Возвращает: новое состояние (HealState или None)
    """
    logger.debug(f"[HEAL] Состояние до обработки: {last_heal_state}")
    current_state = determine_heal_state(screen_cv, region)
    logger.debug(f"[HEAL] определили Состояние: {current_state.value}")

    # Обработка состояний приключения через отдельный модуль
    if current_state in (HealState.ADVENTURE, HealState.ADVENTURE_GET, HealState.ADVENTURE_CONFIRM):
        return process_adventure_state(screen_cv, region, last_heal_state, window, current_state)

    # Обработка каждого состояния
    if current_state == HealState.RECONNECT_POPUP:
        handle_reconnect(screen_cv, region)
        return None

    if current_state == HealState.RECONNECT_REPEAT_POPUP:
        handle_reconnect_repeat(screen_cv, region)
        return None

    if current_state == HealState.BOOK:
        find_and_click(BOOK_IMG, screen_cv, region, CONFIDENCE_THRESHOLD)
        return HealState.MAIN_SCREEN

    if current_state == HealState.MAIL:
        find_and_click(MAIL_IMG, screen_cv, region, CONFIDENCE_THRESHOLD)
        return None

    if current_state == HealState.HEAL_ICON:
        found, _ = find_and_click(HEAL_TOWN_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if found:
            # Ждём открытия меню лечения и сразу ищем кнопки лечения
            time.sleep(0.3)
            # window, region_new = get_window_region()
            # if region_new:
            screen_new = take_screenshot(window, region)
            # Пытаемся нажать бесплатное лечение (порог 0.60 — кнопка может быть частично перекрыта)
            found_free, _ = find_and_click(HEAL_FREE_BUTTON_IMG, screen_new, region, 0.60)
            if found_free:
                logger.info("[HEAL] ✓ Бесплатное лечение нажато!")
                return HealState.MAIN_SCREEN
            # Пытаемся нажать обычное лечение
            found_heal, _ = find_and_click(HEAL_BUTTON_IMG, screen_new, region, CONFIDENCE_THRESHOLD)
            if found_heal:
                logger.info("[HEAL] ✓ Обычное лечение нажато!")
                return HealState.MAIN_SCREEN
            logger.debug("[HEAL] Меню лечения открыто, но кнопки не найдены.")
            return HealState.HEAL_MENU_OPEN
        return None

    if current_state == HealState.HEAL_HELP:
        found, _ = find_and_click(HEAL_HELP_HANDS_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if found:
            return None
        return None

    if current_state == HealState.HEAL_ACTIVE:
        found, _ = find_and_click(HEAL_HELP_HANDS_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if found:
            return None
        return HealState.HEAL_ACTIVE

    if current_state == HealState.HEAL_WAIT:
        logger.info("[HEAL] Лечение в процессе. Ожидаем завершения.")
        return HealState.HEAL_WAIT

    if current_state == HealState.HEAL_MENU_OPEN:
        # Попытка найти и нажать кнопку бесплатного лечения, если доступна
        found, _ = find_and_click(HEAL_FREE_BUTTON_IMG, screen_cv, region, CONFIDENCE_THRESHOLD)
        if found:
            logger.info("[HEAL] ✓ Бесплатное лечение нажато!")
            return HealState.MAIN_SCREEN
        # Если бесплатное лечение недоступно, используем обычное лечение
        found, _ = find_and_click(HEAL_BUTTON_IMG, screen_cv, region, CONFIDENCE_THRESHOLD)
        if found:
            logger.info("[HEAL] ✓ Обычное лечение нажато!")
            return HealState.MAIN_SCREEN
        # Если ни одна кнопка не найдена — закрыва меню
        logger.debug("[HEAL] Меню лечения открыто, но кнопки не найдены. Закрываем.")
        find_and_click(BACK_IMG, screen_cv, region)
        return HealState.UNKNOWN

    if current_state == HealState.FAST_USE_POPUP:
        found, _ = find_and_click(CLOSE_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if found:
            return None
        return None

    if current_state == HealState.HELP_HANDS:
        found, _ = find_and_click(HELP_HANDS_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if found:
            return None
        return None

    if current_state == HealState.UNKNOWN:
        return HealState.UNKNOWN

    return HealState.UNKNOWN