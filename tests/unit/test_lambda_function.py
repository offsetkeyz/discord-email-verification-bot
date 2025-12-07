"""
Unit tests for lambda_function module.

Tests the AWS Lambda entry point for Discord interactions including:
- Discord signature verification (security-critical)
- Request routing to appropriate handlers
- Interaction type handling (PING, APPLICATION_COMMAND, MESSAGE_COMPONENT, MODAL_SUBMIT)
- Error handling and edge cases
- Event parsing and validation
"""
import pytest
import sys
import os
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, call

# Add lambda directory to path
lambda_dir = Path(__file__).parent.parent.parent / 'lambda'
sys.path.insert(0, str(lambda_dir))

from lambda_function import lambda_handler
from discord_interactions import InteractionType


# ==============================================================================
# Test Fixtures
# ==============================================================================

@pytest.fixture
def valid_signature():
    """Mock valid Discord signature."""
    return 'a' * 128  # Valid hex signature


@pytest.fixture
def valid_timestamp():
    """Mock valid timestamp (current time)."""
    return str(int(time.time()))


@pytest.fixture
def base_event(valid_signature, valid_timestamp):
    """Base API Gateway event with valid signature headers."""
    return {
        'headers': {
            'x-signature-ed25519': valid_signature,
            'x-signature-timestamp': valid_timestamp,
            'content-type': 'application/json'
        },
        'body': '{}'
    }


@pytest.fixture
def ping_event(base_event):
    """PING interaction event for Discord endpoint verification."""
    event = base_event.copy()
    event['body'] = json.dumps({'type': InteractionType.PING})
    return event


@pytest.fixture
def command_event(base_event):
    """APPLICATION_COMMAND interaction event."""
    event = base_event.copy()
    event['body'] = json.dumps({
        'type': InteractionType.APPLICATION_COMMAND,
        'data': {
            'name': 'setup-email-verification'
        }
    })
    return event


@pytest.fixture
def button_click_event(base_event):
    """MESSAGE_COMPONENT interaction event for button click."""
    event = base_event.copy()
    event['body'] = json.dumps({
        'type': InteractionType.MESSAGE_COMPONENT,
        'data': {
            'custom_id': 'verify_button',
            'component_type': 2  # BUTTON
        }
    })
    return event


@pytest.fixture
def modal_submit_event(base_event):
    """MODAL_SUBMIT interaction event."""
    event = base_event.copy()
    event['body'] = json.dumps({
        'type': InteractionType.MODAL_SUBMIT,
        'data': {
            'custom_id': 'verification_modal'
        }
    })
    return event


@pytest.fixture
def mock_verify_signature():
    """Mock verify_discord_signature function."""
    with patch('lambda_function.verify_discord_signature') as mock:
        mock.return_value = True
        yield mock


@pytest.fixture
def mock_handlers():
    """Mock all handler functions."""
    with patch('lambda_function.handle_ping') as ping, \
         patch('lambda_function.handle_setup_command') as setup, \
         patch('lambda_function.handle_button_click') as button, \
         patch('lambda_function.handle_modal_submit') as modal, \
         patch('lambda_function.error_response') as error:

        # Configure default return values
        ping.return_value = {'statusCode': 200, 'body': '{"type": 1}'}
        setup.return_value = {'statusCode': 200, 'body': '{"type": 4}'}
        button.return_value = {'statusCode': 200, 'body': '{"type": 4}'}
        modal.return_value = {'statusCode': 200, 'body': '{"type": 4}'}
        error.return_value = {'statusCode': 200, 'body': '{"type": 4, "data": {"content": "Error", "flags": 64}}'}

        yield {
            'ping': ping,
            'setup': setup,
            'button': button,
            'modal': modal,
            'error': error
        }


# ==============================================================================
# Signature Verification Tests (Security-Critical)
# ==============================================================================

def test_missing_signature_header(lambda_context):
    """Test that requests without signature header are rejected."""
    event = {
        'headers': {
            'x-signature-timestamp': str(int(time.time()))
        },
        'body': '{}'
    }

    response = lambda_handler(event, lambda_context)

    assert response['statusCode'] == 401
    body = json.loads(response['body'])
    assert 'Unauthorized' in body['error']
    assert 'missing signature' in body['error']


def test_missing_timestamp_header(lambda_context):
    """Test that requests without timestamp header are rejected."""
    event = {
        'headers': {
            'x-signature-ed25519': 'a' * 128
        },
        'body': '{}'
    }

    response = lambda_handler(event, lambda_context)

    assert response['statusCode'] == 401
    body = json.loads(response['body'])
    assert 'Unauthorized' in body['error']
    assert 'missing signature' in body['error']


def test_invalid_signature(base_event, lambda_context):
    """Test that requests with invalid signature are rejected."""
    with patch('lambda_function.verify_discord_signature') as mock_verify:
        mock_verify.return_value = False

        response = lambda_handler(base_event, lambda_context)

        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert 'Unauthorized' in body['error']
        assert 'invalid signature' in body['error']
        mock_verify.assert_called_once()


def test_valid_signature_proceeds(ping_event, lambda_context, mock_verify_signature, mock_handlers):
    """Test that requests with valid signature proceed to routing."""
    response = lambda_handler(ping_event, lambda_context)

    assert response['statusCode'] == 200
    mock_verify_signature.assert_called_once()
    mock_handlers['ping'].assert_called_once()


def test_missing_headers_dict(lambda_context):
    """Test handling of event without headers dictionary."""
    event = {
        'body': '{}'
    }

    response = lambda_handler(event, lambda_context)

    assert response['statusCode'] == 401
    body = json.loads(response['body'])
    assert 'Unauthorized' in body['error']


# ==============================================================================
# JSON Parsing Tests
# ==============================================================================

def test_invalid_json_body(base_event, lambda_context, mock_verify_signature):
    """Test handling of malformed JSON in request body."""
    event = base_event.copy()
    event['body'] = 'invalid json {'

    response = lambda_handler(event, lambda_context)

    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert 'Invalid JSON' in body['error']


def test_missing_body(base_event, lambda_context, mock_verify_signature, mock_handlers):
    """Test handling of event without body field."""
    event = base_event.copy()
    del event['body']

    response = lambda_handler(event, lambda_context)

    # Should default to '{}' and parse successfully, then return error_response
    assert response['statusCode'] == 200  # error_response returns 200
    mock_handlers['error'].assert_called_once()  # Unknown interaction type routes to error


def test_empty_body_string(base_event, lambda_context, mock_verify_signature, mock_handlers):
    """Test handling of empty body string."""
    event = base_event.copy()
    event['body'] = ''

    response = lambda_handler(event, lambda_context)

    # Empty string is not valid JSON
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert 'Invalid JSON' in body['error']


# ==============================================================================
# Interaction Type Routing Tests
# ==============================================================================

def test_ping_interaction_routing(ping_event, lambda_context, mock_verify_signature, mock_handlers):
    """Test PING interaction is routed to handle_ping."""
    response = lambda_handler(ping_event, lambda_context)

    assert response['statusCode'] == 200
    mock_handlers['ping'].assert_called_once()
    mock_handlers['setup'].assert_not_called()
    mock_handlers['button'].assert_not_called()
    mock_handlers['modal'].assert_not_called()


def test_application_command_routing(command_event, lambda_context, mock_verify_signature, mock_handlers):
    """Test APPLICATION_COMMAND interaction is routed to setup handler."""
    response = lambda_handler(command_event, lambda_context)

    assert response['statusCode'] == 200
    mock_handlers['setup'].assert_called_once()
    # Verify the interaction body is passed
    call_args = mock_handlers['setup'].call_args[0][0]
    assert call_args['type'] == InteractionType.APPLICATION_COMMAND


def test_unknown_command_name(base_event, lambda_context, mock_verify_signature, mock_handlers):
    """Test unknown slash command returns error."""
    event = base_event.copy()
    event['body'] = json.dumps({
        'type': InteractionType.APPLICATION_COMMAND,
        'data': {
            'name': 'unknown-command'
        }
    })

    response = lambda_handler(event, lambda_context)

    assert response['statusCode'] == 200  # error_response returns 200
    mock_handlers['error'].assert_called_once()
    call_args = mock_handlers['error'].call_args[0][0]
    assert 'Unknown command' in call_args


def test_message_component_routing(button_click_event, lambda_context, mock_verify_signature, mock_handlers):
    """Test MESSAGE_COMPONENT interaction is routed to button handler."""
    response = lambda_handler(button_click_event, lambda_context)

    assert response['statusCode'] == 200
    mock_handlers['button'].assert_called_once()
    call_args = mock_handlers['button'].call_args[0][0]
    assert call_args['type'] == InteractionType.MESSAGE_COMPONENT


def test_modal_submit_routing(modal_submit_event, lambda_context, mock_verify_signature, mock_handlers):
    """Test MODAL_SUBMIT interaction is routed to modal handler."""
    response = lambda_handler(modal_submit_event, lambda_context)

    assert response['statusCode'] == 200
    mock_handlers['modal'].assert_called_once()
    call_args = mock_handlers['modal'].call_args[0][0]
    assert call_args['type'] == InteractionType.MODAL_SUBMIT


def test_unknown_interaction_type(base_event, lambda_context, mock_verify_signature, mock_handlers):
    """Test unknown interaction type returns error."""
    event = base_event.copy()
    event['body'] = json.dumps({
        'type': 99  # Invalid type
    })

    response = lambda_handler(event, lambda_context)

    assert response['statusCode'] == 200  # error_response returns 200
    mock_handlers['error'].assert_called_once()
    call_args = mock_handlers['error'].call_args[0][0]
    assert 'Unknown interaction type' in call_args


# ==============================================================================
# Setup Handler Routing Tests
# ==============================================================================

@patch('lambda_function.handle_setup_select_menu')
def test_setup_role_select_routing(mock_select, base_event, lambda_context, mock_verify_signature):
    """Test setup role select menu routing."""
    mock_select.return_value = {'statusCode': 200, 'body': '{}'}
    event = base_event.copy()
    event['body'] = json.dumps({
        'type': InteractionType.MESSAGE_COMPONENT,
        'data': {
            'custom_id': 'setup_role_select',
            'component_type': 3  # SELECT_MENU
        }
    })

    response = lambda_handler(event, lambda_context)

    assert response['statusCode'] == 200
    mock_select.assert_called_once()


@patch('lambda_function.handle_setup_select_menu')
def test_setup_channel_select_routing(mock_select, base_event, lambda_context, mock_verify_signature):
    """Test setup channel select menu routing."""
    mock_select.return_value = {'statusCode': 200, 'body': '{}'}
    event = base_event.copy()
    event['body'] = json.dumps({
        'type': InteractionType.MESSAGE_COMPONENT,
        'data': {
            'custom_id': 'setup_channel_select',
            'component_type': 3
        }
    })

    response = lambda_handler(event, lambda_context)

    assert response['statusCode'] == 200
    mock_select.assert_called_once()


@patch('lambda_function.handle_setup_continue')
def test_setup_continue_routing(mock_continue, base_event, lambda_context, mock_verify_signature):
    """Test setup continue button routing."""
    mock_continue.return_value = {'statusCode': 200, 'body': '{}'}
    event = base_event.copy()
    event['body'] = json.dumps({
        'type': InteractionType.MESSAGE_COMPONENT,
        'data': {
            'custom_id': 'setup_continue',
            'component_type': 2
        }
    })

    response = lambda_handler(event, lambda_context)

    assert response['statusCode'] == 200
    mock_continue.assert_called_once()


@patch('lambda_function.handle_message_link_button')
def test_setup_message_link_routing(mock_link, base_event, lambda_context, mock_verify_signature):
    """Test setup message link button routing."""
    mock_link.return_value = {'statusCode': 200, 'body': '{}'}
    event = base_event.copy()
    event['body'] = json.dumps({
        'type': InteractionType.MESSAGE_COMPONENT,
        'data': {
            'custom_id': 'setup_message_link_123',
            'component_type': 2
        }
    })

    response = lambda_handler(event, lambda_context)

    assert response['statusCode'] == 200
    mock_link.assert_called_once()


@patch('lambda_function.handle_skip_message_button')
def test_setup_skip_message_routing(mock_skip, base_event, lambda_context, mock_verify_signature):
    """Test setup skip message button routing."""
    mock_skip.return_value = {'statusCode': 200, 'body': '{}'}
    event = base_event.copy()
    event['body'] = json.dumps({
        'type': InteractionType.MESSAGE_COMPONENT,
        'data': {
            'custom_id': 'setup_skip_message_123',
            'component_type': 2
        }
    })

    response = lambda_handler(event, lambda_context)

    assert response['statusCode'] == 200
    mock_skip.assert_called_once()


@patch('lambda_function.handle_setup_approve')
def test_setup_approve_routing(mock_approve, base_event, lambda_context, mock_verify_signature):
    """Test setup approve button routing."""
    mock_approve.return_value = {'statusCode': 200, 'body': '{}'}
    event = base_event.copy()
    event['body'] = json.dumps({
        'type': InteractionType.MESSAGE_COMPONENT,
        'data': {
            'custom_id': 'setup_approve_123',
            'component_type': 2
        }
    })

    response = lambda_handler(event, lambda_context)

    assert response['statusCode'] == 200
    mock_approve.assert_called_once()


@patch('lambda_function.handle_setup_cancel')
def test_setup_cancel_routing(mock_cancel, base_event, lambda_context, mock_verify_signature):
    """Test setup cancel button routing."""
    mock_cancel.return_value = {'statusCode': 200, 'body': '{}'}
    event = base_event.copy()
    event['body'] = json.dumps({
        'type': InteractionType.MESSAGE_COMPONENT,
        'data': {
            'custom_id': 'setup_cancel',
            'component_type': 2
        }
    })

    response = lambda_handler(event, lambda_context)

    assert response['statusCode'] == 200
    mock_cancel.assert_called_once()


@patch('lambda_function.handle_domains_modal_submit')
def test_setup_domains_modal_routing(mock_domains, base_event, lambda_context, mock_verify_signature):
    """Test setup domains modal submit routing."""
    mock_domains.return_value = {'statusCode': 200, 'body': '{}'}
    event = base_event.copy()
    event['body'] = json.dumps({
        'type': InteractionType.MODAL_SUBMIT,
        'data': {
            'custom_id': 'setup_domains_modal_123'
        }
    })

    response = lambda_handler(event, lambda_context)

    assert response['statusCode'] == 200
    mock_domains.assert_called_once()


@patch('lambda_function.handle_message_modal_submit')
def test_setup_link_modal_routing(mock_message, base_event, lambda_context, mock_verify_signature):
    """Test setup link modal submit routing."""
    mock_message.return_value = {'statusCode': 200, 'body': '{}'}
    event = base_event.copy()
    event['body'] = json.dumps({
        'type': InteractionType.MODAL_SUBMIT,
        'data': {
            'custom_id': 'setup_link_modal_123'
        }
    })

    response = lambda_handler(event, lambda_context)

    assert response['statusCode'] == 200
    mock_message.assert_called_once()


# ==============================================================================
# Error Handling Tests
# ==============================================================================

def test_handler_exception_returns_error(ping_event, lambda_context, mock_verify_signature):
    """Test that exceptions in handlers are caught and return error response."""
    with patch('lambda_function.handle_ping') as mock_ping, \
         patch('lambda_function.error_response') as mock_error:
        mock_ping.side_effect = RuntimeError("Handler crashed")
        mock_error.return_value = {
            'statusCode': 200,
            'body': json.dumps({'type': 4, 'data': {'content': 'Error', 'flags': 64}})
        }

        response = lambda_handler(ping_event, lambda_context)

        assert response['statusCode'] == 200
        mock_error.assert_called_once_with("An internal error occurred")


def test_handler_keyboard_interrupt_propagates(ping_event, lambda_context, mock_verify_signature):
    """Test that KeyboardInterrupt is not caught (allows Lambda shutdown)."""
    with patch('lambda_function.handle_ping') as mock_ping:
        mock_ping.side_effect = KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            lambda_handler(ping_event, lambda_context)


def test_logging_on_signature_failure(base_event, lambda_context, capsys):
    """Test that signature failures are logged."""
    with patch('lambda_function.verify_discord_signature') as mock_verify:
        mock_verify.return_value = False

        lambda_handler(base_event, lambda_context)

        # Check that error was printed
        captured = capsys.readouterr()
        assert 'ERROR: Invalid Discord signature' in captured.out


def test_logging_on_json_error(base_event, lambda_context, mock_verify_signature, capsys):
    """Test that JSON parsing errors are logged."""
    event = base_event.copy()
    event['body'] = 'not json'

    lambda_handler(event, lambda_context)

    captured = capsys.readouterr()
    assert 'ERROR: Invalid JSON' in captured.out


def test_logging_interaction_type(ping_event, lambda_context, mock_verify_signature, mock_handlers, capsys):
    """Test that interaction type is logged."""
    lambda_handler(ping_event, lambda_context)

    captured = capsys.readouterr()
    assert 'Interaction type: 1' in captured.out


def test_logging_command_name(command_event, lambda_context, mock_verify_signature, mock_handlers, capsys):
    """Test that command name is logged."""
    lambda_handler(command_event, lambda_context)

    captured = capsys.readouterr()
    assert 'Slash command: setup-email-verification' in captured.out


# ==============================================================================
# Edge Cases and Integration Tests
# ==============================================================================

def test_missing_interaction_type(base_event, lambda_context, mock_verify_signature, mock_handlers):
    """Test handling of event with missing interaction type."""
    event = base_event.copy()
    event['body'] = json.dumps({'data': {}})

    response = lambda_handler(event, lambda_context)

    assert response['statusCode'] == 200  # error_response returns 200
    mock_handlers['error'].assert_called_once()


def test_missing_command_data(base_event, lambda_context, mock_verify_signature, mock_handlers):
    """Test APPLICATION_COMMAND with missing data field."""
    event = base_event.copy()
    event['body'] = json.dumps({
        'type': InteractionType.APPLICATION_COMMAND
    })

    response = lambda_handler(event, lambda_context)

    # Should attempt to get 'name' from empty dict
    mock_handlers['error'].assert_called_once()


def test_missing_component_data(base_event, lambda_context, mock_verify_signature, mock_handlers):
    """Test MESSAGE_COMPONENT with missing data field."""
    event = base_event.copy()
    event['body'] = json.dumps({
        'type': InteractionType.MESSAGE_COMPONENT
    })

    response = lambda_handler(event, lambda_context)

    # Should default to empty custom_id and route to button handler
    assert response['statusCode'] == 200
    mock_handlers['button'].assert_called_once()


def test_empty_custom_id(base_event, lambda_context, mock_verify_signature, mock_handlers):
    """Test MESSAGE_COMPONENT with empty custom_id."""
    event = base_event.copy()
    event['body'] = json.dumps({
        'type': InteractionType.MESSAGE_COMPONENT,
        'data': {
            'custom_id': '',
            'component_type': 2
        }
    })

    response = lambda_handler(event, lambda_context)

    # Empty custom_id should route to regular button handler
    assert response['statusCode'] == 200
    mock_handlers['button'].assert_called_once()


@patch('lambda_function.log_safe')
def test_event_logging(mock_log, ping_event, lambda_context, mock_verify_signature, mock_handlers):
    """Test that incoming events are logged safely."""
    lambda_handler(ping_event, lambda_context)

    mock_log.assert_called_once_with("Received event", ping_event)


def test_autocomplete_interaction_type(base_event, lambda_context, mock_verify_signature, mock_handlers):
    """Test APPLICATION_COMMAND_AUTOCOMPLETE interaction type (currently unsupported)."""
    event = base_event.copy()
    event['body'] = json.dumps({
        'type': InteractionType.APPLICATION_COMMAND_AUTOCOMPLETE
    })

    response = lambda_handler(event, lambda_context)

    # Should return unknown interaction type error
    assert response['statusCode'] == 200  # error_response returns 200
    mock_handlers['error'].assert_called_once()
    call_args = mock_handlers['error'].call_args[0][0]
    assert 'Unknown interaction type' in call_args


def test_response_format_structure(ping_event, lambda_context, mock_verify_signature):
    """Test that response format matches API Gateway proxy integration requirements."""
    with patch('lambda_function.handle_ping') as mock_ping:
        mock_ping.return_value = {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'type': 1})
        }

        response = lambda_handler(ping_event, lambda_context)

        # Verify response structure
        assert 'statusCode' in response
        assert 'body' in response
        assert isinstance(response['statusCode'], int)
        assert isinstance(response['body'], str)

        # Verify body is valid JSON
        body = json.loads(response['body'])
        assert body['type'] == 1
