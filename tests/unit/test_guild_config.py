"""
Unit tests for guild_config module.

Tests guild configuration management including:
- DynamoDB CRUD operations for guild configs
- Default value fallbacks (domains, messages)
- Configuration validation
- Error handling
"""
import pytest
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime
from moto import mock_aws
import boto3
from freezegun import freeze_time

# Add lambda directory to path
lambda_dir = Path(__file__).parent.parent.parent / 'lambda'
sys.path.insert(0, str(lambda_dir))


# ==============================================================================
# Test Fixtures
# ==============================================================================

@pytest.fixture
def mock_dynamodb_table():
    """Mock DynamoDB guild configs table."""
    with mock_aws():
        # Create DynamoDB resource and table
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

        table = dynamodb.create_table(
            TableName='discord-guild-configs',
            KeySchema=[
                {'AttributeName': 'guild_id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'guild_id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )

        # Patch the module-level table
        with patch('guild_config.configs_table', table):
            yield table


@pytest.fixture
def sample_guild_config():
    """Sample guild configuration data."""
    return {
        'guild_id': '123456789012345678',
        'role_id': '987654321098765432',
        'channel_id': '111222333444555666',
        'allowed_domains': ['auburn.edu', 'student.sans.edu'],
        'custom_message': 'Welcome! Click to verify.',
        'setup_by': '777888999000111222',
        'setup_timestamp': '2025-01-15T10:30:00',
        'last_updated': '2025-01-15T10:30:00'
    }


# Import after setting up mocks
from guild_config import (
    get_guild_config,
    save_guild_config,
    is_guild_configured,
    get_guild_role_id,
    get_guild_allowed_domains,
    get_guild_custom_message,
    delete_guild_config
)


# ==============================================================================
# get_guild_config() Tests
# ==============================================================================

@pytest.mark.unit
class TestGetGuildConfig:
    """Tests for get_guild_config() function."""

    def test_get_existing_config_returns_dict(self, mock_dynamodb_table, sample_guild_config):
        """Test retrieving an existing guild configuration."""
        # Insert test data
        mock_dynamodb_table.put_item(Item=sample_guild_config)

        result = get_guild_config('123456789012345678')

        assert result is not None
        assert result['guild_id'] == '123456789012345678'
        assert result['role_id'] == '987654321098765432'
        assert result['channel_id'] == '111222333444555666'

    def test_get_nonexistent_config_returns_none(self, mock_dynamodb_table):
        """Test retrieving a non-existent guild returns None."""
        result = get_guild_config('nonexistent_guild_id')

        assert result is None

    def test_get_config_includes_all_fields(self, mock_dynamodb_table, sample_guild_config):
        """Test that all configuration fields are returned."""
        mock_dynamodb_table.put_item(Item=sample_guild_config)

        result = get_guild_config('123456789012345678')

        assert 'allowed_domains' in result
        assert 'custom_message' in result
        assert 'setup_by' in result
        assert 'setup_timestamp' in result
        assert 'last_updated' in result

    def test_get_config_error_handling(self, mock_dynamodb_table):
        """Test error handling when DynamoDB operation fails."""
        with patch.object(mock_dynamodb_table, 'get_item', side_effect=Exception("DynamoDB error")):
            result = get_guild_config('123456789012345678')

            assert result is None


# ==============================================================================
# save_guild_config() Tests
# ==============================================================================

@pytest.mark.unit
class TestSaveGuildConfig:
    """Tests for save_guild_config() function."""

    @freeze_time("2025-01-15 10:30:00")
    def test_save_new_config_success(self, mock_dynamodb_table):
        """Test saving a new guild configuration."""
        result = save_guild_config(
            guild_id='123456789012345678',
            role_id='987654321098765432',
            channel_id='111222333444555666',
            setup_by_user_id='777888999000111222'
        )

        assert result is True

        # Verify data was saved
        saved = mock_dynamodb_table.get_item(Key={'guild_id': '123456789012345678'})
        assert saved['Item']['role_id'] == '987654321098765432'
        assert saved['Item']['channel_id'] == '111222333444555666'

    @freeze_time("2025-01-15 10:30:00")
    def test_save_config_with_default_domains(self, mock_dynamodb_table):
        """Test that default allowed domains are set when not provided."""
        save_guild_config(
            guild_id='123456789012345678',
            role_id='987654321098765432',
            channel_id='111222333444555666',
            setup_by_user_id='777888999000111222'
        )

        saved = mock_dynamodb_table.get_item(Key={'guild_id': '123456789012345678'})
        assert saved['Item']['allowed_domains'] == ['auburn.edu', 'student.sans.edu']

    @freeze_time("2025-01-15 10:30:00")
    def test_save_config_with_custom_domains(self, mock_dynamodb_table):
        """Test saving with custom allowed domains."""
        custom_domains = ['example.edu', 'university.edu']

        save_guild_config(
            guild_id='123456789012345678',
            role_id='987654321098765432',
            channel_id='111222333444555666',
            setup_by_user_id='777888999000111222',
            allowed_domains=custom_domains
        )

        saved = mock_dynamodb_table.get_item(Key={'guild_id': '123456789012345678'})
        assert saved['Item']['allowed_domains'] == custom_domains

    @freeze_time("2025-01-15 10:30:00")
    def test_save_config_with_default_message(self, mock_dynamodb_table):
        """Test that default custom message is set when not provided."""
        save_guild_config(
            guild_id='123456789012345678',
            role_id='987654321098765432',
            channel_id='111222333444555666',
            setup_by_user_id='777888999000111222'
        )

        saved = mock_dynamodb_table.get_item(Key={'guild_id': '123456789012345678'})
        assert saved['Item']['custom_message'] == "Click the button below to verify your email address."

    @freeze_time("2025-01-15 10:30:00")
    def test_save_config_with_custom_message(self, mock_dynamodb_table):
        """Test saving with custom verification message."""
        custom_msg = "Welcome to our server! Verify your .edu email to gain access."

        save_guild_config(
            guild_id='123456789012345678',
            role_id='987654321098765432',
            channel_id='111222333444555666',
            setup_by_user_id='777888999000111222',
            custom_message=custom_msg
        )

        saved = mock_dynamodb_table.get_item(Key={'guild_id': '123456789012345678'})
        assert saved['Item']['custom_message'] == custom_msg

    @freeze_time("2025-01-15 10:30:00")
    def test_save_config_includes_timestamps(self, mock_dynamodb_table):
        """Test that timestamps are included in saved config."""
        save_guild_config(
            guild_id='123456789012345678',
            role_id='987654321098765432',
            channel_id='111222333444555666',
            setup_by_user_id='777888999000111222'
        )

        saved = mock_dynamodb_table.get_item(Key={'guild_id': '123456789012345678'})
        assert saved['Item']['setup_timestamp'] == '2025-01-15T10:30:00'
        assert saved['Item']['last_updated'] == '2025-01-15T10:30:00'

    @freeze_time("2025-01-15 10:30:00")
    def test_save_config_includes_setup_user(self, mock_dynamodb_table):
        """Test that setup_by user ID is stored."""
        save_guild_config(
            guild_id='123456789012345678',
            role_id='987654321098765432',
            channel_id='111222333444555666',
            setup_by_user_id='777888999000111222'
        )

        saved = mock_dynamodb_table.get_item(Key={'guild_id': '123456789012345678'})
        assert saved['Item']['setup_by'] == '777888999000111222'

    def test_update_existing_config(self, mock_dynamodb_table, sample_guild_config):
        """Test updating an existing configuration."""
        # Insert initial config
        mock_dynamodb_table.put_item(Item=sample_guild_config)

        # Update with new values
        with freeze_time("2025-01-16 15:45:00"):
            result = save_guild_config(
                guild_id='123456789012345678',
                role_id='new_role_id_123',
                channel_id='new_channel_id_456',
                setup_by_user_id='777888999000111222'
            )

        assert result is True

        # Verify update
        updated = mock_dynamodb_table.get_item(Key={'guild_id': '123456789012345678'})
        assert updated['Item']['role_id'] == 'new_role_id_123'
        assert updated['Item']['channel_id'] == 'new_channel_id_456'
        assert updated['Item']['last_updated'] == '2025-01-16T15:45:00'

    def test_save_config_error_handling(self, mock_dynamodb_table):
        """Test error handling when save operation fails."""
        with patch.object(mock_dynamodb_table, 'put_item', side_effect=Exception("DynamoDB error")):
            result = save_guild_config(
                guild_id='123456789012345678',
                role_id='987654321098765432',
                channel_id='111222333444555666',
                setup_by_user_id='777888999000111222'
            )

            assert result is False


# ==============================================================================
# is_guild_configured() Tests
# ==============================================================================

@pytest.mark.unit
class TestIsGuildConfigured:
    """Tests for is_guild_configured() function."""

    def test_configured_guild_returns_true(self, mock_dynamodb_table, sample_guild_config):
        """Test that properly configured guild returns True."""
        mock_dynamodb_table.put_item(Item=sample_guild_config)

        result = is_guild_configured('123456789012345678')

        assert result is True

    def test_unconfigured_guild_returns_false(self, mock_dynamodb_table):
        """Test that non-existent guild returns False."""
        result = is_guild_configured('nonexistent_guild')

        assert result is False

    def test_partial_config_missing_role_returns_false(self, mock_dynamodb_table):
        """Test that config without role_id returns False."""
        partial_config = {
            'guild_id': '123456789012345678',
            'channel_id': '111222333444555666'
            # role_id missing
        }
        mock_dynamodb_table.put_item(Item=partial_config)

        result = is_guild_configured('123456789012345678')

        assert result is False

    def test_partial_config_missing_channel_returns_false(self, mock_dynamodb_table):
        """Test that config without channel_id returns False."""
        partial_config = {
            'guild_id': '123456789012345678',
            'role_id': '987654321098765432'
            # channel_id missing
        }
        mock_dynamodb_table.put_item(Item=partial_config)

        result = is_guild_configured('123456789012345678')

        assert result is False

    def test_empty_config_returns_false(self, mock_dynamodb_table):
        """Test that empty config object returns False."""
        empty_config = {
            'guild_id': '123456789012345678'
        }
        mock_dynamodb_table.put_item(Item=empty_config)

        result = is_guild_configured('123456789012345678')

        assert result is False


# ==============================================================================
# get_guild_role_id() Tests
# ==============================================================================

@pytest.mark.unit
class TestGetGuildRoleId:
    """Tests for get_guild_role_id() function."""

    def test_get_role_id_from_configured_guild(self, mock_dynamodb_table, sample_guild_config):
        """Test retrieving role ID from configured guild."""
        mock_dynamodb_table.put_item(Item=sample_guild_config)

        result = get_guild_role_id('123456789012345678')

        assert result == '987654321098765432'

    def test_get_role_id_from_unconfigured_guild_returns_none(self, mock_dynamodb_table):
        """Test that non-existent guild returns None."""
        result = get_guild_role_id('nonexistent_guild')

        assert result is None

    def test_get_role_id_from_config_without_role_returns_none(self, mock_dynamodb_table):
        """Test that config without role_id field returns None."""
        config_no_role = {
            'guild_id': '123456789012345678',
            'channel_id': '111222333444555666'
        }
        mock_dynamodb_table.put_item(Item=config_no_role)

        result = get_guild_role_id('123456789012345678')

        assert result is None


# ==============================================================================
# get_guild_allowed_domains() Tests
# ==============================================================================

@pytest.mark.unit
class TestGetGuildAllowedDomains:
    """Tests for get_guild_allowed_domains() function."""

    def test_get_custom_allowed_domains(self, mock_dynamodb_table):
        """Test retrieving custom allowed domains."""
        config_with_domains = {
            'guild_id': '123456789012345678',
            'allowed_domains': ['example.edu', 'university.edu', 'college.edu']
        }
        mock_dynamodb_table.put_item(Item=config_with_domains)

        result = get_guild_allowed_domains('123456789012345678')

        assert result == ['example.edu', 'university.edu', 'college.edu']

    def test_get_allowed_domains_returns_default_for_unconfigured_guild(self, mock_dynamodb_table):
        """Test that unconfigured guild returns default domains."""
        result = get_guild_allowed_domains('nonexistent_guild')

        assert result == ['auburn.edu', 'student.sans.edu']

    def test_get_allowed_domains_returns_default_when_field_missing(self, mock_dynamodb_table):
        """Test that config without allowed_domains returns default."""
        config_no_domains = {
            'guild_id': '123456789012345678',
            'role_id': '987654321098765432'
        }
        mock_dynamodb_table.put_item(Item=config_no_domains)

        result = get_guild_allowed_domains('123456789012345678')

        assert result == ['auburn.edu', 'student.sans.edu']

    def test_get_allowed_domains_empty_list(self, mock_dynamodb_table):
        """Test handling of empty allowed_domains list."""
        config_empty_domains = {
            'guild_id': '123456789012345678',
            'allowed_domains': []
        }
        mock_dynamodb_table.put_item(Item=config_empty_domains)

        result = get_guild_allowed_domains('123456789012345678')

        # Empty list should be returned as-is, not replaced with defaults
        assert result == []


# ==============================================================================
# get_guild_custom_message() Tests
# ==============================================================================

@pytest.mark.unit
class TestGetGuildCustomMessage:
    """Tests for get_guild_custom_message() function."""

    def test_get_custom_message(self, mock_dynamodb_table):
        """Test retrieving custom verification message."""
        custom_msg = "Welcome! Verify your .edu email to access all channels."
        config_with_message = {
            'guild_id': '123456789012345678',
            'custom_message': custom_msg
        }
        mock_dynamodb_table.put_item(Item=config_with_message)

        result = get_guild_custom_message('123456789012345678')

        assert result == custom_msg

    def test_get_custom_message_returns_default_for_unconfigured_guild(self, mock_dynamodb_table):
        """Test that unconfigured guild returns default message."""
        result = get_guild_custom_message('nonexistent_guild')

        assert result == "Click the button below to verify your email address."

    def test_get_custom_message_returns_default_when_field_missing(self, mock_dynamodb_table):
        """Test that config without custom_message returns default."""
        config_no_message = {
            'guild_id': '123456789012345678',
            'role_id': '987654321098765432'
        }
        mock_dynamodb_table.put_item(Item=config_no_message)

        result = get_guild_custom_message('123456789012345678')

        assert result == "Click the button below to verify your email address."

    def test_get_custom_message_empty_string(self, mock_dynamodb_table):
        """Test handling of empty custom_message string."""
        config_empty_message = {
            'guild_id': '123456789012345678',
            'custom_message': ''
        }
        mock_dynamodb_table.put_item(Item=config_empty_message)

        result = get_guild_custom_message('123456789012345678')

        # Empty string should be returned as-is, not replaced with default
        assert result == ''


# ==============================================================================
# delete_guild_config() Tests
# ==============================================================================

@pytest.mark.unit
class TestDeleteGuildConfig:
    """Tests for delete_guild_config() function."""

    def test_delete_existing_config_success(self, mock_dynamodb_table, sample_guild_config):
        """Test deleting an existing guild configuration."""
        # Create config
        mock_dynamodb_table.put_item(Item=sample_guild_config)

        # Delete it
        result = delete_guild_config('123456789012345678')

        assert result is True

        # Verify deletion
        response = mock_dynamodb_table.get_item(Key={'guild_id': '123456789012345678'})
        assert 'Item' not in response

    def test_delete_nonexistent_config_success(self, mock_dynamodb_table):
        """Test that deleting non-existent config still returns True."""
        # DynamoDB delete_item is idempotent - doesn't error if item doesn't exist
        result = delete_guild_config('nonexistent_guild')

        assert result is True

    def test_delete_config_error_handling(self, mock_dynamodb_table):
        """Test error handling when delete operation fails."""
        with patch.object(mock_dynamodb_table, 'delete_item', side_effect=Exception("DynamoDB error")):
            result = delete_guild_config('123456789012345678')

            assert result is False


# ==============================================================================
# Integration Tests
# ==============================================================================

@pytest.mark.unit
class TestGuildConfigIntegration:
    """Integration-style tests for guild config workflows."""

    @freeze_time("2025-01-15 10:30:00")
    def test_complete_guild_setup_workflow(self, mock_dynamodb_table):
        """Test complete workflow: check configured → save → verify → retrieve values."""
        guild_id = '123456789012345678'

        # 1. Check not configured initially
        assert is_guild_configured(guild_id) is False

        # 2. Save configuration
        save_result = save_guild_config(
            guild_id=guild_id,
            role_id='role_123',
            channel_id='channel_456',
            setup_by_user_id='user_789',
            allowed_domains=['test.edu'],
            custom_message='Test message'
        )
        assert save_result is True

        # 3. Verify configured
        assert is_guild_configured(guild_id) is True

        # 4. Retrieve individual values
        assert get_guild_role_id(guild_id) == 'role_123'
        assert get_guild_allowed_domains(guild_id) == ['test.edu']
        assert get_guild_custom_message(guild_id) == 'Test message'

        # 5. Get full config
        config = get_guild_config(guild_id)
        assert config is not None
        assert config['channel_id'] == 'channel_456'

    @freeze_time("2025-01-15 10:30:00")
    def test_update_then_delete_workflow(self, mock_dynamodb_table):
        """Test saving, updating, then deleting config."""
        guild_id = '123456789012345678'

        # Save initial config
        save_guild_config(
            guild_id=guild_id,
            role_id='role_v1',
            channel_id='channel_v1',
            setup_by_user_id='user_123'
        )

        # Update config
        with freeze_time("2025-01-16 14:00:00"):
            save_guild_config(
                guild_id=guild_id,
                role_id='role_v2',
                channel_id='channel_v2',
                setup_by_user_id='user_456'
            )

        # Verify update
        config = get_guild_config(guild_id)
        assert config['role_id'] == 'role_v2'
        assert config['last_updated'] == '2025-01-16T14:00:00'

        # Delete
        assert delete_guild_config(guild_id) is True
        assert is_guild_configured(guild_id) is False

    def test_multiple_guilds_independent(self, mock_dynamodb_table):
        """Test that multiple guild configs are independent."""
        # Save configs for two guilds
        save_guild_config(
            guild_id='guild_1',
            role_id='role_1',
            channel_id='channel_1',
            setup_by_user_id='user_1'
        )

        save_guild_config(
            guild_id='guild_2',
            role_id='role_2',
            channel_id='channel_2',
            setup_by_user_id='user_2',
            allowed_domains=['custom.edu']
        )

        # Verify independence
        assert get_guild_role_id('guild_1') == 'role_1'
        assert get_guild_role_id('guild_2') == 'role_2'

        # guild_1 should have default domains
        assert get_guild_allowed_domains('guild_1') == ['auburn.edu', 'student.sans.edu']
        # guild_2 should have custom domains
        assert get_guild_allowed_domains('guild_2') == ['custom.edu']
