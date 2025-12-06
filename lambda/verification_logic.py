"""
Verification logic helpers.
Reused from verification_service.py - pure functions with no database dependencies.
"""
import re
import secrets


# Configuration
MAX_VERIFICATION_ATTEMPTS = 3
CODE_LENGTH = 6


def generate_code(length: int = CODE_LENGTH) -> str:
    """
    Generate a random numeric verification code.

    Args:
        length: The length of the code (default: 6)

    Returns:
        A string of random digits
    """
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def validate_edu_email(email: str, allowed_domains: list = None) -> bool:
    """
    Validate that an email address is valid and is from an allowed domain.

    Args:
        email: The email address to validate
        allowed_domains: List of allowed domains (e.g., ['auburn.edu', 'student.sans.edu'])
                        If None, defaults to auburn.edu and student.sans.edu

    Returns:
        True if valid and from an allowed domain, False otherwise
    """
    # Basic email regex pattern
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

    if not re.match(email_pattern, email):
        return False

    # Use default domains if none provided
    if allowed_domains is None:
        allowed_domains = ['auburn.edu', 'student.sans.edu']

    # Check if it ends with an allowed domain
    email_lower = email.lower()

    return any(email_lower.endswith(f"@{domain}") for domain in allowed_domains)


def is_valid_code_format(code: str) -> bool:
    """
    Check if a string matches the expected code format (all digits, correct length).

    Args:
        code: The code to check

    Returns:
        True if it matches the expected format, False otherwise
    """
    return code.isdigit() and len(code) == CODE_LENGTH
