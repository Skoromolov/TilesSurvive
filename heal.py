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

    coords, _ = find_on_screen(get_template(HEAL_BUTTON_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
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
        found, _ = find_and_click(HEAL_TOWN_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if found:
            return HealState.HEAL_MENU_OPEN
        return None

    if current_state == HealState.HEAL_HELP:
        found, _ = find_and_click(HEAL_HELP_HANDS_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if found:
            return None

    if current_state == HealState.HEAL_ACTIVE:
        found, _ = find_and_click(HEAL_HELP_HANDS_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if found:
            return None
        return HealState.HEAL_ACTIVE

    if current_state == HealState.FAST_USE_POPUP:
        found, _ = find_and_click(CLOSE_IMG, screen_cv, region)
        if found:
            return HealState.UNKNOWN

    if current_state == HealState.HEAL_MENU_OPEN:
        # Попытка найти и нажать кнопку бесплатного лечения, если доступна
        found, _ = find_and_click(HEAL_FREE_BUTTON_IMG, screen_cv, region)
        if found:
            return HealState.MAIN_SCREEN
        # Если бесплатное лечение недоступно, используем обычное лечение
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

    # Защита от перехода в режим редактирования поселения
    # Если мы не нашли ни одной из ключевых иконок игры, вероятно мы в режиме редактирования
    # Нужно кликнуть по безопасной области (верхней части экрана) чтобы выйти из этого режима
    key_icons_found = False
    # Проверяем наличие ключевых иконок, которые должны быть видимы в нормальном режиме игры
    key_templates = [
        WILD_EARTH_IMG,    # Дикие земли - указывает на главный экран
        EVENTS_IMG,        # События
        HELP_HANDS_IMG,    # Помощь союзу
        SOUZ_IMG,          # Союз (альтернативная иконка)
        HEAL_TOWN_IMG,     # Иконка лечения
        MAIL_IMG,          # Почта
    ]
    
    for template_path in key_templates:
        template = get_template(template_path)
        if template is not None:
            coords, conf = find_on_screen(template, screen_cv, region, CONFIDENCE_THRESHOLD)
            if coords and conf >= CONFIDENCE_THRESHOLD:
                key_icons_found = True
                break
    
    if not key_icons_found:
        print("[HEAL] ⚠️ Не найдены ключевые иконки игры - возможен переход в режим редактирования поселения")
        print("[HEAL] Выполняем клик по верхней части экрана для выхода из режима редактирования")
        # Клик по верхней центральной части экрана (безопасная зона)
        click_x = region[0] + region[2] // 2  # Центр по X
        click_y = region[1] + int(region[3] * 0.15)  # 15% от высоты от верхней границы
        pyautogui.click(click_x, click_y)
        time.sleep(1)  # Небольшая пауза после клика
        return None

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
