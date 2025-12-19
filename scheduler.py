"""
Scheduler for Automatic Updates and Monthly Reset
"""

import logging
from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import *
from models import reset_monthly_stats
from leaderboard import update_leaderboard, announce_monthly_winners

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def setup_scheduler(bot):
    """Setup background tasks"""
    
    # Update leaderboard every 5 minutes
    scheduler.add_job(
        update_leaderboard_task,
        'interval',
        minutes=UPDATE_INTERVAL_MINUTES,
        args=[bot],
        id='update_leaderboard',
        replace_existing=True
    )
    
    # Monthly reset - check at 8 AM every day
    scheduler.add_job(
        monthly_reset_task,
        'cron',
        hour=MONTHLY_RESET_HOUR,
        timezone=MONTHLY_RESET_TIMEZONE,
        args=[bot],
        id='monthly_reset',
        replace_existing=True
    )
    
    scheduler.start()
    
    logger.info('✅ Scheduler configured:')
    logger.info(f'  - Leaderboard updates: Every {UPDATE_INTERVAL_MINUTES} minutes')
    logger.info(f'  - Monthly reset: At {MONTHLY_RESET_HOUR}:00 AM ({MONTHLY_RESET_TIMEZONE})')


async def update_leaderboard_task(bot):
    """Scheduled leaderboard update"""
    logger.info('⏰ Running 5-minute leaderboard update...')
    await update_leaderboard(bot)


async def monthly_reset_task(bot):
    """Check if today is last day of month and reset"""
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    
    # Check if tomorrow is a new month (today is last day)
    if tomorrow.month != now.month:
        logger.info('🗓️ Last day of month detected - Running monthly reset...')
        
        try:
            # Announce winners before reset
            await announce_monthly_winners(bot)
            
            # Wait a bit to ensure announcement is sent
            await asyncio.sleep(2)
            
            # Reset monthly stats
            reset_monthly_stats()
            logger.info('✅ Monthly stats reset')
            
            # Update leaderboard to show empty monthly stats
            await update_leaderboard(bot)
            logger.info('✅ Monthly reset complete')
        
        except Exception as e:
            logger.error(f'❌ Error during monthly reset: {e}')


# Make scheduler accessible
def get_scheduler():
    """Get the scheduler instance"""
    return scheduler


# Import asyncio for sleep
import asyncio
