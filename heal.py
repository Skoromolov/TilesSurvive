# ==========================================
# ЛОГИКА ЛЕЧЕНИЯ
# ==========================================

from config import *
from utils import *
from adventure import process_adventure_state

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
    print(f"[HEAL] Состояние до обработки: {last_heal_state}")
    current_state = determine_heal_state(screen_cv, region)
    # if current_state != last_heal_state:
    print(f"[HEAL] определили Состояние: {current_state.value}")

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
                print("[HEAL] ✓ Бесплатное лечение нажато!")
                return HealState.MAIN_SCREEN
            # Пытаемся нажать обычное лечение
            found_heal, _ = find_and_click(HEAL_BUTTON_IMG, screen_new, region, CONFIDENCE_THRESHOLD)
            if found_heal:
                print("[HEAL] ✓ Обычное лечение нажато!")
                return HealState.MAIN_SCREEN
            print("[HEAL] Меню лечения открыто, но кнопки не найдены.")
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
        print("[HEAL] Лечение в процессе. Ожидаем завершения.")
        return HealState.HEAL_WAIT

    if current_state == HealState.HEAL_MENU_OPEN:
        # Попытка найти и нажать кнопку бесплатного лечения, если доступна
        found, _ = find_and_click(HEAL_FREE_BUTTON_IMG, screen_cv, region, CONFIDENCE_THRESHOLD)
        if found:
            print("[HEAL] ✓ Бесплатное лечение нажато!")
            return HealState.MAIN_SCREEN
        # Если бесплатное лечение недоступно, используем обычное лечение
        found, _ = find_and_click(HEAL_BUTTON_IMG, screen_cv, region, CONFIDENCE_THRESHOLD)
        if found:
            print("[HEAL] ✓ Обычное лечение нажато!")
            return HealState.MAIN_SCREEN
        # Если ни одна кнопка не найдена — закрыва меню
        print("[HEAL] Меню лечения открыто, но кнопки не найдены. Закрываем.")
        find_and_click(BACK_IMG, screen_cv, region)
        return HealState.UNKNOWN

    if current_state == HealState.FAST_USE_POPUP:
        found, _ = find_and_click(CLOSE_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if found:
            return HealState.UNKNOWN
        return None

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
    return find_and_click(HELP_HANDS_IMG, screen_cv, region, CONFIDENCE_THRESHOLD)


# ==========================================
# БЫСТРОЕ ЛЕЧЕНИЕ С КАРТЫ МИРА
# ==========================================
def determine_fast_heal_from_map_state(screen_cv, region):
    """
    Определить состояние для быстрого лечения с карты мира.
    Приоритет: reconnect -> popup -> heal with time -> heal menu -> ambulance -> help -> main screen
    """
    coords, _ = find_on_screen(get_template(RECONNECT_IMG), screen_cv, region)
    if coords:
        return HealState.RECONNECT_POPUP

    coords, _ = find_on_screen(get_template(RECONNECT_REPEAT_IMG), screen_cv, region)
    if coords:
        return HealState.RECONNECT_REPEAT_POPUP

    coords, _ = find_on_screen(get_template(HEAL_HELP_WITH_TIME_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if coords:
        return HealState.HEAL_HELP_WITH_TIME

    coords, _ = find_on_screen(get_template(HEAL_BUTTON_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if coords:
        return HealState.HEAL_MENU_OPEN

    coords, _ = find_on_screen(get_template(HEAL_FREE_BUTTON_IMG), screen_cv, region, threshold=NAVIGATION_THRESHOLD)
    if coords:
        return HealState.HEAL_MENU_OPEN

    coords, _ = find_on_screen(get_template(AMBULANCE_ON_MAP_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if coords:
        return HealState.AMBULANCE_ON_MAP

    coords, _ = find_on_screen(get_template(AMBULANCE_ON_MAP_WIDE_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if coords:
        return HealState.AMBULANCE_ON_MAP

    coords, _ = find_on_screen(get_template(HELP_HANDS_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if coords:
        return HealState.HELP_HANDS

    coords, _ = find_on_screen(get_template(WILD_EARTH_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if coords:
        return HealState.MAIN_SCREEN

    return HealState.UNKNOWN


def process_fast_heal_from_map(screen_cv, region, last_heal_state):
    """
    Обработать один шаг быстрого лечения с карты мира.
    Цикл: ambulance -> heal_help_with_time -> help_hands -> ambulance
    """
    current_state = determine_fast_heal_from_map_state(screen_cv, region)

    if current_state != last_heal_state and current_state.value:
        print(f"[FAST_HEAL] Состояние: {current_state.value}")

    # Reconnect
    if current_state == HealState.RECONNECT_POPUP:
        handle_reconnect(screen_cv, region)
        return None
    if current_state == HealState.RECONNECT_REPEAT_POPUP:
        handle_reconnect_repeat(screen_cv, region)
        return None

    # Кнопка лечения с таймером (после клика по ambulance)
    if current_state == HealState.HEAL_HELP_WITH_TIME:
        found, _ = find_and_click(HEAL_HELP_WITH_TIME_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if found:
            print("[FAST_HEAL] ✓ Клик по 'лечить' с таймером")
            # После лечения обычно появляется кнопка помощи или возврат на карту
            return HealState.HELP_HANDS
        return None

    # Меню лечения (если сразу открылось без таймера)
    if current_state == HealState.HEAL_MENU_OPEN:
        found, _ = find_and_click(HEAL_FREE_BUTTON_IMG, screen_cv, region, CONFIDENCE_THRESHOLD)
        if found:
            return HealState.MAIN_SCREEN
        found, _ = find_and_click(HEAL_BUTTON_IMG, screen_cv, region, CONFIDENCE_THRESHOLD)
        if found:
            return HealState.MAIN_SCREEN
        return None

    # Иконка ambulance на карте мира
    if current_state == HealState.AMBULANCE_ON_MAP:
        # Пробуем обычную версию
        found, _ = find_and_click(AMBULANCE_ON_MAP_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if found:
            print("[FAST_HEAL] ✓ Клик по ambulance на карте мира")
            return HealState.HEAL_HELP_WITH_TIME
        # Пробуем wide версию если обычная не сработала
        found, _ = find_and_click(AMBULANCE_ON_MAP_WIDE_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if found:
            print("[FAST_HEAL] ✓ Клик по ambulance (wide) на карте мира")
            return HealState.HEAL_HELP_WITH_TIME
        return None

    # Кнопка помощи союзу
    if current_state == HealState.HELP_HANDS:
        found, _ = find_and_click(HELP_HANDS_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if found:
            print("[FAST_HEAL] ✓ Клик по кнопке помощи союзу")
            return HealState.AMBULANCE_ON_MAP
        return None

    # На главном экране карты мира — ждём появления ambulance
    if current_state == HealState.MAIN_SCREEN:
        # Ничего не делаем, просто ждём
        return HealState.MAIN_SCREEN

    # Неизвестное состояние — ничего не делаем, ждём
    # (возможно в окне госпиталя с открытым fast use popup)
    if current_state == HealState.UNKNOWN:
        return HealState.UNKNOWN

    return HealState.UNKNOWN