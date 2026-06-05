import numpy as np
import cv2
import pyautogui
import time
import pygetwindow as gw
import win32gui
from datetime import datetime
import os

# Константы изображений
PLUS_IMG = 'plus3.png'
MARCH_IMG = 'raid_march_button.png'
OK_IMG = 'ok.png'
RECONNECT_IMG = 'reconnect.png'
SOUZ_IMG = 'souz.png'
NEWS_IMG = 'news.png'
REID_IMG = 'raid_active.png'  # Активная кнопка (видна внутри окна рейдов)
REID_NAV_IMG = 'raid_not_active.png'  # Неактивная кнопка (видна снаружи, для навигации)
NO_FREE_SPACE_IMG = 'noFreeSpace.png'

# Папка для скриншотов отладки
DEBUG_SCREENSHOTS_DIR = 'debug_screenshots'
os.makedirs(DEBUG_SCREENSHOTS_DIR, exist_ok=True)

CONFIDENCE_THRESHOLD = 0.75  # Снижен с 0.9 для лучшего поиска
MARCH_THRESHOLD = 0.65  # Специальный порог для кнопки Марш (зелёный фон)
NAVIGATION_THRESHOLD = 0.7  # Порог для кнопок навигации (Союз, Новости)
clicks_on_march = 0  # счетчик успешных нажатий

# Название окна BlueStacks (может отличаться, проверьте через диспетчер задач или вручную)
bluestacks_window_title = "BlueStacks App Player"


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


def find_template(template, screen_cv, region, threshold=CONFIDENCE_THRESHOLD):
    """
    Найти шаблон на скриншоте.
    Возвращает координаты центра найденного элемента или None.
    """
    res = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    # print(f"max_val: {max_val}")

    if max_val >= threshold:
        button_x = region[0] + max_loc[0] + template.shape[1] / 2
        button_y = region[1] + max_loc[1] + template.shape[0] / 2
        return (button_x, button_y), max_val
    return None, max_val


def find_march_button(screen_cv, region, timeout=3):
    """
    Специальная функция для поиска кнопки МАРШ с пониженным порогом.
    Возвращает координаты или None.
    """
    template = prepare_template(MARCH_IMG)
    if template is None:
        print("[МАРШ] ОШИБКА: Не удалось загрузить шаблон raid_march_button.png")
        return None

    start_time = time.time()

    while time.time() - start_time < timeout:
        res = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

        if max_val >= MARCH_THRESHOLD:
            button_x = region[0] + max_loc[0] + template.shape[1] / 2
            button_y = region[1] + max_loc[1] + template.shape[0] / 2
            return (button_x, button_y), max_val

        time.sleep(0.3)
        # Обновляем скриншот
        window_new, region_new = get_window_region()
        if region_new:
            screen_cv = take_screenshot(region_new)

    return None, max_val


def take_screenshot(region):
    """Сделать скриншот области и преобразовать в формат BGR."""
    screenshot = pyautogui.screenshot(region=region)
    screen_cv = np.array(screenshot)

    if screen_cv.dtype != np.uint8:
        screen_cv = screen_cv.astype(np.uint8)
    screen_cv = cv2.cvtColor(screen_cv, cv2.COLOR_RGB2BGR)

    return screen_cv


def save_debug_screenshot(screen_cv, step_name):
    """Сохранить отладочный скриншот с меткой времени."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{step_name}.png"
    filepath = os.path.join(DEBUG_SCREENSHOTS_DIR, filename)
    cv2.imwrite(filepath, screen_cv)
    return filepath


def find_and_click(template_path, timeout=5, region=None, click=True, threshold=None):
    """
    Найти шаблон на экране и кликнуть по нему.

    Args:
        template_path: Путь к изображению шаблона
        timeout: Время поиска в секундах
        region: Область поиска (x, y, width, height)
        click: Если True, кликнуть по найденному элементу
        threshold: Порог уверенности (по умолчанию CONFIDENCE_THRESHOLD)

    Returns:
        True если элемент найден и клик выполнен, False иначе
    """
    if region is None:
        _, region = get_window_region()
        if region is None:
            return False

    if threshold is None:
        threshold = CONFIDENCE_THRESHOLD

    template = prepare_template(template_path)
    if template is None:
        return False

    start_time = time.time()
    template_name = os.path.basename(template_path)

    while time.time() - start_time < timeout:
        win32gui.SetForegroundWindow(window._hWnd)
        screen_cv = take_screenshot(region)
        coords, max_val = find_template(template, screen_cv, region, threshold=threshold)

        if coords:
            if click:
                pyautogui.click(coords[0], coords[1])
            # print(f"[НАЙДЕНО] {template_name} (confidence: {max_val:.3f})")
            return True

    # print(f"[НЕ НАЙДЕНО] {template_name} (timeout: {timeout}c)")
    return False


def find_template_on_screen(template_path, timeout=5, region=None, threshold=None):
    """
    Найти шаблон на экране без клика.
    Возвращает координаты или None.
    """
    if region is None:
        _, region = get_window_region()
        if region is None:
            return None

    if threshold is None:
        threshold = CONFIDENCE_THRESHOLD

    template = prepare_template(template_path)
    if template is None:
        return None

    start_time = time.time()
    template_name = os.path.basename(template_path)

    while time.time() - start_time < timeout:
        screen_cv = take_screenshot(region)
        coords, max_val = find_template(template, screen_cv, region, threshold=threshold)

        if coords:
            # print(f"[НАЙДЕНО] {template_name} (confidence: {max_val:.3f})")
            return coords
        time.sleep(0.5)

    # print(f"[НЕ НАЙДЕНО] {template_name} (timeout: {timeout}c)")
    return None


def is_reid_visible():
    """Проверить, видна ли кнопка 'Рейды' (активная, внутри окна)."""
    coords = find_template_on_screen(REID_IMG, timeout=3)
    # if coords:
        # print(f"[ПРОВЕРКА] Кнопка 'Рейды' ВИДНА (активная, координаты: {coords})")
    # else:
        # print(f"[ПРОВЕРКА] Кнопка 'Рейды' НЕ видна (активная)")
    return coords is not None


def navigate_to_reid_window():
    """
    Вернуться в окно рейдов союза.
    Последовательность: Союз -> Новости -> Проверка Рейды
    """
    print("=" * 50)
    print("[НАВИГАЦИЯ] Начало перехода в окно рейдов...")
    print("=" * 50)

    window, region = get_window_region()
    if region is None:
        print("[НАВИГАЦИЯ] ОШИБКА: Не удалось получить область окна")
        return False

    # Нажать кнопку "Союз" с пониженным порогом
    print("[НАВИГАЦИЯ] Шаг 1: Поиск кнопки 'Союз'...")
    if find_and_click(SOUZ_IMG, timeout=5, region=region, threshold=NAVIGATION_THRESHOLD):
        print("[НАВИГАЦИЯ] ✓ Нажата кнопка 'Союз'")
        time.sleep(1.5)
    else:
        print("[НАВИГАЦИЯ] ✗ Кнопка 'Союз' НЕ найдена")
        return False

    # Нажать кнопку "Новости"
    print("[НАВИГАЦИЯ] Шаг 2: Поиск кнопки 'Новости'...")
    if find_and_click(NEWS_IMG, timeout=3, region=region, threshold=NAVIGATION_THRESHOLD):
        print("[НАВИГАЦИЯ] ✓ Нажата кнопка 'Новости'")
        time.sleep(1)
    else:
        print("[НАВИГАЦИЯ] ✗ Кнопка 'Новости' НЕ найдена")
        return False

    # Нажать кнопку "Рейды"
    print("[НАВИГАЦИЯ] Шаг 3: Поиск кнопки 'Рейды'...")
    if find_and_click(REID_NAV_IMG, timeout=3, region=region, threshold=NAVIGATION_THRESHOLD):
        print("[НАВИГАЦИЯ] ✓ Нажата кнопка 'Рейды'")
        time.sleep(1)
        print("[НАВИГАЦИЯ] Переход в рейды завершен успешно")
        print("=" * 50)
        return True
    else:
        print("[НАВИГАЦИЯ] ✗ Кнопка 'Рейды' НЕ найдена")
        print("[НАВИГАЦИЯ] Переход в рейды НЕ удался")
        print("=" * 50)
        return False


def handle_reconnect():
    """Обработать окно переподключения."""
    if find_and_click(RECONNECT_IMG, timeout=2):
        print("Нажата кнопка 'Переподключиться'")
        time.sleep(2)
        # Убедиться, что кнопка пропала
        reconnect_coords = find_template_on_screen(RECONNECT_IMG, timeout=3)
        if reconnect_coords is None:
            print("Окно переподключения закрыто")
            return True
    return False


def check_no_free_space():
    """Проверить, есть ли сообщение о отсутствии свободных мест."""
    coords = find_template_on_screen(NO_FREE_SPACE_IMG, timeout=1)
    return coords is not None


def click_ok():
    """Нажать кнопку OK (когда нет мест)."""
    if find_and_click(OK_IMG, timeout=1):
        print("Нажата кнопка 'OK' (нет мест в марше)")
        time.sleep(1)
        return True
    return False


# Инициализация окна при старте
window, region = get_window_region()
if region is None:
    exit()

print(f"Определено окно BlueStacks: {region}")

# Основной цикл
while True:
    try:
        # Проверка на переподключение
        if handle_reconnect():
            continue
        
        # Проверка на исходное состояние - видна ли кнопка "Рейды"
        if not is_reid_visible():
            print("[ГЛАВНЫЙ] Кнопка 'Рейды' не видна, возвращаемся в окно рейдов...")
            nav_result = navigate_to_reid_window()
            if nav_result:
                print("[ГЛАВНЫЙ] Навигация успешна, продолжаем работу")
            else:
                print("[ГЛАВНЫЙ] Навигация НЕ удалась, повторная попытка через 2с")
            time.sleep(2)
            continue
        
        # Ищем кнопку '+'
        # print("[ГЛАВНЫЙ] Поиск кнопки '+'...")

        if find_and_click(PLUS_IMG, timeout=2):
            print("Найден '+'! Ищем 'Марш'...")
            time.sleep(1)  # Ждём появления окна с кнопкой Марш

            # Обновляем скриншот после открытия окна
            window, region = get_window_region()
            if region:
                screen_cv = take_screenshot(region)

            # Используем специальную функцию для поиска МАРШ
            march_result, march_conf = find_march_button(screen_cv, region, timeout=5)

            if march_result:
                print(f"[МАРШ] Нажимаем кнопку! (confidence: {march_conf:.3f})")
                pyautogui.click(march_result[0], march_result[1])
                clicks_on_march += 1
                print(f"clicks_on_march: {clicks_on_march}")
                time.sleep(1)

                # Проверка на отсутствие мест
                if check_no_free_space():
                    print("Нет свободных мест в марше!")
                    click_ok()
                    time.sleep(1)

                # Проверяем, есть ли еще кнопка '+' (значит рейд активен)
                time.sleep(1)
                plus_still_visible = find_and_click(PLUS_IMG, timeout=1, click=False)
                if not plus_still_visible:
                    print("[РЕЙД] Кнопка '+' не видна - рейд закончился или окно закрыто")
                    # Пробуем нажать OK если окно еще висит
                    if not click_ok():
                        print("[РЕЙД] OK не найден, возвращаемся в окно рейдов...")
                        navigate_to_reid_window()
                        time.sleep(1)
                    continue
            else:
                print("[МАРШ] ✗ Кнопка НЕ НАЙДЕНА после всех попыток!")
                time.sleep(2)
                continue
        # Обработка кнопки OK (если нет мест)
        if click_ok():
            continue
            
    except Exception as e:
        print(f"Произошла ошибка: {e}")
    
    time.sleep(5)  # задержка перед новой итерацией