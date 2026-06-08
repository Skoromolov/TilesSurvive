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

# ==========================================
# НАСТРОЙКИ РЕЖИМА РАБОТЫ
# ==========================================
FORCE_HEAL_ONLY = False   # True = только лечение, False = автопереключение
FORCE_RAID_ONLY = False   # True = только рейды, False = автопереключение

# ==========================================
# НАСТРОЙКИ ЗОЛОТОДОБЫЧИ
# ==========================================
GOLD_ENABLED = False           # True = включить автоматизацию золотодобычи
GOLD_INTERVAL = 3600          # Интервал в секундах (1 час)
GOLD_SEARCH_TIMEOUT = 60      # Таймаут поиска рудника в секундах
GOLD_TIMEOUT = 180            # Таймаут всего процесса золотодобычи (3 минуты)

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
VILLAGE_IMG = FOLDER + FOLDER_COMMON + 'village.png'
WILD_EARTH_IMG = FOLDER + FOLDER_COMMON + 'wild_earth.png'
CLOSE_IMG = FOLDER + FOLDER_COMMON + 'close.png'
BACK_IMG = FOLDER + FOLDER_COMMON + 'back.png'
EVENTS_IMG = FOLDER + FOLDER_COMMON + 'events.png'

# Элементы лечения
HEAL_TOWN_IMG = FOLDER + FOLDER_HEAL + 'heal_town.png'
HEAL_BUTTON_IMG = FOLDER + FOLDER_HEAL + 'heal_button.png'
HEAL_WAIT_IMG = FOLDER + FOLDER_HEAL + 'heal_wait.png'
HEAL_HELP_HANDS_IMG = FOLDER + FOLDER_HEAL + 'heal_help_hands.png'
HEAL_FREE_BUTTON_IMG = FOLDER + FOLDER_HEAL + 'heal_free_button.png'
FAST_USE_IMG = FOLDER + FOLDER_HEAL + 'fast_use.png'

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

# Элементы золотодобычи
GOLD_RUDNIK_IMG = FOLDER + FOLDER_GOLD + 'rudnik.png'
GOLD_RUDNIK_OPENED_IMG = FOLDER + FOLDER_GOLD + 'rudnik_opened.png'
GOLD_FIND_IMG = FOLDER + FOLDER_GOLD + 'find.png'
GOLD_MY_RUDNIK_IMG = FOLDER + FOLDER_GOLD + 'my_rudnik.png'
GOLD_RETURN_IMG = FOLDER + FOLDER_GOLD + 'return.png'
GOLD_RETURN_BOYS_IMG = FOLDER + FOLDER_GOLD + 'return_boys.png'
GOLD_GRIND_IMG = FOLDER + FOLDER_GOLD + 'grind.png'
GOLD_WORK_IMG = FOLDER + FOLDER_GOLD + 'work.png'
GOLD_GO_IMG = FOLDER + FOLDER_GOLD + 'go.png'

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
RAID_JOIN_TIMEOUT = 120      # секунд (2 минуты)
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
    HEAL = "heal"
    RAID = "raid"
    GOLD = "gold"  # Режим золотодобычи


class HealState(Enum):
    UNKNOWN = "unknown"
    MAIN_SCREEN = "main_screen"
    HEAL_ICON = "heal_icon_visible"
    HEAL_MENU_OPEN = "heal_menu_open"
    HEAL_HELP = "heal_help_visible"
    HEAL_ACTIVE = "heal_active"
    RECONNECT_POPUP = "reconnect_popup"
    RECONNECT_REPEAT_POPUP = "reconnect_repeat_popup"
    FAST_USE_POPUP = "fast_use_popup"
    HEAL_WAIT = "heal_wait"
    HEAL_TOWN = "heal_town"
    CONFIRM_BUTTON_REQUIRED = "confirm_button_required"
    MAIL = "mail"
    HELP_HANDS = "help_hands"


class RaidState(Enum):
    UNKNOWN = "unknown"
    REID_WINDOW_ACTIVE = "reid_window_active"
    REID_TAB_NOT_ACTIVE = "reid_tab_not_active"
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


class GoldState(Enum):
    UNKNOWN = "unknown"
    MAIN_SCREEN = "main_screen"
    EVENTS_OPEN = "events_open"
    RUDNIK_TAB = "rudnik_tab"
    FIND_VISIBLE = "find_visible"
    GRIND_VISIBLE = "grind_visible"
    WORK_VISIBLE = "work_visible"
    GO_VISIBLE = "go_visible"
    MY_RUDNIK_VISIBLE = "my_rudnik_visible"
    RETURN_CONFIRM_VISIBLE = "return_confirm_visible"
    RECONNECT_POPUP = "reconnect_popup"
    RECONNECT_REPEAT_POPUP = "reconnect_repeat_popup"
    COMPLETED = "completed"
