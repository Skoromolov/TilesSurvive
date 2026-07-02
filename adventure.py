# ==========================================
# ЛОГИКА ПРИКЛЮЧЕНИЙ (Adventure)
# ==========================================

from config import *
from utils import *
from logger import logger  # Импортируем логгер

# Счётчик попыток сбора приключения (защита от зацикливания)
_adventure_get_attempts = 0

def process_adventure_state(screen_cv, region, last_heal_state, window, current_state):
    """
    Обработать одно состояние приключения.
    Возвращает: следующее состояние (HealState или None)
    """
    global _adventure_get_attempts

    if current_state == HealState.ADVENTURE:
        logger.info("[HEAL] Нажимаем adventure.png для входа в приключения.")
        _adventure_get_attempts = 0
        find_and_click(ADVENTURE_IMG, screen_cv, region, CONFIDENCE_THRESHOLD)
        if window is None:
            return None
        time.sleep(1.0)
        screen_after = take_screenshot(window, region)
        get_coords, _ = find_on_screen(get_template(ADVENTURE_GET_IMG), screen_after, region, CONFIDENCE_THRESHOLD)
        if get_coords:
            return HealState.ADVENTURE_GET
        # Похоже, наград нет или экран не изменился — выходим
        find_and_click(BACK_IMG, screen_after, region)
        return HealState.UNKNOWN

    if current_state == HealState.ADVENTURE_GET:
        logger.info("[HEAL] Нажимаем get.png для сбора приключения.")
        _adventure_get_attempts += 1
        if _adventure_get_attempts > 5:
            logger.warning("[HEAL] Слишком много попыток сбора приключения. Выходим.")
            _adventure_get_attempts = 0
            find_and_click(BACK_IMG, screen_cv, region)
            return HealState.UNKNOWN
        find_and_click(ADVENTURE_GET_IMG, screen_cv, region, CONFIDENCE_THRESHOLD)
        if window is None:
            return None
        time.sleep(1)
        screen_after = take_screenshot(window, region)
        # Попап подтверждения может появиться с задержкой и выглядеть по-разному
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
            return HealState.ADVENTURE_CONFIRM
        # Если get.png всё ещё виден — ещё награды
        get_coords, _ = find_on_screen(get_template(ADVENTURE_GET_IMG), screen_after, region, CONFIDENCE_THRESHOLD)
        if get_coords:
            return HealState.ADVENTURE_GET
        # Наград больше — выходим
        _adventure_get_attempts = 0
        find_and_click(BACK_IMG, screen_after, region)
        return HealState.UNKNOWN

    if current_state == HealState.ADVENTURE_CONFIRM:
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
        # После подтверждения может снова появиться get.png (следующая награда)
        get_coords, _ = find_on_screen(get_template(ADVENTURE_GET_IMG), screen_after, region, CONFIDENCE_THRESHOLD)
        if get_coords:
            return HealState.ADVENTURE_GET
        find_and_click(BACK_IMG, screen_after, region)
        return HealState.UNKNOWN

    # Если не одно из приключенческих состояний, возвращаем None (не меняем состояние)
    return None