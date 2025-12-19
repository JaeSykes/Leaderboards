""
Leaderboard Generator and Formatter
Creates beautiful embed messages with top statistics
"""

import logging
import discord
from datetime import datetime

from config import *
from models import get_top_stats, get_leaderboard_message, save_leaderboard_message

logger = logging.getLogger(__name__)


def format_stat_value(stat_name: str, value: int) -> str:
    """Format statistic value based on type"""
    if stat_name == 'voice_time' or stat_name == 'lineage_time':
        # Convert seconds to hours:minutes
        hours = value // 3600
        minutes = (value % 3600) // 60
        return f'{hours}h {minutes}m'
    else:
        return str(value)


def create_leaderboard_embed(stats: dict, table_type: str, limit: int = 4) -> discord.Embed:
    """Create a formatted leaderboard embed with 4-column layout"""
    
    if table_type == 'monthly':
        color = EMBED_COLOR_MONTHLY
        title = '📊 MĚSÍČNÍ LEADERBOARD'
        timestamp = datetime.now()
    else:
        color = EMBED_COLOR_OVERALL
        title = '🏆 CELKOVÝ LEADERBOARD'
        timestamp = datetime.now()
    
    embed = discord.Embed(
        title=title,
        color=color,
        timestamp=timestamp,
        description='Nejlepších hráčů v každé kategorii'
    )
    
    embed.set_footer(text='Aktualizováno • Lineage 2 Stats')
    
    # Add each category in 4-column layout
    col_count = 0
    for stat_key, category_name in STAT_CATEGORIES.items():
        leaderboard_data = stats.get(stat_key, [])
        
        if not leaderboard_data:
            value = '❌ Žádná data'
        else:
            lines = []
            medals = ['🥇', '🥈', '🥉', '4️⃣']
            
            for idx, entry in enumerate(leaderboard_data[:limit]):
                medal = medals[idx] if idx < len(medals) else f'{idx + 1}.'
                username = entry['username'][:18] # Truncate long names
                formatted_value = format_stat_value(stat_key, entry['value'])
                lines.append(f'{medal} {username}\n  {formatted_value}')
            
            value = '\n'.join(lines)
        
        # 4 columns per row (inline=True creates columns)
        embed.add_field(
            name=category_name,
            value=value,
            inline=True
        )
        
        col_count += 1
        
        # Add empty field to force line break after every 4 columns
        if col_count % 4 == 0 and col_count < len(STAT_CATEGORIES):
            embed.add_field(name='\u200b', value='\u200b', inline=False)
    
    return embed


async def update_leaderboard(bot):
    """Update permanent leaderboard embeds"""
    try:
        channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
        if not channel:
            logger.error(f'❌ Leaderboard channel not found: {LEADERBOARD_CHANNEL_ID}')
            return
        
        # Get monthly and overall stats
        monthly_stats = get_top_stats('monthly_stats', TOP_LIMIT)
        overall_stats = get_top_stats('overall_stats', TOP_LIMIT)
        
        # Create embeds
        monthly_embed = create_leaderboard_embed(monthly_stats, 'monthly', TOP_LIMIT)
        overall_embed = create_leaderboard_embed(overall_stats, 'overall', TOP_LIMIT)
        
        # Get or create messages
        monthly_msg_id = get_leaderboard_message('monthly')
        overall_msg_id = get_leaderboard_message('overall')
        
        # Update or send monthly leaderboard
        if monthly_msg_id:
            try:
                msg = await channel.fetch_message(monthly_msg_id)
                await msg.edit(embed=monthly_embed)
                logger.info('✅ Monthly leaderboard updated')
            except discord.NotFound:
                # Message was deleted, send new one
                msg = await channel.send(embed=monthly_embed)
                save_leaderboard_message('monthly', msg.id)
                logger.info('✅ Monthly leaderboard message recreated')
        else:
            msg = await channel.send(embed=monthly_embed)
            save_leaderboard_message('monthly', msg.id)
            logger.info('✅ Monthly leaderboard message created')
        
        # Update or send overall leaderboard
        if overall_msg_id:
            try:
                msg = await channel.fetch_message(overall_msg_id)
                await msg.edit(embed=overall_embed)
                logger.info('✅ Overall leaderboard updated')
            except discord.NotFound:
                # Message was deleted, send new one
                msg = await channel.send(embed=overall_embed)
                save_leaderboard_message('overall', msg.id)
                logger.info('✅ Overall leaderboard message recreated')
        else:
            msg = await channel.send(embed=overall_embed)
            save_leaderboard_message('overall', msg.id)
            logger.info('✅ Overall leaderboard message created')
    
    except Exception as e:
        logger.error(f'❌ Error updating leaderboard: {e}')


async def announce_monthly_winners(bot):
    """Announce monthly winners"""
    try:
        channel = bot.get_channel(ANNOUNCEMENT_CHANNEL_ID)
        if not channel:
            logger.error(f'❌ Announcement channel not found: {ANNOUNCEMENT_CHANNEL_ID}')
            return
        
        # Get monthly stats
        monthly_stats = get_top_stats('monthly_stats', TOP_LIMIT)
        
        # Create announcement embed
        embed = discord.Embed(
            title='🏆 MĚSÍČNÍ TOP HRÁČI 🏆',
            color=EMBED_COLOR_ANNOUNCEMENT,
            timestamp=datetime.now()
        )
        
        embed.set_footer(text=f'Měsíc: {datetime.now().strftime("%B %Y")}')
        
        # Add top categories (one per line for announcement)
        for stat_key, category_name in STAT_CATEGORIES.items():
            leaderboard_data = monthly_stats.get(stat_key, [])
            if leaderboard_data:
                top_player = leaderboard_data[0]
                username = top_player['username']
                value = format_stat_value(stat_key, top_player['value'])
                medal = '🥇'
                
                embed.add_field(
                    name=category_name,
                    value=f'{medal} **{username}** - {value}',
                    inline=False
                )
        
        await channel.send(embed=embed)
        logger.info('✅ Monthly winners announced')
    
    except Exception as e:
        logger.error(f'❌ Error announcing winners: {e}')
