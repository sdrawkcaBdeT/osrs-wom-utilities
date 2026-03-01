# config.py
import os
import sqlite3
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

SEED_LISTS = {
    "real_ones": [
        "CashBaggins", 
        "CacheBaggins", 
        "BaboHouse", 
        "CashDragons", 
        "BaboMouse", 
        "Ez Purpp",
        "Degener4te",
        "Brutalx_ALT",
        "Mandy Yew",
        "slamincam",
        "Thief GodMan",
        "Pdawg 19",
        "Superioritay",
        
        

    ],
    "suspected_bots": [
        "xingyun 2025",
        "sharomprince",

               
    ],
    # You can add more lists easily here
    # "clan_mates": ["Name1", "Name2"],
}


# 2. DYNAMIC MERGE FROM CENSUS DATABASE
# We create a new dictionary to hold the final results
PLAYER_LISTS = {
    "real_ones": list(SEED_LISTS["real_ones"]),
    "suspected_bots": list(SEED_LISTS["suspected_bots"])
}

CENSUS_DB = "census.db"

if os.path.exists(CENSUS_DB):
    try:
        # Open Read-Only connection to avoid locking the DB used by the UI
        # uri=True allows us to specify mode=ro
        conn = sqlite3.connect(f"file:{CENSUS_DB}?mode=ro", uri=True)
        c = conn.cursor()
        
        # Fetch Real Ones from DB
        c.execute("SELECT username FROM roster WHERE status = 'REAL'")
        db_real = [row[0] for row in c.fetchall()]
        
        # Fetch Suspects from DB
        c.execute("SELECT username FROM roster WHERE status = 'SUSPECT'")
        db_suspects = [row[0] for row in c.fetchall()]
        
        conn.close()
        
        # Merge and Deduplicate (Set logic)
        # We combine Seed + DB, then convert to set to remove duplicates, then back to list
        PLAYER_LISTS["real_ones"] = list(set(PLAYER_LISTS["real_ones"] + db_real))
        PLAYER_LISTS["suspected_bots"] = list(set(PLAYER_LISTS["suspected_bots"] + db_suspects))
        
        print(f"[CONFIG] Loaded Dynamic Lists. Real: {len(PLAYER_LISTS['real_ones'])}, Bots: {len(PLAYER_LISTS['suspected_bots'])}")

    except Exception as e:
        print(f"[CONFIG] Warning: Could not read census.db. Using seed lists only. Error: {e}")
else:
    print("[CONFIG] No census.db found. Using seed lists.")

# ==========================================
# DEDUCTION ENGINE (FILL IN THE BLANKS)
# ==========================================
# This allows us to estimate "Hours Played" based on gains.
# Logic: If they gained 200k XP, and the rate is 100k/hr, they played 2 hours.

ACTIVITY_CONFIG = {
    # Configuration for the "suspected_bots" list
    "suspected_bots": {
        "primary_metric": "ranged",         # The skill they are likely training
        "xp_per_hour": 85_995,               # Est. XP/hr for Brutal Black Dragons { BRUTAL-BLACK-DRAGON-HP * (EXP-PER-DAMAGE * BONUS-EXP-MOD) * KILLS-PER-HOUR }
                                            # { 315 * (4 * 1.05) * 75 } = 99,225 RANGED EXP
                                            # { 315 * (4 * 1.05) * 70 } = 92,610 RANGED EXP
                                            # { 315 * (4 * 1.05) * 65 } = 85,995 RANGED EXP ** IN USE
                                            # { 315 * (4 * 1.05) * 60 } = 79,380 RANGED EXP
                                            # { 315 * (4 * 1.05) * 55 } = 72,765 RANGED EXP
                                            # { 315 * (4 * 1.05) * 50 } = 66,150 RANGED EXP
                                            # { 315 * (4 * 1.05) * 1} = 1,323 RANGED EXP
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