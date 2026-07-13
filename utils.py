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
            try:
                window.activate()
            except Exception as e:
                logger.debug(f"[WINDOW] Не удалось активировать окно: {e}")
        return window, (window.left, window.top, window.width, window.height)
    except IndexError:
        logger.info(f"Окно '{BLUESTACKS_WINDOW_TITLE}' не найдено.")
        return None, None
    except Exception as e:
        logger.error(f"[WINDOW] Ошибка при получении окна: {e}")
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
def _ensure_bgr_uint8(screen_cv):
    """Привести скриншот к валидному BGR uint8 3-канальному ndarray."""
    if screen_cv is None or not isinstance(screen_cv, np.ndarray):
        return None
    if screen_cv.dtype != np.uint8:
        screen_cv = screen_cv.astype(np.uint8)
    if screen_cv.ndim == 2:
        screen_cv = cv2.cvtColor(screen_cv, cv2.COLOR_GRAY2BGR)
    elif screen_cv.ndim == 3 and screen_cv.shape[2] == 4:
        screen_cv = cv2.cvtColor(screen_cv, cv2.COLOR_BGRA2BGR)
    elif screen_cv.ndim == 3 and screen_cv.shape[2] != 3:
        # Drop/convert any other channel count to BGR
        screen_cv = cv2.cvtColor(screen_cv, cv2.COLOR_BGRA2BGR)
    elif screen_cv.ndim not in (2, 3):
        return None
    return screen_cv


def take_screenshot(window, region):
    """
    Создать скриншот области окна через win32 API.
    Фолбэк на pyautogui при ошибке.
    Возвращает None если region невалиден или скриншот получить не удалось.
    """
    if region is None:
        return None
    x, y, w, h = region
    if w <= 0 or h <= 0:
        logger.warning(f"[СКРИНШОТ] Невалидный region: {region}")
        return None

    hwnd = getattr(window, '_hWnd', None)
    if hwnd is None:
        logger.warning("[СКРИНШОТ] Нет hwnd окна.")
        return None

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
        expected_size = h * w * 4
        if img.size != expected_size:
            logger.warning(f"[СКРИНШОТ] Размер bitmap не совпадает: {img.size} != {expected_size}")
            win32gui.DeleteObject(saveBitMap.GetHandle())
            saveDC.DeleteDC()
            mfcDC.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwndDC)
            return None
        img.shape = (h, w, 4)

        win32gui.DeleteObject(saveBitMap.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwndDC)

        screen_cv = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return _ensure_bgr_uint8(screen_cv)

    except Exception as e:
        logger.info(f"[СКРИНШОТ] win32 не сработал: {e}")
        try:
            screenshot = pyautogui.screenshot(region=region)
            screen_cv = np.array(screenshot)
            return _ensure_bgr_uint8(screen_cv)
        except Exception as e2:
            logger.error(f"[СКРИНШОТ] pyautogui фолбэк тоже не сработал: {e2}")
            return None


# ==========================================
# ПОИСК И КЛИК
# ==========================================
def find_on_screen(template, screen_cv, region, threshold=CONFIDENCE_THRESHOLD):
    """
    Найти шаблон на экране через matchTemplate.
    Возвращает: ((center_x, center_y), confidence) или (None, max_val)
    """
    if screen_cv is None or template is None:
        return None, 0.0
    if not isinstance(screen_cv, np.ndarray) or not isinstance(template, np.ndarray):
        return None, 0.0
    if screen_cv.ndim != 3 or screen_cv.shape[2] != 3:
        logger.warning(f"[find_on_screen] Невалидный screen_cv: shape={screen_cv.shape}, dtype={screen_cv.dtype}")
        return None, 0.0
    if template.ndim != 3 or template.shape[2] != 3:
        logger.warning(f"[find_on_screen] Невалидный template: shape={template.shape}, dtype={template.dtype}")
        return None, 0.0
    if screen_cv.shape[0] < template.shape[0] or screen_cv.shape[1] < template.shape[1]:
        logger.warning(f"[find_on_screen] Скриншот меньше шаблона: screen={screen_cv.shape}, template={template.shape}")
        return None, 0.0

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
    if screen_cv is None or region is None:
        logger.warning(f"[find_and_click] Невалидные входные данные: screen_cv={screen_cv}, region={region}")
        return False, None
    template = get_template(template_path)
    if template is None:
        logger.error(f"[find_and_click] шаблон не найден: {template_path}")
        return False, None

    coords, conf = find_on_screen(template, screen_cv, region, threshold)

    if coords:
        if conf >= threshold:
            logger.debug(f"[find_and_click] ✓ найден: {template_path} (conf={conf:.3f}, coords={coords})")
            try:
                pyautogui.click(coords[0], coords[1])
            except pyautogui.FailSafeException:
                logger.error("[find_and_click] Fail-safe сработал — мышь в углу экрана. Пропускаем клик.")
                return False, coords
            # print(f"[find_and_click] ✓ клик выполнен по: {template_path}")
            return True, coords
        else:
            logger.debug(f"[find_and_click] ✗ найден ниже порога: {template_path} (conf={conf:.3f}, порог={threshold})")
            return False, None
    else:
        logger.debug(f"[find_and_click] ✗ не найден: {template_path} (max_conf={conf:.3f}, порог={threshold})")
        return False, None

def find_and_click_no_logs(template_path, screen_cv, region, threshold=CONFIDENCE_THRESHOLD):
    """
    Найти шаблон (с кэшированием) и кликнуть по нему.
    Возвращает: (found: bool, coords: tuple or None)
    """
    if screen_cv is None or region is None:
        return False, None
    template = get_template(template_path)
    if template is None:
        return False, None

    coords, conf = find_on_screen(template, screen_cv, region, threshold)

    if coords:
        if conf >= threshold:
            try:
                pyautogui.click(coords[0], coords[1])
            except pyautogui.FailSafeException:
                return False, coords
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
    if template is None or screen_cv is None:
        return []
    if not isinstance(screen_cv, np.ndarray) or not isinstance(template, np.ndarray):
        return []
    if screen_cv.ndim != 3 or screen_cv.shape[2] != 3:
        return []
    if template.ndim != 3 or template.shape[2] != 3:
        return []
    if screen_cv.shape[0] < template.shape[0] or screen_cv.shape[1] < template.shape[1]:
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


def scroll_in_region(region, direction, step_ratio=0.3, duration=0.2):
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


def click_top_screen_safe(region, y_ratio=0.05, delay=0.2):
    """Клик в верхнюю часть экрана. По умолчанию выше стандартной верхней панели (y=5%)."""
    click_x = region[0] + region[2] // 2
    click_y = region[1] + int(region[3] * y_ratio)
    pyautogui.click(click_x, click_y)
    time.sleep(delay)


def click_top_screen_fallback(region, y_ratio=0.05, delay=0.2):
    """Резервный клик в верхнюю часть экрана (алиас для совместимости)."""
    click_top_screen_safe(region, y_ratio=y_ratio, delay=delay)


def is_at_main_screen_village(screen_cv, region):
    """
    Проверить, что мы находимся в окне поселения.
    В диких землях (wild lands) виден WILD_EARTH_IMG и кнопка VILLAGE_IMG ("в поселение").
    В поселении видны поселенческие маркеры (souz, heal_town, events, mail, book) и НЕ видна кнопка "в поселение".
    """
    # Если видна кнопка "в поселение" — мы на карте мира, не в поселении
    village_coords, _ = find_on_screen(get_template(VILLAGE_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if village_coords:
        return False

    # Settlement markers — требуем хотя бы один явный признак поселения.
    # WILD_EARTH нельзя использовать как fallback, потому что фон диких земель
    # виден и на экране активной золотодобычи/рейда.
    settlement_markers = [
        (SOUZ_IMG, CONFIDENCE_MEDIUM_THRESHOLD),
        (HEAL_TOWN_IMG, CONFIDENCE_MEDIUM_THRESHOLD),
        (EVENTS_IMG, CONFIDENCE_MEDIUM_THRESHOLD),
        (MAIL_IMG, CONFIDENCE_MEDIUM_THRESHOLD),
        (BOOK_IMG, CONFIDENCE_MEDIUM_THRESHOLD),
    ]
    for img, threshold in settlement_markers:
        coords, _ = find_on_screen(get_template(img), screen_cv, region, threshold=threshold)
        if coords:
            return True

    return False


def ensure_exit_to_main_screen(window, region, max_attempts=5):
    """
    Пытаться выйти в окно поселения.
    Если бот на карте мира (видна кнопка "в поселение") — нажимаем её.
    Иначе закрываем случайные меню через back/close.
    Возвращает True если выход подтверждён, False если превышено число попыток.
    """
    for attempt in range(1, max_attempts + 1):
        screen_cv = take_screenshot(window, region)
        if is_at_main_screen_village(screen_cv, region):
            logger.info("[EXIT] Подтверждён выход в окно поселения.")
            return True

        # На экранах активной добычи/рейда — специальная кнопка "в поселение" (голубая стрелка слева внизу)
        exit_clicked, exit_coords = find_and_click(EXIT_TO_VILLAGE_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if exit_clicked:
            exit_conf = 0.0
            if exit_coords:
                _, exit_conf = find_on_screen(get_template(EXIT_TO_VILLAGE_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
            logger.info(f"[EXIT] Попытка {attempt}/{max_attempts}: нажимаем 'в поселение' (conf={exit_conf:.3f})")
            time.sleep(0.5)
            continue

        # На карте мира — нажимаем кнопку "в поселение" (иконка с мячом)
        village_clicked, village_coords = find_and_click(VILLAGE_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if village_clicked:
            village_conf = 0.0
            if village_coords:
                _, village_conf = find_on_screen(get_template(VILLAGE_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
            logger.info(f"[EXIT] Попытка {attempt}/{max_attempts}: нажимаем кнопку 'в поселение' (conf={village_conf:.3f})")
            time.sleep(0.5)
            continue

        # Явное распознавание карты мира по WILD_EARTH_IMG (дикие земли)
        wild_coords, wild_conf = find_on_screen(get_template(WILD_EARTH_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if wild_coords:
            logger.info(f"[EXIT] Попытка {attempt}/{max_attempts}: мы на карте мира (wild_earth conf={wild_conf:.3f}), нажимаем village.png")
            find_and_click(VILLAGE_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
            time.sleep(0.5)
            continue

        # Закрываем случайные меню / попапы
        logger.info(f"[EXIT] Попытка выхода {attempt}/{max_attempts}: нажимаем back.png")
        back_clicked, _ = find_and_click(BACK_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if back_clicked:
            time.sleep(0.5)
            screen_after = take_screenshot(window, region)
            if is_at_main_screen_village(screen_after, region):
                return True

        logger.info(f"[EXIT] Попытка выхода {attempt}/{max_attempts}: нажимаем close.png")
        close_clicked, _ = find_and_click(CLOSE_IMG, screen_cv if not back_clicked else screen_after, region, threshold=CONFIDENCE_THRESHOLD)
        if close_clicked:
            time.sleep(0.5)
            screen_after = take_screenshot(window, region)
            if is_at_main_screen_village(screen_after, region):
                return True

        # Универсальный защитный клик: если после back/close/в поселение мы всё ещё
        # не в поселении и не на карте мира — кликаем в верхнюю часть экрана,
        # чтобы сбросить оверлей/детали здания/попап.
        screen_check = screen_after if (back_clicked or close_clicked) else screen_cv
        if not is_at_main_screen_village(screen_check, region):
            logger.info(f"[EXIT] Стандартные кнопки не вывели в поселение. Клик в верхнюю часть экрана (защитный).")
            try:
                click_top_screen_safe(region)
            except Exception:
                click_top_screen_fallback(region)
            time.sleep(0.5)
            continue

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
        time.sleep(10)
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
        time.sleep(10)
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
    logger.debug(f"[DEBUG] Скриншот сохранён: {filepath}")
