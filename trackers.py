"""
Updated trackers.py - Rentals Fixed - Tracks item count by USERNAME
Tracks all user activities and parses bot embeds
"""

import re
import logging
import discord
from config import *
from models import (
    increment_stat, start_voice_session, end_voice_session,
    start_activity_session, end_activity_session
)

logger = logging.getLogger(__name__)

# Track rental item counts per username to detect changes
RENTAL_ITEM_COUNTS = {}  # Format: {username: item_count}


def get_rental_item_count_by_username(desc: str, username: str) -> int:
    """
    Extract how many items this user is currently renting
    Format in embed: "Má: Username"
    
    Returns count of items they have listed
    """
    # Find section for this user: "Má: Username" followed by items
    user_pattern = rf'Má:\s+{re.escape(username)}\s*\n([\s\S]*?)(?=Má:|Vzal si|$)'
    match = re.search(user_pattern, desc)
    
    if not match:
        return 0
    
    items_text = match.group(1)
    # Count item lines (lines with emoji + item name)
    # Filter out "Dostupný" lines
    items = [line.strip() for line in items_text.split('\n') 
             if line.strip() and 'Dostupný' not in line and '✅' not in line and '❌' not in line]
    return len(items)


def setup_trackers(bot):
    """Setup all event listeners"""
    
    @bot.event
    async def on_voice_state_update(member, before, after):
        """Track voice channel time"""
        if member.guild.id != GUILD_ID:
            return
        
        if member.bot:
            return
        
        user_id = str(member.id)
        username = member.display_name
        
        # User joined voice
        if not before.channel and after.channel:
            start_voice_session(user_id, username)
            logger.info(f'🎙️ {username} joined voice')
        
        # User left voice
        elif before.channel and not after.channel:
            end_voice_session(user_id, username)
            logger.info(f'🎙️ {username} left voice')
    
    
    @bot.event
    async def on_message(message):
        """Track messages, AQ UP calls, screenshots"""
        if message.guild is None or message.guild.id != GUILD_ID:
            return
        
        if message.author.bot:
            # Parse bot embeds instead
            await parse_bot_embeds(bot, message)
            return
        
        user_id = str(message.author.id)
        username = message.author.display_name
        
        # Count message
        increment_stat(user_id, username, 'message_count', 1)
        
        # Count AQ UP calls
        if 'AQ UP' in message.content.upper():
            increment_stat(user_id, username, 'aq_calls', 1)
            logger.info(f'📢 {username} called AQ UP')
        
        # Count screenshots in screenshots channel
        if message.channel.id == SCREENSHOTS_CHANNEL_ID:
            if message.attachments or message.embeds:
                increment_stat(user_id, username, 'screenshot_count', 1)
                logger.info(f'📸 {username} posted screenshot')
        
        await bot.process_commands(message)
    
    
    @bot.event
    async def on_message_edit(before, after):
        """Track edited messages (catches Navrátil rental updates)"""
        if after.guild is None or after.guild.id != GUILD_ID:
            return
        
        if not after.author.bot:
            return
        
        # Parse bot embeds on edit (Navrátil updates existing rental embeds)
        await parse_bot_embeds(bot, after)
    
    
    @bot.event
    async def on_reaction_add(reaction, user):
        """Track reactions received"""
        if reaction.message.guild is None or reaction.message.guild.id != GUILD_ID:
            return
        
        # ✅ FIX: Check message author exists and is not a bot
        if not reaction.message.author:
            return
        
        if reaction.message.author.bot:
            return
        
        if user.bot:
            return
        
        author_id = str(reaction.message.author.id)
        author_name = reaction.message.author.display_name
        
        # ✅ Track reaction
        increment_stat(author_id, author_name, 'reaction_count', 1)
        logger.info(f'👍 {author_name} received reaction from {user.display_name}')
    
    
    @bot.event
    async def on_presence_update(before, after):
        """Track Lineage 2 Reborn playtime"""
        if after.guild.id != GUILD_ID:
            return
        
        if after.bot:
            return
        
        user_id = str(after.id)
        
        # Get member for username
        try:
            member = await after.guild.fetch_member(int(user_id))
            username = member.display_name
        except Exception:
            return
        
        # Find L2Reborn activity
        old_activity = None
        new_activity = None
        
        if before and before.activities:
            old_activity = next(
                (a for a in before.activities if 'L2Reborn' in a.name),
                None
            )
        
        if after.activities:
            new_activity = next(
                (a for a in after.activities if 'L2Reborn' in a.name),
                None
            )
        
        # Started playing L2Reborn
        if not old_activity and new_activity:
            start_activity_session(user_id, username)
            logger.info(f'⚔️ {username} started playing L2Reborn')
        
        # Stopped playing L2Reborn
        elif old_activity and not new_activity:
            end_activity_session(user_id, username)
            logger.info(f'⚔️ {username} stopped playing L2Reborn')
    
    
    logger.info('✅ All event trackers registered')


async def parse_bot_embeds(bot, message):
    """Parse embeds from tracked bots"""
    guild = message.guild
    
    if not message.embeds:
        return
    
    # Ignore own bot embeds
    if message.author.id == bot.user.id:
        return
    
    embed = message.embeds[0]
    bot_username = message.author.name
    
    try:
        # Apollo Bot - Event attendance
        if bot_username == BOT_NAMES['apollo'] and embed.description:
            await parse_apollo_embed(guild, embed)
        
        # Party Maker Bot - Party creation
        elif bot_username == BOT_NAMES['party_maker'] and embed.description:
            await parse_party_embed(guild, embed)
        
        # Rental Bot - Rentals (Navrátil) - Track by item count changes
        elif bot_username == BOT_NAMES['rental'] and embed.description:
            await parse_rental_embed(guild, embed)
        
        # DEBUG: Log unmatched bot embeds for tracking
        else:
            logger.info(f'🔍 [UNMATCHED BOT] "{bot_username}" | Expected: {list(BOT_NAMES.values())}')
    
    except Exception as e:
        logger.error(f'Error parsing embed from {bot_username}: {e}', exc_info=True)


async def parse_apollo_embed(guild, embed):
    """Parse Apollo bot event attendance"""
    desc = embed.description
    
    if not desc:
        return
    
    # Find "Accepted (N)" section
    accepted_pattern = r'✅ Accepted \((\d+)\)([\s\S]*?)(?=❌|$)'
    match = re.search(accepted_pattern, desc)
    
    if match:
        # Extract user mentions
        mentions = re.findall(r'<@!?(\d+)>', match.group(2))
        
        for user_id in mentions:
            try:
                member = await guild.fetch_member(int(user_id))
                increment_stat(user_id, member.display_name, 'apollo_events', 1)
                logger.info(f'📅 {member.display_name} attendance recorded')
            except Exception as e:
                logger.error(f'Error fetching member {user_id}: {e}')


async def parse_party_embed(guild, embed):
    """Parse Party Maker bot party creation"""
    desc = embed.description
    
    if not desc:
        return
    
    # Find party creator "Založatel: @user" or "Zakladatel: @user"
    creator_pattern = r'[Zz]akladatel[a]?:\s*<@!?(\d+)>'
    match = re.search(creator_pattern, desc)
    
    if match:
        user_id = match.group(1)
        try:
            member = await guild.fetch_member(int(user_id))
            increment_stat(user_id, member.display_name, 'party_count', 1)
            logger.info(f'👥 {member.display_name} party counted')
        except Exception as e:
            logger.error(f'Error fetching member {user_id}: {e}')


async def parse_rental_embed(guild, embed):
    """Parse Rental bot rental usage (Navrátil)
    
    Detects item count changes by USERNAME (not user ID):
    - If items increased → +1 rental for each new item
    - If items decreased or same → skip (item was returned)
    
    Format: "Má: Username\n  🔲 ItemName\n    Dostupný"
    """
    desc = embed.description
    
    if not desc:
        return
    
    # Find all users with items: "Má: Username"
    owner_pattern = r'Má:\s+([^\n]+)'
    matches = re.finditer(owner_pattern, desc)
    
    for match in matches:
        username = match.group(1).strip()
        
        try:
            # Get current item count
            current_count = get_rental_item_count_by_username(desc, username)
            
            # Get previous count (default 0 if first time seeing this user)
            previous_count = RENTAL_ITEM_COUNTS.get(username, 0)
            
            # Calculate difference
            item_diff = current_count - previous_count
            
            # Only count if items INCREASED (new rental)
            if item_diff > 0:
                # Try to find Discord member by username
                try:
                    # Search in guild members
                    member = None
                    async for m in guild.fetch_members(limit=None):
                        if m.display_name == username or m.name == username:
                            member = m
                            break
                    
                    if member:
                        # Add +1 for EACH new item
                        for _ in range(item_diff):
                            increment_stat(str(member.id), member.display_name, 'rental_count', 1)
                            logger.info(f'🔑 {member.display_name} rented new item ({current_count} total)')
                    else:
                        logger.warning(f'🔑 Could not find member "{username}" - rental count +{item_diff} not recorded')
                
                except Exception as e:
                    logger.error(f'Error fetching member {username}: {e}')
            
            elif item_diff < 0:
                logger.info(f'🔄 {username} returned item ({current_count} remaining)')
            
            # Update tracking
            RENTAL_ITEM_COUNTS[username] = current_count
            
        except Exception as e:
            logger.error(f'Error processing rental for {username}: {e}')
