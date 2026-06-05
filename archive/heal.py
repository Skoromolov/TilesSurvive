import numpy as np
import cv2
import pyautogui
import time
import pygetwindow as gw
import win32gui
from enum import Enum
from datetime import datetime

# Константы изображений
HEAL_TOWN_IMG = 'heal_town.png'
HEAL_BUTTON_IMG = 'heal_button.png'
HEAL_HELP_IMG = 'heal_help.png'
HEAL_WAIT_IMG = 'heal_wait.png'
RECONNECT_IMG = 'reconnect.png'
WILD_EARTH_IMG = 'wild_earth.png'

CONFIDENCE_THRESHOLD = 0.8
LOG_SEARCH_DETAILS = True  # Включить детальное логирование поиска элементов

# Название окна BlueStacks (может отличаться, проверьте через диспетчер задач или вручную)
bluestacks_window_title = "BlueStacks App Player"


class UIState(Enum):
    """Состояния UI в цикле лечения."""
    UNKNOWN = "unknown"
    MAIN_SCREEN = "main_screen"  # Видна кнопка "Дикие земли" - главный экран
    HEAL_ICON_VISIBLE = "heal_icon_visible"  # Видна иконка шприца
    HEAL_MENU_OPEN = "heal_menu_open"  # Открыто меню лечения (видна кнопка "Лечить")
    HEAL_HELP_VISIBLE = "heal_help_visible"  # Видна иконка помощи (нужно нажать)
    HEAL_ACTIVE = "heal_active"  # Лечение активно (идёт таймер)
    RECONNECT_POPUP = "reconnect_popup"  # Окно переподключения


def get_window_region():
    """Получить координаты и размеры окна BlueStacks."""
    try:
        window = gw.getWindowsWithTitle(bluestacks_window_title)[0]
        if not window.isActive:
            window.activate()
        return window, (window.left, window.top, window.width, window.height)
    except IndexError:
        print("Окно BlueStacks не найдено. Проверьте название окна.")
        return None, None


def prepare_template(template_path):
    """Загрузить и подготовить шаблон для поиска."""
    template = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)
    if template is None:
        print(f"Не удалось загрузить изображение шаблона: {template_path}")
        return None

    if template.shape[2] == 4:
        template = cv2.cvtColor(template, cv2.COLOR_BGRA2BGR)
    if template.dtype != np.uint8:
        template = template.astype(np.uint8)

    return template


def find_template(template, screen_cv, region, threshold=CONFIDENCE_THRESHOLD, log_name=None):
    """
    Найти шаблон на скриншоте.
    Возвращает координаты центра найденного элемента или None.
    
    Args:
        template: Шаблон для поиска
        screen_cv: Скриншот в формате BGR
        region: Область поиска (x, y, width, height)
        threshold: Порог уверенности
        log_name: Имя элемента для логирования
    
    Returns:
        (coords, max_val): Кортеж координат и значения уверенности
    """
    res = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

    if max_val >= threshold:
        button_x = region[0] + max_loc[0] + template.shape[1] / 2
        button_y = region[1] + max_loc[1] + template.shape[0] / 2
        coords = (button_x, button_y)
        if LOG_SEARCH_DETAILS and log_name:
            print(f"[ПОИСК] ✓ {log_name}: найдено в ({coords[0]:.1f}, {coords[1]:.1f}), уверенность={max_val:.3f}")
        return coords, max_val
    else:
        if LOG_SEARCH_DETAILS and log_name:
            print(f"[ПОИСК] ✗ {log_name}: не найдено (макс. уверенность={max_val:.3f}, порог={threshold})")
        return None, max_val


def take_screenshot(region):
    """Сделать скриншот области и преобразовать в формат BGR."""
    screenshot = pyautogui.screenshot(region=region)
    screen_cv = np.array(screenshot)

    if screen_cv.dtype != np.uint8:
        screen_cv = screen_cv.astype(np.uint8)
    screen_cv = cv2.cvtColor(screen_cv, cv2.COLOR_RGB2BGR)

    return screen_cv


def find_and_click(template_path, timeout=5, region=None, click=True, log_name=None):
    """
    Найти шаблон на экране и кликнуть по нему.

    Args:
        template_path: Путь к изображению шаблона
        timeout: Время поиска в секундах
        region: Область поиска (x, y, width, height)
        click: Если True, кликнуть по найденному элементу
        log_name: Имя элемента для логирования

    Returns:
        (found: bool, coords: tuple или None): Результат поиска и координаты
    """
    if region is None:
        _, region = get_window_region()
        if region is None:
            return False, None

    template = prepare_template(template_path)
    if template is None:
        return False, None

    display_name = log_name or template_path
    start_time = time.time()
    last_confidence = 0.0

    while time.time() - start_time < timeout:
        win32gui.SetForegroundWindow(window._hWnd)
        screen_cv = take_screenshot(region)
        coords, max_val = find_template(template, screen_cv, region, log_name=display_name)
        last_confidence = max_val

        if coords:
            if click:
                pyautogui.click(coords[0], coords[1])
                print(f"[КЛИК] {display_name}: клик выполнен в ({coords[0]:.1f}, {coords[1]:.1f})")
            return True, coords

    # Если не нашли за timeout, возвращем последнюю уверенность
    if LOG_SEARCH_DETAILS:
        print(f"[ПРЕДУПРЕЖДЕНИЕ] {display_name}: не найдено за {timeout}с (последняя уверенность={last_confidence:.3f})")
    return False, None


def find_template_on_screen(template_path, timeout=5, region=None, log_name=None):
    """
    Найти шаблон на экране без клика.
    Возвращает координаты или None.
    
    Args:
        template_path: Путь к изображению шаблона
        timeout: Время поиска в секундах
        region: Область поиска
        log_name: Имя элемента для логирования

    Returns:
        (coords, confidence): Кортеж координат и уверенности, или (None, max_val)
    """
    if region is None:
        _, region = get_window_region()
        if region is None:
            return None, 0.0

    template = prepare_template(template_path)
    if template is None:
        return None, 0.0

    display_name = log_name or template_path
    start_time = time.time()
    last_max_val = 0.0

    while time.time() - start_time < timeout:
        screen_cv = take_screenshot(region)
        coords, max_val = find_template(template, screen_cv, region, log_name=display_name)
        last_max_val = max_val

        if coords:
            return coords, max_val
        time.sleep(0.5)

    return None, last_max_val


def handle_reconnect():
    """Обработать окно переподключения."""
    found, _ = find_and_click(RECONNECT_IMG, timeout=2, log_name="Переподключиться")
    if found:
        print("Нажата кнопка 'Переподключиться'")
        time.sleep(2)
        # Убедиться, что кнопка пропала
        coords, conf = find_template_on_screen(RECONNECT_IMG, timeout=3, log_name="Переподключиться (проверка)")
        if coords is None:
            print("Окно переподключения закрыто")
            return True
    return False


def is_wild_earth_visible():
    """Проверить, видна ли кнопка 'Дикие земли'."""
    coords, conf = find_template_on_screen(WILD_EARTH_IMG, timeout=2, log_name="Дикие земли")
    return coords is not None


def determine_ui_state(region, cached_state=None):
    """
    Определить текущее состояние UI.
    Проверяет только ключевые элементы в зависимости от кэшированного состояния.
    
    Args:
        region: Область поиска
        cached_state: Предыдущее состояние для оптимизации проверок
    
    Returns:
        UIState: Текущее состояние интерфейса
    """
    # Проверяем reconnect всегда - он приоритетнее всего
    coords, conf = find_template_on_screen(RECONNECT_IMG, timeout=1, region=region, log_name="Переподключиться")
    if coords:
        return UIState.RECONNECT_POPUP
    
    # Если были в состоянии ожидания лечения - проверяем только его завершение
    if cached_state == UIState.HEAL_ACTIVE:
        # Проверяем, появилась ли снова иконка шприца (лечение завершилось)
        coords, conf = find_template_on_screen(HEAL_TOWN_IMG, timeout=2, region=region, log_name="Иконка лечения (шприц)")
        if coords:
            return UIState.HEAL_ICON_VISIBLE
        # Иначе продолжаем ждать
        return UIState.HEAL_ACTIVE
    
    # Если была видна иконка помощи - проверяем, не пропала ли она
    if cached_state == UIState.HEAL_HELP_VISIBLE:
        coords, conf = find_template_on_screen(HEAL_HELP_IMG, timeout=1, region=region, log_name="Иконка помощи")
        if coords:
            return UIState.HEAL_HELP_VISIBLE
        # Иконка помощи пропала - перешли в режим ожидания
        return UIState.HEAL_ACTIVE
    
    # Полная проверка только если не знаем предыдущего состояния или были на главном экране
    # Проверяем иконку помощи (нужно нажать)
    coords, conf = find_template_on_screen(HEAL_HELP_IMG, timeout=1, region=region, log_name="Иконка помощи")
    if coords:
        return UIState.HEAL_HELP_VISIBLE
    
    # Проверяем таймер лечения (ожидание)
    coords, conf = find_template_on_screen(HEAL_WAIT_IMG, timeout=1, region=region, log_name="Таймер лечения")
    if coords:
        return UIState.HEAL_ACTIVE
    
    # Проверяем кнопку "Лечить" (меню лечения открыто)
    coords, conf = find_template_on_screen(HEAL_BUTTON_IMG, timeout=1, region=region, log_name="Кнопка Лечить")
    if coords:
        return UIState.HEAL_MENU_OPEN
    
    # Проверяем иконку шприца (лечение доступно)
    coords, conf = find_template_on_screen(HEAL_TOWN_IMG, timeout=1, region=region, log_name="Иконка лечения (шприц)")
    if coords:
        return UIState.HEAL_ICON_VISIBLE
    
    # Проверяем главный экран (кнопка "Дикие земли")
    coords, conf = find_template_on_screen(WILD_EARTH_IMG, timeout=1, region=region, log_name="Дикие земли")
    if coords:
        return UIState.MAIN_SCREEN
    
    return UIState.UNKNOWN


# Инициализация окна при старте
window, region = get_window_region()
if region is None:
    exit()

print(f"Определено окно BlueStacks: {region}")
print("Запуск процесса лечения войск...")
print("=" * 60)

# Основной цикл
last_state = None  # Кэшируем предыдущее состояние

while True:
    try:
        # Определяем текущее состояние UI (с учетом предыдущего для оптимизации)
        current_state = determine_ui_state(region, last_state)
        
        # Логгируем смену состояния только если оно изменилось
        if current_state != last_state:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Состояние: {current_state.value}")
        last_state = current_state

        # Обработка в зависимости от состояния
        if current_state == UIState.RECONNECT_POPUP:
            print("[ДЕЙСТВИЕ] Обработка окна переподключения...")
            handle_reconnect()
            time.sleep(2)
            last_state = None  # Сбрасываем кэш после reconnect

        elif current_state == UIState.HEAL_ACTIVE:
            # Лечение активно - ждём завершения
            print("[ОЖИДАНИЕ] Лечение активно. Ожидание завершения...15с")
            time.sleep(15)
            # Не сбрасываем last_state - хотим продолжать ждать в этом состоянии

        elif current_state == UIState.HEAL_HELP_VISIBLE:
            # Видна иконка помощи - нужно нажать для ускорения лечения
            print("[ДЕЙСТВИЕ] Найдена иконка помощи! Нажимаем для ускорения...")
            found, coords = find_and_click(HEAL_HELP_IMG, timeout=2, region=region, log_name="Иконка помощи")
            if found:
                print("Иконка помощи нажата!")
                # После нажатия помощи всё ещё ждём завершения лечения
                last_state = UIState.HEAL_ACTIVE
            else:
                print("[ПРЕДУПРЕЖДЕНИЕ] Не удалось нажать иконку помощи. Продолжаем ожидание...")
                last_state = UIState.HEAL_ACTIVE
            time.sleep(1)

        elif current_state == UIState.HEAL_MENU_OPEN:
            # Меню лечения открыто - нужно нажать "Лечить"
            print("[ДЕЙСТВИЕ] Меню лечения открыто. Нажимаем 'Лечить'...")
            found, coords = find_and_click(HEAL_BUTTON_IMG, timeout=3, region=region, log_name="Кнопка Лечить")
            if found:
                print("Кнопка 'Лечить' нажата!")
                time.sleep(1)
                # После нажатия "Лечить" должна появиться иконка помощи
                last_state = UIState.HEAL_HELP_VISIBLE
            else:
                print("[КРИТИЧЕСКАЯ ОШИБКА] Кнопка 'Лечить' не найдена, хотя меню открыто!")
                print("[ВОССТАНОВЛЕНИЕ] Попытка вернуться на главный экран...")
                found_wild, _ = find_and_click(WILD_EARTH_IMG, timeout=2, region=region, log_name="Дикие земли (возврат)")
                if not found_wild:
                    print("[ПРЕДУПРЕЖДЕНИЕ] Кнопка 'Дикие земли' также не найдена. Продолжаем цикл...")
                time.sleep(2)
                last_state = None  # Сбрасываем кэш для полной проверки

        elif current_state == UIState.HEAL_ICON_VISIBLE:
            # Видна иконка шприца - нужно её нажать
            print("[ДЕЙСТВИЕ] Найдена иконка лечения. Нажимаем...")
            found, coords = find_and_click(HEAL_TOWN_IMG, timeout=2, region=region, log_name="Иконка лечения (шприц)")
            if found:
                print("Иконка лечения нажата!")
                time.sleep(1)
                # После нажатия на шприц должно открыться меню лечения
                last_state = UIState.HEAL_MENU_OPEN
            else:
                print("[КРИТИЧЕСКАЯ ОШИБКА] Иконка лечения не найдена, хотя должна быть видна!")
                print("[ВОССТАНОВЛЕНИЕ] Попытка вернуться на главный экран...")
                found_wild, _ = find_and_click(WILD_EARTH_IMG, timeout=2, region=region, log_name="Дикие земли (возврат)")
                if not found_wild:
                    print("[ПРЕДУПРЕЖДЕНИЕ] Кнопка 'Дикие земли' также не найдена. Продолжаем цикл...")
                time.sleep(2)
                last_state = None  # Сбрасываем кэш для полной проверки

        elif current_state == UIState.MAIN_SCREEN:
            # Главный экран - проверяем, не активен ли таймер лечения
            print("[ДЕЙСТВИЕ] Главный экран. Проверка появления иконки лечения...")
            found_wait, _ = find_template_on_screen(HEAL_WAIT_IMG, timeout=1, region=region, log_name="Таймер лечения")
            if found_wait:
                print("Обнаружен активный таймер лечения. Ожидание...")
                last_state = UIState.HEAL_ACTIVE
                time.sleep(5)
            else:
                # Таймера нет - ждём появления иконки лечения
                time.sleep(2)
            # Остаёмся в MAIN_SCREEN пока не появится иконка лечения

        elif current_state == UIState.UNKNOWN:
            print("[НЕИЗВЕСТНОЕ СОСТОЯНИЕ] Не удалось определить состояние UI.")
            print("[ВОССТАНОВЛЕНИЕ] Попытка найти кнопку 'Дикие земли' для возврата к главному экрану...")
            found_wild, _ = find_and_click(WILD_EARTH_IMG, timeout=3, region=region, log_name="Дикие земли (восстановление)")
            if found_wild:
                print("Кнопка 'Дикие земли' найдена и нажата.")
            else:
                print("[ПРЕДУПРЕЖДЕНИЕ] Кнопка 'Дикие земли' не найдена. Повторная попытка через 3с...")
            time.sleep(3)
            last_state = None  # Сбрасываем кэш для полной проверки

        print("=" * 60)

    except Exception as e:
        print(f"[ОШИБКА] Произошла ошибка: {e}")
        import traceback
        traceback.print_exc()
        time.sleep(10)
        last_state = None  # Сбрасываем кэш после ошибки
