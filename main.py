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
import shutil
import win32gui

# Удаляем stale __pycache__, иначе старые .pyc подгружаются даже с dont_write_bytecode
if os.path.isdir('__pycache__'):
    shutil.rmtree('__pycache__', ignore_errors=True)

import pyautogui

from config import *
from utils import *
from heal import *
from raid import *
from gold import *
from adventure import process_adventure_state, determine_adventure_state, reset_adventure_context
from logger import logger  # Импортируем логгер


# Вывод PID процесса при старте
_pid = os.getpid()
print(f"[MAIN] Запуск бота, PID={_pid}")
logger.info(f"[MAIN] Запуск бота, PID={_pid}")


# ==========================================
# ВЫХОД В ОКНО ПОСЕЛЕНИЯ ПЕРЕД DEFAULT
# ==========================================
def _return_to_main_screen(window, region, reason):
    """Убедиться, что бот вышел в окно поселения, перед возвратом в DEFAULT."""
    logger.info(f"[MAIN] {reason}: запускаем ensure_exit_to_main_screen")
    ensure_exit_to_main_screen(window, region)


def _collect_default_activities(screen_cv, region, window):
    """
    Собрать книги и почту на главном экране поселения.
    Выполняется в DEFAULT перед переключением в HEAL.
    Возвращает True, если была нажата хотя бы одна активность.
    """
    collected = False

    found, _ = find_and_click(BOOK_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if found:
        logger.info("[DEFAULT] ✓ Книга собрана.")
        collected = True

    found, _ = find_and_click(MAIL_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)
    if found:
        logger.info("[DEFAULT] ✓ MAIL нажато, ждём попап подтверждения.")
        collected = True
        time.sleep(1)
        if window is not None:
            screen_cv = take_screenshot(window, region)
        find_and_click(CONFIRM_BUTTON_IMG, screen_cv, region, threshold=CONFIDENCE_THRESHOLD)

    return collected


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
    last_adventure_state = None
    current_mode = MainMode.DEFAULT  # Всегда стартуем с дефолтного режима

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
            if screen_cv is None:
                logger.warning("[MAIN] Не удалось получить скриншот, пропускаем итерацию.")
                time.sleep(1)
                continue

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

            # --- DEFAULT: выбор режима на основе экрана и настроек ---
            if current_mode == MainMode.DEFAULT:
                logger.debug("[MAIN] DEFAULT: выбор режима")

                # 1. Принудительный режим RAID
                if FORCE_RAID_ONLY and not FORCE_HEAL_ONLY:
                    logger.info("[MAIN] Переключение в принудительный режим RAID")
                    current_mode = MainMode.RAID
                    last_raid_state = None
                    raid_start_time = time.time()
                    raid_joined_at_least_once = False
                    last_join_time = time.time()
                    continue

                # 2. Принудительный режим ADVENTURE
                if FORCE_ADVENTURE_ONLY and not FORCE_HEAL_ONLY:
                    logger.info("[MAIN] Переключение в принудительный режим ADVENTURE")
                    current_mode = MainMode.ADVENTURE
                    last_adventure_state = None
                    reset_adventure_context()
                    continue

                # 3. Лечение если форсировано
                if FORCE_HEAL_ONLY:
                    logger.info("[MAIN] Переключение в принудительный режим HEAL")
                    current_mode = MainMode.HEAL
                    last_heal_state = None
                    continue

                # 4. Проверяем рейды
                if check_for_raid_button(screen_cv, region):
                    logger.info("[MAIN] Переключение в режим RAID (найдена кнопка рейда)")
                    current_mode = MainMode.RAID
                    last_gold_state = None
                    raid_start_time = time.time()
                    raid_joined_at_least_once = False
                    last_join_time = time.time()
                    last_raid_state = None
                    continue

                # 5. Проверяем приключения
                if ADVENTURE_ENABLED:
                    adventure_state = determine_adventure_state(screen_cv, region)
                    if adventure_state == AdventureState.ADVENTURE:
                        logger.info("[MAIN] Переключение в режим ADVENTURE (авто)")
                        current_mode = MainMode.ADVENTURE
                        last_adventure_state = None
                        reset_adventure_context()
                        continue

                # 6. Проверяем золото
                if GOLD_ENABLED and (should_do_gold() or gold_mission_should_recall()):
                    logger.info("[MAIN] Переключение в режим GOLD")
                    current_mode = MainMode.GOLD
                    last_gold_state = None
                    reset_gold_context()
                    gold_start_time = time.time()
                    continue

                # 6a. Активная золотодобыча без необходимости отзыва — убеждаемся, что бот в поселении,
                # но не блокируем сбор и HEAL. Один раз выходим на главный экран, затем падаем
                # в обычный дефолтный поток (книги/почта/HEAL/raid), пока не пришло время recall.
                if GOLD_ENABLED and gold_mission_active() and not gold_mission_should_recall():
                    if not is_at_main_screen_village(screen_cv, region):
                        logger.info("[MAIN] Активная золотодобыча: выходим в поселение.")
                        _return_to_main_screen(window, region, "gold active")
                    else:
                        logger.debug("[MAIN] Активная золотодобыча: уже в поселении.")

                # 7. Иначе — лечение как дефолтная активность, но сначала собираем книги/почту.
                if _collect_default_activities(screen_cv, region, window):
                    time.sleep(1)
                    continue

                logger.debug("[MAIN] Переключение в режим HEAL (дефолт)")
                current_mode = MainMode.HEAL
                last_heal_state = None
                continue

            # --- Режим HEAL ---
            elif current_mode == MainMode.HEAL:
                last_heal_state = process_heal(screen_cv, region, last_heal_state, window)
                # HEAL завершается только при COMPLETED или UNKNOWN
                if last_heal_state == HealState.UNKNOWN:
                    logger.info("[MAIN] HEAL завершён или неизвестное состояние, запускаем выход в поселение")
                    _return_to_main_screen(window, region, "HEAL")
                    current_mode = MainMode.DEFAULT
                    last_heal_state = None
                elif last_heal_state == HealState.COMPLETED:
                    logger.debug("[MAIN] HEAL завершён, возврат в DEFAULT")
                    current_mode = MainMode.DEFAULT
                    last_heal_state = None
                continue

            # --- Режим GOLD ---
            elif current_mode == MainMode.GOLD:
                # Защитный таймаут
                if gold_start_time and (time.time() - gold_start_time) >= GOLD_TIMEOUT:
                    logger.info(f"[ТАЙМЕР] Золото затянулось > {GOLD_TIMEOUT} сек. Запускаем выход в поселение.")
                    _return_to_main_screen(window, region, "GOLD timeout")
                    current_mode = MainMode.DEFAULT
                    last_gold_state = None
                    gold_start_time = None
                    continue

                # Если ещё стартуем и не определён state
                if last_gold_state is None:
                    current_gold_state = determine_gold_state(screen_cv, region)
                    logger.info(f"[MAIN] GOLD: стартовое состояние {current_gold_state.value}")
                    last_gold_state = current_gold_state

                # Обработать одно состояние
                current_gold_state = determine_gold_state(screen_cv, region)
                if current_gold_state != last_gold_state:
                    logger.info(f"[MAIN] GOLD: {current_gold_state.value}")

                last_gold_state = process_gold(screen_cv, region, last_gold_state, window)

                # Если добыча завершена — выходим в поселение и возвращаемся в DEFAULT
                if last_gold_state == GoldState.COMPLETED:
                    logger.info("[MAIN] Золотодобыча завершена, запускаем выход в поселение")
                    _return_to_main_screen(window, region, "GOLD completed")
                    current_mode = MainMode.DEFAULT
                    last_gold_state = None
                    gold_start_time = None
                    continue

            # --- Режим RAID ---
            elif current_mode == MainMode.RAID:
                # Защитный таймаут: если режим RAID затянулся на RAID_JOIN_TIMEOUT — выходим в поселение и в DEFAULT
                now = time.time()
                elapsed = now - raid_start_time if raid_start_time else None
                logger.debug(f"[DEBUG RAID] raid_start_time={raid_start_time}, elapsed={elapsed}, timeout={RAID_JOIN_TIMEOUT}")
                if raid_start_time and (now - raid_start_time) >= RAID_JOIN_TIMEOUT:
                    logger.info(f"[ТАЙМЕР] Рейд затянулся > {RAID_JOIN_TIMEOUT} сек. Запускаем выход в поселение.")
                    _return_to_main_screen(window, region, "RAID timeout")
                    current_mode = MainMode.DEFAULT
                    last_raid_state = None
                    raid_start_time = None
                    raid_joined_at_least_once = False
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

                # Если все рейды завершены или рейдов нет — выходим в поселение и возвращаемся в DEFAULT
                if last_raid_state in (RaidState.RAID_COMPLETED, RaidState.NO_REIDS):
                    logger.info("[MAIN] Рейды завершены/отсутствуют, запускаем выход в поселение")
                    _return_to_main_screen(window, region, "RAID completed")
                    current_mode = MainMode.DEFAULT
                    last_raid_state = None
                    raid_start_time = None
                    raid_joined_at_least_once = False
                    continue

            # --- Режим ADVENTURE ---
            elif current_mode == MainMode.ADVENTURE:
                # Обрабатываем состояние приключения
                current_adventure_state = determine_adventure_state(screen_cv, region)
                logger.info(f"[MAIN] ADVENTURE: {current_adventure_state.value}")
                new_adventure_state = process_adventure_state(screen_cv, region, last_adventure_state, window, current_adventure_state)
                last_adventure_state = new_adventure_state
                # Если приключение завершено (возвращено UNKNOWN), запускаем выход в поселение и возвращаемся в DEFAULT
                if new_adventure_state == AdventureState.UNKNOWN:
                    logger.info("[MAIN] Приключение завершено, запускаем выход в поселение")
                    _return_to_main_screen(window, region, "ADVENTURE completed")
                    current_mode = MainMode.DEFAULT
                    last_adventure_state = None
                continue

            # --- Задержка между итерациями ---
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