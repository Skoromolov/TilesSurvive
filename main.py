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
from logger import logger  # Импортируем логгер


# ==========================================
# ОСНОВНОЙ ЦИКЛ
# ==========================================
def main():
    logger.info("=" * 60)
    logger.info("[СИСТЕМА] Запуск Heal and Raid Bot")
    logger.info("=" * 60)

    # Создать папку для отладочных скриншотов
    os.makedirs(DEBUG_SCREENSHOTS_DIR, exist_ok=True)

    # Получить окно
    window, region = get_window_region()
    if region is None:
        logger.error("[СИСТЕМА] Не удалось определить окно BlueStacks. Запуск остановлен.")
        return

    logger.info(f"[СИСТЕМА] Окно BlueStacks: region={region}")

    # Инициализация переменных состояния
    last_heal_state = None
    last_raid_state = None
    last_gold_state = None
    current_mode = MainMode.HEAL

    raid_joined_at_least_once = False
    raid_start_time = None

    gold_start_time = None
    gold_exit_state = None
    gold_exiting = False

    while True:
        try:
            # Обновить окно и область
            window, region = get_window_region()
            if region is None:
                time.sleep(10)
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
                logger.info("[СИСТЕМА] Обработано переподключение. Завершение.")
                return

            if handle_reconnect_repeat(screen_cv, region):
                logger.info("[СИСТЕМА] Обработано повторное переподключение. Завершение.")
                return

            # Режим быстрого лечения с карты мира (высший приоритет, игнорирует всё остальное)
            if FAST_HEAL_FROM_MAP_ENABLED:
                last_heal_state = process_fast_heal_from_map(screen_cv, region, last_heal_state)
                continue

            # Принудительный режим RAID
            if FORCE_RAID_ONLY and not FORCE_HEAL_ONLY:
                current_raid_state = determine_raid_state(screen_cv, region)
                logger.info(f"[MAIN] Принудительный режим RAID: {current_raid_state.value}")
                last_raid_state, last_join_time, raid_joined_at_least_once = process_raid(
                    screen_cv, region, last_raid_state, None, raid_joined_at_least_once, window
                )
                continue

            # Режим HEAL
            if (current_mode == MainMode.HEAL) or FORCE_HEAL_ONLY:
                check_and_click_help_button(screen_cv, region)
                last_heal_state = process_heal(screen_cv, region, last_heal_state, window)

                if FORCE_HEAL_ONLY:
                    # check_and_click_help_button(screen_cv, region)
                    # last_heal_state = process_heal(screen_cv, region, last_heal_state, window)
                    # # Золото: только если включено и пора — после лечения
                    # if GOLD_ENABLED and (should_do_gold() or gold_mission_should_recall()):
                    #     logger.info("[MAIN] Переключение в режим GOLD (FORCE_HEAL_ONLY)")
                    #     current_mode = MainMode.GOLD
                    #     last_gold_state = None
                    #     reset_gold_context()
                    #     time.sleep(0.2)
                    #     gold_start_time = time.time()
                    #     continue
                    continue

                # Потом проверяем рейды
                if check_for_raid_button(screen_cv, region):
                    logger.info("[MAIN] Переключение в режим RAID")
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
                    logger.info("[MAIN] Переключение в режим GOLD")
                    current_mode = MainMode.GOLD
                    last_gold_state = None
                    reset_gold_context()
                    # time.sleep(0.2)
                    gold_start_time = time.time()
                    continue
                continue

            # Режим GOLD
            elif current_mode == MainMode.GOLD:
                # Обрабатываем режим GOLD через вынесенную функцию
                result = handle_gold_mode(screen_cv, region, window, last_gold_state, gold_start_time, gold_exit_state, gold_exiting)
                next_mode, last_gold_state, gold_start_time, gold_exit_state, gold_exiting = result
                
                if next_mode == MainMode.HEAL:
                    current_mode = MainMode.HEAL
                    continue

            # Режим RAID
            elif current_mode == MainMode.RAID:
                # Защитный таймаут: если режим RAID затянулся на RAID_JOIN_TIMEOUT — возвращаемся к лечению
                now = time.time()
                elapsed = now - raid_start_time if raid_start_time else None
                logger.debug(f"[DEBUG RAID] raid_start_time={raid_start_time}, elapsed={elapsed}, timeout={RAID_JOIN_TIMEOUT}")
                if raid_start_time and (now - raid_start_time) >= RAID_JOIN_TIMEOUT:
                    logger.info(f"[ТАЙМЕР] Рейд затянулся > {RAID_JOIN_TIMEOUT} сек. Возвращаемся к лечению.")
                    current_mode = MainMode.HEAL
                    last_raid_state = None
                    raid_start_time = None
                    raid_joined_at_least_once = False
                    raid_terminal_since = None
                    continue

                # Если ещё стартуем и не определён state
                if last_raid_state is None:
                    current_raid_state = determine_raid_state(screen_cv, region)
                    logger.info(f"[MAIN] RAID: стартовое состояние {current_raid_state.value}")
                    last_raid_state = current_raid_state

                # Обработать одно состояние
                current_raid_state = determine_raid_state(screen_cv, region)
                if current_raid_state != last_raid_state:
                    logger.info(f"[MAIN] RAID: {current_raid_state.value}")

                last_raid_state, last_join_time, raid_joined_at_least_once = process_raid(
                    screen_cv, region, last_raid_state, last_join_time, raid_joined_at_least_once, window
                )

                # Защита от зависания в NO_FREE_SPACE / NO_REIDS
                # terminal_states = (RaidState.NO_FREE_SPACE, RaidState.NO_REIDS, RaidState.RAID_COMPLETED)
                # if last_raid_state in terminal_states:
                #     if raid_terminal_since is None:
                #         raid_terminal_since = time.time()
                #     elif time.time() - raid_terminal_since > 30:
                #         logger.info("[MAIN] RAID застрял в терминальном состоянии > 30 сек. Клик по центру и возврат к HEAL.")
                #         center_x = region[0] + region[2] // 2
                #         center_y = region[1] + region[3] // 2
                #         pyautogui.click(center_x, center_y)
                #         time.sleep(0.5)
                #         current_mode = MainMode.HEAL
                #         last_raid_state = None
                #         raid_start_time = None
                #         raid_joined_at_least_once = False
                #         raid_terminal_since = None
                #         continue
                # else:
                #     raid_terminal_since = None

                # Если все рейды завершены — возвращаемся к лечению
                if last_raid_state == RaidState.RAID_COMPLETED:
                    logger.info("[MAIN] Рейды завершены, возврат к лечению")
                    current_mode = MainMode.HEAL
                    last_raid_state = None
                    raid_start_time = None
                    raid_joined_at_least_once = False
                    continue

                # Если рейдов больше нет — тоже возвращаемся
                if last_raid_state == RaidState.NO_REIDS:
                    logger.info("[MAIN] Рейды отсутствуют, возврат к лечению")
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
            logger.error(f"[ОШИБКА] {e}", exc_info=True)
            time.sleep(10)


# ==========================================
# ТОЧКА ВХОДА
# ==========================================
if __name__ == "__main__":
    main()