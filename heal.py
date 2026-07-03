# ==========================================
# ЛОГИКА ЛЕЧЕНИЯ
# ==========================================

from config import *
from utils import *
from logger import logger  # Импортируем логгер


# ==========================================
# ОПРЕДЕЛЕНИЕ СОСТОЯНИЯ ЛЕЧЕНИЯ
# ==========================================
def determine_heal_state(screen_cv, region):
    """
    Определить текущее состояние лечения.
    Возвращает: HealState
    """
    # Сначала проверяем главный экран поселения — высший приоритет,
    # чтобы не уходить в UNKNOWN, когда мы уже дома.
    coords, wild_conf = find_on_screen(get_template(WILD_EARTH_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if coords:
        logger.debug(f"[determine_heal_state] WILD_EARTH_IMG найден (conf={wild_conf:.3f}) -> MAIN_SCREEN")
        return HealState.MAIN_SCREEN

    coords, village_conf = find_on_screen(get_template(VILLAGE_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if coords:
        logger.debug(f"[determine_heal_state] VILLAGE_IMG найден (conf={village_conf:.3f}) -> MAIN_SCREEN")
        return HealState.MAIN_SCREEN

    coords, _ = find_on_screen(get_template(AMBULANCE_ON_MAP_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if coords:
        return HealState.HEAL_MENU_OPEN

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

    coords, heal_town_conf = find_on_screen(get_template(HEAL_TOWN_IMG), screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
    if coords:
        logger.debug(f"[determine_heal_state] HEAL_TOWN_IMG найден (conf={heal_town_conf:.3f}) -> HEAL_ICON")
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

    logger.debug("[determine_heal_state] Ничего не найдено -> UNKNOWN")
    return HealState.UNKNOWN


# ==========================================
# ОБРАБОТКА СОСТОЯНИЙ ЛЕЧЕНИЯ
# ==========================================
# Счётчик неудачных попыток найти кнопки лечения в открытом меню
_heal_menu_open_attempts = 0
_MAX_HEAL_MENU_ATTEMPTS = 5


def reset_heal_context():
    """Сбросить внутреннее состояние модуля лечения."""
    global _heal_menu_open_attempts
    _heal_menu_open_attempts = 0


def process_heal(screen_cv, region, last_heal_state, window=None):
    """
    Обработать текущее состояние лечения.
    Возвращает: новое состояние (HealState или None)
    """
    global _heal_menu_open_attempts

    logger.debug(f"[HEAL] Состояние до обработки: {last_heal_state}")
    current_state = determine_heal_state(screen_cv, region)
    logger.debug(f"[HEAL] определили Состояние: {current_state.value}")

    if current_state == HealState.MAIN_SCREEN:
        _heal_menu_open_attempts = 0
        return HealState.MAIN_SCREEN

    if current_state == HealState.BOOK:
        _heal_menu_open_attempts = 0
        find_and_click(BOOK_IMG, screen_cv, region, CONFIDENCE_THRESHOLD)
        return HealState.MAIN_SCREEN

    if current_state == HealState.MAIL:
        _heal_menu_open_attempts = 0
        find_and_click(MAIL_IMG, screen_cv, region, CONFIDENCE_THRESHOLD)
        logger.info("[HEAL] ✓ MAIL нажато!")
        time.sleep(1)
        screen_cv = take_screenshot(window, region)
        find_and_click(CONFIRM_BUTTON_IMG, screen_cv, region, CONFIDENCE_THRESHOLD)
        return None

    if current_state == HealState.HEAL_ICON:
        _heal_menu_open_attempts = 0
        found, _ = find_and_click(HEAL_TOWN_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if found:
            # Ждём открытия меню лечения — анимация может занимать до 1.5 сек
            time.sleep(1.5)
            if window is None:
                return HealState.HEAL_MENU_OPEN
            screen_new = take_screenshot(window, region)
            # Ищем кнопки с пониженным порогом, т.к. кнопка может быть частично перекрыта
            found_free, _ = find_and_click(HEAL_FREE_BUTTON_IMG, screen_new, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
            if found_free:
                logger.info("[HEAL] ✓ Бесплатное лечение нажато!")
                return HealState.MAIN_SCREEN
            found_heal, _ = find_and_click(HEAL_BUTTON_IMG, screen_new, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
            if found_heal:
                logger.info("[HEAL] ✓ Обычное лечение нажато!")
                return HealState.MAIN_SCREEN
            logger.info("[HEAL] Меню лечения открыто, кнопки пока не найдены — остаёмся в меню.")
            return HealState.HEAL_MENU_OPEN
        return None

    if current_state == HealState.HEAL_HELP:
        _heal_menu_open_attempts = 0
        found, _ = find_and_click(HEAL_HELP_HANDS_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if found:
            return None
        return None

    if current_state == HealState.HEAL_ACTIVE:
        _heal_menu_open_attempts = 0
        found, _ = find_and_click(HEAL_HELP_HANDS_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if found:
            return None
        return HealState.HEAL_ACTIVE

    if current_state == HealState.HEAL_WAIT:
        _heal_menu_open_attempts = 0
        logger.info("[HEAL] Лечение в процессе. Ожидаем завершения.")
        return HealState.HEAL_WAIT

    if current_state == HealState.HEAL_MENU_OPEN:
        _heal_menu_open_attempts += 1
        logger.info(f"[HEAL] Меню лечения открыто (попытка {_heal_menu_open_attempts}/{_MAX_HEAL_MENU_ATTEMPTS}).")

        # Пытаемся найти и нажать кнопку бесплатного лечения, если доступна
        found, _ = find_and_click(HEAL_FREE_BUTTON_IMG, screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
        if found:
            logger.info("[HEAL] ✓ Бесплатное лечение нажато!")
            _heal_menu_open_attempts = 0
            return HealState.MAIN_SCREEN
        # Если бесплатное лечение недоступно, используем обычное лечение
        found, _ = find_and_click(HEAL_BUTTON_IMG, screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
        if found:
            logger.info("[HEAL] ✓ Обычное лечение нажато!")
            _heal_menu_open_attempts = 0
            return HealState.MAIN_SCREEN

        # Если кнопки не найдены, но попыток ещё мало — даём анимации/загрузке время
        if _heal_menu_open_attempts < _MAX_HEAL_MENU_ATTEMPTS:
            logger.info("[HEAL] Кнопки лечения не найдены, подождём следующую итерацию.")
            time.sleep(0.5)
            return HealState.HEAL_MENU_OPEN

        # Если кнопки так и не появились — закрываем меню
        logger.info("[HEAL] Кнопки лечения не появились после нескольких попыток. Закрываем меню.")
        find_and_click(BACK_IMG, screen_cv, region)
        _heal_menu_open_attempts = 0
        return HealState.UNKNOWN

    if current_state == HealState.FAST_USE_POPUP:
        _heal_menu_open_attempts = 0
        found, _ = find_and_click(CLOSE_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if found:
            return None
        return None

    if current_state == HealState.HELP_HANDS:
        _heal_menu_open_attempts = 0
        found, _ = find_and_click(HELP_HANDS_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if found:
            return None
        return None

    if current_state == HealState.CONFIRM_BUTTON_REQUIRED:
        _heal_menu_open_attempts = 0
        found, _ = find_and_click(CONFIRM_BUTTON_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if found:
            logger.info("[HEAL] ✓ Кнопка подтверждения нажата.")
            return HealState.MAIN_SCREEN
        return HealState.CONFIRM_BUTTON_REQUIRED

    if current_state == HealState.UNKNOWN:
        _heal_menu_open_attempts = 0
        return HealState.UNKNOWN

    # Любое другое состояние — сбрасываем счётчик меню
    _heal_menu_open_attempts = 0
    return HealState.UNKNOWN


def determine_fast_heal_from_map_state(screen_cv, region):
    """Определить текущее состояние быстрого лечения с карты мира."""
    # Проверка в порядке приоритета
    # 1. Reconnect
    # coords, _ = find_on_screen(get_template(RECONNECT_IMG), screen_cv, region)
    # if coords:
    #     return HealState.RECONNECT_POPUP
    #
    # coords, _ = find_on_screen(get_template(RECONNECT_REPEAT_IMG), screen_cv, region)
    # if coords:
    #     return HealState.RECONNECT_REPEAT_POPUP

    # 2. HEAL_HELP_WITH_TIME_IMG
    coords, _ = find_on_screen(get_template(HEAL_HELP_WITH_TIME_IMG), screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
    if coords:
        return HealState.HEAL_HELP_WITH_TIME

    # 3. HEAL_BUTTON_IMG / HEAL_FREE_BUTTON_IMG -> HEAL_MENU_OPEN
    coords, _ = find_on_screen(get_template(HEAL_BUTTON_IMG), screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
    if coords:
        return HealState.HEAL_MENU_OPEN
    coords, _ = find_on_screen(get_template(HEAL_FREE_BUTTON_IMG), screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
    if coords:
        return HealState.HEAL_MENU_OPEN

    # 4. AMBULANCE_ON_MAP_IMG / AMBULANCE_ON_MAP_WIDE_IMG -> AMBULANCE_ON_MAP
    coords, _ = find_on_screen(get_template(AMBULANCE_ON_MAP_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if coords:
        return HealState.AMBULANCE_ON_MAP
    coords, _ = find_on_screen(get_template(AMBULANCE_ON_MAP_WIDE_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if coords:
        return HealState.AMBULANCE_ON_MAP

    # 5. HELP_HANDS_IMG -> HELP_HANDS
    coords, _ = find_on_screen(get_template(HELP_HANDS_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if coords:
        return HealState.HELP_HANDS

    # 6. WILD_EARTH_IMG -> MAIN_SCREEN
    coords, _ = find_on_screen(get_template(WILD_EARTH_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if coords:
        return HealState.MAIN_SCREEN

    # 7. Иначе -> UNKNOWN
    return HealState.UNKNOWN


def process_fast_heal_from_map(screen_cv, region, last_heal_state):
    """Обработать текущее состояние быстрого лечения с карты мира.
    Возвращает: следующее состояние (HealState или None)
    """
    logger.debug(f"[FAST HEAL FROM MAP] Состояние до обработки: {last_heal_state}")
    current_state = determine_fast_heal_from_map_state(screen_cv, region)
    logger.debug(f"[FAST HEAL FROM MAP] определили Состояние: {current_state.value}")

    # Обработка переподключения (как в process_heal)
    if current_state == HealState.RECONNECT_POPUP:
        handle_reconnect(screen_cv, region)
        return None
    if current_state == HealState.RECONNECT_REPEAT_POPUP:
        handle_reconnect_repeat(screen_cv, region)
        return None

    # Обработка состояний
    if current_state == HealState.HEAL_HELP_WITH_TIME:
        found, _ = find_and_click(HEAL_HELP_WITH_TIME_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if found:
            return HealState.HELP_HANDS
        return HealState.HEAL_HELP_WITH_TIME  # остаемся в том же состоянии, если не нашли

    if current_state == HealState.HEAL_MENU_OPEN:
        # Пытаемся найти и нажать кнопку бесплатного лечения, если доступна
        found, _ = find_and_click(HEAL_FREE_BUTTON_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if found:
            logger.info("[HEAL] ✓ Бесплатное лечение нажато!")
            return HealState.MAIN_SCREEN
        # Пытаемся нажать обычное лечение
        found, _ = find_and_click(HEAL_BUTTON_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if found:
            logger.info("[HEAL] ✓ Обычное лечение нажато!")
            return HealState.MAIN_SCREEN
        # Если ни одна кнопка не найдена — закрыва меню
        logger.debug("[HEAL] Меню лечения открыто, но кнопки не найдены. Закрываем.")
        find_and_click(BACK_IMG, screen_cv, region)
        return HealState.UNKNOWN

    if current_state == HealState.AMBULANCE_ON_MAP:
        # Пытаемся нажать ambulance.png или ambulance_bottle_wide.png
        found, _ = find_and_click(AMBULANCE_ON_MAP_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if found:
            return HealState.HEAL_HELP_WITH_TIME
        found, _ = find_and_click(AMBULANCE_ON_MAP_WIDE_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if found:
            return HealState.HEAL_HELP_WITH_TIME
        return HealState.AMBULANCE_ON_MAP  # остаемся, если не нашли

    if current_state == HealState.HELP_HANDS:
        found, _ = find_and_click(HELP_HANDS_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if found:
            return HealState.AMBULANCE_ON_MAP
        return HealState.HELP_HANDS

    if current_state == HealState.MAIN_SCREEN:
        # Просто ждем ambulance
        return HealState.MAIN_SCREEN

    if current_state == HealState.UNKNOWN:
        return HealState.UNKNOWN

    # Для любого другого состояния (например, HEAL_ICON, HEAL_ACTIVE и т.д.) возвращаем UNKNOWN
    return HealState.UNKNOWN


def check_and_click_help_button(screen_cv, region):
    """Проверить и кликнуть кнопку помощи союзу (help_hands.png)."""
    found, _ = find_and_click(HELP_HANDS_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if found:
        logger.info("[HELP] Нажата кнопка помощи союзу")