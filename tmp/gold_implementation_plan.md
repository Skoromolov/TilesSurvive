# План доработки золотодобычи — TilesSurvive

## Сделано (22.06.2026)
1. config.py
   - GOLD_LEVEL = 1..6 — целевой уровень рудника.
   - GOLD_MINING_DURATION = 2700 сек (45 мин).
   - GOLD_TIMEOUT увеличен до 300 сек.
   - Добавлены пути к изображениям:
     - select_level.png, current_raid_lvl_icon.png
     - lvl_1..6.png, current_lvl_1..6.png
     - free_place.png, finish.png, confirm.png, hand.png
   - Расширен enum GoldState: EVENTS_NEED_SCROLL, SELECT_LEVEL_VISIBLE,
     LEVEL_LIST_VISIBLE, RAID_LEVEL_ICON_VISIBLE, FREE_PLACE_VISIBLE.

2. utils.py
   - find_all_on_screen() — множественный матч + non-max suppression.
   - swipe_horizontal() — свайп по верхней части экрана вправо/влево.
   - scroll_in_region() — вертикальный drag для списка уровней.

3. gold.py (полностью переписан)
   - Контекст _gold_ctx для отслеживания свайпов, скролла, stuck recovery,
     флага отзыва и времени старта добычи.
   - should_do_gold() / gold_mission_should_recall() — триггеры входа в режим.
   - get_current_level() / get_list_level() / click_level_go_button() — работа
     с уровнями.
   - determine_gold_state() — приоритетная классификация экрана.
   - process_gold() — пошаговое флоу:
     MAIN_SCREEN → EVENTS_MENU_OPEN → свайп вправо до EVENTS_RUDNIK_VISIBLE → клик rudnik.png → RUDNIK_TAB (rudnik_opened.png / current_lvl / find / select_level)
     → RUDNIK_TAB → проверка current_lvl_X → если не совпадает с GOLD_LEVEL,
       открываем select_level, скроллим lvl_X, нажимаем «Перейти» в карточке
       найденного уровня → снова RUDNIK_TAB → FIND → free_place → GRIND → WORK
       → GO → фиксация старта.
     Если отряд уже добывает (my_rudnik / current_raid_lvl_icon) — открываем
     детали, определяем уровень, проверяем 45-минутный таймер. При истечении
     отзываем отряд и перезапускаем на GOLD_LEVEL.
   - process_gold_exit() — выход из меню рудника назад в поселение.

4. main.py
   - Триггер GOLD_ENABLED and (should_do_gold() or gold_mission_should_recall())
     как для FORCE_HEAL_ONLY, так и для авто-режима.
   - reset_gold_context() вызывается при каждом переключении в GOLD.

## Предстоит проверить / донастроить
- Точность распознавания select_level.png и lvl_X.png на реальном экране.
- Работает ли клик «Перейти» по h*0.85 карточки lvl_X.png; при необходимости
  заменить на поиск ближайшей кнопки confirm.png/finish.png/hand.png.
- Направление скролла в списке уровней (вверх/вниз) соответствует порядку 1..6.
- Корректность приоритета между my_rudnik.png и current_raid_lvl_icon.png.
- Не конфликтует ли обработка reconnect в gold.py с глобальной обработкой main.py.
- Добавить UI-тесты Playwright или ручной пробный прогон с включённым
  GOLD_ENABLED.

## Дефер
- Персистентность таймера добычи между перезапусками бота.
- OCR оставшегося времени для более точного отзыва.
