"""
DynamoDB operations for verification state management.
Replaces the SQLite db.py from the original bot.
"""
import boto3
import uuid
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from decimal import Decimal


# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
sessions_table = dynamodb.Table(os.environ.get('DYNAMODB_SESSIONS_TABLE', 'discord-verification-sessions'))
records_table = dynamodb.Table(os.environ.get('DYNAMODB_RECORDS_TABLE', 'discord-verification-records'))


def create_verification_session(
    user_id: str,
    guild_id: str,
    email: str,
    code: str,
    expiry_minutes: int = 15
) -> str:
    """
    Create a new verification session in DynamoDB.

    Args:
        user_id: Discord user ID
        guild_id: Discord guild ID
        email: User's .edu email address
        code: 6-digit verification code
        expiry_minutes: Minutes until code expires (default 15)

    Returns:
        verification_id: Unique ID for this verification
    """
    verification_id = str(uuid.uuid4())
    now = datetime.utcnow()
    expires_at = now + timedelta(minutes=expiry_minutes)
    ttl = int((now + timedelta(hours=24)).timestamp())  # Auto-delete after 24 hours

    session_item = {
        'user_id': user_id,
        'guild_id': guild_id,
        'state': 'awaiting_code',
        'email': email,
        'code': code,
        'verification_id': verification_id,
        'attempts': 0,
        'created_at': now.isoformat(),
        'expires_at': expires_at.isoformat(),
        'ttl': ttl
    }

    record_item = {
        'verification_id': verification_id,
        'user_id': user_id,
        'guild_id': guild_id,
        'user_guild_composite': f"{user_id}#{guild_id}",
        'email': email,
        'code': code,
        'status': 'pending',
        'attempts': 0,
        'created_at': Decimal(str(now.timestamp())),
        'expires_at': Decimal(str(expires_at.timestamp()))
    }

    # Write to both tables
    sessions_table.put_item(Item=session_item)
    records_table.put_item(Item=record_item)

    print(f"Created verification session {verification_id} for user {user_id}")
    return verification_id


def get_verification_session(user_id: str, guild_id: str) -> Optional[Dict[str, Any]]:
    """
    Get active verification session for a user.

    Args:
        user_id: Discord user ID
        guild_id: Discord guild ID

    Returns:
        Session data dict or None if no active session
    """
    try:
        response = sessions_table.get_item(
            Key={'user_id': user_id, 'guild_id': guild_id}
        )
        return response.get('Item')
    except Exception as e:
        print(f"Error getting verification session: {e}")
        return None


def is_user_verified(user_id: str, guild_id: str) -> bool:
    """
    Check if user has already been verified in this guild.

    Args:
        user_id: Discord user ID
        guild_id: Discord guild ID

    Returns:
        True if user has completed verification, False otherwise
    """
    try:
        response = records_table.query(
            IndexName='user_guild-index',
            KeyConditionExpression='user_guild_composite = :composite',
            FilterExpression='#status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':composite': f"{user_id}#{guild_id}",
                ':status': 'verified'
            },
            Limit=1
        )
        return len(response.get('Items', [])) > 0
    except Exception as e:
        print(f"Error checking verification status: {e}")
        return False


def increment_attempts(verification_id: str, user_id: str, guild_id: str) -> int:
    """
    Increment failed verification attempts.

    Args:
        verification_id: Verification ID
        user_id: Discord user ID
        guild_id: Discord guild ID

    Returns:
        New attempt count
    """
    try:
        # Update session table
        sessions_table.update_item(
            Key={'user_id': user_id, 'guild_id': guild_id},
            UpdateExpression='SET attempts = attempts + :inc',
            ExpressionAttributeValues={':inc': 1}
        )

        # Update records table
        response = records_table.update_item(
            Key={'verification_id': verification_id, 'created_at': get_record_created_at(verification_id)},
            UpdateExpression='SET attempts = attempts + :inc',
            ExpressionAttributeValues={':inc': 1},
            ReturnValues='UPDATED_NEW'
        )

        return int(response['Attributes']['attempts'])
    except Exception as e:
        print(f"Error incrementing attempts: {e}")
        return 0


def get_record_created_at(verification_id: str) -> Decimal:
    """Helper to get created_at timestamp for a verification record."""
    try:
        response = records_table.query(
            KeyConditionExpression='verification_id = :vid',
            ExpressionAttributeValues={':vid': verification_id},
            Limit=1
        )
        items = response.get('Items', [])
        if items:
            return items[0]['created_at']
    except Exception as e:
        print(f"Error getting record created_at: {e}")
    return Decimal('0')


def mark_verified(verification_id: str, user_id: str, guild_id: str):
    """
    Mark verification as complete.

    Args:
        verification_id: Verification ID
        user_id: Discord user ID
        guild_id: Discord guild ID
    """
    try:
        now = datetime.utcnow()

        # Update record
        records_table.update_item(
            Key={'verification_id': verification_id, 'created_at': get_record_created_at(verification_id)},
            UpdateExpression='SET #status = :status, verified_at = :verified_at',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'verified',
                ':verified_at': Decimal(str(now.timestamp()))
            }
        )

        # Delete session (verification complete)
        sessions_table.delete_item(Key={'user_id': user_id, 'guild_id': guild_id})

        print(f"Marked verification {verification_id} as verified")
    except Exception as e:
        print(f"Error marking verified: {e}")


def delete_session(user_id: str, guild_id: str):
    """
    Delete a verification session.

    Args:
        user_id: Discord user ID
        guild_id: Discord guild ID
    """
    try:
        sessions_table.delete_item(Key={'user_id': user_id, 'guild_id': guild_id})
        print(f"Deleted session for user {user_id}")
    except Exception as e:
        print(f"Error deleting session: {e}")


def store_pending_setup(setup_id: str, user_id: str, guild_id: str, role_id: str, channel_id: str, allowed_domains: list, custom_message: str, completion_message: str = ""):
    """
    Store pending setup configuration temporarily (5 minute TTL).

    Args:
        setup_id: Unique UUID for this setup session
        user_id: Discord user ID of the admin performing setup
        guild_id: Discord guild ID
        role_id: Discord role ID
        channel_id: Discord channel ID
        allowed_domains: List of allowed email domains
        custom_message: Custom verification message
        completion_message: Custom completion message (optional)
    """
    try:
        from datetime import datetime, timedelta

        # TTL of 5 minutes
        ttl = int((datetime.utcnow() + timedelta(minutes=5)).timestamp())

        sessions_table.put_item(
            Item={
                'user_id': f"setup_{setup_id}",  # Use setup_ prefix to avoid conflicts
                'guild_id': guild_id,
                'setup_id': setup_id,  # Store the UUID
                'admin_user_id': user_id,  # Track who initiated setup
                'role_id': role_id,
                'channel_id': channel_id,
                'allowed_domains': allowed_domains,
                'custom_message': custom_message,
                'completion_message': completion_message,
                'ttl': ttl,
                'created_at': datetime.utcnow().isoformat()
            }
        )
        print(f"Stored pending setup for {setup_id} with completion_message (length: {len(completion_message)})")
    except Exception as e:
        print(f"Error storing pending setup: {e}")


def get_pending_setup(setup_id: str, guild_id: str = None) -> dict:
    """
    Retrieve pending setup configuration.

    Args:
        setup_id: Unique UUID for this setup session
        guild_id: Discord guild ID (required for new UUID-based lookups)

    Returns:
        Dict with setup config or None if not found
    """
    try:
        # Try new format first (with guild_id)
        if guild_id:
            response = sessions_table.get_item(
                Key={
                    'user_id': f"setup_{setup_id}",
                    'guild_id': guild_id
                }
            )
            item = response.get('Item')
            if item:
                return item

        # Fallback to old format for backward compatibility
        response = sessions_table.get_item(
            Key={
                'user_id': setup_id,
                'guild_id': 'PENDING_SETUP'
            }
        )
        return response.get('Item')
    except Exception as e:
        print(f"Error getting pending setup: {e}")
        return None


def delete_pending_setup(setup_id: str, guild_id: str = None):
    """
    Delete pending setup configuration.

    Args:
        setup_id: Unique UUID for this setup session
        guild_id: Discord guild ID (required for new UUID-based deletions)
    """
    try:
        # Try new format first (with guild_id)
        if guild_id:
            sessions_table.delete_item(
                Key={
                    'user_id': f"setup_{setup_id}",
                    'guild_id': guild_id
                }
            )
            print(f"Deleted pending setup for {setup_id}")
            return

        # Fallback to old format for backward compatibility
        sessions_table.delete_item(
            Key={
                'user_id': setup_id,
                'guild_id': 'PENDING_SETUP'
            }
        )
        print(f"Deleted pending setup for {setup_id}")
    except Exception as e:
        print(f"Error deleting pending setup: {e}")


def store_pending_message_capture(capture_id: str, role_id: str, channel_id: str, allowed_domains: list, listening_channel: str):
    """
    Store pending message capture state (2 minute TTL).

    Args:
        capture_id: Unique ID for this capture session (user_id_guild_id)
        role_id: Discord role ID
        channel_id: Discord channel ID for verification
        allowed_domains: List of allowed email domains
        listening_channel: Channel where bot is listening for the message
    """
    try:
        from datetime import datetime, timedelta

        # TTL of 2 minutes
        ttl = int((datetime.utcnow() + timedelta(minutes=2)).timestamp())

        sessions_table.put_item(
            Item={
                'user_id': capture_id,
                'guild_id': 'PENDING_MESSAGE_CAPTURE',
                'role_id': role_id,
                'channel_id': channel_id,
                'allowed_domains': allowed_domains,
                'listening_channel': listening_channel,
                'ttl': ttl,
                'created_at': datetime.utcnow().isoformat()
            }
        )
        print(f"Stored pending message capture for {capture_id}")
    except Exception as e:
        print(f"Error storing pending message capture: {e}")


def get_pending_message_capture(capture_id: str) -> dict:
    """
    Retrieve pending message capture state.

    Args:
        capture_id: Unique ID for this capture session

    Returns:
        Dict with capture config or None if not found
    """
    try:
        response = sessions_table.get_item(
            Key={
                'user_id': capture_id,
                'guild_id': 'PENDING_MESSAGE_CAPTURE'
            }
        )
        return response.get('Item')
    except Exception as e:
        print(f"Error getting pending message capture: {e}")
        return None


def delete_pending_message_capture(capture_id: str):
    """
    Delete pending message capture state.

    Args:
        capture_id: Unique ID for this capture session
    """
    try:
        sessions_table.delete_item(
            Key={
                'user_id': capture_id,
                'guild_id': 'PENDING_MESSAGE_CAPTURE'
            }
        )
        print(f"Deleted pending message capture for {capture_id}")
    except Exception as e:
        print(f"Error deleting pending message capture: {e}")


def check_rate_limit(
    user_id: str,
    guild_id: str,
    cooldown_seconds: int = 60,
    global_cooldown: int = 300  # 5 minutes globally
) -> tuple[bool, int]:
    """
    Check if user is rate limited with both per-guild and global limits.

    Implements a two-tier rate limiting system:
    1. Per-guild cooldown (default 60s) - prevents rapid retries in same server
    2. Global cooldown (default 300s) - prevents abuse across multiple servers

    Args:
        user_id: Discord user ID
        guild_id: Discord guild ID
        cooldown_seconds: Per-guild cooldown in seconds (default 60)
        global_cooldown: Global per-user cooldown in seconds (default 300)

    Returns:
        Tuple of (is_allowed, seconds_remaining)
        - is_allowed: True if user can proceed, False if still in cooldown
        - seconds_remaining: Seconds left in cooldown (0 if allowed)
    """
    try:
        # Check per-guild rate limit
        session = get_verification_session(user_id, guild_id)

        if session:
            # Check when session was created
            created_at_str = session.get('created_at')
            if created_at_str:
                created_at = datetime.fromisoformat(created_at_str)
                now = datetime.utcnow()
                elapsed = (now - created_at).total_seconds()

                if elapsed < cooldown_seconds:
                    # Still in per-guild cooldown
                    remaining = int(cooldown_seconds - elapsed)
                    print(f"Per-guild rate limit: user {user_id} in guild {guild_id}, "
                          f"{remaining}s remaining")
                    return (False, remaining)

        # Check global rate limit (across all guilds)
        global_session = get_verification_session(user_id, 'GLOBAL_RATE_LIMIT')

        if global_session:
            created_at_str = global_session.get('created_at')
            if created_at_str:
                created_at = datetime.fromisoformat(created_at_str)
                now = datetime.utcnow()
                elapsed = (now - created_at).total_seconds()

                if elapsed < global_cooldown:
                    # Still in global cooldown
                    remaining = int(global_cooldown - elapsed)
                    print(f"Global rate limit: user {user_id}, {remaining}s remaining")
                    return (False, remaining)

        # Update global rate limit marker
        ttl = int((datetime.utcnow() + timedelta(seconds=global_cooldown)).timestamp())
        sessions_table.put_item(Item={
            'user_id': user_id,
            'guild_id': 'GLOBAL_RATE_LIMIT',
            'created_at': datetime.utcnow().isoformat(),
            'ttl': ttl
        })

        # User is allowed
        return (True, 0)

    except Exception as e:
        print(f"ERROR: Rate limit check failed: {e}")
        # FAIL CLOSED - deny on error to prevent abuse
        print("Denying request due to rate limit check failure (fail-safe)")
        return (False, 60)  # Conservative 60s cooldown on error
