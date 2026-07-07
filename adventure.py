# ==========================================
# ЛОГИКА ПРИКЛЮЧЕНИЙ (Adventure)
# ==========================================

from config import *
from utils import *
from logger import logger  # Импортируем логгер

# Счётчик попыток сбора приключения (защита от зацикливания)
_adventure_get_attempts = 0

def reset_adventure_context():
    """Reset the adventure module's internal state."""
    global _adventure_get_attempts
    _adventure_get_attempts = 0

def process_adventure_state(screen_cv, region, last_adventure_state, window, current_state):
    """
    Обработать одно состояние приключения.
    Возвращает: следующее состояние (AdventureState или None)
    """
    global _adventure_get_attempts

    if current_state == AdventureState.ADVENTURE:
        logger.info("[ADVENTURE] Нажимаем adventure.png для входа в приключения.")
        _adventure_get_attempts = 0
        find_and_click(ADVENTURE_IMG, screen_cv, region, CONFIDENCE_MEDIUM_THRESHOLD)
        if window is None:
            return None
        time.sleep(1.0)
        screen_after = take_screenshot(window, region)
        # Проверяем, что открылась страница приключений
        page_coords, _ = find_on_screen(get_template(ADVENTURE_PAGE_IMG), screen_after, region, CONFIDENCE_MEDIUM_THRESHOLD)
        if page_coords:
            logger.info("[ADVENTURE] Открылась страница приключений.")
            return AdventureState.ADVENTURE_PAGE
        else:
            logger.warning("[ADVENTURE] Не удалось найти adventure_page.png после нажатия adventure.png")
            # Попытка вернуться назад
            find_and_click(BACK_IMG, screen_after, region)
            return AdventureState.UNKNOWN

    if current_state == AdventureState.ADVENTURE_PAGE:
        logger.info("[ADVENTURE] На странице приключений, ищем get.png для сбора.")
        find_and_click(ADVENTURE_GET_IMG, screen_cv, region, CONFIDENCE_MEDIUM_THRESHOLD)
        if window is None:
            return None
        time.sleep(1)
        screen_after = take_screenshot(window, region)
        # Проверяем, что появился попап с багажем
        popup_coords, _ = find_on_screen(get_template(ADVENTURE_BAGGAGE_POPUP_IMG), screen_after, region, CONFIDENCE_MEDIUM_THRESHOLD)
        if popup_coords:
            logger.info("[ADVENTURE] Появился попап багажа.")
            return AdventureState.BAGGAGE_POPUP
        else:
            logger.warning("[ADVENTURE] Не удалось найти baggage_popup.png после нажатия get.png")
            # Возможно, награда уже собрана или что-то пошло не так
            # Попробуем еще раз нажать get или вернемся назад
            find_and_click(BACK_IMG, screen_after, region)
            return AdventureState.UNKNOWN

    if current_state == AdventureState.BAGGAGE_POPUP:
        logger.info("[ADVENTURE] На попапе багажа, нажимаем get_big_button.png для сбора награды.")
        _adventure_get_attempts += 1
        if _adventure_get_attempts > 5:
            logger.warning("[ADVENTURE] Слишком много попыток сбора приключения. Выходим.")
            _adventure_get_attempts = 0
            ensure_exit_to_main_screen(window, region)
            return AdventureState.UNKNOWN

        screen_cv = take_screenshot(window, region)
        find_and_click(ADVENTURE_GET_BIG_BUTTON_IMG, screen_cv, region, CONFIDENCE_MEDIUM_THRESHOLD)

        if window is None:
            return None
        time.sleep(1)
        screen_after = take_screenshot(window, region)

        # После сбора награды проверяем, есть ли еще get_big_button.png
        get_coords, _ = find_on_screen(get_template(ADVENTURE_GET_BIG_BUTTON_IMG), screen_after, region, CONFIDENCE_MEDIUM_THRESHOLD)
        if get_coords:
            logger.info("[ADVENTURE] Еще есть награды, продолжаем сбор.")
            return AdventureState.BAGGAGE_POPUP

        # Наград больше нет — выходим в поселение
        logger.info("[ADVENTURE] Сбор наград завершён. Выходим в поселение.")
        _adventure_get_attempts = 0
        ensure_exit_to_main_screen(window, region)
        return AdventureState.UNKNOWN

    if current_state == AdventureState.ADVENTURE_CONFIRM:
        logger.info("[ADVENTURE] Подтверждаем награду приключения.")
        _adventure_get_attempts = 0
        find_and_click(ADVENTURE_GET_BIG_BUTTON_IMG, screen_cv, region, CONFIDENCE_MEDIUM_THRESHOLD)
        if window is None:
            return None
        time.sleep(1)
        screen_after = take_screenshot(window, region)
        # После подтверждения проверяем, есть ли еще get_big_button.png
        get_coords, _ = find_on_screen(get_template(ADVENTURE_GET_BIG_BUTTON_IMG), screen_after, region, CONFIDENCE_MEDIUM_THRESHOLD)
        if get_coords:
            return AdventureState.BAGGAGE_POPUP
        # Выходим в поселение
        logger.info("[ADVENTURE] Сбор наград завершён. Выходим в поселение.")
        ensure_exit_to_main_screen(window, region)
        return AdventureState.UNKNOWN

    # Если не одно из приключенческих состояний, возвращаем None (не меняем состояние)
    return None


def determine_adventure_state(screen_cv, region):
    """
    Determine if the current screen shows an adventure-related state.
    Returns: AdventureState.ADVENTURE, AdventureState.ADVENTURE_PAGE, AdventureState.BAGGAGE_POPUP, AdventureState.ADVENTURE_GET, AdventureState.ADVENTURE_CONFIRM, or AdventureState.UNKNOWN
    """
    # Check for adventure button (enter adventure)
    # confidence on main screen is ~0.73, below CONFIDENCE_MEDIUM_THRESHOLD (0.80)
    coords, _ = find_on_screen(get_template(ADVENTURE_IMG), screen_cv, region, threshold=0.65)
    if coords:
        return AdventureState.ADVENTURE
    # Check for adventure page (after clicking adventure)
    coords, _ = find_on_screen(get_template(ADVENTURE_PAGE_IMG), screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
    if coords:
        return AdventureState.ADVENTURE_PAGE
    # Check for baggage popup (after clicking get)
    coords, _ = find_on_screen(get_template(ADVENTURE_BAGGAGE_POPUP_IMG), screen_cv, region, threshold=CONFIDENCE_MEDIUM_THRESHOLD)
    if coords:
        return AdventureState.BAGGAGE_POPUP
    # Check for big get button
    coords, _ = find_on_screen(get_template(ADVENTURE_GET_BIG_BUTTON_IMG), screen_cv, region, threshold=0.60)
    if coords:
        return AdventureState.ADVENTURE_CONFIRM

    return AdventureState.UNKNOWN