"""
SQLAlchemy Database Models and Operations
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from config import DB_PATH

logger = logging.getLogger(__name__)

# Ensure data directory exists
Path('data').mkdir(exist_ok=True)


def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database tables"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Monthly stats table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS monthly_stats (
            user_id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            voice_time INTEGER DEFAULT 0,
            message_count INTEGER DEFAULT 0,
            lineage_time INTEGER DEFAULT 0,
            reaction_count INTEGER DEFAULT 0,
            apollo_events INTEGER DEFAULT 0,
            party_count INTEGER DEFAULT 0,
            aq_calls INTEGER DEFAULT 0,
            rental_count INTEGER DEFAULT 0,
            screenshot_count INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Overall stats table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS overall_stats (
            user_id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            voice_time INTEGER DEFAULT 0,
            message_count INTEGER DEFAULT 0,
            lineage_time INTEGER DEFAULT 0,
            reaction_count INTEGER DEFAULT 0,
            apollo_events INTEGER DEFAULT 0,
            party_count INTEGER DEFAULT 0,
            aq_calls INTEGER DEFAULT 0,
            rental_count INTEGER DEFAULT 0,
            screenshot_count INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Voice sessions table (for tracking duration)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS voice_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            join_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    # Activity sessions table (for tracking Lineage 2 playtime)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    # Leaderboard messages tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leaderboard_messages (
            id INTEGER PRIMARY KEY,
            message_type TEXT NOT NULL,
            message_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info('✅ Database initialized')


def increment_stat(user_id: str, username: str, stat_type: str, amount: int = 1):
    """Increment a statistic for a user in both monthly and overall tables"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Validate stat_type to prevent SQL injection
        valid_stats = ['voice_time', 'message_count', 'lineage_time', 'reaction_count', 
                      'apollo_events', 'party_count', 'aq_calls', 'rental_count', 'screenshot_count']
        if stat_type not in valid_stats:
            return
        
        # OPRAVENO: Používáme dynamické sloupce správně ✅
        # Update monthly stats
        cursor.execute(f'''
            INSERT INTO monthly_stats (user_id, username, {stat_type})
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                {stat_type} = {stat_type} + excluded.{stat_type},
                updated_at = CURRENT_TIMESTAMP
        ''', (user_id, username, amount))
        
        # Update overall stats
        cursor.execute(f'''
            INSERT INTO overall_stats (user_id, username, {stat_type})
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                {stat_type} = {stat_type} + excluded.{stat_type},
                updated_at = CURRENT_TIMESTAMP
        ''', (user_id, username, amount))
        
        conn.commit()
        logger.info(f'✅ {username}: +{amount} {stat_type}')
    except Exception as e:
        logger.error(f'❌ Error in increment_stat: {e}')
        conn.rollback()
    finally:
        conn.close()


def get_top_stats(table: str = 'monthly_stats', limit: int = 10) -> dict:
    """Get top statistics from a table"""
    conn = get_db()
    cursor = conn.cursor()
    
    stats_dict = {
        'voice_time': [],
        'message_count': [],
        'lineage_time': [],
        'reaction_count': [],
        'apollo_events': [],
        'party_count': [],
        'aq_calls': [],
        'rental_count': [],
        'screenshot_count': []
    }
    
    try:
        for stat_name in stats_dict.keys():
            sql = f'''
                SELECT user_id, username, {stat_name} as value
                FROM {table}
                WHERE {stat_name} > 0
                ORDER BY {stat_name} DESC
                LIMIT ?
            '''
            cursor.execute(sql, (limit,))
            stats_dict[stat_name] = [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f'❌ Error in get_top_stats: {e}')
    finally:
        conn.close()
    
    return stats_dict


def reset_monthly_stats():
    """Reset monthly statistics (called on last day of month)"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('DELETE FROM monthly_stats')
        cursor.execute('DELETE FROM voice_sessions WHERE is_active = 1')
        cursor.execute('DELETE FROM activity_sessions WHERE is_active = 1')
        conn.commit()
        logger.info('✅ Monthly stats reset')
    except Exception as e:
        logger.error(f'❌ Error in reset_monthly_stats: {e}')
        conn.rollback()
    finally:
        conn.close()


def start_voice_session(user_id: str, username: str):
    """Start tracking voice session"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO voice_sessions (user_id, username, join_time, is_active)
            VALUES (?, ?, CURRENT_TIMESTAMP, 1)
        ''', (user_id, username))
        conn.commit()
        logger.info(f'✅ Voice session started: {username}')
    except Exception as e:
        logger.error(f'❌ Error in start_voice_session: {e}')
        conn.rollback()
    finally:
        conn.close()


def end_voice_session(user_id: str, username: str):
    """End voice session and calculate duration"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get the most recent active session
        cursor.execute('''
            SELECT id, join_time FROM voice_sessions
            WHERE user_id = ? AND is_active = 1
            ORDER BY join_time DESC LIMIT 1
        ''', (user_id,))
        
        session = cursor.fetchone()
        
        if session:
            join_time = datetime.fromisoformat(session['join_time'])
            duration = int((datetime.now() - join_time).total_seconds())
            
            # Update stats
            increment_stat(user_id, username, 'voice_time', duration)
            
            # Mark session as inactive
            cursor.execute('''
                UPDATE voice_sessions SET is_active = 0 WHERE id = ?
            ''', (session['id'],))
            
            conn.commit()
            logger.info(f'✅ Voice session ended: {username} ({duration}s)')
    except Exception as e:
        logger.error(f'❌ Error in end_voice_session: {e}')
        conn.rollback()
    finally:
        conn.close()


def start_activity_session(user_id: str, username: str):
    """Start tracking Lineage 2 activity"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Check if already has active session
        cursor.execute('''
            SELECT id FROM activity_sessions
            WHERE user_id = ? AND is_active = 1
        ''', (user_id,))
        
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO activity_sessions (user_id, username, start_time, is_active)
                VALUES (?, ?, CURRENT_TIMESTAMP, 1)
            ''', (user_id, username))
            conn.commit()
            logger.info(f'✅ Activity session started: {username}')
    except Exception as e:
        logger.error(f'❌ Error in start_activity_session: {e}')
        conn.rollback()
    finally:
        conn.close()


def end_activity_session(user_id: str, username: str):
    """End activity session and calculate duration"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get the most recent active session
        cursor.execute('''
            SELECT id, start_time FROM activity_sessions
            WHERE user_id = ? AND is_active = 1
            ORDER BY start_time DESC LIMIT 1
        ''', (user_id,))
        
        session = cursor.fetchone()
        
        if session:
            start_time = datetime.fromisoformat(session['start_time'])
            duration = int((datetime.now() - start_time).total_seconds())
            
            # Update stats
            increment_stat(user_id, username, 'lineage_time', duration)
            
            # Mark session as inactive
            cursor.execute('''
                UPDATE activity_sessions SET is_active = 0 WHERE id = ?
            ''', (session['id'],))
            
            conn.commit()
            logger.info(f'✅ Activity session ended: {username} ({duration}s)')
    except Exception as e:
        logger.error(f'❌ Error in end_activity_session: {e}')
        conn.rollback()
    finally:
        conn.close()


def get_all_stats() -> dict:
    """Get all stats for all users (used for monthly reset announcement)"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT * FROM monthly_stats')
        users = {}
        for row in cursor.fetchall():
            users[row['user_id']] = dict(row)
        return users
    except Exception as e:
        logger.error(f'❌ Error in get_all_stats: {e}')
        return {}
    finally:
        conn.close()


def save_leaderboard_message(message_type: str, message_id: int):
    """Save leaderboard message ID for future updates"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO leaderboard_messages (message_type, message_id)
            VALUES (?, ?)
        ''', (message_type, message_id))
        conn.commit()
    except Exception as e:
        logger.error(f'❌ Error in save_leaderboard_message: {e}')
        conn.rollback()
    finally:
        conn.close()


def get_leaderboard_message(message_type: str) -> int:
    """Get leaderboard message ID"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT message_id FROM leaderboard_messages
            WHERE message_type = ?
        ''', (message_type,))
        
        result = cursor.fetchone()
        return result['message_id'] if result else None
    except Exception as e:
        logger.error(f'❌ Error in get_leaderboard_message: {e}')
        return None
    finally:
        conn.close()
