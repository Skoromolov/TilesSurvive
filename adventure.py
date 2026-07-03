# ==========================================
# ЛОГИКА ПРИКЛЮЧЕНИЙ (Adventure)
# ==========================================

from config import *
from utils import *
from logger import logger  # Импортируем логгер

# Счётчик попыток сбора приключения (защита от зацикливания)
_adventure_get_attempts = 0

def process_adventure_state(screen_cv, region, last_adventure_state, window, current_state):
    """
    Обработать одно состояние приключения.
    Возвращает: следующее состояние (AdventureState или None)
    """
    global _adventure_get_attempts

    if current_state == AdventureState.ADVENTURE:
        logger.info("[HEAL] Нажимаем adventure.png для входа в приключения.")
        _adventure_get_attempts = 0
        find_and_click(ADVENTURE_IMG, screen_cv, region, CONFIDENCE_THRESHOLD)
        if window is None:
            return None
        time.sleep(1.0)
        screen_after = take_screenshot(window, region)
        # Проверяем, что открылась страница приключений
        page_coords, _ = find_on_screen(get_template(ADVENTURE_PAGE_IMG), screen_after, region, CONFIDENCE_THRESHOLD)
        if page_coords:
            logger.info("[HEAL] Открылась страница приключений.")
            return AdventureState.ADVENTURE_PAGE
        else:
            logger.warning("[HEAL] Не удалось найти adventure_page.png после нажатия adventure.png")
            # Попытка вернуться назад
            find_and_click(BACK_IMG, screen_after, region)
            return AdventureState.UNKNOWN

    if current_state == AdventureState.ADVENTURE_PAGE:
        logger.info("[HEAL] На странице приключений, ищем get.png для сбора.")
        find_and_click(ADVENTURE_GET_IMG, screen_cv, region, CONFIDENCE_THRESHOLD)
        if window is None:
            return None
        time.sleep(1)
        screen_after = take_screenshot(window, region)
        # Проверяем, что появился попап с багажем
        popup_coords, _ = find_on_screen(get_template(BAGGAGE_POPUP_IMG), screen_after, region, CONFIDENCE_THRESHOLD)
        if popup_coords:
            logger.info("[HEAL] Появился попап багажа.")
            return AdventureState.BAGGAGE_POPUP
        else:
            logger.warning("[HEAL] Не удалось найти baggage_popup.png после нажатия get.png")
            # Возможно, награда уже собрана или что-то пошло не так
            # Попробуем еще раз нажать get или вернемся назад
            find_and_click(BACK_IMG, screen_after, region)
            return AdventureState.UNKNOWN

    if current_state == AdventureState.BAGGAGE_POPUP:
        logger.info("[HEAL] На поппапе багажа, нажимаем get.png для сбора награды.")
        _adventure_get_attempts += 1
        if _adventure_get_attempts > 5:
            logger.warning("[HEAL] Слишком много попыток сбора приключения. Выходим.")
            _adventure_get_attempts = 0
            find_and_click(BACK_IMG, screen_cv, region)
            return AdventureState.UNKNOWN
        find_and_click(ADVENTURE_GET_IMG, screen_cv, region, CONFIDENCE_THRESHOLD)
        if window is None:
            return None
        time.sleep(1)
        screen_after = take_screenshot(window, region)
        # После сбора награды проверяем, есть ли еще get.png (значит есть еще награды)
        get_coords, _ = find_on_screen(get_template(ADVENTURE_GET_IMG), screen_after, region, CONFIDENCE_THRESHOLD)
        if get_coords:
            logger.info("[HEAL] Еще есть награды, продолжаем сбор.")
            return AdventureState.BAGGAGE_POPUP  # Остаемся в том же состоянии для следующего сбора
        # Наград больше нет или нужно подтверждение - проверяем подтверждение
        confirm_candidates = [
            (CONFIRM_BUTTON_IMG, CONFIDENCE_THRESHOLD),
            (GOLD_CONFIRM_IMG, CONFIDENCE_THRESHOLD),
            (RAID_OK_IMG, CONFIDENCE_THRESHOLD),
            (CONFIRM_BUTTON_IMG, 0.60),
            (GOLD_CONFIRM_IMG, 0.60),
        ]
        confirm_coords = None
        confirm_path = None
        for img_path, thresh in confirm_candidates:
            confirm_coords, _ = find_on_screen(get_template(img_path), screen_after, region, thresh)
            if confirm_coords:
                confirm_path = img_path
                break
        if confirm_coords:
            logger.info(f"[HEAL] Найдено подтверждение сбора: {confirm_path}")
            _adventure_get_attempts = 0
            return AdventureState.ADVENTURE_CONFIRM
        # Если ничего не найдено, считаем процесс завершенным и выходим
        _adventure_get_attempts = 0
        find_and_click(BACK_IMG, screen_after, region)
        return AdventureState.UNKNOWN

    if current_state == AdventureState.ADVENTURE_CONFIRM:
        logger.info("[HEAL] Подтверждаем награду приключения.")
        _adventure_get_attempts = 0
        # Пробуем любую известную кнопку подтверждения
        confirm_clicked = False
        for img_path in (CONFIRM_BUTTON_IMG, GOLD_CONFIRM_IMG, RAID_OK_IMG):
            confirm_clicked, _ = find_and_click(img_path, screen_cv, region, 0.60)
            if confirm_clicked:
                logger.info(f"[HEAL] Нажато подтверждение: {img_path}")
                break
        if window is None:
            return None
        time.sleep(1)
        screen_after = take_screenshot(window, region)
        # После подтверждения проверяем, есть ли еще get.png
        get_coords, _ = find_on_screen(get_template(ADVENTURE_GET_IMG), screen_after, region, CONFIDENCE_THRESHOLD)
        if get_coords:
            return AdventureState.BAGGAGE_POPUP
        find_and_click(BACK_IMG, screen_after, region)
        return AdventureState.UNKNOWN

    # Если не одно из приключенческих состояний, возвращаем None (не меняем состояние)
    return None


def determine_adventure_state(screen_cv, region):
    """
    Determine if the current screen shows an adventure-related state.
    Returns: AdventureState.ADVENTURE, AdventureState.ADVENTURE_PAGE, AdventureState.BAGGAGE_POPUP, AdventureState.ADVENTURE_GET, AdventureState.ADVENTURE_CONFIRM, or AdventureState.UNKNOWN
    """
    # Check for adventure button (enter adventure)
    coords, _ = find_on_screen(get_template(ADVENTURE_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if coords:
        return AdventureState.ADVENTURE
    # Check for adventure page (after clicking adventure)
    coords, _ = find_on_screen(get_template(ADVENTURE_PAGE_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if coords:
        return AdventureState.ADVENTURE_PAGE
    # Check for baggage popup (after clicking get)
    coords, _ = find_on_screen(get_template(BAGGAGE_POPUP_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if coords:
        return AdventureState.BAGGAGE_POPUP
    # Check for get button (collect reward) - on adventure page or baggage popup
    coords, _ = find_on_screen(get_template(ADVENTURE_GET_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if coords:
        return AdventureState.ADVENTURE_GET
    # Check for confirm button (after clicking get) - use lower threshold as in adventure.py
    coords, _ = find_on_screen(get_template(CONFIRM_BUTTON_IMG), screen_cv, region, threshold=0.60)
    if coords:
        return AdventureState.ADVENTURE_CONFIRM
    # Also check gold confirm and raid ok as possible confirm buttons
    coords, _ = find_on_screen(get_template(GOLD_CONFIRM_IMG), screen_cv, region, threshold=0.60)
    if coords:
        return AdventureState.ADVENTURE_CONFIRM
    coords, _ = find_on_screen(get_template(RAID_OK_IMG), screen_cv, region, threshold=0.60)
    if coords:
        return AdventureState.ADVENTURE_CONFIRM
    return AdventureState.UNKNOWN


def reset_adventure_context():
    """Reset the adventure module's internal state."""
    global _adventure_get_attempts
    _adventure_get_attempts = 0