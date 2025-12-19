"""
Event Trackers and Embed Parsers
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
        username = member.name
        
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
        username = message.author.name
        
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
    async def on_reaction_add(reaction, user):
        """Track reactions received"""
        if reaction.message.guild is None or reaction.message.guild.id != GUILD_ID:
            return
        
        if not reaction.message.author or reaction.message.author.bot:
            return
        
        if user.bot:
            return
        
        author_id = str(reaction.message.author.id)
        author_name = reaction.message.author.name
        
        increment_stat(author_id, author_name, 'reaction_count', 1)
    
    
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
            username = member.name
        except Exception:
            return
        
        # Find Lineage activity
        old_activity = None
        new_activity = None
        
        if before and before.activities:
            old_activity = next(
                (a for a in before.activities if 'Lineage' in a.name),
                None
            )
        
        if after.activities:
            new_activity = next(
                (a for a in after.activities if 'Lineage' in a.name),
                None
            )
        
        # Started playing Lineage
        if not old_activity and new_activity:
            start_activity_session(user_id, username)
            logger.info(f'⚔️ {username} started playing Lineage 2')
        
        # Stopped playing Lineage
        elif old_activity and not new_activity:
            end_activity_session(user_id, username)
            logger.info(f'⚔️ {username} stopped playing Lineage 2')
    
    
    logger.info('✅ All event trackers registered')


async def parse_bot_embeds(bot, message):
    """Parse embeds from tracked bots"""
    guild = message.guild
    
    if not message.embeds:
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
        
        # Accounting Bot - CP turnover
        elif bot_username == BOT_NAMES['accounting'] and embed.title:
            await parse_accounting_embed(guild, embed)
        
        # Rental Bot - Rentals
        elif bot_username == BOT_NAMES['rental'] and embed.description:
            await parse_rental_embed(guild, embed)
    
    except Exception as e:
        logger.error(f'Error parsing embed from {bot_username}: {e}')


async def parse_apollo_embed(guild, embed):
    """Parse Apollo bot event attendance"""
    desc = embed.description
    
    # Find "Accepted (N)" section
    accepted_pattern = r'✅ Accepted \((\d+)\)([\s\S]*?)(?=❌|$)'
    match = re.search(accepted_pattern, desc)
    
    if match:
        # Extract user mentions
        mentions = re.findall(r'<@!?(\d+)>', match.group(2))
        
        for user_id in mentions:
            try:
                member = await guild.fetch_member(int(user_id))
                increment_stat(user_id, member.name, 'apollo_events', 1)
                logger.info(f'📅 {member.name} attendance recorded')
            except Exception as e:
                logger.error(f'Error fetching member {user_id}: {e}')


async def parse_party_embed(guild, embed):
    """Parse Party Maker bot party creation"""
    desc = embed.description
    
    # Find party creator "Založatel: @user"
    creator_pattern = r'Založatel:\s*<@!?(\d+)>'
    match = re.search(creator_pattern, desc)
    
    if match:
        user_id = match.group(1)
        try:
            member = await guild.fetch_member(int(user_id))
            increment_stat(user_id, member.name, 'party_count', 1)
            logger.info(f'👥 {member.name} party counted')
        except Exception as e:
            logger.error(f'Error fetching member {user_id}: {e}')


async def parse_accounting_embed(guild, embed):
    """Parse Accounting bot CP turnover"""
    desc = embed.description or ''
    title = embed.title or ''
    
    if 'Nová Transakce' not in title:
        return
    
    # Find amount pattern "Nový pohyb: X Adena"
    amount_pattern = r'Nový pohyb:\s*([-\d.,]+)\s*Adena'
    amount_match = re.search(amount_pattern, desc)
    
    if amount_match:
        amount_str = amount_match.group(1).replace(',', '').replace('.', '')
        try:
            amount = abs(int(amount_str))
            
            # Try to find who made the transaction
            # Look for mentions in description
            mentions = re.findall(r'<@!?(\d+)>', desc)
            
            if mentions:
                user_id = mentions[0]
                try:
                    member = await guild.fetch_member(int(user_id))
                    increment_stat(user_id, member.name, 'cp_turnover', amount)
                    logger.info(f'💰 {member.name} CP turnover: {amount}')
                except Exception as e:
                    logger.error(f'Error fetching member {user_id}: {e}')
        
        except ValueError:
            logger.warning(f'Could not parse CP amount: {amount_match.group(1)}')


async def parse_rental_embed(guild, embed):
    """Parse Rental bot rental usage"""
    desc = embed.description
    
    # Find rental owner "Má: @user"
    owner_pattern = r'Má:\s*<@!?(\d+)>'
    match = re.search(owner_pattern, desc)
    
    if match:
        user_id = match.group(1)
        try:
            member = await guild.fetch_member(int(user_id))
            increment_stat(user_id, member.name, 'rental_count', 1)
            logger.info(f'🔑 {member.name} rental counted')
        except Exception as e:
            logger.error(f'Error fetching member {user_id}: {e}')
