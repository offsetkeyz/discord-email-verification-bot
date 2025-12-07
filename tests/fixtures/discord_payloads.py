"""
Sample Discord interaction payloads for testing.

This module provides realistic Discord API payloads for:
- PING interactions
- Slash command interactions
- Button click interactions
- Modal submission interactions
- Member objects with various permission levels
"""

import json
from datetime import datetime, timedelta


# ==============================================================================
# Discord Interaction Types
# ==============================================================================

INTERACTION_PING = 1
INTERACTION_APPLICATION_COMMAND = 2
INTERACTION_MESSAGE_COMPONENT = 3
INTERACTION_MODAL_SUBMIT = 5


# ==============================================================================
# Component Types
# ==============================================================================

COMPONENT_TYPE_BUTTON = 2
COMPONENT_TYPE_SELECT_MENU = 3


# ==============================================================================
# Permission Flags
# ==============================================================================

PERMISSION_ADMINISTRATOR = 0x8
PERMISSION_MANAGE_GUILD = 0x20
PERMISSION_MANAGE_ROLES = 0x10000000


# ==============================================================================
# PING Interactions
# ==============================================================================

def get_ping_payload():
    """Discord PING interaction for endpoint verification."""
    return {
        "type": INTERACTION_PING,
        "id": "1234567890123456789",
        "application_id": "1234567890",
        "token": "unique_interaction_token_abc123"
    }


# ==============================================================================
# Member Objects
# ==============================================================================

def get_admin_member(user_id="789012", username="admin_user"):
    """Member object with ADMINISTRATOR permission."""
    return {
        "user": {
            "id": user_id,
            "username": username,
            "discriminator": "0001",
            "avatar": "avatar_hash_123"
        },
        "roles": ["role_id_111", "role_id_222"],
        "nick": f"{username}_nick",
        "permissions": str(PERMISSION_ADMINISTRATOR)
    }


def get_regular_member(user_id="789013", username="regular_user"):
    """Member object without admin permissions."""
    return {
        "user": {
            "id": user_id,
            "username": username,
            "discriminator": "0002",
            "avatar": "avatar_hash_456"
        },
        "roles": ["role_id_333"],
        "nick": f"{username}_nick",
        "permissions": str(PERMISSION_MANAGE_ROLES)  # Not admin
    }


def get_member_with_verified_role(user_id="789014", role_id="111222"):
    """Member object that already has the verified role."""
    return {
        "user": {
            "id": user_id,
            "username": "verified_user",
            "discriminator": "0003"
        },
        "roles": [role_id, "other_role_id"],
        "permissions": "0"
    }


# ==============================================================================
# Slash Command Interactions - /setup-email-verification
# ==============================================================================

def get_setup_command_payload(user_id="789012", guild_id="123456", is_admin=True):
    """
    /setup-email-verification command interaction.

    Args:
        user_id: Discord user ID
        guild_id: Discord guild ID
        is_admin: Whether user has ADMINISTRATOR permission
    """
    permissions = str(PERMISSION_ADMINISTRATOR) if is_admin else str(PERMISSION_MANAGE_ROLES)

    return {
        "type": INTERACTION_APPLICATION_COMMAND,
        "id": "interaction_id_setup_001",
        "application_id": "1234567890",
        "token": "setup_interaction_token",
        "guild_id": guild_id,
        "channel_id": "channel_id_999",
        "member": {
            "user": {
                "id": user_id,
                "username": "setup_user",
                "discriminator": "0001"
            },
            "roles": ["role_id_111"],
            "permissions": permissions
        },
        "data": {
            "id": "command_id_123",
            "name": "setup-email-verification",
            "type": 1
        }
    }


# ==============================================================================
# Button Click Interactions - Verification Flow
# ==============================================================================

def get_start_verification_button_payload(user_id="789012", guild_id="123456"):
    """Start Verification button click."""
    return {
        "type": INTERACTION_MESSAGE_COMPONENT,
        "id": "interaction_id_start_001",
        "application_id": "1234567890",
        "token": "start_verification_token",
        "guild_id": guild_id,
        "channel_id": "channel_id_999",
        "member": get_regular_member(user_id=user_id),
        "message": {
            "id": "message_id_777",
            "channel_id": "channel_id_999",
            "content": "Click the button to verify!",
            "components": []
        },
        "data": {
            "custom_id": "start_verification",
            "component_type": COMPONENT_TYPE_BUTTON
        }
    }


def get_submit_code_button_payload(user_id="789012", guild_id="123456"):
    """Submit Verification Code button click."""
    return {
        "type": INTERACTION_MESSAGE_COMPONENT,
        "id": "interaction_id_submit_001",
        "application_id": "1234567890",
        "token": "submit_code_token",
        "guild_id": guild_id,
        "channel_id": "channel_id_999",
        "member": get_regular_member(user_id=user_id),
        "data": {
            "custom_id": "submit_code",
            "component_type": COMPONENT_TYPE_BUTTON
        }
    }


# ==============================================================================
# Button Click Interactions - Setup Flow
# ==============================================================================

def get_setup_button_payload(button_id, user_id="789012", guild_id="123456", is_admin=True):
    """
    Setup flow button clicks.

    Args:
        button_id: One of 'setup_domains', 'setup_message_link', 'setup_skip_message',
                   'setup_approve', 'setup_cancel'
        user_id: Discord user ID
        guild_id: Discord guild ID
        is_admin: Whether user has ADMINISTRATOR permission
    """
    permissions = str(PERMISSION_ADMINISTRATOR) if is_admin else str(PERMISSION_MANAGE_ROLES)

    return {
        "type": INTERACTION_MESSAGE_COMPONENT,
        "id": f"interaction_id_{button_id}_001",
        "application_id": "1234567890",
        "token": f"{button_id}_token",
        "guild_id": guild_id,
        "channel_id": "channel_id_999",
        "member": {
            "user": {
                "id": user_id,
                "username": "setup_admin",
                "discriminator": "0001"
            },
            "roles": ["role_id_111"],
            "permissions": permissions
        },
        "message": {
            "id": "setup_message_id",
            "flags": 64  # EPHEMERAL
        },
        "data": {
            "custom_id": button_id,
            "component_type": COMPONENT_TYPE_BUTTON
        }
    }


# ==============================================================================
# Select Menu Interactions - Setup Flow
# ==============================================================================

def get_setup_role_select_payload(role_id="111222", user_id="789012", guild_id="123456"):
    """Role selection in setup flow."""
    return {
        "type": INTERACTION_MESSAGE_COMPONENT,
        "id": "interaction_id_role_select_001",
        "application_id": "1234567890",
        "token": "role_select_token",
        "guild_id": guild_id,
        "channel_id": "channel_id_999",
        "member": get_admin_member(user_id=user_id),
        "message": {
            "id": "setup_message_id",
            "flags": 64
        },
        "data": {
            "custom_id": "setup_role_select",
            "component_type": COMPONENT_TYPE_SELECT_MENU,
            "values": [role_id]
        }
    }


def get_setup_channel_select_payload(channel_id="999888", user_id="789012", guild_id="123456"):
    """Channel selection in setup flow."""
    return {
        "type": INTERACTION_MESSAGE_COMPONENT,
        "id": "interaction_id_channel_select_001",
        "application_id": "1234567890",
        "token": "channel_select_token",
        "guild_id": guild_id,
        "channel_id": "channel_id_999",
        "member": get_admin_member(user_id=user_id),
        "message": {
            "id": "setup_message_id",
            "flags": 64
        },
        "data": {
            "custom_id": "setup_channel_select",
            "component_type": COMPONENT_TYPE_SELECT_MENU,
            "values": [channel_id]
        }
    }


# ==============================================================================
# Modal Submit Interactions - Verification Flow
# ==============================================================================

def get_email_modal_submit_payload(email="test@auburn.edu", user_id="789012", guild_id="123456"):
    """Email submission modal."""
    return {
        "type": INTERACTION_MODAL_SUBMIT,
        "id": "interaction_id_email_001",
        "application_id": "1234567890",
        "token": "email_modal_token",
        "guild_id": guild_id,
        "channel_id": "channel_id_999",
        "member": get_regular_member(user_id=user_id),
        "data": {
            "custom_id": "email_modal",
            "components": [
                {
                    "type": 1,  # ACTION_ROW
                    "components": [
                        {
                            "type": 4,  # TEXT_INPUT
                            "custom_id": "email_input",
                            "value": email
                        }
                    ]
                }
            ]
        }
    }


def get_code_modal_submit_payload(code="123456", user_id="789012", guild_id="123456"):
    """Verification code submission modal."""
    return {
        "type": INTERACTION_MODAL_SUBMIT,
        "id": "interaction_id_code_001",
        "application_id": "1234567890",
        "token": "code_modal_token",
        "guild_id": guild_id,
        "channel_id": "channel_id_999",
        "member": get_regular_member(user_id=user_id),
        "data": {
            "custom_id": "code_modal",
            "components": [
                {
                    "type": 1,
                    "components": [
                        {
                            "type": 4,
                            "custom_id": "code_input",
                            "value": code
                        }
                    ]
                }
            ]
        }
    }


# ==============================================================================
# Modal Submit Interactions - Setup Flow
# ==============================================================================

def get_domains_modal_submit_payload(domains="auburn.edu, student.sans.edu",
                                      user_id="789012", guild_id="123456"):
    """Domains configuration modal submission."""
    return {
        "type": INTERACTION_MODAL_SUBMIT,
        "id": "interaction_id_domains_001",
        "application_id": "1234567890",
        "token": "domains_modal_token",
        "guild_id": guild_id,
        "channel_id": "channel_id_999",
        "member": get_admin_member(user_id=user_id),
        "message": {
            "id": "setup_message_id",
            "flags": 64
        },
        "data": {
            "custom_id": "domains_modal",
            "components": [
                {
                    "type": 1,
                    "components": [
                        {
                            "type": 4,
                            "custom_id": "domains_input",
                            "value": domains
                        }
                    ]
                }
            ]
        }
    }


def get_message_link_modal_submit_payload(message_link, user_id="789012", guild_id="123456"):
    """
    Message link modal submission.

    Args:
        message_link: Discord message link (e.g., https://discord.com/channels/123456/999888/777666)
    """
    return {
        "type": INTERACTION_MODAL_SUBMIT,
        "id": "interaction_id_msglink_001",
        "application_id": "1234567890",
        "token": "msglink_modal_token",
        "guild_id": guild_id,
        "channel_id": "channel_id_999",
        "member": get_admin_member(user_id=user_id),
        "message": {
            "id": "setup_message_id",
            "flags": 64
        },
        "data": {
            "custom_id": "message_link_modal",
            "components": [
                {
                    "type": 1,
                    "components": [
                        {
                            "type": 4,
                            "custom_id": "message_link_input",
                            "value": message_link
                        }
                    ]
                }
            ]
        }
    }


# ==============================================================================
# API Gateway Event Wrappers
# ==============================================================================

def create_api_gateway_event(interaction_payload, signature="valid_signature", timestamp=None):
    """
    Wrap Discord interaction in API Gateway Lambda event.

    Args:
        interaction_payload: Dict of Discord interaction data
        signature: Ed25519 signature (hex string)
        timestamp: Unix timestamp string (defaults to current time)

    Returns:
        Dict in API Gateway Lambda event format
    """
    if timestamp is None:
        timestamp = str(int(datetime.utcnow().timestamp()))

    return {
        "headers": {
            "x-signature-ed25519": signature,
            "x-signature-timestamp": timestamp,
            "content-type": "application/json"
        },
        "body": json.dumps(interaction_payload),
        "requestContext": {
            "http": {
                "method": "POST",
                "path": "/interactions"
            }
        }
    }


# ==============================================================================
# Discord REST API Responses
# ==============================================================================

def get_discord_message_response(message_id="777666", channel_id="999888",
                                  guild_id="123456", content="Verify your email! 📧"):
    """Mock response from GET /channels/{channel_id}/messages/{message_id}"""
    return {
        "id": message_id,
        "channel_id": channel_id,
        "guild_id": guild_id,
        "content": content,
        "author": {
            "id": "1234567890",
            "username": "verification_bot",
            "discriminator": "0000",
            "bot": True
        },
        "timestamp": datetime.utcnow().isoformat(),
        "type": 0,  # DEFAULT
        "flags": 0
    }


def get_discord_member_response(user_id="789012", roles=None, username="testuser"):
    """Mock response from GET /guilds/{guild_id}/members/{user_id}"""
    if roles is None:
        roles = []

    return {
        "user": {
            "id": user_id,
            "username": username,
            "discriminator": "0001",
            "avatar": "avatar_hash"
        },
        "nick": None,
        "roles": roles,
        "joined_at": (datetime.utcnow() - timedelta(days=30)).isoformat(),
        "premium_since": None,
        "deaf": False,
        "mute": False,
        "pending": False,
        "permissions": "0"
    }


# ==============================================================================
# Common Test Scenarios
# ==============================================================================

# Valid message links for testing
VALID_MESSAGE_LINK = "https://discord.com/channels/123456/999888/777666"
INVALID_MESSAGE_LINK_DIFFERENT_GUILD = "https://discord.com/channels/999999/999888/777666"
INVALID_MESSAGE_LINK_FORMAT = "https://not-discord.com/invalid"

# Valid and invalid emails
VALID_AUBURN_EMAIL = "student@auburn.edu"
VALID_SANS_EMAIL = "student@student.sans.edu"
INVALID_EMAIL_WRONG_DOMAIN = "student@gmail.com"
INVALID_EMAIL_FORMAT = "not-an-email"

# Valid and invalid codes
VALID_CODE = "123456"
INVALID_CODE_FORMAT = "12345"  # Too short
INVALID_CODE_LETTERS = "12345a"  # Contains letters
EXPIRED_CODE = "999999"  # Use in tests with time mocking

# Common IDs
TEST_GUILD_ID = "123456"
TEST_USER_ID = "789012"
TEST_ROLE_ID = "111222"
TEST_CHANNEL_ID = "999888"
TEST_MESSAGE_ID = "777666"
