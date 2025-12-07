"""
Setup command handler for multi-guild configuration.
Allows server admins to configure the bot via /setup command with select menus.
"""
import json
import requests
from discord_interactions import (
    InteractionResponseType,
    MessageFlags,
    ComponentType,
    ButtonStyle
)
from guild_config import save_guild_config, get_guild_config, is_guild_configured
from ssm_utils import get_parameter
from validation_utils import (
    extract_role_channel_from_custom_id,
    extract_setup_id_from_custom_id,
    validate_discord_message_url,
    validate_discord_id
)


# Discord Permission: ADMINISTRATOR (0x8)
ADMINISTRATOR_PERMISSION = 0x0000000008


def has_admin_permissions(member: dict, guild_id: str) -> bool:
    """
    Check if a Discord member has administrator permissions with enhanced validation.

    Args:
        member: Discord member object from interaction
        guild_id: Guild ID to validate against

    Returns:
        True if user is admin, False otherwise
    """
    # Validate guild context (prevent DM usage)
    if not guild_id or guild_id == '@me':
        print("ERROR: Command used outside of guild context")
        return False

    # Check permissions field exists
    if 'permissions' not in member:
        print("ERROR: Permissions field missing from member object")
        return False

    # Validate and parse permissions
    try:
        permissions = int(member['permissions'])
    except (ValueError, TypeError) as e:
        print(f"ERROR: Invalid permissions value: {member.get('permissions')} - {e}")
        return False

    # Check for Administrator permission bit
    has_admin = (permissions & ADMINISTRATOR_PERMISSION) == ADMINISTRATOR_PERMISSION

    # Log authorization check for security audit
    user_id = member.get('user', {}).get('id', 'unknown')
    user_name = member.get('user', {}).get('username', 'unknown')
    print(f"Authorization check: user={user_name}({user_id}), guild={guild_id}, "
          f"permissions={permissions}, admin={has_admin}")

    return has_admin


def handle_setup_command(interaction: dict) -> dict:
    """
    Handle /setup slash command.
    Shows role and channel select menus for easy configuration.

    Args:
        interaction: Discord interaction payload

    Returns:
        Lambda response dict
    """
    member = interaction.get('member', {})
    guild_id = interaction.get('guild_id')

    # Check admin permissions
    if not has_admin_permissions(member, guild_id):
        return ephemeral_response(
            "❌ You need **Administrator** permissions to run this command.\n\n"
            "Only server administrators can configure the verification bot."
        )

    # Show current config if exists
    current_config_text = ""
    instruction_text = "Select the verification role and channel below."

    if is_guild_configured(guild_id):
        config = get_guild_config(guild_id)
        current_config_text = (
            f"\n\n**Current Configuration:**\n"
            f"• Role: <@&{config.get('role_id')}>\n"
            f"• Channel: <#{config.get('channel_id')}>\n"
            f"• Domains: {', '.join(config.get('allowed_domains', []))}\n"
        )
        instruction_text = "Update the role and channel if needed, or click Continue to keep current settings."

    # Show select menus for role and channel
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'type': InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
            'data': {
                'content': f"## ⚙️ Bot Setup\n\n{instruction_text}{current_config_text}",
                'flags': MessageFlags.EPHEMERAL,
                'components': [
                    {
                        'type': ComponentType.ACTION_ROW,
                        'components': [
                            {
                                'type': ComponentType.ROLE_SELECT,
                                'custom_id': 'setup_role_select',
                                'placeholder': 'Select verification role',
                                'min_values': 1,
                                'max_values': 1
                            }
                        ]
                    },
                    {
                        'type': ComponentType.ACTION_ROW,
                        'components': [
                            {
                                'type': ComponentType.CHANNEL_SELECT,
                                'custom_id': 'setup_channel_select',
                                'placeholder': 'Select verification channel',
                                'min_values': 1,
                                'max_values': 1
                            }
                        ]
                    },
                    {
                        'type': ComponentType.ACTION_ROW,
                        'components': [
                            {
                                'type': ComponentType.BUTTON,
                                'style': ButtonStyle.PRIMARY,
                                'label': 'Continue to Message & Domains',
                                'custom_id': 'setup_continue'
                            }
                        ]
                    }
                ]
            }
        })
    }


def handle_setup_select_menu(interaction: dict) -> dict:
    """
    Handle role or channel select menu interactions during setup.
    Updates the message to show what was selected.

    Args:
        interaction: Discord interaction payload

    Returns:
        Lambda response dict
    """
    custom_id = interaction['data']['custom_id']
    values = interaction['data'].get('values', [])

    if not values:
        return ephemeral_response("❌ Please select an option.")

    # Store the selected value in the message for later retrieval
    # We'll update the message to show what was selected
    guild_id = interaction.get('guild_id')

    # Get current message content
    message = interaction.get('message', {})
    current_content = message.get('content', '')
    components = message.get('components', [])

    # Update content to show selection
    if custom_id == 'setup_role_select':
        role_id = values[0]
        # Update message to show selected role
        if '✅ **Selected Role:**' in current_content:
            # Replace existing role mention
            lines = current_content.split('\n')
            new_lines = []
            for line in lines:
                if line.startswith('✅ **Selected Role:**'):
                    new_lines.append(f'✅ **Selected Role:** <@&{role_id}>')
                else:
                    new_lines.append(line)
            current_content = '\n'.join(new_lines)
        else:
            current_content += f'\n\n✅ **Selected Role:** <@&{role_id}>'

    elif custom_id == 'setup_channel_select':
        channel_id = values[0]
        # Update message to show selected channel
        if '✅ **Selected Channel:**' in current_content:
            # Replace existing channel mention
            lines = current_content.split('\n')
            new_lines = []
            for line in lines:
                if line.startswith('✅ **Selected Channel:**'):
                    new_lines.append(f'✅ **Selected Channel:** <#{channel_id}>')
                else:
                    new_lines.append(line)
            current_content = '\n'.join(new_lines)
        else:
            current_content += f'\n✅ **Selected Channel:** <#{channel_id}>'

    # Return updated message
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'type': InteractionResponseType.UPDATE_MESSAGE,
            'data': {
                'content': current_content,
                'components': components,
                'flags': MessageFlags.EPHEMERAL
            }
        })
    }


def handle_setup_continue(interaction: dict) -> dict:
    """
    Handle "Continue" button click to show modal for domains.
    Extracts role_id and channel_id from the message content.
    Falls back to existing config if user didn't select new ones.

    Args:
        interaction: Discord interaction payload

    Returns:
        Lambda response dict
    """
    message = interaction.get('message', {})
    content = message.get('content', '')
    guild_id = interaction.get('guild_id')

    # Extract role_id and channel_id from message content
    role_id = None
    channel_id = None

    # First try to get from "Selected" lines (user made new selections)
    for line in content.split('\n'):
        if '**Selected Role:**' in line and '<@&' in line:
            # Extract role ID from mention
            start = line.find('<@&') + 3
            end = line.find('>', start)
            if start > 2 and end > start:
                role_id = line[start:end]

        if '**Selected Channel:**' in line and '<#' in line:
            # Extract channel ID from mention
            start = line.find('<#') + 2
            end = line.find('>', start)
            if start > 1 and end > start:
                channel_id = line[start:end]

    # If not selected, fall back to current config (from "Current Configuration" section)
    if not role_id or not channel_id:
        config = get_guild_config(guild_id)
        if config:
            if not role_id:
                role_id = config.get('role_id')
            if not channel_id:
                channel_id = config.get('channel_id')

    # Final check - if still no role/channel, require selection
    if not role_id or not channel_id:
        return ephemeral_response(
            "❌ Please select both a role and a channel before continuing."
        )

    # Check if guild has existing config to determine if domains are required
    existing_config = get_guild_config(guild_id)
    domains_required = not existing_config or not existing_config.get('allowed_domains')

    # Determine label and requirement based on whether config exists
    if domains_required:
        domains_label = 'Allowed Email Domains'
        domains_placeholder = 'e.g., yourschool.edu, example.edu'
    else:
        domains_label = 'Allowed Email Domains (optional)'
        domains_placeholder = 'e.g., auburn.edu, student.sans.edu'

    # Show modal for domains only
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'type': InteractionResponseType.MODAL,
            'data': {
                'custom_id': f'setup_domains_modal_{role_id}_{channel_id}',
                'title': 'Email Domains',
                'components': [
                    {
                        'type': ComponentType.ACTION_ROW,
                        'components': [
                            {
                                'type': ComponentType.TEXT_INPUT,
                                'custom_id': 'allowed_domains',
                                'label': domains_label,
                                'style': 1,  # Short text input
                                'placeholder': domains_placeholder,
                                'required': domains_required
                            }
                        ]
                    }
                ]
            }
        })
    }


def handle_domains_modal_submit(interaction: dict) -> dict:
    """
    Handle domains modal submission.
    Stores domains and shows button to submit message link.

    Args:
        interaction: Discord interaction payload

    Returns:
        Lambda response dict
    """
    member = interaction.get('member', {})
    guild_id = interaction.get('guild_id')
    user_id = member.get('user', {}).get('id')

    # Extract role_id and channel_id from custom_id (with security validation)
    custom_id = interaction['data']['custom_id']
    role_id, channel_id = extract_role_channel_from_custom_id(custom_id, 'setup_domains_modal')

    if not role_id or not channel_id:
        return ephemeral_response("❌ Invalid setup state. Please run /setup again.")

    # Get domains from modal
    components = interaction['data']['components']
    allowed_domains_str = components[0]['components'][0].get('value', '').strip()

    # If empty, try to get from existing config
    if not allowed_domains_str:
        from guild_config import get_guild_config
        existing_config = get_guild_config(guild_id)
        if existing_config and existing_config.get('allowed_domains'):
            allowed_domains = existing_config.get('allowed_domains')
        else:
            # This shouldn't happen if the modal was set to required, but handle it
            return ephemeral_response(
                "❌ Please specify at least one allowed email domain.\n\n"
                "Run `/setup` again and enter domains like: `yourschool.edu, example.edu`"
            )
    else:
        allowed_domains = [d.strip() for d in allowed_domains_str.split(',') if d.strip()]
        if not allowed_domains:
            return ephemeral_response(
                "❌ Please specify at least one valid email domain.\n\n"
                "Run `/setup` again and enter domains like: `yourschool.edu, example.edu`"
            )

    # Store domains temporarily
    from dynamodb_operations import store_pending_setup

    setup_id = f"{user_id}_{guild_id}"
    store_pending_setup(
        setup_id=setup_id,
        role_id=role_id,
        channel_id=channel_id,
        allowed_domains=allowed_domains,
        custom_message=""  # Will be filled from message link
    )

    # Check if there's an existing message to allow skipping
    from guild_config import get_guild_config
    existing_config = get_guild_config(guild_id)
    has_existing_message = existing_config and existing_config.get('custom_message')

    # Build button row
    buttons = [
        {
            'type': ComponentType.BUTTON,
            'style': ButtonStyle.PRIMARY,
            'label': '📝 Submit Message Link',
            'custom_id': f'setup_message_link_{setup_id}'
        }
    ]

    # Add skip button if there's an existing message
    if has_existing_message:
        buttons.append({
            'type': ComponentType.BUTTON,
            'style': ButtonStyle.SECONDARY,
            'label': 'Skip (Keep Current Message)',
            'custom_id': f'setup_skip_message_{setup_id}'
        })

    # Show instructions with button to enter message link
    instructions = (
        "## ✍️ Create Your Verification Message\n\n"
        "**Step 1:** Type your verification message in any Discord channel (don't send it yet)\n"
        "• Use Discord's emoji picker for emojis\n"
        "• Use **bold**, *italic*, and other formatting\n\n"
        "**Step 2:** Send the message\n\n"
        "**Step 3:** Right-click (or long-press on mobile) your message → **Copy Message Link**\n\n"
        "**Step 4:** Click the button below and paste the link"
    )

    if has_existing_message:
        instructions += "\n\n*Or click 'Skip' to keep your current verification message.*"

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'type': InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
            'data': {
                'content': instructions,
                'flags': MessageFlags.EPHEMERAL,
                'components': [
                    {
                        'type': ComponentType.ACTION_ROW,
                        'components': buttons
                    }
                ]
            }
        })
    }


def handle_skip_message_button(interaction: dict) -> dict:
    """
    Handle skip message button - use existing message, save config and show preview.

    Args:
        interaction: Discord interaction payload

    Returns:
        Lambda response dict
    """
    from dynamodb_operations import get_pending_setup
    from guild_config import get_guild_config

    member = interaction.get('member', {})
    guild_id = interaction.get('guild_id')
    user_id = member.get('user', {}).get('id')

    custom_id = interaction['data']['custom_id']
    # Format: setup_skip_message_{setup_id} (with security validation)
    setup_id = extract_setup_id_from_custom_id(custom_id, 'setup_skip_message')

    if not setup_id:
        return ephemeral_response("❌ Invalid state. Please run /setup again.")

    # Get pending setup config
    pending_config = get_pending_setup(setup_id)
    if not pending_config:
        return ephemeral_response("❌ Setup session expired. Please run /setup again.")

    # Get existing message from guild config
    existing_config = get_guild_config(guild_id)
    if not existing_config or not existing_config.get('custom_message'):
        return ephemeral_response(
            "❌ No existing message found. Please submit a message link instead."
        )

    role_id = pending_config['role_id']
    channel_id = pending_config['channel_id']
    allowed_domains = pending_config['allowed_domains']
    custom_message = existing_config['custom_message']

    # Update pending setup with existing message
    from dynamodb_operations import store_pending_setup
    store_pending_setup(
        setup_id=setup_id,
        role_id=role_id,
        channel_id=channel_id,
        allowed_domains=allowed_domains,
        custom_message=custom_message
    )

    # Show preview with approve/cancel buttons
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'type': InteractionResponseType.UPDATE_MESSAGE,
            'data': {
                'content': (
                    f"## 👀 Preview Your Verification Message\n\n"
                    f"**Configuration:**\n"
                    f"• Role: <@&{role_id}>\n"
                    f"• Channel: <#{channel_id}>\n"
                    f"• Allowed Domains: {', '.join(allowed_domains)}\n\n"
                    f"**Message Preview:**\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"{custom_message}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"This is how the message will appear in <#{channel_id}>."
                ),
                'flags': MessageFlags.EPHEMERAL,
                'components': [
                    {
                        'type': ComponentType.ACTION_ROW,
                        'components': [
                            {
                                'type': ComponentType.BUTTON,
                                'style': ButtonStyle.SUCCESS,
                                'label': '✅ Approve & Post',
                                'custom_id': f'setup_approve_{setup_id}'
                            },
                            {
                                'type': ComponentType.BUTTON,
                                'style': ButtonStyle.DANGER,
                                'label': '❌ Cancel',
                                'custom_id': 'setup_cancel'
                            }
                        ]
                    }
                ]
            }
        })
    }


def handle_message_link_button(interaction: dict) -> dict:
    """
    Handle message link button click - show modal for message link.

    Args:
        interaction: Discord interaction payload

    Returns:
        Lambda response dict
    """
    custom_id = interaction['data']['custom_id']
    # Format: setup_message_link_{setup_id} (with security validation)
    setup_id = extract_setup_id_from_custom_id(custom_id, 'setup_message_link')

    if not setup_id:
        return ephemeral_response("❌ Invalid state. Please run /setup again.")

    # Show modal for message link input
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'type': InteractionResponseType.MODAL,
            'data': {
                'custom_id': f'setup_link_modal_{setup_id}',
                'title': 'Message Link',
                'components': [
                    {
                        'type': ComponentType.ACTION_ROW,
                        'components': [
                            {
                                'type': ComponentType.TEXT_INPUT,
                                'custom_id': 'message_link',
                                'label': 'Discord Message Link',
                                'style': 1,  # Short text input
                                'placeholder': 'https://discord.com/channels/...',
                                'required': True
                            }
                        ]
                    }
                ]
            }
        })
    }


def handle_message_modal_submit(interaction: dict) -> dict:
    """
    Handle message link modal submission.
    Fetches message content from the link and shows preview.

    Args:
        interaction: Discord interaction payload

    Returns:
        Lambda response dict
    """
    from dynamodb_operations import get_pending_setup
    from ssm_utils import get_parameter
    import requests
    import re

    member = interaction.get('member', {})
    guild_id = interaction.get('guild_id')
    user_id = member.get('user', {}).get('id')

    # Extract setup_id from custom_id (with security validation)
    custom_id = interaction['data']['custom_id']
    setup_id = extract_setup_id_from_custom_id(custom_id, 'setup_link_modal')

    if not setup_id:
        return ephemeral_response("❌ Invalid setup state. Please run /setup again.")

    # Get pending setup config
    config = get_pending_setup(setup_id)
    if not config:
        return ephemeral_response("❌ Setup session expired. Please run /setup again.")

    role_id = config['role_id']
    channel_id = config['channel_id']
    allowed_domains = config['allowed_domains']

    # Get message link from modal
    components = interaction['data']['components']
    message_link = components[0]['components'][0].get('value', '').strip()

    if not message_link:
        return ephemeral_response("❌ Please provide a message link.")

    # Parse and validate message link (with SSRF protection)
    link_guild_id, link_channel_id, message_id = validate_discord_message_url(message_link, guild_id)

    if not link_guild_id:
        return ephemeral_response(
            "❌ Invalid message link.\n\n"
            "Please provide a valid Discord message link from this server.\n\n"
            "To get a message link:\n"
            "1. Right-click your message\n"
            "2. Select **Copy Message Link**"
        )

    # Guild ID already verified by validation function
    # Fetch the message content
    try:
        bot_token = get_parameter('/discord-bot/token')
        fetch_url = f"https://discord.com/api/v10/channels/{link_channel_id}/messages/{message_id}"
        headers = {"Authorization": f"Bot {bot_token}"}

        response = requests.get(fetch_url, headers=headers)

        print(f"Message fetch response: {response.status_code}")

        if response.status_code != 200:
            print(f"Error response: {response.text}")
            return ephemeral_response(
                f"❌ Could not fetch message. Error: {response.status_code}\n\n"
                "Make sure:\n"
                "• The message exists\n"
                "• I have permission to view the channel\n"
                "• The message link is correct"
            )

        message_data = response.json()
        print(f"Message data: {json.dumps(message_data)}")

        custom_message = message_data.get('content', '').strip()

        if not custom_message:
            print(f"Message content is empty. Full message: {message_data}")
            return ephemeral_response(
                f"❌ The message appears to be empty or contains only embeds/attachments.\n\n"
                f"Please make sure your message contains text content."
            )

    except Exception as e:
        print(f"Error fetching message: {e}")
        return ephemeral_response(f"❌ Error fetching message: {str(e)}")

    # Store config temporarily
    from dynamodb_operations import store_pending_setup

    setup_id = f"{user_id}_{guild_id}"
    store_pending_setup(
        setup_id=setup_id,
        role_id=role_id,
        channel_id=channel_id,
        allowed_domains=allowed_domains,
        custom_message=custom_message
    )

    # Show preview with approve/cancel buttons
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'type': InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
            'data': {
                'content': (
                    f"## 👀 Preview Your Verification Message\n\n"
                    f"**Configuration:**\n"
                    f"• Role: <@&{role_id}>\n"
                    f"• Channel: <#{channel_id}>\n"
                    f"• Allowed Domains: {', '.join(allowed_domains)}\n\n"
                    f"**Message Preview:**\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"{custom_message}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"This is how the message will appear in <#{channel_id}>."
                ),
                'flags': MessageFlags.EPHEMERAL,
                'components': [
                    {
                        'type': ComponentType.ACTION_ROW,
                        'components': [
                            {
                                'type': ComponentType.BUTTON,
                                'style': ButtonStyle.SUCCESS,
                                'label': '✅ Approve & Post',
                                'custom_id': f'setup_approve_{setup_id}'
                            },
                            {
                                'type': ComponentType.BUTTON,
                                'style': ButtonStyle.DANGER,
                                'label': '❌ Cancel',
                                'custom_id': 'setup_cancel'
                            }
                        ]
                    }
                ]
            }
        })
    }


def handle_setup_approve(interaction: dict) -> dict:
    """
    Handle approval button click - saves config and posts message.

    Args:
        interaction: Discord interaction payload

    Returns:
        Lambda response dict
    """
    from dynamodb_operations import get_pending_setup, delete_pending_setup

    member = interaction.get('member', {})
    guild_id = interaction.get('guild_id')
    user_id = member.get('user', {}).get('id')

    # Get setup_id from custom_id (with security validation)
    custom_id = interaction['data']['custom_id']
    setup_id = extract_setup_id_from_custom_id(custom_id, 'setup_approve')

    if not setup_id:
        return ephemeral_response("❌ Invalid approval state. Please run /setup again.")

    # Retrieve pending setup from DynamoDB
    config_data = get_pending_setup(setup_id)
    if not config_data:
        return ephemeral_response("❌ Setup session expired. Please run /setup again.")

    try:
        role_id = config_data['role_id']
        channel_id = config_data['channel_id']
        allowed_domains = config_data['allowed_domains']
        custom_message = config_data['custom_message']

    except KeyError as e:
        print(f"Error retrieving config: {e}")
        return ephemeral_response("❌ Invalid configuration data. Please run /setup again.")

    # Save configuration
    success = save_guild_config(guild_id, role_id, channel_id, user_id, allowed_domains, custom_message)

    if not success:
        return ephemeral_response(
            "❌ Failed to save configuration. Please try again or contact support."
        )

    # Post verification message to the channel
    posted = post_verification_message(guild_id, channel_id, custom_message)

    # Clean up pending setup
    delete_pending_setup(setup_id)

    if not posted:
        return ephemeral_response(
            "⚠️ Configuration saved, but I couldn't post the verification message.\n\n"
            "Please check that:\n"
            "• The channel ID is correct\n"
            "• I have permission to send messages in that channel\n"
            "• I have permission to view the channel"
        )

    # Update the message to show success
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'type': InteractionResponseType.UPDATE_MESSAGE,
            'data': {
                'content': (
                    f"✅ **Setup Complete!**\n\n"
                    f"**Configuration Saved:**\n"
                    f"• Verification Role: <@&{role_id}>\n"
                    f"• Verification Channel: <#{channel_id}>\n"
                    f"• Allowed Domains: {', '.join(allowed_domains)}\n\n"
                    f"I've posted the verification message in <#{channel_id}>.\n"
                    f"Users can now click the button to start verification!"
                ),
                'components': [],  # Remove buttons
                'flags': MessageFlags.EPHEMERAL
            }
        })
    }


def handle_setup_cancel(interaction: dict) -> dict:
    """
    Handle cancel button click - aborts setup without saving.

    Args:
        interaction: Discord interaction payload

    Returns:
        Lambda response dict
    """
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'type': InteractionResponseType.UPDATE_MESSAGE,
            'data': {
                'content': "❌ Setup cancelled. No changes were made.\n\nRun `/setup` again if you want to configure the bot.",
                'components': [],  # Remove buttons
                'flags': MessageFlags.EPHEMERAL
            }
        })
    }


def post_verification_message(guild_id: str, channel_id: str, custom_message: str = None) -> bool:
    """
    Post the verification message with button to a channel.

    Args:
        guild_id: Discord guild ID
        channel_id: Channel ID to post in
        custom_message: Custom message to display (optional)

    Returns:
        True if posted successfully, False otherwise
    """
    try:
        bot_token = get_parameter('/discord-bot/token')

        if not custom_message:
            custom_message = "Click the button below to verify your email address."

        message_data = {
            "content": custom_message,
            "components": [
                {
                    "type": ComponentType.ACTION_ROW,
                    "components": [
                        {
                            "type": ComponentType.BUTTON,
                            "style": ButtonStyle.PRIMARY,
                            "label": "Start Verification",
                            "custom_id": "start_verification"
                        }
                    ]
                }
            ]
        }

        url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
        headers = {
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json"
        }

        response = requests.post(url, headers=headers, json=message_data)

        if response.status_code in [200, 201]:
            print(f"Posted verification message to channel {channel_id}")
            return True
        else:
            print(f"Failed to post message: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print(f"Error posting verification message: {e}")
        return False


def ephemeral_response(content: str) -> dict:
    """Create an ephemeral message response."""
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
