"""
Discord Interactions API utilities and constants.
"""
from enum import IntEnum
import os
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError


class InteractionType(IntEnum):
    """Discord interaction types."""
    PING = 1
    APPLICATION_COMMAND = 2
    MESSAGE_COMPONENT = 3
    APPLICATION_COMMAND_AUTOCOMPLETE = 4
    MODAL_SUBMIT = 5


class InteractionResponseType(IntEnum):
    """Discord interaction response types."""
    PONG = 1
    CHANNEL_MESSAGE_WITH_SOURCE = 4
    DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE = 5
    DEFERRED_UPDATE_MESSAGE = 6
    UPDATE_MESSAGE = 7
    APPLICATION_COMMAND_AUTOCOMPLETE_RESULT = 8
    MODAL = 9


class MessageFlags(IntEnum):
    """Discord message flags."""
    EPHEMERAL = 64  # Only visible to user who triggered interaction


class ComponentType(IntEnum):
    """Discord component types."""
    ACTION_ROW = 1
    BUTTON = 2
    STRING_SELECT = 3
    TEXT_INPUT = 4
    USER_SELECT = 5
    ROLE_SELECT = 6
    MENTIONABLE_SELECT = 7
    CHANNEL_SELECT = 8


class ButtonStyle(IntEnum):
    """Discord button styles."""
    PRIMARY = 1    # Blurple
    SECONDARY = 2  # Grey
    SUCCESS = 3    # Green
    DANGER = 4     # Red
    LINK = 5       # Grey with link


def verify_discord_signature(signature: str, timestamp: str, body: str) -> bool:
    """
    Verify Discord interaction signature using Ed25519 with replay protection.

    Args:
        signature: x-signature-ed25519 header
        timestamp: x-signature-timestamp header
        body: Raw request body

    Returns:
        True if signature is valid, False otherwise
    """
    try:
        # Validate timestamp to prevent replay attacks
        import time
        try:
            current_time = int(time.time())
            request_time = int(timestamp)

            # Reject requests older than 5 minutes or in the future
            time_diff = abs(current_time - request_time)
            if time_diff > 300:  # 5 minutes in seconds
                print(f"ERROR: Request timestamp too old or in future. "
                      f"Diff: {time_diff}s, Request: {request_time}, Current: {current_time}")
                return False
        except (ValueError, TypeError) as e:
            print(f"ERROR: Invalid timestamp format: {e}")
            return False

        # Verify the Ed25519 signature
        public_key = os.environ.get('DISCORD_PUBLIC_KEY')
        if not public_key:
            print("ERROR: DISCORD_PUBLIC_KEY not found in environment")
            return False

        verify_key = VerifyKey(bytes.fromhex(public_key))
        verify_key.verify(f"{timestamp}{body}".encode(), bytes.fromhex(signature))
        return True
    except BadSignatureError:
        print("ERROR: Invalid Discord signature")
        return False
    except Exception as e:
        print(f"ERROR: Signature verification failed: {e}")
        return False
