#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Heal and Raid Bot - Основной скрипт
Автоматизация лечения войск и участия в рейдах
"""

import sys
sys.dont_write_bytecode = True  # отключить кеширование .pyc (эквивалент python -B)

import time
import os
import win32gui
import pyautogui

from config import *
from utils import *
from heal import *
from raid import *
from gold import *


# ==========================================
# ОСНОВНОЙ ЦИКЛ
# ==========================================
def main():
    print("=" * 60)
    print("[СИСТЕМА] Запуск Heal and Raid Bot")
    print("=" * 60)

    # Создать папку для отладочных скриншотов
    os.makedirs(DEBUG_SCREENSHOTS_DIR, exist_ok=True)

    # Получить окно
    window, region = get_window_region()
    if region is None:
        print("[СИСТЕМА] Не удалось определить окно BlueStacks. Запуск остановлен.")
        return

    print(f"[СИСТЕМА] Окно BlueStacks: region={region}")

    # Инициализация переменных состояния
    last_heal_state = None
    last_raid_state = None
    last_gold_state = None
    raid_nav_grace_until = time.time() + 1
    current_mode = MainMode.HEAL

    raid_start_time = None
    raid_joined_at_least_once = False
    raid_nav_grace_until = 0
    raid_start_time = None
    raid_terminal_since = None
    gold_start_time = None
    gold_exit_state = None
    gold_exiting = False

    while True:
        try:
            # Обновить окно и область
            window, region = get_window_region()
            if region is None:
                time.sleep(5)
                continue

            # Активировать окно
            win32gui.SetForegroundWindow(window._hWnd)

            # Сделать скриншот
            screen_cv = take_screenshot(window, region)

            # Обрезаем правую панель инструментов BlueStacks (~40 px),
            # чтобы шаблоны не матчились на toolbar иконках (like, share и т.д.)
            TOOLBAR_WIDTH = 40
            if screen_cv.shape[1] > TOOLBAR_WIDTH:
                screen_cv = screen_cv[:, :-TOOLBAR_WIDTH]
                region = (region[0], region[1], region[2] - TOOLBAR_WIDTH, region[3])

            # Глобальная проверка reconnect (завершает программу)
            if handle_reconnect(screen_cv, region):
                print("[СИСТЕМА] Обработано переподключение. Завершение.")
                return

            if handle_reconnect_repeat(screen_cv, region):
                print("[СИСТЕМА] Обработано повторное переподключение. Завершение.")
                return

            # Режим быстрого лечения с карты мира (высший приоритет, игнорирует всё остальное)
            if FAST_HEAL_FROM_MAP_ENABLED:
                last_heal_state = process_fast_heal_from_map(screen_cv, region, last_heal_state)
                time.sleep(1)
                continue

            # Принудительный режим RAID
            if FORCE_RAID_ONLY and not FORCE_HEAL_ONLY:
                current_raid_state = determine_raid_state(screen_cv, region)
                print(f"[MAIN] Принудительный режим RAID: {current_raid_state.value}")
                last_raid_state, last_join_time, raid_joined_at_least_once = process_raid(
                    screen_cv, region, last_raid_state, last_join_time, raid_joined_at_least_once, window
                )
                continue

            # Режим HEAL
            if (current_mode == MainMode.HEAL) or FORCE_HEAL_ONLY:
                if FORCE_HEAL_ONLY:
                    check_and_click_help_button(screen_cv, region)
                    last_heal_state = process_heal(screen_cv, region, last_heal_state, window)
                    # Золото: только если включено и пора — после лечения
                    if GOLD_ENABLED and (should_do_gold() or gold_mission_should_recall()):
                        print("[MAIN] Переключение в режим GOLD (FORCE_HEAL_ONLY)")
                        current_mode = MainMode.GOLD
                        last_gold_state = None
                        reset_gold_context()
                        time.sleep(0.2)
                        gold_start_time = time.time()
                        continue
                    continue

                # Сначала лечим
                check_and_click_help_button(screen_cv, region)
                last_heal_state = process_heal(screen_cv, region, last_heal_state, window)

                # Если process_heal открыл меню лечения, daily-окна, лечение в процессе или не завершил обработку —
                # не переключаемся в RAID/GOLD
                heal_in_progress_states = {
                    HealState.HEAL_MENU_OPEN,
                    HealState.HEAL_WAIT,
                    HealState.BOOK,
                    HealState.ADVENTURE,
                    HealState.ADVENTURE_GET,
                    HealState.ADVENTURE_CONFIRM,
                }
                if last_heal_state in heal_in_progress_states:
                    print("[MAIN] Обработка лечения/daily ещё не завершена — продолжаем.")
                    continue

                # Ждём закрытия меню лечения и обновляем скриншот
                time.sleep(0.5)
                screen_cv = take_screenshot(window, region)

                # Не переключаемся в RAID/GOLD если меню лечения открыто —
                # нужно сначала нажать кнопку лечения
                heal_menu_open = False
                hb_coords, _ = find_on_screen(get_template(HEAL_BUTTON_IMG), screen_cv, region, threshold=0.70)
                if hb_coords:
                    heal_menu_open = True
                hfb_coords, _ = find_on_screen(get_template(HEAL_FREE_BUTTON_IMG), screen_cv, region, threshold=0.70)
                if hfb_coords:
                    heal_menu_open = True

                if heal_menu_open:
                    # Защита от зацикливания: счётчик попыток лечения
                    if not hasattr(main, '_heal_menu_tries'):
                        main._heal_menu_tries = 0
                    main._heal_menu_tries += 1
                    if main._heal_menu_tries > 3:
                        print(f"[MAIN] Лечение не закрывается {main._heal_menu_tries} раз. Закрываем через back и пропускаем.")
                        find_and_click(BACK_IMG, screen_cv, region)
                        main._heal_menu_tries = 0
                        time.sleep(0.5)
                        # Принудительно проверяем рейды/золото
                        screen_cv = take_screenshot(window, region)
                    else:
                        print("[MAIN] Меню лечения открыто — лечим перед переключением режима.")
                        last_heal_state = process_heal(screen_cv, region, last_heal_state, window)
                        time.sleep(0.3)
                        continue

                # Потом проверяем рейды
                if check_for_raid_button(screen_cv, region):
                    print("[MAIN] Переключение в режим RAID")
                    current_mode = MainMode.RAID
                    last_gold_state = None
                    raid_start_time = time.time()
                    raid_joined_at_least_once = False
                    last_join_time = time.time()
                    raid_nav_grace_until = time.time() + 10
                    last_raid_state = None
                    continue

                # Потом золото — если включено и пора
                if GOLD_ENABLED and (should_do_gold() or gold_mission_should_recall()):
                    print("[MAIN] Переключение в режим GOLD")
                    current_mode = MainMode.GOLD
                    last_gold_state = None
                    reset_gold_context()
                    time.sleep(0.2)
                    gold_start_time = time.time()
                    continue

                continue

            # Режим GOLD
            elif current_mode == MainMode.GOLD:
                # Защитный таймаут
                if gold_start_time and (time.time() - gold_start_time) >= GOLD_TIMEOUT:
                    print(f"[ТАЙМЕР] Золото затянулось > {GOLD_TIMEOUT} сек. Возвращаемся к лечению.")
                    current_mode = MainMode.HEAL
                    last_gold_state = None
                    gold_start_time = None
                    continue

                # Если ещё стартуем и не определён state
                if last_gold_state is None:
                    current_gold_state = determine_gold_state(screen_cv, region)
                    print(f"[MAIN] GOLD: стартовое состояние {current_gold_state.value}")
                    last_gold_state = current_gold_state

                # Обработать одно состояние
                if not gold_exiting:
                    current_gold_state = determine_gold_state(screen_cv, region)
                    if current_gold_state != last_gold_state:
                        if current_gold_state.value:
                            print(f"[MAIN] GOLD: {current_gold_state.value}")
                        else:
                            print(f"[MAIN] GOLD: {current_gold_state}")
                    last_gold_state = process_gold(screen_cv, region, last_gold_state, window)

                # Если добыча завершена — выходим
                if last_gold_state == GoldState.COMPLETED:
                    print("[MAIN] Золотодобыча завершена, возврат к лечению")
                    current_mode = MainMode.HEAL
                    last_gold_state = None
                    gold_exit_state = None
                    gold_start_time = None
                    gold_exiting = False
                    continue

            # Режим RAID
            elif current_mode == MainMode.RAID:
                # Защитный таймаут: если режим RAID затянулся на RAID_JOIN_TIMEOUT — возвращаемся к лечению
                now = time.time()
                elapsed = now - raid_start_time if raid_start_time else None
                print(f"[DEBUG RAID] raid_start_time={raid_start_time}, elapsed={elapsed}, timeout={RAID_JOIN_TIMEOUT}")
                if raid_start_time and (now - raid_start_time) >= RAID_JOIN_TIMEOUT:
                    print(f"[ТАЙМЕР] Рейд затянулся > {RAID_JOIN_TIMEOUT} сек. Возвращаемся к лечению.")
                    current_mode = MainMode.HEAL
                    last_raid_state = None
                    raid_start_time = None
                    raid_joined_at_least_once = False
                    raid_terminal_since = None
                    continue

                # Если ещё стартуем и не определён state
                if last_raid_state is None:
                    current_raid_state = determine_raid_state(screen_cv, region)
                    print(f"[MAIN] RAID: стартовое состояние {current_raid_state.value}")
                    last_raid_state = current_raid_state

                # Обработать одно состояние
                current_raid_state = determine_raid_state(screen_cv, region)
                if current_raid_state != last_raid_state:
                    print(f"[MAIN] RAID: {current_raid_state.value}")

                last_raid_state, last_join_time, raid_joined_at_least_once = process_raid(
                    screen_cv, region, last_raid_state, last_join_time, raid_joined_at_least_once, window
                )

                # Защита от зависания в NO_FREE_SPACE / NO_REIDS
                terminal_states = (RaidState.NO_FREE_SPACE, RaidState.NO_REIDS, RaidState.RAID_COMPLETED)
                if last_raid_state in terminal_states:
                    if raid_terminal_since is None:
                        raid_terminal_since = time.time()
                    elif time.time() - raid_terminal_since > 30:
                        print("[MAIN] RAID застрял в терминальном состоянии > 30 сек. Клик по центру и возврат к HEAL.")
                        center_x = region[0] + region[2] // 2
                        center_y = region[1] + region[3] // 2
                        pyautogui.click(center_x, center_y)
                        time.sleep(0.5)
                        current_mode = MainMode.HEAL
                        last_raid_state = None
                        raid_start_time = None
                        raid_joined_at_least_once = False
                        raid_terminal_since = None
                        continue
                else:
                    raid_terminal_since = None

                # Если все рейды завершены — возвращаемся к лечению
                if last_raid_state == RaidState.RAID_COMPLETED:
                    print("[MAIN] Рейды завершены, возврат к лечению")
                    current_mode = MainMode.HEAL
                    last_raid_state = None
                    raid_start_time = None
                    raid_joined_at_least_once = False
                    continue

                # Если рейдов больше нет — тоже возвращаемся
                if last_raid_state == RaidState.NO_REIDS:
                    print("[MAIN] Рейды отсутствуют, возврат к лечению")
                    current_mode = MainMode.HEAL
                    last_raid_state = None
                    raid_start_time = None
                    raid_joined_at_least_once = False
                    continue

            if current_mode == MainMode.GOLD:
                time.sleep(GOLD_LOOP_DELAY)
            else:
                time.sleep(1)

        except Exception as e:
            print(f"[ОШИБКА] {e}")
            time.sleep(5)


# ==========================================
# ТОЧКА ВХОДА
# ==========================================
if __name__ == "__main__":
    main()
