"""
Unit tests for custom completion message feature (TDD approach).

These tests define the expected behavior for customizable verification
completion messages. They WILL FAIL until the backend implements the feature.

Tests cover:
- Guild config functions (get/save completion message)
- Handler functions (use custom completion message  
- Validation (character limits, sanitization)
- Backward compatibility (missing field handling)
"""
import pytest
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta
from moto import mock_aws
import boto3
from freezegun import freeze_time
import json

# Add lambda directory to path
lambda_dir = Path(__file__).parent.parent.parent / 'lambda'
sys.path.insert(0, str(lambda_dir))


# ==============================================================================
# Constants
# ==============================================================================

DEFAULT_COMPLETION_MESSAGE = "🎉 **Verification complete!** You now have access to the server.\n\nWelcome! 👋"
COMPLETION_MESSAGE_MAX_LENGTH = 2000  # Discord limit


# ==============================================================================
# Test Fixtures
# ==============================================================================

@pytest.fixture
def mock_dynamodb_tables():
    """Mock DynamoDB tables for testing."""
    with mock_aws():
        # Create DynamoDB resource
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

        # Create guild configs table
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

        # Create sessions table
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

        # Patch module-level tables
        with patch('guild_config.configs_table', configs_table), \
             patch('dynamodb_operations.sessions_table', sessions_table):
            yield {'configs': configs_table, 'sessions': sessions_table}


@pytest.fixture
def sample_guild_config():
    """Sample guild configuration WITH completion_message."""
    return {
        'guild_id': '123456789012345678',
        'role_id': '987654321098765432',
        'channel_id': '111222333444555666',
        'allowed_domains': ['auburn.edu', 'student.sans.edu'],
        'custom_message': 'Click to verify!',
        'completion_message': '✅ Welcome! You are now verified.',
        'setup_by': '777888999000111222',
        'setup_timestamp': '2025-01-15T10:30:00',
        'last_updated': '2025-01-15T10:30:00'
    }


@pytest.fixture
def sample_guild_config_no_completion():
    """Sample guild configuration WITHOUT completion_message (legacy)."""
    return {
        'guild_id': '999888777666555444',
        'role_id': '444555666777888999',
        'channel_id': '222333444555666777',
        'allowed_domains': ['test.edu'],
        'custom_message': 'Verify here',
        'setup_by': '111222333444555666',
        'setup_timestamp': '2025-01-10T09:00:00',
        'last_updated': '2025-01-10T09:00:00'
        # Note: No 'completion_message' field - testing backward compatibility
    }


# Import after setting up fixtures path
from guild_config import (
    get_guild_config,
    save_guild_config,
    is_guild_configured,
    get_guild_role_id
)
