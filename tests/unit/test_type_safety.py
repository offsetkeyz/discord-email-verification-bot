"""
Type safety tests for function parameter validation.

Tests wrong data types, None values, and malformed inputs
to address QA concerns from PR #11.

Note: These tests document actual behavior rather than ideal behavior.
Some functions are permissive and don't validate input types strictly.
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timedelta
from decimal import Decimal
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
        
        with patch('guild_config.configs_table', table):
            yield table


@pytest.fixture
def mock_dynamodb_tables():
    """Mock both DynamoDB tables."""
    with mock_aws():
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        
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
        
        with patch('dynamodb_operations.sessions_table', sessions_table), \
             patch('dynamodb_operations.records_table', records_table):
            yield {'sessions': sessions_table, 'records': records_table}


from guild_config import save_guild_config, get_guild_config
from dynamodb_operations import (
    create_verification_session,
    get_verification_session,
    check_rate_limit
)
from verification_logic import validate_edu_email, is_valid_code_format


# ==============================================================================
# guild_config Type Safety Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.security
class TestGuildConfigTypeSafety:
    """Tests for type safety in guild_config functions."""
    
    def test_save_config_none_custom_message_uses_default(self, mock_dynamodb_table):
        """Test that None custom_message uses default."""
        result = save_guild_config(
            guild_id='guild123',
            role_id='role123',
            channel_id='channel123',
            setup_by_user_id='user123',
            custom_message=None
        )
        
        assert result is True
        # Should use default message
        from guild_config import get_guild_custom_message
        message = get_guild_custom_message('guild123')
        assert message == "Click the button below to verify your email address."
    
    def test_save_config_empty_string_custom_message_preserved(self, mock_dynamodb_table):
        """Test saving config with empty string custom_message."""
        result = save_guild_config(
            guild_id='guild123',
            role_id='role123',
            channel_id='channel123',
            setup_by_user_id='user123',
            custom_message=''
        )
        
        assert result is True
        # Empty string should be preserved
        from guild_config import get_guild_custom_message
        message = get_guild_custom_message('guild123')
        assert message == ''
    
    def test_save_config_none_allowed_domains_uses_default(self, mock_dynamodb_table):
        """Test that None allowed_domains uses default."""
        result = save_guild_config(
            guild_id='guild123',
            role_id='role123',
            channel_id='channel123',
            setup_by_user_id='user123',
            allowed_domains=None
        )
        
        assert result is True
        from guild_config import get_guild_allowed_domains
        domains = get_guild_allowed_domains('guild123')
        assert domains == ['auburn.edu', 'student.sans.edu']


# ==============================================================================
# dynamodb_operations Type Safety Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.security
class TestDynamoDBOperationsTypeSafety:
    """Tests for type safety in dynamodb_operations functions."""
    
    @freeze_time("2025-01-15 10:30:00")
    def test_create_session_negative_expiry(self, mock_dynamodb_tables):
        """Test creating session with negative expiry_minutes."""
        # Should handle gracefully (create expired session)
        result = create_verification_session(
            user_id='user123',
            guild_id='guild123',
            email='test@auburn.edu',
            code='123456',
            expiry_minutes=-10
        )
        
        # Should succeed but session will be immediately expired
        assert isinstance(result, str)
    
    @freeze_time("2025-01-15 10:30:00")
    def test_create_session_zero_expiry(self, mock_dynamodb_tables):
        """Test creating session with zero expiry_minutes."""
        result = create_verification_session(
            user_id='user123',
            guild_id='guild123',
            email='test@auburn.edu',
            code='123456',
            expiry_minutes=0
        )
        
        # Should succeed
        assert isinstance(result, str)
    
    @freeze_time("2025-01-15 10:30:00")
    def test_create_session_very_large_expiry(self, mock_dynamodb_tables):
        """Test creating session with very large expiry_minutes."""
        result = create_verification_session(
            user_id='user123',
            guild_id='guild123',
            email='test@auburn.edu',
            code='123456',
            expiry_minutes=10000  # ~7 days
        )
        
        # Should succeed
        assert isinstance(result, str)


# ==============================================================================
# Malformed Timestamp Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.security
class TestMalformedTimestamps:
    """Tests for malformed timestamp handling."""
    
    @freeze_time("2025-01-15 10:30:00")
    def test_invalid_iso_format_timestamp(self, mock_dynamodb_tables):
        """Test rate limit check with invalid ISO format timestamp."""
        # Create session with malformed timestamp
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'guild456',
            'created_at': 'not-a-valid-timestamp',
            'state': 'awaiting_code'
        })
        
        # Should handle gracefully
        is_allowed, seconds_remaining = check_rate_limit('user123', 'guild456')
        
        # Error should cause fail-closed behavior
        assert is_allowed is False
    
    @freeze_time("2025-01-15 10:30:00")
    def test_numeric_timestamp_instead_of_iso(self, mock_dynamodb_tables):
        """Test rate limit check with numeric timestamp instead of ISO string."""
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'guild456',
            'created_at': 1234567890,  # Unix timestamp instead of ISO string
            'state': 'awaiting_code'
        })
        
        is_allowed, seconds_remaining = check_rate_limit('user123', 'guild456')
        
        # Should handle gracefully (likely fail closed)
        assert is_allowed is False
    
    @freeze_time("2025-01-15 10:30:00")
    def test_future_date_timestamp(self, mock_dynamodb_tables):
        """Test rate limit check with far future timestamp."""
        future_date = "2099-12-31T23:59:59"
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'guild456',
            'created_at': future_date,
            'state': 'awaiting_code'
        })
        
        is_allowed, seconds_remaining = check_rate_limit('user123', 'guild456')
        
        # Future timestamp means negative elapsed time
        # Should be blocked (treated as recent)
        assert is_allowed is False
    
    @freeze_time("2025-01-15 10:30:00")
    def test_ancient_date_timestamp(self, mock_dynamodb_tables):
        """Test rate limit check with very old timestamp."""
        ancient_date = "1970-01-01T00:00:00"
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'guild456',
            'created_at': ancient_date,
            'state': 'awaiting_code'
        })
        
        is_allowed, seconds_remaining = check_rate_limit('user123', 'guild456')
        
        # Very old timestamp should be allowed (cooldown long expired)
        assert is_allowed is True
        assert seconds_remaining == 0
    
    @freeze_time("2025-01-15 10:30:00")
    def test_timestamp_with_timezone_info(self, mock_dynamodb_tables):
        """Test timestamp with timezone information."""
        # ISO format with timezone
        past_time = datetime.utcnow() - timedelta(seconds=30)
        tz_timestamp = past_time.isoformat() + "+00:00"
        
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'guild456',
            'created_at': tz_timestamp,
            'state': 'awaiting_code'
        })
        
        is_allowed, seconds_remaining = check_rate_limit('user123', 'guild456')
        
        # Should handle timezone-aware timestamps
        assert isinstance(is_allowed, bool)


# ==============================================================================
# verification_logic Type Safety Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.security
class TestVerificationLogicTypeSafety:
    """Tests for type safety in verification_logic functions."""
    
    def test_validate_email_none_input_raises_error(self):
        """Test email validation with None input."""
        with pytest.raises(TypeError):
            validate_edu_email(None)
    
    def test_validate_email_none_allowed_domains_uses_default(self):
        """Test that None allowed_domains uses defaults."""
        result = validate_edu_email('student@auburn.edu', allowed_domains=None)
        assert result is True
    
    def test_validate_email_empty_list_allowed_domains(self):
        """Test with empty allowed_domains list."""
        result = validate_edu_email('student@auburn.edu', allowed_domains=[])
        assert result is False
    
    def test_is_valid_code_none_input_raises_error(self):
        """Test code format validation with None input."""
        with pytest.raises(AttributeError):
            is_valid_code_format(None)
    
    def test_is_valid_code_integer_input_raises_error(self):
        """Test code format validation with integer input."""
        with pytest.raises(AttributeError):
            is_valid_code_format(123456)
    
    def test_is_valid_code_empty_string(self):
        """Test code format validation with empty string."""
        result = is_valid_code_format('')
        assert result is False
    
    def test_is_valid_code_whitespace_string(self):
        """Test code format validation with whitespace."""
        result = is_valid_code_format('      ')
        assert result is False


# ==============================================================================
# Edge Cases for Rate Limiting with Malformed Data
# ==============================================================================

@pytest.mark.unit
@pytest.mark.security
class TestRateLimitMalformedData:
    """Tests for rate limiting with malformed or missing data."""
    
    @freeze_time("2025-01-15 10:30:00")
    def test_zero_cooldown_always_allowed(self, mock_dynamodb_tables):
        """Test that zero cooldown always allows requests."""
        # Create session just now
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'guild456',
            'created_at': datetime.utcnow().isoformat(),
            'state': 'awaiting_code'
        })
        
        is_allowed, seconds_remaining = check_rate_limit('user123', 'guild456', cooldown_seconds=0)
        
        # Zero cooldown means no rate limiting
        assert is_allowed is True
        assert seconds_remaining == 0
    
    @freeze_time("2025-01-15 10:30:00")
    def test_very_long_cooldown(self, mock_dynamodb_tables):
        """Test very long cooldown period (1 hour)."""
        # Create session 30 minutes ago
        past_time = datetime.utcnow() - timedelta(minutes=30)
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'guild456',
            'created_at': past_time.isoformat(),
            'state': 'awaiting_code'
        })
        
        is_allowed, seconds_remaining = check_rate_limit('user123', 'guild456', cooldown_seconds=3600)
        
        assert is_allowed is False
        # Should have ~30 minutes (1800s) remaining
        assert 1700 < seconds_remaining < 1900
    
    @freeze_time("2025-01-15 10:30:00")
    def test_negative_cooldown_treated_as_zero(self, mock_dynamodb_tables):
        """Test that negative cooldown is treated as always allowed."""
        # Create session 1 second ago
        past_time = datetime.utcnow() - timedelta(seconds=1)
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'guild456',
            'created_at': past_time.isoformat(),
            'state': 'awaiting_code'
        })
        
        is_allowed, seconds_remaining = check_rate_limit('user123', 'guild456', cooldown_seconds=-60)
        
        # Negative cooldown: elapsed (1s) > cooldown (-60s), so allowed
        assert is_allowed is True


# ==============================================================================
# Input Sanitization Documentation Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.security
class TestInputSanitizationDocumentation:
    """Tests that document lack of input sanitization (by design)."""
    
    def test_custom_message_not_sanitized_at_storage(self, mock_dynamodb_table):
        """Document that custom messages are NOT sanitized at storage time.
        
        This is intentional - sanitization should happen at render time.
        """
        malicious_message = "<script>alert('xss')</script>"
        
        result = save_guild_config(
            guild_id='guild123',
            role_id='role123',
            channel_id='channel123',
            setup_by_user_id='user123',
            custom_message=malicious_message
        )
        
        assert result is True
        # Message stored as-is (NOT sanitized)
        from guild_config import get_guild_custom_message
        retrieved = get_guild_custom_message('guild123')
        assert retrieved == malicious_message
        
    def test_domain_not_validated_at_storage(self, mock_dynamodb_table):
        """Document that domains are NOT validated at storage time."""
        invalid_domain = "not-a-real-domain!@#$%"
        
        result = save_guild_config(
            guild_id='guild123',
            role_id='role123',
            channel_id='channel123',
            setup_by_user_id='user123',
            allowed_domains=[invalid_domain]
        )
        
        assert result is True
        # Domain stored as-is (NOT validated)
        from guild_config import get_guild_allowed_domains
        domains = get_guild_allowed_domains('guild123')
        assert invalid_domain in domains


# ==============================================================================
# Boundary Value Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.security
class TestBoundaryValues:
    """Tests for boundary values in various inputs."""
    
    def test_email_max_length(self):
        """Test email at maximum typical length (320 chars)."""
        # Max email: 64 chars local + 1 @ + 255 chars domain = 320
        long_local = "a" * 64
        long_domain = "b" * 240 + ".auburn.edu"  # ~251 chars
        long_email = f"{long_local}@{long_domain}"
        
        # Will likely be rejected due to domain not matching allowed list
        result = validate_edu_email(long_email)
        assert result is False
    
    def test_code_boundary_lengths(self):
        """Test code validation at various boundary lengths."""
        assert is_valid_code_format("12345") is False  # Too short
        assert is_valid_code_format("123456") is True   # Exact
        assert is_valid_code_format("1234567") is False # Too long
    
    @freeze_time("2025-01-15 10:30:00")
    def test_session_with_maximum_expiry(self, mock_dynamodb_tables):
        """Test session with very long expiry time."""
        # Max int32 minutes would be ~4000 years
        result = create_verification_session(
            user_id='user123',
            guild_id='guild123',
            email='test@auburn.edu',
            code='123456',
            expiry_minutes=525600  # 1 year in minutes
        )
        
        assert isinstance(result, str)
