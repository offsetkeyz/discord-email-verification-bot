"""
Logging utilities with sensitive data sanitization.
"""
import re
import json
from typing import Any, Dict, List


# Sensitive keys that should be redacted
SENSITIVE_KEYS = {
    'email', 'code', 'token', 'password', 'secret',
    'authorization', 'x-signature-ed25519', 'x-signature-timestamp',
    'bot_token', 'api_key', 'private_key'
}


def sanitize_for_logging(data: Any) -> Any:
    """
    Sanitize sensitive data before logging.

    Recursively processes dictionaries, lists, and strings to remove
    sensitive information like emails, tokens, and credentials.

    Args:
        data: Data to sanitize (dict, str, list, or other types)

    Returns:
        Sanitized data safe for logging
    """
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            # Check if key is sensitive
            if key.lower() in SENSITIVE_KEYS:
                sanitized[key] = '***REDACTED***'
            # Recursively sanitize nested structures
            elif isinstance(value, (dict, list)):
                sanitized[key] = sanitize_for_logging(value)
            elif isinstance(value, str):
                sanitized[key] = sanitize_string(value)
            else:
                sanitized[key] = value
        return sanitized

    elif isinstance(data, list):
        return [sanitize_for_logging(item) for item in data]

    elif isinstance(data, str):
        return sanitize_string(data)

    return data


def sanitize_string(text: str) -> str:
    """
    Sanitize sensitive patterns in strings.

    Args:
        text: String to sanitize

    Returns:
        Sanitized string with sensitive patterns redacted
    """
    if not isinstance(text, str):
        return text

    # Redact email addresses
    text = re.sub(
        r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',
        '***EMAIL***',
        text
    )

    # Redact Discord bot tokens (format: MTQ0NjU2... or Bot MTQ0NjU2...)
    text = re.sub(
        r'(Bot\s+)?[A-Za-z0-9_-]{24,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{27,}',
        'Bot ***TOKEN***',
        text
    )

    # Redact AWS access keys
    text = re.sub(
        r'(AKIA|ASIA)[0-9A-Z]{16}',
        '***AWS_KEY***',
        text
    )

    # Redact verification codes (6-8 digit numbers in isolation)
    text = re.sub(
        r'\b\d{6,8}\b',
        '***CODE***',
        text
    )

    return text


def log_safe(message: str, data: Any = None) -> None:
    """
    Log a message with automatically sanitized data.

    Args:
        message: Log message
        data: Optional data to include (will be sanitized)
    """
    if data is not None:
        sanitized_data = sanitize_for_logging(data)
        if isinstance(sanitized_data, (dict, list)):
            print(f"{message}: {json.dumps(sanitized_data)}")
        else:
            print(f"{message}: {sanitized_data}")
    else:
        print(message)


def log_email_event(operation: str, email: str, success: bool, details: str = None) -> None:
    """
    Log an email-related event with sanitized email address.

    Args:
        operation: Operation name (e.g., "sent", "validated")
        email: Email address (will be sanitized)
        success: Whether operation succeeded
        details: Optional additional details
    """
    # Extract domain but hide user part
    domain = email.split('@')[1] if '@' in email else 'unknown'
    status = "SUCCESS" if success else "FAILED"

    if details:
        print(f"Email {operation} {status} to domain @{domain}: {details}")
    else:
        print(f"Email {operation} {status} to domain @{domain}")


def log_discord_error(operation: str, status_code: int, error_code: int = None) -> None:
    """
    Log Discord API errors safely without exposing response details.

    Args:
        operation: Operation that failed (e.g., "assign_role", "get_member")
        status_code: HTTP status code
        error_code: Discord error code if available
    """
    error_info = {
        'operation': operation,
        'status_code': status_code,
        'error_code': error_code
    }
    print(f"Discord API error: {json.dumps(error_info)}")
