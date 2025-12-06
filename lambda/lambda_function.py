"""
AWS Lambda handler for Discord verification bot.
Main entry point for all Discord interactions.
"""
import json
from discord_interactions import (
    InteractionType,
    verify_discord_signature
)
from handlers import (
    handle_ping,
    handle_button_click,
    handle_modal_submit,
    error_response
)
from setup_handler import (
    handle_setup_command,
    handle_setup_select_menu,
    handle_setup_continue,
    handle_domains_modal_submit,
    handle_message_link_button,
    handle_skip_message_button,
    handle_message_modal_submit,
    handle_setup_approve,
    handle_setup_cancel
)


def lambda_handler(event, context):
    """
    Main Lambda handler for Discord interactions.

    Discord sends POST requests to this endpoint with interaction data.
    Must respond within 3 seconds or use deferred responses.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response
    """
    print(f"Event: {json.dumps(event)}")

    # Get headers and body
    headers = event.get('headers', {})
    body_str = event.get('body', '{}')

    # Discord sends these headers for signature verification
    signature = headers.get('x-signature-ed25519', '')
    timestamp = headers.get('x-signature-timestamp', '')

    # Verify signature
    if signature and timestamp:
        if not verify_discord_signature(signature, timestamp, body_str):
            print("ERROR: Invalid Discord signature")
            return {
                'statusCode': 401,
                'body': json.dumps({'error': 'Invalid signature'})
            }

    # Parse the body
    try:
        body = json.loads(body_str)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON: {e}")
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid JSON'})
        }

    # Get interaction type
    interaction_type = body.get('type')
    print(f"Interaction type: {interaction_type}")

    # Route based on interaction type
    try:
        if interaction_type == InteractionType.PING:
            return handle_ping()

        elif interaction_type == InteractionType.APPLICATION_COMMAND:
            # Slash commands
            command_name = body.get('data', {}).get('name')
            print(f"Slash command: {command_name}")

            if command_name == 'setup-email-verification':
                return handle_setup_command(body)
            else:
                return error_response(f"Unknown command: {command_name}")

        elif interaction_type == InteractionType.MESSAGE_COMPONENT:
            # Button clicks and select menus
            custom_id = body.get('data', {}).get('custom_id', '')
            component_type = body.get('data', {}).get('component_type')

            # Handle setup-related interactions
            if custom_id in ['setup_role_select', 'setup_channel_select']:
                return handle_setup_select_menu(body)
            elif custom_id == 'setup_continue':
                return handle_setup_continue(body)
            elif custom_id.startswith('setup_message_link_'):
                return handle_message_link_button(body)
            elif custom_id.startswith('setup_skip_message_'):
                return handle_skip_message_button(body)
            elif custom_id.startswith('setup_approve_'):
                return handle_setup_approve(body)
            elif custom_id == 'setup_cancel':
                return handle_setup_cancel(body)
            else:
                # Regular button clicks (verification flow)
                return handle_button_click(body)

        elif interaction_type == InteractionType.MODAL_SUBMIT:
            # Modal form submissions
            custom_id = body.get('data', {}).get('custom_id')

            if custom_id.startswith('setup_domains_modal_'):
                return handle_domains_modal_submit(body)
            elif custom_id.startswith('setup_link_modal_'):
                return handle_message_modal_submit(body)
            else:
                return handle_modal_submit(body)

        else:
            print(f"WARNING: Unknown interaction type: {interaction_type}")
            return error_response("Unknown interaction type")

    except Exception as e:
        print(f"ERROR: Exception handling interaction: {e}")
        import traceback
        traceback.print_exc()
        return error_response("An internal error occurred")
