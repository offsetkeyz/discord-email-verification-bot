"""
Main interaction handlers for Discord bot.
Handles button clicks, modal submissions, and verification flow.
"""
import json
from datetime import datetime
from discord_interactions import (
    InteractionResponseType,
    MessageFlags,
    ComponentType,
    ButtonStyle
)
from dynamodb_operations import (
    create_verification_session,
    get_verification_session,
    is_user_verified,
    increment_attempts,
    mark_verified,
    delete_session,
    check_rate_limit
)
from ses_email import send_verification_email
from verification_logic import (
    generate_code,
    validate_edu_email,
    is_valid_code_format,
    MAX_VERIFICATION_ATTEMPTS
)
from discord_api import assign_role, user_has_role
from ssm_utils import get_parameter
from guild_config import get_guild_config, get_guild_role_id, get_guild_allowed_domains, is_guild_configured, get_guild_completion_message


def handle_ping() -> dict:
    """Handle Discord PING for endpoint verification."""
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'type': InteractionResponseType.PONG})
    }


def handle_button_click(interaction: dict) -> dict:
    """
    Handle button clicks.

    Args:
        interaction: Discord interaction payload

    Returns:
        Lambda response dict
    """
    custom_id = interaction['data']['custom_id']
    user_id = interaction['member']['user']['id']
    guild_id = interaction['guild_id']

    if custom_id == 'start_verification':
        return handle_start_verification(user_id, guild_id)

    elif custom_id == 'submit_code':
        return show_code_modal(user_id, guild_id)

    else:
        return error_response("Unknown button action")


def handle_start_verification(user_id: str, guild_id: str) -> dict:
    """
    Start verification flow by showing email modal.

    Args:
        user_id: Discord user ID
        guild_id: Discord guild ID

    Returns:
        Modal response
    """
    # Check if guild is configured
    if not is_guild_configured(guild_id):
        return ephemeral_response(
            "⚠️ **This server hasn't been configured yet.**\n\n"
            "A server administrator needs to run `/setup` first to configure the verification bot."
        )

    # Get guild configuration
    try:
        role_id = get_guild_role_id(guild_id)
        bot_token = get_parameter('/discord-bot/token')
    except Exception as e:
        print(f"Error getting configuration: {e}")
        return error_response("Configuration error. Please contact an administrator.")

    # Check if user already has the role (saves API calls and prevents abuse)
    if user_has_role(user_id, guild_id, role_id, bot_token):
        return ephemeral_response(
            "✅ You already have the verified role! No need to verify again."
        )

    # Check rate limiting (prevents spam/DDOS)
    is_allowed, seconds_remaining = check_rate_limit(user_id, guild_id, cooldown_seconds=60)
    if not is_allowed:
        return ephemeral_response(
            f"⏱️ Please wait {seconds_remaining} seconds before starting a new verification.\n\n"
            "This cooldown prevents spam and protects our email service."
        )

    # Show email modal
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'type': InteractionResponseType.MODAL,
            'data': {
                'custom_id': 'email_submission_modal',
                'title': 'Email Verification',
                'components': [
                    {
                        'type': ComponentType.ACTION_ROW,
                        'components': [
                            {
                                'type': ComponentType.TEXT_INPUT,
                                'custom_id': 'edu_email',
                                'label': 'Enter your .edu email address',
                                'style': 1,  # Short text input
                                'placeholder': 'yourname@university.edu',
                                'required': True,
                                'max_length': 100
                            }
                        ]
                    }
                ]
            }
        })
    }


def show_code_modal(user_id: str, guild_id: str) -> dict:
    """
    Show code submission modal.

    Args:
        user_id: Discord user ID
        guild_id: Discord guild ID

    Returns:
        Modal response
    """
    # Check if user has an active session
    session = get_verification_session(user_id, guild_id)
    if not session:
        return ephemeral_response(
            "❌ No pending verification found. Please click 'Start Verification' first."
        )

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'type': InteractionResponseType.MODAL,
            'data': {
                'custom_id': 'code_submission_modal',
                'title': 'Verification Code',
                'components': [
                    {
                        'type': ComponentType.ACTION_ROW,
                        'components': [
                            {
                                'type': ComponentType.TEXT_INPUT,
                                'custom_id': 'verification_code',
                                'label': 'Enter the 6-digit code from your email',
                                'style': 1,
                                'placeholder': '123456',
                                'required': True,
                                'min_length': 6,
                                'max_length': 6
                            }
                        ]
                    }
                ]
            }
        })
    }


def handle_modal_submit(interaction: dict) -> dict:
    """
    Handle modal form submissions.

    Args:
        interaction: Discord interaction payload

    Returns:
        Lambda response dict
    """
    custom_id = interaction['data']['custom_id']
    user_id = interaction['member']['user']['id']
    guild_id = interaction['guild_id']

    if custom_id == 'email_submission_modal':
        return handle_email_submission(interaction, user_id, guild_id)

    elif custom_id == 'code_submission_modal':
        return handle_code_verification(interaction, user_id, guild_id)

    else:
        return error_response("Unknown modal submission")


def handle_email_submission(interaction: dict, user_id: str, guild_id: str) -> dict:
    """
    Process email submission from modal.

    Args:
        interaction: Discord interaction payload
        user_id: Discord user ID
        guild_id: Discord guild ID

    Returns:
        Success response with Submit Code button
    """
    from guild_config import get_guild_allowed_domains

    # Extract email from modal
    components = interaction['data']['components']
    email = components[0]['components'][0]['value'].strip()

    # Get configured domains for this guild
    allowed_domains = get_guild_allowed_domains(guild_id)
    if not allowed_domains:
        allowed_domains = ['auburn.edu', 'student.sans.edu']  # Fallback

    # Validate email against guild's allowed domains
    if not validate_edu_email(email, allowed_domains):
        # Build domain list for error message
        domain_list = "\n".join([f"• **@{domain}**" for domain in allowed_domains])

        return ephemeral_response(
            f"❌ That doesn't appear to be a valid email address from an allowed domain.\n\n"
            f"Only these email domains are accepted:\n"
            f"{domain_list}\n\n"
            f"Click 'Start Verification' again to try again."
        )

    # Generate code
    code = generate_code()

    # Create verification session
    try:
        verification_id = create_verification_session(
            user_id, guild_id, email, code
        )

        # Send email via SES
        email_sent = send_verification_email(email, code)

        if not email_sent:
            # Clean up session if email failed
            delete_session(user_id, guild_id)
            return ephemeral_response(
                "❌ Failed to send verification email. This might be because:\n"
                "• The email address is invalid\n"
                "• Our email service is in sandbox mode and can't send to unverified addresses\n\n"
                "Please contact a server administrator."
            )

        # Success - show submit code button
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'type': InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
                'data': {
                    'content': f"✉️ I've sent a verification code to **{email}**.\n\n"
                               f"Click the button below to enter your code.\n"
                               f"⏱️ The code will expire in 15 minutes.",
                    'flags': MessageFlags.EPHEMERAL,
                    'components': [
                        {
                            'type': ComponentType.ACTION_ROW,
                            'components': [
                                {
                                    'type': ComponentType.BUTTON,
                                    'style': ButtonStyle.PRIMARY,
                                    'label': 'Submit Code',
                                    'custom_id': 'submit_code'
                                }
                            ]
                        }
                    ]
                }
            })
        }

    except Exception as e:
        print(f"Error creating verification: {e}")
        return error_response("An error occurred. Please try again.")


def handle_code_verification(interaction: dict, user_id: str, guild_id: str) -> dict:
    """
    Process code submission from modal.

    Args:
        interaction: Discord interaction payload
        user_id: Discord user ID
        guild_id: Discord guild ID

    Returns:
        Success or error response
    """
    # Extract code from modal
    components = interaction['data']['components']
    submitted_code = components[0]['components'][0]['value'].strip()

    # Validate format
    if not is_valid_code_format(submitted_code):
        return ephemeral_response(
            "❌ Please enter a valid 6-digit verification code.\n"
            "Check your email for the code."
        )

    # Get session
    session = get_verification_session(user_id, guild_id)
    if not session:
        return ephemeral_response(
            "❌ No pending verification found. Please start the verification process again."
        )

    # Check expiration
    expires_at = datetime.fromisoformat(session['expires_at'])
    if datetime.utcnow() > expires_at:
        delete_session(user_id, guild_id)
        return ephemeral_response(
            "❌ Verification code has expired (15 minutes).\n\n"
            "Please click 'Start Verification' again to get a new code."
        )

    # Check attempts
    if session['attempts'] >= MAX_VERIFICATION_ATTEMPTS:
        delete_session(user_id, guild_id)
        return ephemeral_response(
            "❌ Too many failed attempts. Please start over."
        )

    # Verify code
    if submitted_code != session['code']:
        new_attempts = increment_attempts(session['verification_id'], user_id, guild_id)
        remaining = MAX_VERIFICATION_ATTEMPTS - new_attempts

        if remaining > 0:
            return ephemeral_response(
                f"❌ Incorrect code. You have {remaining} attempt(s) remaining.\n\n"
                f"Click 'Submit Code' to try again."
            )
        else:
            delete_session(user_id, guild_id)
            return ephemeral_response(
                "❌ Incorrect code. Too many failed attempts.\n\n"
                "Please click 'Start Verification' to start over."
            )

    # Code correct! Mark as verified
    mark_verified(session['verification_id'], user_id, guild_id)

    # Assign role using guild configuration
    role_id = get_guild_role_id(guild_id)
    bot_token = get_parameter('/discord-bot/token')

    success = assign_role(user_id, guild_id, role_id, bot_token)

    if success:
        # Get custom completion message from guild config
        completion_message = get_guild_completion_message(guild_id)
        return ephemeral_response(completion_message)
    else:
        return ephemeral_response(
            "✅ Verification successful, but I encountered an issue assigning your role.\n\n"
            "Please contact a server administrator."
        )


def ephemeral_response(content: str) -> dict:
    """Helper to create ephemeral message response."""
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'type': InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
            'data': {
                'content': content,
                'flags': MessageFlags.EPHEMERAL
            }
        })
    }


def error_response(message: str) -> dict:
    """Helper for error responses."""
    return ephemeral_response(f"❌ {message}")
