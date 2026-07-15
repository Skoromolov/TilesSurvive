# ==========================================
# КОНФИГУРАЦИЯ И КОНСТАНТЫ
# ==========================================

from enum import Enum
import os

# ==========================================
# ПУТИ К ИЗОБРАЖЕНИЯМ
# ==========================================
FOLDER = 'pictures/'
FOLDER_COMMON = 'common/'
FOLDER_HEAL = 'heal/'
FOLDER_HELP = 'help/'
FOLDER_RAID = 'raid/'
FOLDER_GOLD = 'gold/'
FOLDER_ADVENTURE = 'adventure/'

# ==========================================
# НАСТРОЙКИ РЕЖИМА РАБОТЫ
# ==========================================
FORCE_HEAL_ONLY = False   # True = только лечение, False = автопереключение
FORCE_RAID_ONLY = False   # True = только рейды, False = автопереключение
FORCE_ADVENTURE_ONLY = False   # True = только приключения, False = автопереключение
ADVENTURE_ENABLED = True    # Включить автоматическое переключение в режим приключений
GOLD_ENABLED = True           # True = включить автоматизацию золотодобычи
RAID_ENABLED = True           # True = включать автоматическое участие в рейдах, False = отключить рейды

# ==========================================
# НАСТРОЙКИ БЫСТРОГО ЛЕЧЕНИЯ С КАРТЫ МИРА
# ==========================================
# True = работать только в режиме быстрого лечения с карты мира
# Игнорирует рейды и автопереключение. Лечит войска через иконку ambulance
# на карте мира (дикие земли), обрабатывает таймеры.
FAST_HEAL_FROM_MAP_ENABLED = False

# ==========================================
# НАСТРОЙКИ ЗОЛОТОДОБЫЧИ
# ==========================================
GOLD_INTERVAL = 2700          # Интервал между успешными золотодобычами (30 минут)
GOLD_LEVEL = 6              # Уровень рудника 1-6, на котором работаем
# Длительность одной добычи: через сколько секунд отзывать отряд и искать новое место
GOLD_MINING_DURATION = 2760   # 46 минут — с запасом, т.к. игра не даёт отозвать раньше 45 мин (уровни 5-6)
GOLD_SEARCH_TIMEOUT = 600     # Таймаут поиска рудника в секундах
GOLD_TIMEOUT = 300            # Таймаут всего процесса золотодобычи (5 минут)
GOLD_LEVEL_CONFIDENCE_THRESHOLD = 0.85  # ПОРОГ lowered — 0.90 заставлял проходит лишних повторений
GOLD_LIST_LEVEL_CONFIDENCE_THRESHOLD = 0.85  # Порог для lvl_X в списке
GOLD_LOOP_DELAY = 0.05        # Задержка между итерациями в режиме GOLD (сек)
GOLD_ACTION_DELAY = 0.15      # Короткая пауза после клика внутри gold-процесса (сек)


# ==========================================
# КОНСТАНТЫ ИЗОБРАЖЕНИЙ
# ==========================================
# Общие элементы
MAIL_IMG = FOLDER + FOLDER_COMMON + 'mail.png'
CONFIRM_BUTTON_IMG = FOLDER + FOLDER_COMMON + 'conferm_button.png'
RECONNECT_IMG = FOLDER + FOLDER_COMMON + 'reconnect.png'
RECONNECT_REPEAT_IMG = FOLDER + FOLDER_COMMON + 'reconnectRepeat.png'
SOUZ_IMG = FOLDER + FOLDER_COMMON + 'souz.png'
NEWS_IMG = FOLDER + FOLDER_COMMON + 'news.png'
VILLAGE_IMG = FOLDER + FOLDER_COMMON + 'village_footbool.png'
WILD_EARTH_IMG = FOLDER + FOLDER_COMMON + 'wild_earth_footbool.png'
CLOSE_IMG = FOLDER + FOLDER_COMMON + 'close.png'
BACK_IMG = FOLDER + FOLDER_COMMON + 'back.png'
HELP_HANDS_IMG = FOLDER + FOLDER_COMMON + 'help_hands.png'
EVENTS_IMG = FOLDER + FOLDER_COMMON + 'events.png'
INFO_IMG = FOLDER + FOLDER_COMMON + 'info.png'
CALENDAR_IMG = FOLDER + FOLDER_COMMON + 'calendar.png'
CALENDAR_OPENED_IMG = FOLDER + FOLDER_COMMON + 'calendar_opened.png'
EVENT_GOLD_IMG = FOLDER + FOLDER_COMMON + 'event_gold.png'
BOOK_IMG = FOLDER + FOLDER_COMMON + 'book.png'
EXIT_TO_VILLAGE_IMG = FOLDER + FOLDER_COMMON + 'exit_to_village.png'

GOLD_CLOSE_IMG = FOLDER + FOLDER_GOLD + 'close.png'  # кнопка закрытия попапов внутри золотодобычи

# Gold
GOLD_FOLDER = FOLDER + FOLDER_GOLD

# Heal
HEAL_TOWN_IMG = FOLDER + FOLDER_HEAL + 'heal_town.png'
HEAL_BUTTON_IMG  = FOLDER + FOLDER_HEAL + 'heal_button.png'
HEAL_WAIT_IMG    = FOLDER + FOLDER_HEAL + 'heal_wait.png'
HEAL_HELP_HANDS_IMG = FOLDER + FOLDER_HEAL + 'heal_help_hands.png'
HEAL_FREE_BUTTON_IMG  = FOLDER + FOLDER_HEAL + 'heal_free_button.png'
FAST_USE_IMG     = FOLDER + FOLDER_HEAL + 'fast_use.png'

# Элементы быстрого лечения с карты мира
AMBULANCE_ON_MAP_IMG = FOLDER + FOLDER_HEAL + 'ambulance.png'
AMBULANCE_ON_MAP_WIDE_IMG = FOLDER + FOLDER_HEAL + 'ambulance_bottle_wide.png'
HEAL_HELP_WITH_TIME_IMG = FOLDER + FOLDER_HEAL + 'heal_help_with_time_button.png'

# Элементы помощи
HELP_HANDS_IMG = FOLDER + FOLDER_HELP + 'help_hands.png'

# Элементы рейдов
RAID_PLUS_IMG = FOLDER + FOLDER_RAID + 'raid_plus.png'
RAID_MARCH_IMG = FOLDER + FOLDER_RAID + 'raid_march_button.png'
RAID_OK_IMG = FOLDER + FOLDER_RAID + 'ok.png'
RAID_ACTIVE_IMG = FOLDER + FOLDER_RAID + 'raid_active.png'
RAID_NOT_ACTIVE_IMG = FOLDER + FOLDER_RAID + 'raid_not_active.png'
RAID_NO_FREE_SPACE_IMG = FOLDER + FOLDER_RAID + 'noFreeSpace.png'
RAID_HAVE_TO_CONNECT_IMG = FOLDER + FOLDER_RAID + 'raid_connect.png'
RAID_HAVE_TO_CONNECT_2_IMG = FOLDER + FOLDER_RAID + 'raid_connect_2.png'
RAID_ATTACK_IMG = FOLDER + FOLDER_RAID + 'attack.png'
RAID_FULL_IMG = FOLDER + FOLDER_RAID + 'raid_full.png'
RAID_INFO_IMG = FOLDER + FOLDER_RAID + 'raid_info.png'

# Элементы золотодобычи
GOLD_RUDNIK_IMG = FOLDER + FOLDER_GOLD + 'rudnik.png'
GOLD_RUDNIK_OPENED_IMG = FOLDER + FOLDER_GOLD + 'rudnik_opened.png'
GOLD_SELECT_LEVEL_IMG = FOLDER + FOLDER_GOLD + 'select_level.png'
GOLD_LEVEL_IMAGES = {
    level: FOLDER + FOLDER_GOLD + f'lvl_{level}.png'
    for level in range(1, 7)
}
GOLD_CURRENT_LEVEL_IMAGES = {
    level: FOLDER + FOLDER_GOLD + f'current_lvl_{level}.png'
    for level in range(1, 7)
}
GOLD_CURRENT_RAID_LEVEL_ICON_IMG = FOLDER + FOLDER_GOLD + 'current_raid_lvl_icon.png'
GOLD_FIND_IMG = FOLDER + FOLDER_GOLD + 'find.png'
GOLD_MY_RUDNIK_IMG = FOLDER + FOLDER_GOLD + 'my_rudnik.png'
GOLD_RETURN_IMG = FOLDER + FOLDER_GOLD + 'return.png'
GOLD_RETURN_BOYS_IMG = FOLDER + FOLDER_GOLD + 'return_boys.png'
GOLD_FREE_PLACE_IMG = FOLDER + FOLDER_GOLD + 'free_place.png'
GOLD_GRIND_IMG = FOLDER + FOLDER_GOLD + 'grind.png'
GOLD_WORK_IMG = FOLDER + FOLDER_GOLD + 'join.png'
GOLD_GO_IMG = FOLDER + FOLDER_GOLD + 'go.png'
GOLD_MOVEON_IMG = FOLDER + FOLDER_GOLD + 'moveOn.png'
GOLD_FINISH_IMG = FOLDER + FOLDER_GOLD + 'finish.png'
GOLD_CONFIRM_IMG = FOLDER + FOLDER_GOLD + 'confirm.png'
GOLD_ADVICE_IMG = FOLDER + FOLDER_GOLD + 'advice.png'
GOLD_CONFIRM_ORANGE_IMG = FOLDER + FOLDER_GOLD + 'confirm_orange.png'
GOLD_SUMMARY_STRENGTH_TEXT_IMG = FOLDER + FOLDER_GOLD + 'summary_strength_text.png'
GOLD_HAND_IMG = FOLDER + FOLDER_GOLD + 'hand.png'
GOLD_NO_FREE_RUDNIK_IMG = FOLDER + FOLDER_GOLD + 'no_free_rudnik.png'
GOLD_FORWARD_IMG = FOLDER + FOLDER_GOLD + 'forward.png'

## элементы приключений
ADVENTURE_GET_IMG = FOLDER + FOLDER_COMMON + 'get.png'
ADVENTURE_IMG = FOLDER + FOLDER_ADVENTURE + 'adventure.png'
ADVENTURE_PAGE_IMG = FOLDER + FOLDER_ADVENTURE + 'adventure_page.png'
ADVENTURE_BAGGAGE_POPUP_IMG = FOLDER + FOLDER_ADVENTURE + 'baggage_popup.png'
ADVENTURE_GET_BIG_BUTTON_IMG = FOLDER + FOLDER_ADVENTURE + 'get_big_button.png'

# ==========================================
# ПАРАМЕТРЫ ЧУВСТВИТЕЛЬНОСТИ
# ==========================================
CONFIDENCE_THRESHOLD = 0.70
CONFIDENCE_HIGH = 0.95
MARCH_THRESHOLD = 0.90
NAVIGATION_THRESHOLD = 0.90
CONFIDENCE_MEDIUM_THRESHOLD = 0.80

# ==========================================
# ПАРАМЕТРЫ РЕЙДОВ
# ==========================================
RAID_JOIN_TIMEOUT = 180     # секунд (3 минуты)
RAID_SCROLL_THRESHOLD = 2    # макс упоминаний "Атака" перед скроллом

# ==========================================
# ОКНО ЭМУЛЯТОРА
# ==========================================
BLUESTACKS_WINDOW_TITLE = "BlueStacks App Player"

# ==========================================
# ОТЛАДКА
# ==========================================
DEBUG_SCREENSHOTS_DIR = 'debug_screenshots'

# ==========================================
# ENUM: РЕЖИМЫ И СОСТОЯНИЯ
# ==========================================
class MainMode(Enum):
    DEFAULT = "default"  # Дефолтный режим: точка входа и возврата после любого мода
    HEAL = "heal"
    RAID = "raid"
    GOLD = "gold"  # Режим золотодобычи
    ADVENTURE = "adventure"  # Режим приключений


class AdventureState(Enum):
    UNKNOWN = "unknown"
    ADVENTURE = "adventure"          # Кнопка adventure видима на главном экране
    ADVENTURE_PAGE = "adventure_page"  # Открыта страница приключений
    ADVENTURE_GET = "adventure_get"    # Кнопка get видима на странице приключений
    BAGGAGE_POPUP = "baggage_popup"    # Появился попап с багажом после нажатия get
    ADVENTURE_CONFIRM = "adventure_confirm"  # Кнопка подтверждения видима (fallback)


class HealState(Enum):
    UNKNOWN = "unknown"
    MAIN_SCREEN = "main_screen"
    HEAL_ICON = "heal_icon"
    HEAL_MENU_OPEN = "heal_menu_open"
    HEAL_HELP = "heal_help"
    HEAL_ACTIVE = "heal_active"
    RECONNECT_POPUP = "reconnect_popup"
    RECONNECT_REPEAT_POPUP = "reconnect_repeat_popup"
    FAST_USE_POPUP = "fast_use_popup"
    HEAL_WAIT = "heal_wait"
    HEAL_TOWN = "heal_town"
    CONFIRM_BUTTON_REQUIRED = "confirm_button_required"
    MAIL = "mail"
    HELP_HANDS = "help_hands"
    BOOK = "book"
    COMPLETED = "completed"
    # Быстрое лечение с карты мира
    AMBULANCE_ON_MAP = "ambulance_on_map"
    HEAL_HELP_WITH_TIME = "heal_help_with_time"


class RaidState(Enum):
    UNKNOWN = "unknown"
    RAID_WINDOW_ACTIVE = "raid_window_active"
    RAID_TAB_NOT_ACTIVE = "raid_tab_not_active"
    PLUS_VISIBLE = "plus_visible"
    MARCH_VISIBLE = "march_visible"
    RAID_IN_PROGRESS = "raid_in_progress"
    RAID_COMPLETED = "raid_completed"
    NO_FREE_SPACE = "no_free_space"
    NO_REIDS = "no_reids"
    RECONNECT_POPUP = "reconnect_popup"
    RECONNECT_REPEAT_POPUP = "reconnect_repeat_popup"
    NAVIGATION_NEEDED = "navigation_needed"
    NEEDS_SCROLL = "needs_scroll"
    RAID_FULL = "raid_full"
    RAID_INFO_VISIBLE = "raid_info_visible"


class GoldState(Enum):
    UNKNOWN = "unknown"
    MAIN_SCREEN = "main_screen"
    EVENTS_OPEN = "events_open"
    EVENTS_NEED_SCROLL = "events_need_scroll"
    EVENTS_RUDNIK_VISIBLE = "events_rudnik_visible"
    FORWARD_POPUP_VISIBLE = "forward_popup"
    EVENTS_MENU_OPEN = "events_menu_open"
    RUDNIK_TAB = "rudnik_tab"
    SELECT_LEVEL_VISIBLE = "select_level_visible"
    LEVEL_LIST_VISIBLE = "level_list_visible"
    RAID_LEVEL_ICON_VISIBLE = "raid_level_icon_visible"
    FIND_VISIBLE = "find_visible"
    GRIND_VISIBLE = "grind_visible"
    WORK_VISIBLE = "work_visible"
    GO_VISIBLE = "go_visible"
    MY_RUDNIK_VISIBLE = "my_rudnik_visible"
    RETURN_CONFIRM_VISIBLE = "return_confirm_visible"
    RETURN_BUTTON_VISIBLE = "return_button_visible"
    FINISH_VISIBLE = "finish_visible"
    CONFIRM_VISIBLE = "confirm_visible"
    SUMMARY_STRENGTH_TEXT_VISIBLE = "summary_strength_text_visible"
    RECONNECT_POPUP = "reconnect_popup"
    RECONNECT_REPEAT_POPUP = "reconnect_repeat_popup"
    FREE_PLACE_VISIBLE = "free_place_visible"
    NO_FREE_RUDNIK = "no_free_rudnik"
    ADVICE_VISIBLE = "advice_visible"
    COMPLETED = "completed"