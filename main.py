"""
Discord Stats Bot - Main Entry Point
Lineage 2 Leaderboards System
"""

import os
import logging
from dotenv import load_dotenv
import discord
from discord.ext import commands

from config import *
from models import init_db
from trackers import setup_trackers
from scheduler import setup_scheduler, update_leaderboard_task

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize bot with intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
intents.voice_states = True
intents.guild_messages = True
intents.reactions = True

bot = commands.Bot(command_prefix='!', intents=intents)


@bot.event
async def on_ready():
    """Bot startup sequence"""
    logger.info(f'✅ Bot logged in as {bot.user}')
    
    # Initialize database
    init_db()
    logger.info('✅ Database initialized')
    
    # Setup all event trackers
    setup_trackers(bot)
    logger.info('✅ Trackers started')
    
    # Setup scheduler (5-min updates & monthly reset)
    setup_scheduler(bot)
    logger.info('✅ Scheduler started')
    
    # Initial leaderboard update
    try:
        await update_leaderboard_task(bot)
        logger.info('✅ Initial leaderboard created')
    except Exception as e:
        logger.error(f'Error creating initial leaderboard: {e}')
    
    logger.info('🚀 Bot is fully operational!')
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="Lineage 2 Stats"
        )
    )


@bot.command(name='leaderboard')
@commands.has_role('Admin')
async def update_leaderboard(ctx):
    """Manually update leaderboard - Admin only"""
    try:
        await ctx.defer()
        await update_leaderboard_task(bot)
        await ctx.followup.send('✅ Leaderboard updated!')
        logger.info(f'📊 Leaderboard manually updated by {ctx.author.name}')
    except Exception as e:
        await ctx.followup.send(f'❌ Error: {str(e)}')
        logger.error(f'Error updating leaderboard: {e}')


@bot.event
async def on_error(event, *args, **kwargs):
    """Error handler"""
    logger.error(f'Error in {event}:', exc_info=True)


def main():
    """Main entry point"""
    token = os.getenv('DISCORD_TOKEN')
    
    if not token:
        logger.error('❌ DISCORD_TOKEN not found in .env file')
        return
    
    try:
        bot.run(token)
    except Exception as e:
        logger.error(f'❌ Failed to start bot: {e}')


if __name__ == '__main__':
    main()
