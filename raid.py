# ==========================================
# ЛОГИКА РЕЙДОВ
# ==========================================

import os
import cv2
import numpy as np
import pyautogui
import time

from config import *
from utils import *


# ==========================================
# ПОДСЧЁТ АТАК
# ==========================================
def count_attack_mentions(screen_cv):
    """
    Посчитать количество упоминаний 'Атаки' на экране.
    Возвращает: int (количество уникальных найденных совпадений)
    """
    attack_text_img = RAID_ATTACK_IMG

    if not os.path.exists(attack_text_img):
        return 0

    attack_text_template = get_template(attack_text_img)
    if attack_text_template is None:
        return 0

    res = cv2.matchTemplate(screen_cv, attack_text_template, cv2.TM_CCOEFF_NORMED)
    threshold = 0.6
    loc = np.where(res >= threshold)

    min_distance = 15
    unique_points = []

    for pt in zip(*loc[::-1]):
        is_new = True
        for existing_pt in unique_points:
            distance = ((pt[0] - existing_pt[0])**2 + (pt[1] - existing_pt[1])**2)**0.5
            if distance < min_distance:
                is_new = False
                break
        if is_new:
            unique_points.append(pt)

    return len(unique_points)


# ==========================================
# СКРОЛЛИНГ СПИСКА РЕЙДОВ
# ==========================================
def check_and_scroll_for_attack(screen_cv, region, log_details=True):
    """
    Проверить количество атак и сделать скролл если нужно.
    Возвращает: (after_scroll: bool, attack_count: int)
    """
    attack_count = count_attack_mentions(screen_cv)

    if log_details:
        print(f"[RAID] Найдено упоминаний 'Атака': {attack_count}")

    needs_scroll = attack_count > RAID_SCROLL_THRESHOLD

    if needs_scroll:
        center_x = region[0] + region[2] // 2
        center_y = region[1] + region[3] // 2
        swipe_distance = int(region[3] * 0.6)
        start_y = center_y + int(region[3] * 0.25)

        print(f"[RAID] СКРОЛЛ! Пролистываем вниз")

        pyautogui.moveTo(center_x, start_y, duration=0.1)
        time.sleep(0.1)
        pyautogui.drag(0, -swipe_distance, duration=0.3, button='left')
        time.sleep(0.3)

        window, region_new = get_window_region()
        if region_new:
            screen_cv = take_screenshot(window, region_new)
            attack_after_scroll = count_attack_mentions(screen_cv)
            print(f"[RAID] После скролла 'Атака': {attack_after_scroll}")

            if attack_after_scroll > RAID_SCROLL_THRESHOLD:
                print(f"[RAID] Всё ещё много атак: {attack_after_scroll}, скроллим ещё...")
                pyautogui.moveTo(center_x, start_y, duration=0.1)
                time.sleep(0.1)
                pyautogui.drag(0, -int(swipe_distance * 0.7), duration=0.3, button='left')
                time.sleep(0.3)

                window, region_new = get_window_region()
                if region_new:
                    screen_cv = take_screenshot(window, region_new)
                    attack_after_second_scroll = count_attack_mentions(screen_cv)
                    print(f"[RAID] После второго скролла 'Атака': {attack_after_second_scroll}")
                    return False, attack_after_second_scroll
            else:
                return False, attack_after_scroll

        return False, attack_count

    return False, attack_count


# ==========================================
# НАВИГАЦИЯ К ОКНУ РЕЙДОВ
# ==========================================
def navigate_to_reid_window():
    """
    Навигация к окну рейдов через Союз -> Новости -> Рейды.
    Возвращает: True если успешно
    """
    print("[RAID] Навигация к окну рейдов...")

    window, region = get_window_region()
    if region is None:
        print("[RAID] ОШИБКА: Не удалось получить область окна")
        return False

    screen_cv = take_screenshot(window, region)

    # Если находимся в попапе лечения — сначала закрываем его через back/close
    heal_btn_coords, _ = find_on_screen(get_template(HEAL_BUTTON_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if heal_btn_coords:
        print("[RAID] Обнаружен попап лечения — закрываем перед навигацией.")
        find_and_click(BACK_IMG, screen_cv, region)
        time.sleep(0.3)
        screen_cv = take_screenshot(window, region)

    # Проверим, не находимся ли мы уже в окне рейдов
    reid_active, _ = find_on_screen(get_template(RAID_ACTIVE_IMG), screen_cv, region, threshold=NAVIGATION_THRESHOLD)
    reid_not_active, _ = find_on_screen(get_template(RAID_NOT_ACTIVE_IMG), screen_cv, region, threshold=NAVIGATION_THRESHOLD)
    if reid_active or reid_not_active:
        print("[RAID] Уже в окне рейдов.")
        return True

    if find_and_click(SOUZ_IMG, screen_cv, region, threshold=NAVIGATION_THRESHOLD):
        time.sleep(0.3)
    else:
        # Fallback с пониженным порогом
        if find_and_click(SOUZ_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD):
            time.sleep(0.3)
        else:
            print("[RAID] ✗ Кнопка 'Союз' НЕ найдена")
            return False

    screen_cv = take_screenshot(window, region)

    if find_and_click(NEWS_IMG, screen_cv, region, threshold=NAVIGATION_THRESHOLD):
        print("[RAID] ✓ Нажата кнопка 'Новости'")
        time.sleep(0.3)
    else:
        if find_and_click(NEWS_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD):
            print("[RAID] ✓ Нажата кнопка 'Новости' (fallback)")
            time.sleep(0.3)
        else:
            print("[RAID] ✗ Кнопка 'Новости' НЕ найдена")
            return False

    screen_cv = take_screenshot(window, region)

    if find_and_click(RAID_NOT_ACTIVE_IMG, screen_cv, region, threshold=NAVIGATION_THRESHOLD):
        time.sleep(0.3)
        print("[RAID] Переход в рейды завершен")
        return True
    else:
        print("[RAID] ✗ Переход в рейды НЕ удался")
        return False


# ==========================================
# ОПРЕДЕЛЕНИЕ СОСТОЯНИЯ РЕЙДА
# ==========================================
def determine_raid_state(screen_cv, region):
    """
    Определить текущее состояние рейда.
    Возвращает: RaidState
    """
    coords, _ = find_on_screen(get_template(RECONNECT_IMG), screen_cv, region)
    if coords:
        return RaidState.RECONNECT_POPUP

    coords, _ = find_on_screen(get_template(RECONNECT_REPEAT_IMG), screen_cv, region)
    if coords:
        return RaidState.RECONNECT_REPEAT_POPUP

    coords, _ = find_on_screen(get_template(RAID_FULL_IMG), screen_cv, region)
    if coords:
        return RaidState.RAID_FULL

    coords, _ = find_on_screen(get_template(RAID_NO_FREE_SPACE_IMG), screen_cv, region)
    if coords:
        return RaidState.NO_FREE_SPACE

    coords, conf = find_on_screen(get_template(RAID_ACTIVE_IMG), screen_cv, region, threshold=NAVIGATION_THRESHOLD)
    reid_active_found = coords is not None

    coords_nav, conf_nav = find_on_screen(get_template(RAID_NOT_ACTIVE_IMG), screen_cv, region, threshold=NAVIGATION_THRESHOLD)
    reid_not_active_found = coords_nav is not None

    if reid_not_active_found:
        return RaidState.REID_TAB_NOT_ACTIVE

    coords, conf = find_on_screen(get_template(RAID_PLUS_IMG), screen_cv, region, threshold=CONFIDENCE_HIGH)
    plus_found = coords is not None
    if plus_found:
        return RaidState.PLUS_VISIBLE

    attack_count = count_attack_mentions(screen_cv)

    coords, conf = find_on_screen(get_template(RAID_MARCH_IMG), screen_cv, region)
    if coords:
        return RaidState.MARCH_VISIBLE

    if attack_count > 2:
        return RaidState.NEEDS_SCROLL
    if attack_count > 0:
        return RaidState.RAID_IN_PROGRESS
    else:
        if not reid_active_found and not reid_not_active_found:
            return RaidState.NAVIGATION_NEEDED
        if plus_found:
            return RaidState.NO_REIDS
        else:
            return RaidState.RAID_COMPLETED


# ==========================================
# ОБРАБОТКА СОСТОЯНИЙ РЕЙДА
# ==========================================
def process_raid(screen_cv, region, last_raid_state, last_join_time, raid_joined_at_least_once, window):
    """
    Обработать текущее состояние рейда.
    Возвращает: (новое_состояние, новое_время, флаг_присоединения)
    :param window:
    """
    current_state = determine_raid_state(screen_cv, region)

    if current_state != last_raid_state:
        print(f"[RAID] Состояние: {current_state.value}")

    if current_state == RaidState.RECONNECT_POPUP:
        handle_reconnect(screen_cv, region)
        return None, last_join_time, raid_joined_at_least_once

    if current_state == RaidState.RECONNECT_REPEAT_POPUP:
        handle_reconnect_repeat(screen_cv, region)
        return None, last_join_time, raid_joined_at_least_once

    if current_state == RaidState.NAVIGATION_NEEDED:
        success = navigate_to_reid_window()
        if not success:
            print("[RAID] Навигация к рейдам не удалась. Завершаем режим RAID.")
            return RaidState.RAID_COMPLETED, last_join_time, raid_joined_at_least_once
        return None, last_join_time, raid_joined_at_least_once

    if current_state == RaidState.REID_TAB_NOT_ACTIVE:
        found, _ = find_and_click(RAID_NOT_ACTIVE_IMG, screen_cv, region)
        if found:
            return RaidState.REID_WINDOW_ACTIVE, last_join_time, raid_joined_at_least_once
        print("[RAID] Вкладка рейдов не активна и не нажалась. Завершаем режим RAID.")
        return RaidState.RAID_COMPLETED, last_join_time, raid_joined_at_least_once

    if current_state == RaidState.NO_FREE_SPACE:
        clicked, _ = find_and_click(RAID_OK_IMG, screen_cv, region)
        if not clicked:
            find_and_click(BACK_IMG, screen_cv, region)
            find_and_click(CLOSE_IMG, screen_cv, region)
        time.sleep(0.5)
        return RaidState.RAID_COMPLETED, time.time(), raid_joined_at_least_once

    if current_state == RaidState.RAID_FULL:
        find_and_click(RAID_OK_IMG, screen_cv, region)
        time.sleep(0.5)
        return RaidState.RAID_COMPLETED, time.time(), raid_joined_at_least_once

    if current_state == RaidState.NO_REIDS:
        village_coords, _ = find_on_screen(get_template(VILLAGE_IMG), screen_cv, region)
        if village_coords:
            navigate_to_reid_window()
            return None, last_join_time, raid_joined_at_least_once
        return RaidState.NO_REIDS, time.time(), raid_joined_at_least_once

    if current_state == RaidState.NEEDS_SCROLL:
        check_and_scroll_for_attack(screen_cv, region)
        return RaidState.RAID_IN_PROGRESS, time.time(), raid_joined_at_least_once

    if current_state == RaidState.RAID_IN_PROGRESS:
        return current_state, time.time(), raid_joined_at_least_once

    if current_state == RaidState.PLUS_VISIBLE:
        found, _ = find_and_click(RAID_PLUS_IMG, screen_cv, region)
        if found:
            time.sleep(0.5)
            screen_cv = take_screenshot(window, region)
            found2, _ = find_and_click(RAID_MARCH_IMG, screen_cv, region)
            if found2:
                time.sleep(0.5)
                screen_cv = take_screenshot(window, region)
                no_space_found, _ = find_and_click(RAID_NO_FREE_SPACE_IMG, screen_cv, region)
                if no_space_found:
                    time.sleep(0.5)
                    screen_cv = take_screenshot(window, region)
                    find_and_click(RAID_OK_IMG, screen_cv, region)
                    return RaidState.NO_FREE_SPACE, time.time(), True
                return RaidState.RAID_IN_PROGRESS, time.time(), True
            return None, last_join_time, raid_joined_at_least_once
        return RaidState.NO_REIDS, time.time(), True

    if current_state == RaidState.MARCH_VISIBLE:
        screen_cv = take_screenshot(window, region)
        found2, _ = find_and_click(RAID_MARCH_IMG, screen_cv, region)
        if found2:
            time.sleep(0.5)
            screen_cv = take_screenshot(window, region)
            
            # Check for OK button immediately after marching (e.g., "raid full" confirmation)
            ok_found, _ = find_and_click(RAID_OK_IMG, screen_cv, region)
            if ok_found:
                time.sleep(0.5)
                screen_cv = take_screenshot(window, region)
                return RaidState.NO_FREE_SPACE, time.time(), True
            
            # Original logic: check for "no free space" popup
            no_space_found, _ = find_and_click(RAID_NO_FREE_SPACE_IMG, screen_cv, region)
            if no_space_found:
                time.sleep(0.5)
                screen_cv = take_screenshot(window, region)
                find_and_click(RAID_OK_IMG, screen_cv, region)
                return RaidState.NO_FREE_SPACE, time.time(), True
            return RaidState.RAID_IN_PROGRESS, time.time(), True

    return current_state, last_join_time, raid_joined_at_least_once


# ==========================================
# ПРОВЕРКА КНОПОК ПРИСОЕДИНЕНИЯ К РЕЙДУ
# ==========================================
def check_for_raid_button(screen_cv, region):
    """
    Проверить наличие кнопок присоединения к рейду.
    Возвращает: True если найдена и нажата
    """
    # Не ищем рейды если открыт попап лечения — heal_button или heal_free_button
    heal_button = get_template(HEAL_BUTTON_IMG)
    heal_free_button = get_template(HEAL_FREE_BUTTON_IMG)
    if heal_button is not None:
        coords, _ = find_on_screen(heal_button, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if coords:
            return False
    if heal_free_button is not None:
        coords, _ = find_on_screen(heal_free_button, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
        if coords:
            return False

    # Проверка первой кнопки
    found, conf = find_on_screen(get_template(RAID_HAVE_TO_CONNECT_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if found:
        print(f"[RAID] Найден рейд (RAID_HAVE_TO_CONNECT_IMG, conf={conf:.3f})")
        find_and_click(RAID_HAVE_TO_CONNECT_IMG, screen_cv, region, CONFIDENCE_THRESHOLD)
        return True

    # Проверка второй кнопки
    found, conf = find_on_screen(get_template(RAID_HAVE_TO_CONNECT_2_IMG), screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if found:
        print(f"[RAID] Найден рейд (RAID_HAVE_TO_CONNECT_2_IMG, conf={conf:.3f})")
        find_and_click(RAID_HAVE_TO_CONNECT_2_IMG, screen_cv, region, CONFIDENCE_THRESHOLD)
        return True

    return False
