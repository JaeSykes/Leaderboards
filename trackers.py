"""
DEBUGOVACÍ VERZE - trackers.py
Tracks all user activities and parses bot embeds
WITH FULL DEBUG LOGGING FOR NAVRÁTIL EMBED PARSING
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
    """
    user_pattern = rf'Má:\s+{re.escape(username)}\s*\n([\s\S]*?)(?=Má:|Vzal si|$)'
    match = re.search(user_pattern, desc)
    
    if not match:
        logger.debug(f'  ❌ No rental pattern found for "{username}"')
        return 0
    
    items_text = match.group(1)
    items = [line.strip() for line in items_text.split('\n') 
             if line.strip() and 'Dostupný' not in line and '✅' not in line and '❌' not in line]
    logger.debug(f'  📦 {username}: {len(items)} items found')
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
        
        if not before.channel and after.channel:
            start_voice_session(user_id, username)
            logger.info(f'🎙️ {username} joined voice')
        elif before.channel and not after.channel:
            end_voice_session(user_id, username)
            logger.info(f'🎙️ {username} left voice')
    
    
    @bot.event
    async def on_message(message):
        """Track messages, AQ UP calls, screenshots"""
        if message.guild is None or message.guild.id != GUILD_ID:
            return
        
        if message.author.bot:
            await parse_bot_embeds(bot, message)
            return
        
        user_id = str(message.author.id)
        username = message.author.display_name
        
        increment_stat(user_id, username, 'message_count', 1)
        
        if 'AQ UP' in message.content.upper():
            increment_stat(user_id, username, 'aq_calls', 1)
            logger.info(f'📢 {username} called AQ UP')
        
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
        
        logger.info(f'📝 [EDIT] Bot "{after.author.name}" edited message in channel {after.channel.id}')
        await parse_bot_embeds(bot, after)
    
    
    @bot.event
    async def on_reaction_add(reaction, user):
        """Track reactions received"""
        if reaction.message.guild is None or reaction.message.guild.id != GUILD_ID:
            return
        
        if not reaction.message.author:
            return
        
        if reaction.message.author.bot:
            return
        
        if user.bot:
            return
        
        author_id = str(reaction.message.author.id)
        author_name = reaction.message.author.display_name
        
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
        
        try:
            member = await after.guild.fetch_member(int(user_id))
            username = member.display_name
        except Exception:
            return
        
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
        
        if not old_activity and new_activity:
            start_activity_session(user_id, username)
            logger.info(f'⚔️ {username} started playing L2Reborn')
        
        elif old_activity and not new_activity:
            end_activity_session(user_id, username)
            logger.info(f'⚔️ {username} stopped playing L2Reborn')
    
    
    logger.info('✅ All event trackers registered')


async def parse_bot_embeds(bot, message):
    """Parse embeds from tracked bots"""
    guild = message.guild
    
    if not message.embeds:
        logger.debug(f'  No embeds in message from {message.author.name}')
        return
    
    if message.author.id == bot.user.id:
        return
    
    embed = message.embeds[0]
    bot_username = message.author.name
    bot_id = message.author.id
    
    # DEBUG: Log ALL bot embeds
    logger.info(f'🤖 [BOT EMBED] Bot: "{bot_username}" (ID: {bot_id}) | Channel: {message.channel.id}')
    logger.info(f'   Expected rental bot: "{BOT_NAMES.get("rental", "NOT SET")}"')
    
    try:
        # Apollo Bot - Event attendance
        if bot_username == BOT_NAMES['apollo'] and embed.description:
            logger.info(f'✅ Processing Apollo embed')
            await parse_apollo_embed(guild, embed)
        
        # Party Maker Bot - Party creation
        elif bot_username == BOT_NAMES['party_maker'] and embed.description:
            logger.info(f'✅ Processing Party Maker embed')
            await parse_party_embed(guild, embed)
        
        # Rental Bot - Rentals (Navrátil) - Track by item count changes
        elif bot_username == BOT_NAMES['rental'] and embed.description:
            logger.info(f'✅ Processing Navrátil rental embed')
            await parse_rental_embed(guild, embed)
        
        else:
            logger.info(f'🔍 [UNMATCHED] Bot "{bot_username}" did not match any tracker')
            logger.debug(f'   Title: {embed.title}')
            logger.debug(f'   Description: {embed.description[:100] if embed.description else "None"}...')
    
    except Exception as e:
        logger.error(f'❌ Error parsing embed from {bot_username}: {e}', exc_info=True)


async def parse_apollo_embed(guild, embed):
    """Parse Apollo bot event attendance"""
    desc = embed.description
    
    if not desc:
        return
    
    accepted_pattern = r'✅ Accepted \((\d+)\)([\s\S]*?)(?=❌|$)'
    match = re.search(accepted_pattern, desc)
    
    if match:
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
    
    Format: "Má: Username\n  🔲 ItemName\n    Dostupný"
    """
    desc = embed.description
    
    if not desc:
        logger.warning('  No description in Navrátil embed!')
        return
    
    logger.info(f'  📋 Navrátil embed description (first 200 chars):')
    logger.info(f'  {desc[:200]}')
    
    # Find all users with items: "Má: Username"
    owner_pattern = r'Má:\s+([^\n]+)'
    matches = list(re.finditer(owner_pattern, desc))
    
    logger.info(f'  Found {len(matches)} users in rental embed')
    
    for match in matches:
        username = match.group(1).strip()
        logger.info(f'  Processing rental for "{username}"')
        
        try:
            current_count = get_rental_item_count_by_username(desc, username)
            previous_count = RENTAL_ITEM_COUNTS.get(username, 0)
            item_diff = current_count - previous_count
            
            logger.info(f'    Current: {current_count}, Previous: {previous_count}, Diff: {item_diff}')
            
            if item_diff > 0:
                try:
                    member = None
                    async for m in guild.fetch_members(limit=None):
                        if m.display_name == username or m.name == username:
                            member = m
                            break
                    
                    if member:
                        for _ in range(item_diff):
                            increment_stat(str(member.id), member.display_name, 'rental_count', 1)
                            logger.info(f'🔑 {member.display_name} rented new item ({current_count} total)')
                    else:
                        logger.warning(f'    ⚠️ Could not find member "{username}"')
                
                except Exception as e:
                    logger.error(f'    Error fetching member {username}: {e}')
            
            elif item_diff < 0:
                logger.info(f'    🔄 {username} returned item ({current_count} remaining)')
            
            RENTAL_ITEM_COUNTS[username] = current_count
            
        except Exception as e:
            logger.error(f'Error processing rental for {username}: {e}')
