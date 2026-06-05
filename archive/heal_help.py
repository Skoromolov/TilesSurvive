import numpy as np
import cv2
import pyautogui
import time
import pygetwindow as gw
import win32gui
import win32ui
import win32con
from enum import Enum
from datetime import datetime
import os

# ==========================================
# КОНСТАНТЫ ИЗОБРАЖЕНИЙ
# ==========================================
# Лечение
HEAL_TOWN_IMG = 'heal_town.png'
HEAL_BUTTON_IMG = 'heal_button.png'
HEAL_WAIT_IMG = 'heal_wait.png'
HELP_HANDS_IMG = 'help_hands.png'        # Общая помощь союза (рукопожатие)
HEAL_HELP_HANDS_IMG = 'heal_help_hands.png'  # Руки помощи лечения (рукопожатие с аптечкой)
WILD_EARTH_IMG = 'wild_earth.png'

# Общие
RECONNECT_IMG = 'reconnect.png'

# Папка для скриншотов отладки
DEBUG_SCREENSHOTS_DIR = 'debug_screenshots'
os.makedirs(DEBUG_SCREENSHOTS_DIR, exist_ok=True)

CONFIDENCE_THRESHOLD = 0.85
CONFIDENCE_HIGH = 0.9  # Для критичных элементов

# Название окна BlueStacks
bluestacks_window_title = "BlueStacks App Player"

# Глобальная переменная для handle окна (используется в take_screenshot)
window = None

# ==========================================
# ПЕРЕЧИСЛЕНИЯ И ТИПЫ
# ==========================================
class Mode(Enum):
    """Режим работы скрипта."""
    HEAL = "heal"

class HealState(Enum):
    """Состояния UI в цикле лечения."""
    UNKNOWN = "unknown"
    MAIN_SCREEN = "main_screen"
    HEAL_ICON_VISIBLE = "heal_icon_visible"
    HEAL_MENU_OPEN = "heal_menu_open"
    HEAL_HELP_VISIBLE = "heal_help_visible"
    HEAL_ACTIVE = "heal_active"
    RECONNECT_POPUP = "reconnect_popup"


# ==========================================
# УТИЛИТЫ
# ==========================================
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


def get_monitors_info():
    """Получить информацию о мониторах."""
    monitors = pyautogui.size()
    try:
        import screeninfo
        monitors_list = screeninfo.get_monitors()
        for i, m in enumerate(monitors_list):
            print(f"[МОНИТОР {i}] {m.name}: x={m.x}, y={m.y}, w={m.width}, h={m.height}")
        return monitors_list
    except ImportError:
        # Если screeninfo не установлен, используем pyautogui
        print(f"[МОНИТОРЫ] Общий рабочий стол: {monitors.width}x{monitors.height}")
        return None


def prepare_template(template_path):
    """Загрузить и подготовить шаблон для поиска."""
    template = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)
    if template is None:
        return None
    if template.shape[2] == 4:
        template = cv2.cvtColor(template, cv2.COLOR_BGRA2BGR)
    if template.dtype != np.uint8:
        template = template.astype(np.uint8)
    return template


# Кэш шаблонов для предотвращения повторной загрузки
_template_cache = {}

def get_template(template_path):
    """Получить шаблон из кэша или загрузить."""
    if template_path not in _template_cache:
        _template_cache[template_path] = prepare_template(template_path)
    return _template_cache[template_path]


def take_screenshot(region):
    """Сделать скриншот окна через Win32 API (надёжнее для GPU-окон)."""
    x, y, w, h = region
    
    # Получаем handle окна
    hwnd = window._hWnd
    
    # Метод 1: Пробуем захват через PrintWindow (для GPU-окон)
    try:
        hwndDC = win32gui.GetWindowDC(hwnd)
        mfcDC = win32ui.CreateDCFromHandle(hwndDC)
        saveDC = mfcDC.CreateCompatibleDC()
        
        saveBitMap = win32ui.CreateBitmap()
        saveBitMap.CreateCompatibleBitmap(mfcDC, w, h)
        saveDC.SelectObject(saveBitMap)
        
        # PrintWindow захватывает содержимое окна даже если оно перекрыто
        saveDC.BitBlt((0, 0), (w, h), mfcDC, (0, 0), win32con.SRCCOPY)
        
        # Конвертируем в numpy
        signedIntsArray = saveBitMap.GetBitmapBits(True)
        img = np.frombuffer(signedIntsArray, dtype='uint8')
        img.shape = (h, w, 4)
        
        # Освобождаем ресурсы
        win32gui.DeleteObject(saveBitMap.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwndDC)
        
        # Конвертируем BGRA → BGR
        screen_cv = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return screen_cv
        
    except Exception as e:
        print(f"[СКРИНШОТ] PrintWindow не сработал: {e}")
        # Метод 2: Fallback на pyautogui
        screenshot = pyautogui.screenshot(region=region)
        screen_cv = np.array(screenshot)
        if screen_cv.dtype != np.uint8:
            screen_cv = screen_cv.astype(np.uint8)
        screen_cv = cv2.cvtColor(screen_cv, cv2.COLOR_RGB2BGR)
        return screen_cv


def verify_screenshot(region):
    """
    Проверить что скриншот успешно снимается с нужного монитора.
    Сохраняет тестовый скриншот и выводит информацию.
    """
    x, y, w, h = region
    print(f"\n[ПРОВЕРКА СКРИНШОТА]")
    print(f"  Область: x={x}, y={y}, w={w}, h={h}")
    print(f"  Левый верхний угол: ({x}, {y})")
    
    # Определяем монитор по координатам
    if x < 0:
        print(f"  → Окно на мониторе СЛЕВА от основного (отрицательные координаты)")
    elif x > 1920:  # типичная ширина основного монитора
        print(f"  → Окно на мониторе СПРАВА от основного")
    else:
        print(f"  → Окно на основном мониторе")
    
    try:
        screen_cv = take_screenshot(region)
        print(f"  Размер скриншота: {screen_cv.shape[1]}x{screen_cv.shape[0]}")
        
        # Проверяем что скриншот не пустой (не весь чёрный)
        mean_brightness = cv2.mean(screen_cv)[:3]
        print(f"  Средняя яркость (BGR): {mean_brightness[0]:.1f}, {mean_brightness[1]:.1f}, {mean_brightness[2]:.1f}")
        
        if mean_brightness[0] < 5 and mean_brightness[1] < 5 and mean_brightness[2] < 5:
            print(f"  ⚠ ВНИМАНИЕ: Скриншот полностью чёрный! Возможно окно не активно или свёрнуто.")
        else:
            print(f"  ✓ Скриншот снят успешно")
        
        # Сохраняем тестовый скриншот
        test_path = os.path.join(DEBUG_SCREENSHOTS_DIR, "test_monitor_check.png")
        cv2.imwrite(test_path, screen_cv)
        print(f"  Скриншот сохранён: {test_path}")
        
        return True
    except Exception as e:
        print(f"  ✗ ОШИБКА при снятии скриншота: {e}")
        return False


def find_on_screen(template, screen_cv, region, threshold=CONFIDENCE_THRESHOLD):
    """
    Найти шаблон на скриншоте (без повторного скриншота!).
    Returns: (coords, confidence)
    """
    res = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    
    if max_val >= threshold:
        button_x = region[0] + max_loc[0] + template.shape[1] / 2
        button_y = region[1] + max_loc[1] + template.shape[0] / 2
        return (button_x, button_y), max_val
    return None, max_val


def find_and_click_cached(template_path, screen_cv, region, threshold=CONFIDENCE_THRESHOLD):
    """Найти и кликнуть по шаблону на УЖЕ сделанном скриншоте."""
    template = get_template(template_path)
    if template is None:
        return False, None
    
    coords, conf = find_on_screen(template, screen_cv, region, threshold)
    if coords:
        pyautogui.click(coords[0], coords[1])
        return True, coords
    return False, None


def save_debug_screenshot(screen_cv, step_name):
    """Сохранить отладочный скриншот."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{step_name}.png"
    filepath = os.path.join(DEBUG_SCREENSHOTS_DIR, filename)
    cv2.imwrite(filepath, screen_cv)


# ==========================================
# ОБЩИЕ ДЕЙСТВИЯ
# ==========================================
def handle_reconnect(screen_cv, region):
    """Обработать окно переподключения."""
    found, _ = find_and_click_cached(RECONNECT_IMG, screen_cv, region, threshold=0.85)
    if found:
        print("[RECONNECT] Нажата кнопка переподключения")
        time.sleep(2)
        return True
    return False


# ==========================================
# РЕЖИМ ЛЕЧЕНИЯ
# ==========================================
def determine_heal_state(screen_cv, region, cached_state=None):
    """Определить текущее состояние UI лечения (без новых скриншотов)."""
    # Reconnect всегда приоритет
    template_reconnect = get_template(RECONNECT_IMG)
    if template_reconnect is not None:
        coords, _ = find_on_screen(template_reconnect, screen_cv, region)
        if coords:
            return HealState.RECONNECT_POPUP

    # Оптимизация: если в ожидании лечения - проверяем только его завершение
    if cached_state == HealState.HEAL_ACTIVE:
        template_heal_town = get_template(HEAL_TOWN_IMG)
        if template_heal_town is not None:
            coords, _ = find_on_screen(template_heal_town, screen_cv, region)
            if coords:
                return HealState.HEAL_ICON_VISIBLE
        return HealState.HEAL_ACTIVE

    # Если была видна иконка помощи лечения - проверяем её
    if cached_state == HealState.HEAL_HELP_VISIBLE:
        template_help = get_template(HEAL_HELP_HANDS_IMG)
        if template_help is not None:
            coords, _ = find_on_screen(template_help, screen_cv, region)
            if coords:
                return HealState.HEAL_HELP_VISIBLE
        return HealState.HEAL_ACTIVE

    # Полная проверка
    checks = [
        (HEAL_HELP_HANDS_IMG, HealState.HEAL_HELP_VISIBLE),
        (HEAL_WAIT_IMG, HealState.HEAL_ACTIVE),
        (HEAL_BUTTON_IMG, HealState.HEAL_MENU_OPEN),
        (HEAL_TOWN_IMG, HealState.HEAL_ICON_VISIBLE),
        (WILD_EARTH_IMG, HealState.MAIN_SCREEN),
    ]
    
    for img_path, state in checks:
        template = get_template(img_path)
        if template is not None:
            coords, _ = find_on_screen(template, screen_cv, region)
            if coords:
                return state
    
    return HealState.UNKNOWN


def process_heal(screen_cv, region, last_heal_state):
    """
    Обработать одну итерацию лечения.
    Returns: обновленное last_heal_state
    """
    current_state = determine_heal_state(screen_cv, region, last_heal_state)
    
    if current_state != last_heal_state:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Лечение: {current_state.value}")
    
    if current_state == HealState.RECONNECT_POPUP:
        handle_reconnect(screen_cv, region)
        time.sleep(2)
        return None

    elif current_state == HealState.HEAL_ACTIVE:
        print("[HEAL] Лечение активно. Ожидание...5с")
        time.sleep(5)
        return current_state

    elif current_state == HealState.HEAL_HELP_VISIBLE:
        print("[HEAL] Найдена иконка помощи лечения! Нажимаем...")
        
        # Вариант 1+4: Повторные попытки нажатия с ожиданием
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            found, coords = find_and_click_cached(HEAL_HELP_HANDS_IMG, screen_cv, region)
            if found:
                print(f"[HEAL] Иконка помощи лечения нажата! (попытка {attempt})")
                time.sleep(1)
                # Возвращаем None чтобы на следующей итерации был новый скриншот
                return None
            else:
                print(f"[HEAL] Попытка {attempt}/{max_attempts} не удалась, пробуем ещё...")
                time.sleep(0.5)
                # Обновляем скриншот для следующей попытки
                window_new, region_new = get_window_region()
                if region_new:
                    screen_cv = take_screenshot(region_new)
        
        print("[HEAL] ⚠ Не удалось нажать иконку помощи после всех попыток")
        time.sleep(2)
        return None

    elif current_state == HealState.HEAL_MENU_OPEN:
        print("[HEAL] Меню лечения открыто. Нажимаем 'Лечить'...")
        found, _ = find_and_click_cached(HEAL_BUTTON_IMG, screen_cv, region)
        if found:
            print("[HEAL] Кнопка 'Лечить' нажата!")
            time.sleep(1)
            return HealState.HEAL_HELP_VISIBLE
        else:
            print("[HEAL] Кнопка 'Лечить' не найдена!")
            find_and_click_cached(WILD_EARTH_IMG, screen_cv, region)
            time.sleep(2)
            return None

    elif current_state == HealState.HEAL_ICON_VISIBLE:
        print("[HEAL] Найдена иконка лечения. Нажимаем...")
        found, _ = find_and_click_cached(HEAL_TOWN_IMG, screen_cv, region)
        if found:
            print("[HEAL] Иконка лечения нажата!")
            time.sleep(1)
            return HealState.HEAL_MENU_OPEN
        else:
            print("[HEAL] Иконка лечения не найдена!")
            find_and_click_cached(WILD_EARTH_IMG, screen_cv, region)
            time.sleep(2)
            return None

    elif current_state == HealState.MAIN_SCREEN:
        print("[HEAL] Главный экран. Ждём иконку лечения...")
        template_wait = get_template(HEAL_WAIT_IMG)
        if template_wait is not None:
            coords, _ = find_on_screen(template_wait, screen_cv, region)
            if coords:
                print("[HEAL] Обнаружен таймер лечения. Ожидание...")
                return HealState.HEAL_ACTIVE
        time.sleep(2)
        return current_state

    elif current_state == HealState.UNKNOWN:
        print("[HEAL] Неизвестное состояние. Возврат на главный экран...")
        find_and_click_cached(WILD_EARTH_IMG, screen_cv, region)
        time.sleep(3)
        return None

    return current_state


# ==========================================
# ОСНОВНОЙ ЦИКЛ
# ==========================================
def main():
    global window
    MODE = Mode.HEAL

    # Информация о мониторах
    print("=" * 60)
    print("[СИСТЕМА] Информация о мониторах:")
    get_monitors_info()
    print("=" * 60)

    window, region = get_window_region()
    if region is None:
        print("Не удалось определить окно BlueStacks. Запуск остановлен.")
        return

    print(f"\nОпределено окно BlueStacks: region={region}")
    
    # Проверка скриншота при старте
    if not verify_screenshot(region):
        print("\n[КРИТИЧЕСКАЯ ОШИБКА] Не удалось сделать скриншот. Запуск остановлен.")
        print("Убедитесь что:")
        print("  1. Окно BlueStacks развёрнуто и не свёрнуто")
        print("  2. Окно не перекрыто другими окнами")
        print("  3. BlueStacks находится на видимом мониторе")
        return
    
    print("\n" + "=" * 60)
    print("Запуск процесса лечения...")
    print("=" * 60)

    last_heal_state = None
    iteration = 0
    
    while True:
        try:
            iteration += 1
            
            # Переопределяем окно на случай изменений
            window, region = get_window_region()
            if region is None:
                time.sleep(5)
                continue
            
            # Активируем окно
            win32gui.SetForegroundWindow(window._hWnd)
            
            # ОДИН скриншот на итерацию
            screen_cv = take_screenshot(region)

            # В начале каждой итерации пробуем нажать кнопку помощи
            # Нашли — нажали, нет — продолжаем дальше
            found_help, _ = find_and_click_cached(HELP_HANDS_IMG, screen_cv, region, threshold=0.85)
            if found_help:
                print("[HELP] ✓ Кнопка помощи найдена и нажата!")
                # Новый скриншот т.к. экран изменился
                screen_cv = take_screenshot(region)

            # Основной цикл лечения
            last_heal_state = process_heal(screen_cv, region, last_heal_state)
            
            # Задержка между итерациями
            time.sleep(2)
            
        except Exception as e:
            print(f"[ОШИБКА] Произошла ошибка: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(5)
            last_heal_state = None


if __name__ == "__main__":
    main()
