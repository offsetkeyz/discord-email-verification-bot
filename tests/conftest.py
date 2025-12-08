"""
Central pytest configuration and fixtures for Discord email verification bot tests.

This module provides reusable fixtures for:
- AWS service mocking (DynamoDB, SES, SSM)
- Discord API mocking
- Environment variable setup
- Test data factories
"""
import pytest
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal

# Add lambda directory to path for imports
lambda_dir = Path(__file__).parent.parent / 'lambda'
sys.path.insert(0, str(lambda_dir))

# AWS mocking
from moto import mock_aws
import boto3
import responses


# ==============================================================================
# Environment Setup
# ==============================================================================

@pytest.fixture(scope='session', autouse=True)
def set_test_environment():
    """Set up test environment variables for all tests."""
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'

    # Discord configuration
    os.environ['DISCORD_PUBLIC_KEY'] = 'a' * 64  # Valid hex string
    os.environ['DISCORD_APP_ID'] = '1234567890'

    # AWS service configuration
    os.environ['DYNAMODB_SESSIONS_TABLE'] = 'discord-verification-sessions'
    os.environ['DYNAMODB_RECORDS_TABLE'] = 'discord-verification-records'
    os.environ['DYNAMODB_GUILD_CONFIGS_TABLE'] = 'discord-guild-configs'
    os.environ['FROM_EMAIL'] = 'test@test.com'

    yield

    # Cleanup (optional)


# ==============================================================================
# AWS Lambda Fixtures
# ==============================================================================

@pytest.fixture
def lambda_context():
    """
    Mock AWS Lambda context object.

    Provides a realistic Lambda context for handler testing with:
    - Function metadata (name, version, memory)
    - Request IDs for tracing
    - Timing information
    """
    class LambdaContext:
        def __init__(self):
            self.function_name = "discord-verification-bot"
            self.function_version = "$LATEST"
            self.invoked_function_arn = (
                "arn:aws:lambda:us-east-1:123456789012:function:discord-verification-bot"
            )
            self.memory_limit_in_mb = 128
            self.request_id = "test-request-id-12345"
            self.aws_request_id = "test-request-id-12345"
            self.log_group_name = "/aws/lambda/discord-verification-bot"
            self.log_stream_name = "2024/01/01/[$LATEST]abcdef123456"
            self._remaining_time_ms = 300000  # 5 minutes

        def get_remaining_time_in_millis(self):
            """Return remaining execution time in milliseconds."""
            return self._remaining_time_ms

    return LambdaContext()


# ==============================================================================
# AWS DynamoDB Fixtures
# ==============================================================================

@pytest.fixture
def aws_credentials():
    """Mock AWS credentials for moto."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'


@pytest.fixture
def mock_dynamodb_tables(aws_credentials):
    """Create mock DynamoDB tables with proper schema."""
    with mock_aws():
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

        # Sessions table
        sessions_table = dynamodb.create_table(
            TableName='discord-verification-sessions',
            KeySchema=[
                {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                {'AttributeName': 'guild_id', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'user_id', 'AttributeType': 'S'},
                {'AttributeName': 'guild_id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )

        # Records table with GSI
        records_table = dynamodb.create_table(
            TableName='discord-verification-records',
            KeySchema=[
                {'AttributeName': 'verification_id', 'KeyType': 'HASH'},
                {'AttributeName': 'created_at', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'verification_id', 'AttributeType': 'S'},
                {'AttributeName': 'created_at', 'AttributeType': 'N'},
                {'AttributeName': 'user_guild_composite', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[{
                'IndexName': 'user_guild-index',
                'KeySchema': [
                    {'AttributeName': 'user_guild_composite', 'KeyType': 'HASH'},
                    {'AttributeName': 'created_at', 'KeyType': 'RANGE'}
                ],
                'Projection': {'ProjectionType': 'ALL'}
            }],
            BillingMode='PAY_PER_REQUEST'
        )

        # Guild configs table
        configs_table = dynamodb.create_table(
            TableName='discord-guild-configs',
            KeySchema=[
                {'AttributeName': 'guild_id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'guild_id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )

        yield {
            'sessions': sessions_table,
            'records': records_table,
            'configs': configs_table,
            'dynamodb': dynamodb
        }


# ==============================================================================
# AWS SES Fixtures
# ==============================================================================

@pytest.fixture
def mock_ses_service(aws_credentials):
    """Mock AWS SES service."""
    with mock_aws():
        ses = boto3.client('ses', region_name='us-east-1')
        # Verify a test email address
        ses.verify_email_identity(EmailAddress='test@test.com')
        yield ses


# ==============================================================================
# AWS SSM Fixtures
# ==============================================================================

@pytest.fixture
def mock_ssm_parameters(aws_credentials):
    """Mock AWS SSM Parameter Store with bot token."""
    with mock_aws():
        ssm = boto3.client('ssm', region_name='us-east-1')
        ssm.put_parameter(
            Name='/discord-bot/token',
            Value='test_bot_token_12345',
            Type='SecureString'
        )
        yield ssm


# ==============================================================================
# Discord API Fixtures
# ==============================================================================

@pytest.fixture
def mock_discord_api():
    """Mock Discord REST API with responses library."""
    with responses.RequestsMock() as rsps:
        yield rsps


@pytest.fixture
def mock_discord_role_assignment_success(mock_discord_api):
    """Mock successful Discord role assignment."""
    mock_discord_api.add(
        responses.PUT,
        'https://discord.com/api/v10/guilds/123456/members/789012/roles/111222',
        status=204
    )
    return mock_discord_api


@pytest.fixture
def mock_discord_member_with_role(mock_discord_api):
    """Mock Discord member fetch with role."""
    mock_discord_api.add(
        responses.GET,
        'https://discord.com/api/v10/guilds/123456/members/789012',
        json={
            'user': {'id': '789012', 'username': 'testuser'},
            'roles': ['111222']
        },
        status=200
    )
    return mock_discord_api


@pytest.fixture
def mock_discord_member_without_role(mock_discord_api):
    """Mock Discord member fetch without role."""
    mock_discord_api.add(
        responses.GET,
        'https://discord.com/api/v10/guilds/123456/members/789012',
        json={
            'user': {'id': '789012', 'username': 'testuser'},
            'roles': []
        },
        status=200
    )
    return mock_discord_api


@pytest.fixture
def mock_discord_message_fetch(mock_discord_api):
    """Mock Discord message fetch for setup flow."""
    mock_discord_api.add(
        responses.GET,
        'https://discord.com/api/v10/channels/999888/messages/777666',
        json={
            'id': '777666',
            'channel_id': '999888',
            'guild_id': '123456',
            'content': 'Click the button below to verify your email! 📧',
            'author': {'id': '1234567890', 'username': 'botuser'}
        },
        status=200
    )
    return mock_discord_api


# ==============================================================================
# Combined Fixture for Full System
# ==============================================================================

@pytest.fixture
def full_system_mock(mock_dynamodb_tables, mock_ses_service, mock_ssm_parameters, mock_discord_api):
    """Combined fixture with all AWS and Discord mocks configured."""
    return {
        'dynamodb': mock_dynamodb_tables,
        'ses': mock_ses_service,
        'ssm': mock_ssm_parameters,
        'discord_api': mock_discord_api
    }


# ==============================================================================
# Test Data Factories
# ==============================================================================

@pytest.fixture
def sample_verification_session():
    """Create a sample verification session dict."""
    now = datetime.utcnow()
    return {
        'user_id': '789012',
        'guild_id': '123456',
        'email': 'test@auburn.edu',
        'code': '123456',
        'verification_id': 'test-verification-id-001',
        'attempts': 0,
        'state': 'awaiting_code',
        'created_at': now.isoformat(),
        'expires_at': (now + timedelta(minutes=15)).isoformat(),
        'ttl': int((now + timedelta(hours=24)).timestamp())
    }


@pytest.fixture
def sample_guild_config():
    """Create a sample guild configuration dict."""
    return {
        'guild_id': '123456',
        'role_id': '111222',
        'channel_id': '999888',
        'allowed_domains': ['auburn.edu', 'student.sans.edu'],
        'custom_message': 'Click the button below to verify your email!',
        'setup_by': '789012',
        'setup_timestamp': datetime.utcnow().isoformat()
    }


@pytest.fixture
def sample_api_gateway_event():
    """Create a sample API Gateway event."""
    return {
        'headers': {
            'x-signature-ed25519': 'valid_signature',
            'x-signature-timestamp': '1234567890'
        },
        'body': '{"type": 1}'
    }


# ==============================================================================
# Helper Functions
# ==============================================================================

def create_api_gateway_event(body_dict, signature='valid_sig', timestamp='1234567890'):
    """Helper to create API Gateway Lambda event."""
    import json
    return {
        'headers': {
            'x-signature-ed25519': signature,
            'x-signature-timestamp': timestamp,
            'content-type': 'application/json'
        },
        'body': json.dumps(body_dict)
    }


def assert_response_status(response, expected_status):
    """Assert response has expected HTTP status code."""
    assert response.get('statusCode') == expected_status, \
        f"Expected status {expected_status}, got {response.get('statusCode')}"


def assert_ephemeral_response(response, expected_content=None):
    """
    Assert response is an ephemeral Discord message.

    Args:
        response: Lambda response dict
        expected_content: Optional substring to check in response content
    """
    import json
    assert response['statusCode'] == 200
    body = json.loads(response['body'])

    # Check ephemeral flag (64 = EPHEMERAL)
    assert 'data' in body or 'type' in body, "Response missing Discord interaction data"

    if expected_content and 'data' in body:
        content = body['data'].get('content', '')
        assert expected_content in content, \
            f"Expected '{expected_content}' in response, got: {content}"


def get_table_item_count(dynamodb_table):
    """Get number of items in a DynamoDB table (for cleanup verification)."""
    response = dynamodb_table.scan(Select='COUNT')
    return response.get('Count', 0)


# ==============================================================================
# Integration Test Fixtures (Phase 3A+)
# ==============================================================================

@pytest.fixture
def integration_mock_env(mock_dynamodb_tables, mock_ses_service, mock_ssm_parameters):
    """Complete integration environment with all AWS services mocked."""
    from unittest.mock import patch

    # Patch all module-level clients
    with patch('dynamodb_operations.sessions_table', mock_dynamodb_tables['sessions']), \
         patch('dynamodb_operations.records_table', mock_dynamodb_tables['records']), \
         patch('guild_config.configs_table', mock_dynamodb_tables['configs']), \
         patch('ses_email.ses_client', mock_ses_service), \
         patch('ssm_utils.ssm_client', mock_ssm_parameters):

        yield {
            'dynamodb': mock_dynamodb_tables,
            'ses': mock_ses_service,
            'ssm': mock_ssm_parameters
        }


@pytest.fixture
def setup_test_guild(integration_mock_env):
    """Set up a test guild configuration."""
    import sys
    from pathlib import Path

    # Add lambda directory to path if not already there
    lambda_dir = Path(__file__).parent.parent / 'lambda'
    if str(lambda_dir) not in sys.path:
        sys.path.insert(0, str(lambda_dir))

    from guild_config import save_guild_config

    save_guild_config(
        guild_id='test_guild_123',
        role_id='verified_role_456',
        channel_id='verify_channel_789',
        setup_by_user_id='admin_user_001',
        allowed_domains=['auburn.edu', 'test.edu'],
        custom_message='Welcome! Please verify your .edu email to gain access.'
    )

    return {
        'guild_id': 'test_guild_123',
        'role_id': 'verified_role_456',
        'channel_id': 'verify_channel_789',
        'user_id': 'test_user_999'
    }


# Make helper functions available to tests
pytest.create_api_gateway_event = create_api_gateway_event
pytest.assert_response_status = assert_response_status
pytest.assert_ephemeral_response = assert_ephemeral_response
pytest.get_table_item_count = get_table_item_count
