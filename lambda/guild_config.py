"""
Guild configuration management.
Stores per-guild settings in DynamoDB for multi-server support.
"""
import boto3
import os
from typing import Optional, Dict, Any
from datetime import datetime


# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')
configs_table = dynamodb.Table(os.environ.get('DYNAMODB_GUILD_CONFIGS_TABLE', 'discord-guild-configs'))


def get_guild_config(guild_id: str) -> Optional[Dict[str, Any]]:
    """
    Get configuration for a specific guild.

    Args:
        guild_id: Discord guild ID

    Returns:
        Guild config dict or None if not configured
    """
    try:
        response = configs_table.get_item(Key={'guild_id': guild_id})
        config = response.get('Item')

        if config:
            print(f"Found config for guild {guild_id}: role={config.get('role_id')}, channel={config.get('channel_id')}")
        else:
            print(f"No config found for guild {guild_id}")

        return config
    except Exception as e:
        print(f"Error getting guild config: {e}")
        return None


def save_guild_config(
    guild_id: str,
    role_id: str,
    channel_id: str,
    setup_by_user_id: str,
    allowed_domains: Optional[list] = None,
    custom_message: Optional[str] = None
) -> bool:
    """
    Save or update guild configuration.

    Args:
        guild_id: Discord guild ID
        role_id: Verification role ID
        channel_id: Channel ID for verification message
        setup_by_user_id: User ID who ran setup
        allowed_domains: Optional list of allowed email domains (defaults to auburn.edu, student.sans.edu)
        custom_message: Optional custom verification message

    Returns:
        True if saved successfully, False otherwise
    """
    try:
        now = datetime.utcnow()

        if allowed_domains is None:
            allowed_domains = ['auburn.edu', 'student.sans.edu']

        if custom_message is None:
            custom_message = "Click the button below to verify your email address."

        config_item = {
            'guild_id': guild_id,
            'role_id': role_id,
            'channel_id': channel_id,
            'allowed_domains': allowed_domains,
            'custom_message': custom_message,
            'setup_by': setup_by_user_id,
            'setup_timestamp': now.isoformat(),
            'last_updated': now.isoformat()
        }

        configs_table.put_item(Item=config_item)
        print(f"Saved config for guild {guild_id}: role={role_id}, channel={channel_id}")
        return True

    except Exception as e:
        print(f"Error saving guild config: {e}")
        return False


def is_guild_configured(guild_id: str) -> bool:
    """
    Check if a guild has been configured.

    Args:
        guild_id: Discord guild ID

    Returns:
        True if guild is configured, False otherwise
    """
    config = get_guild_config(guild_id)
    return config is not None and 'role_id' in config and 'channel_id' in config


def get_guild_role_id(guild_id: str) -> Optional[str]:
    """
    Get the verification role ID for a guild.

    Args:
        guild_id: Discord guild ID

    Returns:
        Role ID or None if not configured
    """
    config = get_guild_config(guild_id)
    return config.get('role_id') if config else None


def get_guild_allowed_domains(guild_id: str) -> list:
    """
    Get the allowed email domains for a guild.

    Args:
        guild_id: Discord guild ID

    Returns:
        List of allowed domains (defaults to auburn.edu, student.sans.edu)
    """
    config = get_guild_config(guild_id)
    if config and 'allowed_domains' in config:
        return config['allowed_domains']

    # Default domains if not configured
    return ['auburn.edu', 'student.sans.edu']


def get_guild_custom_message(guild_id: str) -> str:
    """
    Get the custom verification message for a guild.

    Args:
        guild_id: Discord guild ID

    Returns:
        Custom message or default message if not configured
    """
    config = get_guild_config(guild_id)
    if config and 'custom_message' in config:
        return config['custom_message']

    # Default message if not configured
    return "Click the button below to verify your email address."


def delete_guild_config(guild_id: str) -> bool:
    """
    Delete guild configuration.

    Args:
        guild_id: Discord guild ID

    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        configs_table.delete_item(Key={'guild_id': guild_id})
        print(f"Deleted config for guild {guild_id}")
        return True
    except Exception as e:
        print(f"Error deleting guild config: {e}")
        return False
