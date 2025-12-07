"""
Input validation utilities for security.
"""
import re
from typing import Optional, Tuple


def validate_discord_id(value: str) -> bool:
    """
    Validate a Discord snowflake ID.

    Discord IDs are 17-20 digit numeric strings.

    Args:
        value: String to validate

    Returns:
        True if valid Discord ID, False otherwise
    """
    if not value or not isinstance(value, str):
        return False
    return bool(re.match(r'^\d{17,20}$', value))


def extract_role_channel_from_custom_id(custom_id: str, expected_prefix: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Safely extract role_id and channel_id from custom_id with validation.

    Expected format: {prefix}_{role_id}_{channel_id}

    Args:
        custom_id: The custom_id string from Discord interaction
        expected_prefix: Expected prefix (e.g., 'setup_domains_modal')

    Returns:
        Tuple of (role_id, channel_id) or (None, None) if invalid
    """
    if not custom_id or not isinstance(custom_id, str):
        return (None, None)

    # Validate format: prefix_ROLE_CHANNEL
    # Discord IDs are 17-20 digit snowflakes
    pattern = rf'^{re.escape(expected_prefix)}_(\d{{17,20}})_(\d{{17,20}})$'
    match = re.match(pattern, custom_id)

    if not match:
        print(f"ERROR: Invalid custom_id format. Expected: {expected_prefix}_<role_id>_<channel_id>")
        return (None, None)

    role_id = match.group(1)
    channel_id = match.group(2)

    return (role_id, channel_id)


def extract_setup_id_from_custom_id(custom_id: str, expected_prefix: str) -> Optional[str]:
    """
    Safely extract setup_id from custom_id with validation.

    Expected format: {prefix}_{setup_id}

    Args:
        custom_id: The custom_id string from Discord interaction
        expected_prefix: Expected prefix (e.g., 'setup_message_link')

    Returns:
        setup_id if valid, None if invalid
    """
    if not custom_id or not isinstance(custom_id, str):
        return None

    # Validate format: prefix_SETUPID
    # Setup IDs are UUIDs (alphanumeric + hyphens, 36 chars)
    pattern = rf'^{re.escape(expected_prefix)}_([a-f0-9]{{8}}-[a-f0-9]{{4}}-[a-f0-9]{{4}}-[a-f0-9]{{4}}-[a-f0-9]{{12}})$'
    match = re.match(pattern, custom_id)

    if not match:
        print(f"ERROR: Invalid custom_id format. Expected: {expected_prefix}_<setup_id>")
        return None

    setup_id = match.group(1)
    return setup_id


def validate_email_address(email: str) -> bool:
    """
    Validate email address format.

    Args:
        email: Email address to validate

    Returns:
        True if valid format, False otherwise
    """
    if not email or not isinstance(email, str):
        return False

    # More strict RFC-compliant email regex (prevents consecutive dots)
    # Max length 254 chars per RFC 5321
    if len(email) > 254:
        return False

    pattern = r'^[a-zA-Z0-9][a-zA-Z0-9._%+-]*[a-zA-Z0-9]@[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_domain(domain: str) -> bool:
    """
    Validate domain name format.

    Args:
        domain: Domain name to validate

    Returns:
        True if valid format, False otherwise
    """
    if not domain or not isinstance(domain, str):
        return False

    # Max length 253 chars per RFC 1035
    if len(domain) > 253:
        return False

    # Domain pattern: alphanumeric with hyphens, dots between labels
    pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*$'
    return bool(re.match(pattern, domain))


def validate_discord_message_url(url: str, expected_guild_id: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Validate and parse Discord message URL.

    Expected format: https://discord.com/channels/{guild_id}/{channel_id}/{message_id}

    Args:
        url: Discord message URL
        expected_guild_id: Expected guild ID to validate against

    Returns:
        Tuple of (guild_id, channel_id, message_id) or (None, None, None) if invalid
    """
    if not url or not isinstance(url, str):
        return (None, None, None)

    # Only allow discord.com URLs (prevent SSRF)
    import urllib.parse
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.netloc not in ['discord.com', 'www.discord.com']:
            print(f"ERROR: Invalid Discord URL domain: {parsed.netloc}")
            return (None, None, None)
    except Exception as e:
        print(f"ERROR: Failed to parse URL: {e}")
        return (None, None, None)

    # Validate format and extract IDs
    pattern = r'^https://discord\.com/channels/(\d{17,20})/(\d{17,20})/(\d{17,20})$'
    match = re.match(pattern, url)

    if not match:
        print("ERROR: Invalid Discord message URL format")
        return (None, None, None)

    guild_id, channel_id, message_id = match.groups()

    # Verify guild matches expected
    if guild_id != expected_guild_id:
        print(f"ERROR: Guild ID mismatch. Expected: {expected_guild_id}, Got: {guild_id}")
        return (None, None, None)

    return (guild_id, channel_id, message_id)


# Input length limits
MAX_EMAIL_LENGTH = 254  # RFC 5321
MAX_DOMAIN_LENGTH = 253  # RFC 1035
MAX_DOMAINS_COUNT = 10
MAX_MESSAGE_LENGTH = 2000
MAX_CUSTOM_MESSAGE_LENGTH = 4000


def validate_input_lengths(
    email: Optional[str] = None,
    domains: Optional[list] = None,
    message: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate input lengths to prevent resource exhaustion.

    Args:
        email: Email address (optional)
        domains: List of domains (optional)
        message: Message text (optional)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if email and len(email) > MAX_EMAIL_LENGTH:
        return (False, "Email address too long (max 254 characters)")

    if domains:
        if len(domains) > MAX_DOMAINS_COUNT:
            return (False, f"Too many domains (max {MAX_DOMAINS_COUNT})")

        for domain in domains:
            if len(domain) > MAX_DOMAIN_LENGTH:
                return (False, f"Domain '{domain}' too long (max 253 characters)")

    if message and len(message) > MAX_CUSTOM_MESSAGE_LENGTH:
        return (False, f"Message too long (max {MAX_CUSTOM_MESSAGE_LENGTH} characters)")

    return (True, None)
