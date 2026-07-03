# ==========================================
# ОБЩИЕ УТИЛИТЫ
# ==========================================

import cv2
import numpy as np
import pyautogui
import time
import os
from datetime import datetime

import pygetwindow as gw
import win32gui
import win32ui
import win32con

from config import *

from logger import logger


# ==========================================
# РАБОТА С ОКНОМ
# ==========================================
def get_window_region():
    """
    Получить область окна BlueStacks, активировать если не активно.
    Возвращает: (window_object, (left, top, width, height)) или (None, None)
    """
    try:
        window = gw.getWindowsWithTitle(BLUESTACKS_WINDOW_TITLE)[0]
        if not window.isActive:
            window.activate()
        return window, (window.left, window.top, window.width, window.height)
    except IndexError:
        logger.info(f"Окно '{BLUESTACKS_WINDOW_TITLE}' не найдено.")
        return None, None


# ==========================================
# РАБОТА С ИЗОБРАЖЕНИЯМИ
# ==========================================
_template_cache = {}


def prepare_template(template_path):
    """
    Загрузить и подготовить шаблон для матчинга.
    Конвертирует в BGR и uint8.
    """
    template = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)
    if template is None:
        return None
    if template.shape[2] == 4:
        template = cv2.cvtColor(template, cv2.COLOR_BGRA2BGR)
    if template.dtype != np.uint8:
        template = template.astype(np.uint8)
    return template


def get_template(template_path):
    """Получить шаблон с кэшированием."""
    if template_path not in _template_cache:
        _template_cache[template_path] = prepare_template(template_path)
    return _template_cache[template_path]


# ==========================================
# СКРИНШОТЫ
# ==========================================
def take_screenshot(window, region):
    """
    Создать скриншот области окна через win32 API.
    Фолбэк на pyautogui при ошибке.
    """
    x, y, w, h = region
    hwnd = window._hWnd

    try:
        hwndDC = win32gui.GetWindowDC(hwnd)
        mfcDC = win32ui.CreateDCFromHandle(hwndDC)
        saveDC = mfcDC.CreateCompatibleDC()

        saveBitMap = win32ui.CreateBitmap()
        saveBitMap.CreateCompatibleBitmap(mfcDC, w, h)
        saveDC.SelectObject(saveBitMap)

        saveDC.BitBlt((0, 0), (w, h), mfcDC, (0, 0), win32con.SRCCOPY)

        signedIntsArray = saveBitMap.GetBitmapBits(True)
        img = np.frombuffer(signedIntsArray, dtype='uint8')
        img.shape = (h, w, 4)

        win32gui.DeleteObject(saveBitMap.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwndDC)

        screen_cv = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return screen_cv

    except Exception as e:
        logger.info(f"[СКРИНШОТ] win32 не сработал: {e}")
        screenshot = pyautogui.screenshot(region=region)
        screen_cv = np.array(screenshot)
        if screen_cv.dtype != np.uint8:
            screen_cv = screen_cv.astype(np.uint8)
        screen_cv = cv2.cvtColor(screen_cv, cv2.COLOR_RGB2BGR)
        return screen_cv


# ==========================================
# ПОИСК И КЛИК
# ==========================================
def find_on_screen(template, screen_cv, region, threshold=CONFIDENCE_THRESHOLD):
    """
    Найти шаблон на экране через matchTemplate.
    Возвращает: ((center_x, center_y), confidence) или (None, max_val)
    """
    res = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

    if max_val >= threshold:
        button_x = region[0] + max_loc[0] + template.shape[1] / 2
        button_y = region[1] + max_loc[1] + template.shape[0] / 2
        # print(f"[find_on_screen] ✓ template: {template.shape}, max_val={max_val:.3f}, loc={max_loc}")
        return (button_x, button_y), max_val

    # print(f"[find_on_screen] ✗ max_val={max_val:.3f} < threshold={threshold}")
    return None, max_val


def find_and_click(template_path, screen_cv, region, threshold=CONFIDENCE_THRESHOLD):
    """
    Найти шаблон (с кэшированием) и кликнуть по нему.
    Возвращает: (found: bool, coords: tuple or None)
    """
    template = get_template(template_path)
    if template is None:
        logger.info(f"[find_and_click] шаблон не найден: {template_path}")
        return False, None

    coords, conf = find_on_screen(template, screen_cv, region, threshold)

    if coords:
        if conf >= threshold:
            logger.info(f"[find_and_click] ✓ найден: {template_path} (conf={conf:.3f}, coords={coords})")
            pyautogui.click(coords[0], coords[1])
            # print(f"[find_and_click] ✓ клик выполнен по: {template_path}")
            return True, coords
        else:
            logger.info(f"[find_and_click] ✗ найден ниже порога: {template_path} (conf={conf:.3f}, порог={threshold})")
            return False, None
    else:
        logger.info(f"[find_and_click] ✗ не найден: {template_path} (max_conf={conf:.3f}, порог={threshold})")
        return False, None

def find_and_click_no_logs(template_path, screen_cv, region, threshold=CONFIDENCE_THRESHOLD):
    """
    Найти шаблон (с кэшированием) и кликнуть по нему.
    Возвращает: (found: bool, coords: tuple or None)
    """
    template = get_template(template_path)
    if template is None:
        logger.info(f"[find_and_click] шаблон не найден: {template_path}")
        return False, None

    coords, conf = find_on_screen(template, screen_cv, region, threshold)

    if coords:
        if conf >= threshold:
            pyautogui.click(coords[0], coords[1])
            return True, coords
        else:
            return False, None
    else:
        return False, None


def find_all_on_screen(template, screen_cv, region, threshold=CONFIDENCE_THRESHOLD):
    """
    Найти ВСЕ вхождения шаблона на экране с помощью matchTemplate + non-max suppression.
    Возвращает: [(center_x, center_y, conf), ...] в координатах экрана.
    """
    if template is None:
        return []
    res = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
    loc = np.where(res >= threshold)
    h, w = template.shape[:2]
    matches = []
    for pt in zip(*loc[::-1]):
        cx = region[0] + pt[0] + w / 2
        cy = region[1] + pt[1] + h / 2
        matches.append((cx, cy, float(res[pt[1], pt[0]])))

    # простое подавление близких дубликатов
    filtered = []
    for m in sorted(matches, key=lambda x: x[2], reverse=True):
        if not any(abs(m[0] - f[0]) < w * 0.8 and abs(m[1] - f[1]) < h * 0.8 for f in filtered):
            filtered.append(m)
    return filtered


def swipe_horizontal(region, direction="right", duration=0.5, y_offset=80):
    """
    Горизонтальный свайп в верхней части окна BlueStacks.
    direction: 'right' или 'left'.
    y_offset: фиксированный отступ от верхнего края окна (по умолчанию 80 px),
              чтобы свайп проходил по верхнему меню/карусели событий,
              но ниже панели инструментов BlueStacks.
    """
    x1 = region[0] + int(region[2] * 0.80)
    x2 = region[0] + int(region[2] * 0.20)
    y = region[1] + y_offset
    if direction == "left":
        x1, x2 = x2, x1
    pyautogui.moveTo(x1, y, duration=0.2)
    pyautogui.dragTo(x2, y, duration=duration, button="left")
    logger.info(f"[SWIPE] {direction}: ({x1},{y}) -> ({x2},{y})")


def scroll_in_region(region, direction="down", duration=0.3, step_ratio=0.3):
    """
    Вертикальный скролл (drag) в центре окна.
    direction: 'down' или 'up'.
    step_ratio: доля высоты окна, на которую выполняется один drag
                 (по умолчанию 0.3; для списка уровней используется меньшее значение).
    """
    cx = region[0] + region[2] // 2
    half_step = int(region[3] * step_ratio / 2)
    y_center = region[1] + region[3] // 2
    y1 = y_center + half_step
    y2 = y_center - half_step
    if direction == "up":
        y1, y2 = y2, y1
    pyautogui.moveTo(cx, y1, duration=0.2)
    pyautogui.dragTo(cx, y2, duration=duration, button="left")
    logger.info(f"[SCROLL] {direction}: ({cx},{y1}) -> ({cx},{y2})")


def _is_at_main_screen_village(screen_cv, region):
    """Проверить, что мы вышли в окно поселения (виден WILD_EARTH_IMG или VILLAGE_IMG)."""
    wild_coords, _ = find_on_screen(get_template(WILD_EARTH_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if wild_coords:
        return True
    return False


def ensure_exit_to_main_screen(window, region, max_attempts=10):
    """
    Пытаться выйти в окно поселения, пока не увидим WILD_EARTH_IMG/VILLAGE_IMG.
    Если видна кнопка village — нажимаем на неё, чтобы вернуться в поселение.
    Возвращает True если выход подтверждён, False если превышено число попыток.
    """
    for attempt in range(1, max_attempts + 1):
        screen_cv = take_screenshot(window, region)
        if _is_at_main_screen_village(screen_cv, region):
            logger.info("[EXIT] Подтверждён выход в окно поселения (wild/village видно).")
            return True

        # Если видна кнопка village — нажимаем на неё, чтобы вернуться в поселение
        village_coords, village_conf = find_and_click(VILLAGE_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)

        logger.info(f"[EXIT] Попытка выхода {attempt}/{max_attempts}: нажимаем back.png")
        find_and_click(BACK_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        time.sleep(0.5)
        screen_cv = take_screenshot(window, region)
        if _is_at_main_screen_village(screen_cv, region):
            return True

        logger.info(f"[EXIT] Попытка выхода {attempt}/{max_attempts}: нажимаем close.png")
        find_and_click(CLOSE_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        time.sleep(0.5)

    logger.warning("[EXIT] Не удалось подтвердить выход в окно поселения после всех попыток.")
    return False

# ==========================================
# ОБРАБОТКА RECONNECT
# ==========================================
def handle_reconnect(screen_cv, region):
    """
    Обработать окно переподключения.
    Возвращает: True если найдено и обработано
    """
    found, _ = find_and_click_no_logs(RECONNECT_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if found:
        logger.info("[RECONNECT] Нажата кнопка переподключения")
        time.sleep(3)
        return True
    return False


def handle_reconnect_repeat(screen_cv, region):
    """
    Обработать окно повторного переподключения.
    Возвращает: True если найдено и обработано
    """
    found, _ = find_and_click_no_logs(RECONNECT_REPEAT_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if found:
        logger.info("[RECONNECT_REPEAT] Нажата кнопка переподключения")
        time.sleep(3)
        return True
    return False


# ==========================================
# ОТЛАДКА
# ==========================================
def save_debug_screenshot(screen_cv, step_name):
    """Сохранить отладочный скриншот с временной меткой."""
    os.makedirs(DEBUG_SCREENSHOTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{step_name}.png"
    filepath = os.path.join(DEBUG_SCREENSHOTS_DIR, filename)
    cv2.imwrite(filepath, screen_cv)
    logger.info(f"[DEBUG] Скриншот сохранён: {filepath}")
