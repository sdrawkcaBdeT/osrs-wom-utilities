# config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ==========================================
# USER CONFIGURATION
# ==========================================

# REQUIRED: The API docs state you MUST provide a User Agent.
# Please put your Discord username or App name here.
USER_AGENT = "MyOSRSUpdater/1.0 (Discord: sdrawkcabdet)"

# The Base URL for Wise Old Man V2
BASE_URL = "https://api.wiseoldman.net/v2"

# How often to run the full update cycle (in seconds)
# Docs recommend 1-6 hours (3600 - 21600 seconds) to avoid redundant data.
CYCLE_INTERVAL = 3600  # 1 Hour

# Delay between individual API calls (in seconds)
# Limit is 20 requests per 60 seconds. 
# 5 seconds = 12 requests per minute (Safe & Polite)
REQUEST_DELAY = 5 

# SECURE API KEY LOAD
API_KEY = os.getenv("WOM_API_KEY")

# --- PROJECT START DATE ---
# The Archiver will ignore any data before this date.
# Format: ISO 8601 String (YYYY-MM-DD)
PROJECT_START_DATE = "2026-01-04T00:00:00"

# ==========================================
# PLAYER LISTS
# ==========================================

PLAYER_LISTS = {
    "real_ones": [
        "CashBaggins", 
        "CacheBaggins", 
        "BaboHouse", 
        "BrutalBDMain", 
        "BaboMouse", 
        "Ez Purpp"
    ],
    "suspected_bots": [
        "BISKIEZ209", 
        "frostytimez", 
        "xingyun 2025",
        "Touroshui",
        "geensliyh",
        "gigidere",
        "triunhiji",
               
    ],
    # You can add more lists easily here
    # "clan_mates": ["Name1", "Name2"],
}

# ==========================================
# DEDUCTION ENGINE (FILL IN THE BLANKS)
# ==========================================
# This allows us to estimate "Hours Played" based on gains.
# Logic: If they gained 200k XP, and the rate is 100k/hr, they played 2 hours.

ACTIVITY_CONFIG = {
    # Configuration for the "suspected_bots" list
    "suspected_bots": {
        "primary_metric": "ranged",         # The skill they are likely training
        "xp_per_hour": 79_380,               # Est. XP/hr for Brutal Black Dragons { BRUTAL-BLACK-DRAGON-HP * (EXP-PER-DAMAGE * BONUS-EXP-MOD) * KILLS-PER-HOUR }
                                            # { 315 * (4 * 1.05) * 75 } = 99,225
                                            # { 315 * (4 * 1.05) * 70 } = 92,610
                                            # { 315 * (4 * 1.05) * 65 } = 85,995 
                                            # { 315 * (4 * 1.05) * 60 } = 79,380 ** IN USE
                                            # { 315 * (4 * 1.05) * 55 } = 72,765
                                            # { 315 * (4 * 1.05) * 50 } = 66,150
        "secondary_metric": "hitpoints",    # Secondary check
    },
    
    # Configuration for "real_ones" (Harder to guess, but we can try a general rate)
    "real_ones": {
        "primary_metric": "overall",      # Real players do everything
        "xp_per_hour": 75_000,             # A conservative average for casual play
    }
}

# ==========================================
# VISUALIZATION SETTINGS
# ==========================================

# Timezone Configuration
# Use 'America/Chicago' for Central Time.
TIMEZONE = 'America/Chicago'
# TIMEZONE = 'America/New_York'   # Eastern
# TIMEZONE = 'America/Los_Angeles' # Pacific
# TIMEZONE = 'Europe/London'      # UTC/BST
# TIMEZONE = 'Australia/Sydney'   # AEST

# Font Configuration
# Place your .otf or .ttf files in a folder named 'fonts' next to this script.
# If the file isn't found, it will default to a basic system font.
FONT_PATH_PRIMARY = "fonts/industryultra.OTF" 
FONT_PATH_SECONDARY = "fonts/EXPRESSWAY RG-BOLD.OTF"

# OSRS Skill Color Palette (Hex Codes)
# You can tweak these to match your community's preference.
SKILL_COLORS = {
    "attack": "#9b2020",      # Deep Red
    "defence": "#6277be",     # Blue
    "strength": "#04955a",    # Green
    "hitpoints": "#d61a1a",   # Bright Red
    "ranged": "#6d8e13",      # Range Green
    "prayer": "#f4e648",      # Gold
    "magic": "#2f32a0",       # Magic Blue
    "cooking": "#702386",     # Purple
    "woodcutting": "#348c25", # Tree Green
    "fletching": "#038d7d",   # Teal
    "fishing": "#6a84a4",     # Grey-Blue
    "firemaking": "#bd6718",  # Orange
    "crafting": "#976e4d",    # Brown
    "smithing": "#6c6c6b",    # Grey
    "mining": "#5d8fa7",      # Cyan-Grey
    "herblore": "#078509",    # Herb Green
    "agility": "#3a3c89",     # Dark Blue
    "thieving": "#6c3457",    # Magenta
    "slayer": "#646464",      # Dark Grey
    "farming": "#65983f",     # Farm Green
    "runecrafting": "#aa8d1a",# Rune Gold
    "hunter": "#5c5941",      # Hunter Brown
    "construction": "#82795f",# Beige
    "overall": "#ffffff"      # White
}