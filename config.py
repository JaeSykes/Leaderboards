"""
Configuration and Constants
"""

# Discord IDs
GUILD_ID = 1397286059406000249
LEADERBOARD_CHANNEL_ID = 1451514121345306695
ANNOUNCEMENT_CHANNEL_ID = 1405693987100033075
SCREENSHOTS_CHANNEL_ID = 1397653994889019434

# Tracked Roles
TRACKED_ROLES = [1397286685544284361, 1397286545379033219]

# Top Rankings
TOP_LIMIT = 4

# Database
DB_PATH = 'data/stats.db'

# Scheduler
UPDATE_INTERVAL_MINUTES = 5
MONTHLY_RESET_HOUR = 8
MONTHLY_RESET_TIMEZONE = 'Europe/Prague'

# Bot Configuration
BOT_PREFIX = '!'
BOT_ACTIVITY = 'Lineage 2 Stats'

# Category Names (for leaderboard display) - CP Turnover REMOVED ✅
STAT_CATEGORIES = {
    'voice_time': '🎙️ Voice Channel Time',
    'message_count': '💬 Message Count',
    'lineage_time': '⚔️ L2 Reborn Playtime',
    'reaction_count': '👍 Reactions Received',
    'apollo_events': '📅 Event Attendance',
    'party_count': '👥 Parties Created',
    'aq_calls': '📢 AQ UP Calls',
    'rental_count': '🔑 Půjčovna',
    'screenshot_count': '📸 Screenshots DKP'
}

# Formatting
TIME_FORMAT = '%d.%m.%Y %H:%M:%S'
EMBED_COLOR_MONTHLY = 0x3498db # Blue
EMBED_COLOR_OVERALL = 0x2ecc71 # Green
EMBED_COLOR_ANNOUNCEMENT = 0xf39c12 # Orange

# Bot Usernames (for embed parsing)
BOT_NAMES = {
    'apollo': 'Apollo',
    'party_maker': 'Party Jack',
    'accounting': 'Mišička z účtárny',
    'rental': 'Navrátil'
}
