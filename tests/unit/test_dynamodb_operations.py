"""
Unit tests for dynamodb_operations module.

Tests DynamoDB operations for verification state management including:
- Dual-table operations (sessions + records)
- Verification session lifecycle
- GSI queries for verification status
- TTL and expiry handling
- Rate limiting
- Pending setup/capture state management
"""
import pytest
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from decimal import Decimal
from moto import mock_aws
import boto3
from freezegun import freeze_time
import uuid

# Add lambda directory to path
lambda_dir = Path(__file__).parent.parent.parent / 'lambda'
sys.path.insert(0, str(lambda_dir))


# ==============================================================================
# Test Fixtures
# ==============================================================================

@pytest.fixture
def mock_dynamodb_tables():
    """Mock both DynamoDB tables (sessions and records) with proper schema."""
    with mock_aws():
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

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

        # Create records table with GSI
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

        # Patch the module-level tables
        with patch('dynamodb_operations.sessions_table', sessions_table), \
             patch('dynamodb_operations.records_table', records_table):
            yield {'sessions': sessions_table, 'records': records_table}


@pytest.fixture
def fixed_uuid():
    """Fixed UUID for deterministic testing."""
    test_uuid = 'test-uuid-1234-5678-90ab-cdef12345678'
    with patch('uuid.uuid4', return_value=MagicMock(hex=test_uuid, __str__=lambda self: test_uuid)):
        yield test_uuid


# Import after setting up mocks
from dynamodb_operations import (
    create_verification_session,
    get_verification_session,
    is_user_verified,
    increment_attempts,
    get_record_created_at,
    mark_verified,
    delete_session,
    store_pending_setup,
    get_pending_setup,
    delete_pending_setup,
    store_pending_message_capture,
    get_pending_message_capture,
    delete_pending_message_capture,
    check_rate_limit
)


# ==============================================================================
# create_verification_session() Tests
# ==============================================================================

@pytest.mark.unit
class TestCreateVerificationSession:
    """Tests for create_verification_session() function."""

    @freeze_time("2025-01-15 10:30:00")
    def test_create_session_returns_verification_id(self, mock_dynamodb_tables, fixed_uuid):
        """Test that creating a session returns a verification ID."""
        result = create_verification_session(
            user_id='user123',
            guild_id='guild456',
            email='test@auburn.edu',
            code='123456'
        )

        assert result == fixed_uuid

    @freeze_time("2025-01-15 10:30:00")
    def test_create_session_writes_to_sessions_table(self, mock_dynamodb_tables, fixed_uuid):
        """Test that session data is written to sessions table."""
        create_verification_session(
            user_id='user123',
            guild_id='guild456',
            email='test@auburn.edu',
            code='123456'
        )

        # Retrieve from sessions table
        session = mock_dynamodb_tables['sessions'].get_item(
            Key={'user_id': 'user123', 'guild_id': 'guild456'}
        )

        assert 'Item' in session
        assert session['Item']['email'] == 'test@auburn.edu'
        assert session['Item']['code'] == '123456'
        assert session['Item']['state'] == 'awaiting_code'
        assert session['Item']['attempts'] == 0

    @freeze_time("2025-01-15 10:30:00")
    def test_create_session_writes_to_records_table(self, mock_dynamodb_tables, fixed_uuid):
        """Test that session data is written to records table."""
        create_verification_session(
            user_id='user123',
            guild_id='guild456',
            email='test@auburn.edu',
            code='123456'
        )

        # Query records table by verification_id
        response = mock_dynamodb_tables['records'].query(
            KeyConditionExpression='verification_id = :vid',
            ExpressionAttributeValues={':vid': fixed_uuid}
        )

        assert len(response['Items']) == 1
        record = response['Items'][0]
        assert record['user_id'] == 'user123'
        assert record['guild_id'] == 'guild456'
        assert record['email'] == 'test@auburn.edu'
        assert record['status'] == 'pending'

    @freeze_time("2025-01-15 10:30:00")
    def test_create_session_sets_expiry_time(self, mock_dynamodb_tables, fixed_uuid):
        """Test that expiry is set correctly (default 15 minutes)."""
        create_verification_session(
            user_id='user123',
            guild_id='guild456',
            email='test@auburn.edu',
            code='123456'
        )

        session = mock_dynamodb_tables['sessions'].get_item(
            Key={'user_id': 'user123', 'guild_id': 'guild456'}
        )

        # Expiry should be 15 minutes from now
        expected_expiry = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
        assert session['Item']['expires_at'] == expected_expiry

    @freeze_time("2025-01-15 10:30:00")
    def test_create_session_custom_expiry_minutes(self, mock_dynamodb_tables, fixed_uuid):
        """Test creating session with custom expiry time."""
        create_verification_session(
            user_id='user123',
            guild_id='guild456',
            email='test@auburn.edu',
            code='123456',
            expiry_minutes=30
        )

        session = mock_dynamodb_tables['sessions'].get_item(
            Key={'user_id': 'user123', 'guild_id': 'guild456'}
        )

        expected_expiry = (datetime.utcnow() + timedelta(minutes=30)).isoformat()
        assert session['Item']['expires_at'] == expected_expiry

    @freeze_time("2025-01-15 10:30:00")
    def test_create_session_sets_ttl(self, mock_dynamodb_tables, fixed_uuid):
        """Test that TTL is set for auto-deletion (24 hours)."""
        create_verification_session(
            user_id='user123',
            guild_id='guild456',
            email='test@auburn.edu',
            code='123456'
        )

        session = mock_dynamodb_tables['sessions'].get_item(
            Key={'user_id': 'user123', 'guild_id': 'guild456'}
        )

        expected_ttl = int((datetime.utcnow() + timedelta(hours=24)).timestamp())
        assert session['Item']['ttl'] == expected_ttl

    @freeze_time("2025-01-15 10:30:00")
    def test_create_session_sets_user_guild_composite(self, mock_dynamodb_tables, fixed_uuid):
        """Test that user_guild_composite key is set for GSI queries."""
        create_verification_session(
            user_id='user123',
            guild_id='guild456',
            email='test@auburn.edu',
            code='123456'
        )

        response = mock_dynamodb_tables['records'].query(
            KeyConditionExpression='verification_id = :vid',
            ExpressionAttributeValues={':vid': fixed_uuid}
        )

        record = response['Items'][0]
        assert record['user_guild_composite'] == 'user123#guild456'

    @freeze_time("2025-01-15 10:30:00")
    def test_create_session_uses_decimal_for_timestamps(self, mock_dynamodb_tables, fixed_uuid):
        """Test that record timestamps use Decimal type for DynamoDB."""
        create_verification_session(
            user_id='user123',
            guild_id='guild456',
            email='test@auburn.edu',
            code='123456'
        )

        response = mock_dynamodb_tables['records'].query(
            KeyConditionExpression='verification_id = :vid',
            ExpressionAttributeValues={':vid': fixed_uuid}
        )

        record = response['Items'][0]
        assert isinstance(record['created_at'], Decimal)
        assert isinstance(record['expires_at'], Decimal)


# ==============================================================================
# get_verification_session() Tests
# ==============================================================================

@pytest.mark.unit
class TestGetVerificationSession:
    """Tests for get_verification_session() function."""

    def test_get_existing_session_returns_data(self, mock_dynamodb_tables):
        """Test retrieving an existing verification session."""
        # Create session manually
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'guild456',
            'email': 'test@auburn.edu',
            'code': '123456',
            'state': 'awaiting_code'
        })

        result = get_verification_session('user123', 'guild456')

        assert result is not None
        assert result['email'] == 'test@auburn.edu'
        assert result['code'] == '123456'

    def test_get_nonexistent_session_returns_none(self, mock_dynamodb_tables):
        """Test that non-existent session returns None."""
        result = get_verification_session('nonexistent', 'guild456')

        assert result is None

    def test_get_session_error_handling(self, mock_dynamodb_tables):
        """Test error handling when DynamoDB operation fails."""
        with patch.object(mock_dynamodb_tables['sessions'], 'get_item', side_effect=Exception("DynamoDB error")):
            result = get_verification_session('user123', 'guild456')

            assert result is None


# ==============================================================================
# is_user_verified() Tests
# ==============================================================================

@pytest.mark.unit
class TestIsUserVerified:
    """Tests for is_user_verified() function."""

    @freeze_time("2025-01-15 10:30:00")
    def test_verified_user_returns_true(self, mock_dynamodb_tables):
        """Test that verified user returns True."""
        # Create verified record
        mock_dynamodb_tables['records'].put_item(Item={
            'verification_id': 'vid123',
            'created_at': Decimal(str(datetime.utcnow().timestamp())),
            'user_id': 'user123',
            'guild_id': 'guild456',
            'user_guild_composite': 'user123#guild456',
            'status': 'verified'
        })

        result = is_user_verified('user123', 'guild456')

        assert result is True

    def test_unverified_user_returns_false(self, mock_dynamodb_tables):
        """Test that user without verified status returns False."""
        result = is_user_verified('user123', 'guild456')

        assert result is False

    @freeze_time("2025-01-15 10:30:00")
    def test_pending_user_returns_false(self, mock_dynamodb_tables):
        """Test that user with pending status returns False."""
        # Create pending record
        mock_dynamodb_tables['records'].put_item(Item={
            'verification_id': 'vid123',
            'created_at': Decimal(str(datetime.utcnow().timestamp())),
            'user_id': 'user123',
            'guild_id': 'guild456',
            'user_guild_composite': 'user123#guild456',
            'status': 'pending'
        })

        result = is_user_verified('user123', 'guild456')

        assert result is False

    def test_is_verified_uses_gsi_query(self, mock_dynamodb_tables):
        """Test that is_user_verified uses the user_guild-index GSI."""
        # This test verifies the GSI query structure
        with patch.object(mock_dynamodb_tables['records'], 'query', return_value={'Items': []}) as mock_query:
            is_user_verified('user123', 'guild456')

            # Verify GSI was used
            mock_query.assert_called_once()
            call_kwargs = mock_query.call_args[1]
            assert call_kwargs['IndexName'] == 'user_guild-index'

    def test_is_verified_error_handling(self, mock_dynamodb_tables):
        """Test error handling when query fails."""
        with patch.object(mock_dynamodb_tables['records'], 'query', side_effect=Exception("DynamoDB error")):
            result = is_user_verified('user123', 'guild456')

            assert result is False


# ==============================================================================
# increment_attempts() Tests
# ==============================================================================

@pytest.mark.unit
class TestIncrementAttempts:
    """Tests for increment_attempts() function."""

    @freeze_time("2025-01-15 10:30:00")
    def test_increment_attempts_updates_both_tables(self, mock_dynamodb_tables, fixed_uuid):
        """Test that increment updates both sessions and records tables."""
        # Create initial session and record
        timestamp = Decimal(str(datetime.utcnow().timestamp()))
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'guild456',
            'attempts': 0
        })
        mock_dynamodb_tables['records'].put_item(Item={
            'verification_id': fixed_uuid,
            'created_at': timestamp,
            'attempts': 0
        })

        result = increment_attempts(fixed_uuid, 'user123', 'guild456')

        assert result == 1

        # Verify session updated
        session = mock_dynamodb_tables['sessions'].get_item(
            Key={'user_id': 'user123', 'guild_id': 'guild456'}
        )
        assert session['Item']['attempts'] == 1

        # Verify record updated
        record = mock_dynamodb_tables['records'].get_item(
            Key={'verification_id': fixed_uuid, 'created_at': timestamp}
        )
        assert record['Item']['attempts'] == 1

    @freeze_time("2025-01-15 10:30:00")
    def test_increment_attempts_multiple_times(self, mock_dynamodb_tables, fixed_uuid):
        """Test incrementing attempts multiple times."""
        timestamp = Decimal(str(datetime.utcnow().timestamp()))
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'guild456',
            'attempts': 0
        })
        mock_dynamodb_tables['records'].put_item(Item={
            'verification_id': fixed_uuid,
            'created_at': timestamp,
            'attempts': 0
        })

        # Increment 3 times
        increment_attempts(fixed_uuid, 'user123', 'guild456')
        increment_attempts(fixed_uuid, 'user123', 'guild456')
        result = increment_attempts(fixed_uuid, 'user123', 'guild456')

        assert result == 3

    def test_increment_attempts_error_handling(self, mock_dynamodb_tables):
        """Test error handling when increment fails."""
        with patch.object(mock_dynamodb_tables['sessions'], 'update_item', side_effect=Exception("DynamoDB error")):
            result = increment_attempts('vid123', 'user123', 'guild456')

            assert result == 0


# ==============================================================================
# get_record_created_at() Tests
# ==============================================================================

@pytest.mark.unit
class TestGetRecordCreatedAt:
    """Tests for get_record_created_at() helper function."""

    @freeze_time("2025-01-15 10:30:00")
    def test_get_created_at_for_existing_record(self, mock_dynamodb_tables):
        """Test retrieving created_at timestamp from existing record."""
        timestamp = Decimal(str(datetime.utcnow().timestamp()))
        mock_dynamodb_tables['records'].put_item(Item={
            'verification_id': 'vid123',
            'created_at': timestamp,
            'user_id': 'user123'
        })

        result = get_record_created_at('vid123')

        assert result == timestamp

    def test_get_created_at_nonexistent_record_returns_zero(self, mock_dynamodb_tables):
        """Test that non-existent record returns Decimal('0')."""
        result = get_record_created_at('nonexistent')

        assert result == Decimal('0')

    def test_get_created_at_error_handling(self, mock_dynamodb_tables):
        """Test error handling when query fails."""
        with patch.object(mock_dynamodb_tables['records'], 'query', side_effect=Exception("DynamoDB error")):
            result = get_record_created_at('vid123')

            assert result == Decimal('0')


# ==============================================================================
# mark_verified() Tests
# ==============================================================================

@pytest.mark.unit
class TestMarkVerified:
    """Tests for mark_verified() function."""

    @freeze_time("2025-01-15 10:30:00")
    def test_mark_verified_updates_record_status(self, mock_dynamodb_tables):
        """Test that marking verified updates record status."""
        timestamp = Decimal(str(datetime.utcnow().timestamp()))
        mock_dynamodb_tables['records'].put_item(Item={
            'verification_id': 'vid123',
            'created_at': timestamp,
            'status': 'pending'
        })

        mark_verified('vid123', 'user123', 'guild456')

        # Verify record updated
        record = mock_dynamodb_tables['records'].get_item(
            Key={'verification_id': 'vid123', 'created_at': timestamp}
        )
        assert record['Item']['status'] == 'verified'
        assert 'verified_at' in record['Item']

    @freeze_time("2025-01-15 10:30:00")
    def test_mark_verified_sets_verified_timestamp(self, mock_dynamodb_tables):
        """Test that verified_at timestamp is set."""
        timestamp = Decimal(str(datetime.utcnow().timestamp()))
        mock_dynamodb_tables['records'].put_item(Item={
            'verification_id': 'vid123',
            'created_at': timestamp,
            'status': 'pending'
        })

        mark_verified('vid123', 'user123', 'guild456')

        record = mock_dynamodb_tables['records'].get_item(
            Key={'verification_id': 'vid123', 'created_at': timestamp}
        )
        verified_at = record['Item']['verified_at']
        assert isinstance(verified_at, Decimal)

    @freeze_time("2025-01-15 10:30:00")
    def test_mark_verified_deletes_session(self, mock_dynamodb_tables):
        """Test that marking verified deletes the session."""
        timestamp = Decimal(str(datetime.utcnow().timestamp()))
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'guild456',
            'state': 'awaiting_code'
        })
        mock_dynamodb_tables['records'].put_item(Item={
            'verification_id': 'vid123',
            'created_at': timestamp,
            'status': 'pending'
        })

        mark_verified('vid123', 'user123', 'guild456')

        # Verify session deleted
        response = mock_dynamodb_tables['sessions'].get_item(
            Key={'user_id': 'user123', 'guild_id': 'guild456'}
        )
        assert 'Item' not in response


# ==============================================================================
# delete_session() Tests
# ==============================================================================

@pytest.mark.unit
class TestDeleteSession:
    """Tests for delete_session() function."""

    def test_delete_existing_session(self, mock_dynamodb_tables):
        """Test deleting an existing session."""
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'guild456',
            'state': 'awaiting_code'
        })

        delete_session('user123', 'guild456')

        # Verify deletion
        response = mock_dynamodb_tables['sessions'].get_item(
            Key={'user_id': 'user123', 'guild_id': 'guild456'}
        )
        assert 'Item' not in response

    def test_delete_nonexistent_session(self, mock_dynamodb_tables):
        """Test that deleting non-existent session doesn't error (idempotent)."""
        # Should not raise exception
        delete_session('nonexistent', 'guild456')


# ==============================================================================
# Pending Setup Tests
# ==============================================================================

@pytest.mark.unit
class TestPendingSetup:
    """Tests for pending setup state management."""

    @freeze_time("2025-01-15 10:30:00")
    def test_store_pending_setup(self, mock_dynamodb_tables):
        """Test storing pending setup configuration."""
        store_pending_setup(
            setup_id='user123_guild456',
            role_id='role123',
            channel_id='channel456',
            allowed_domains=['test.edu'],
            custom_message='Test message'
        )

        # Verify storage
        response = mock_dynamodb_tables['sessions'].get_item(
            Key={'user_id': 'user123_guild456', 'guild_id': 'PENDING_SETUP'}
        )

        assert 'Item' in response
        assert response['Item']['role_id'] == 'role123'
        assert response['Item']['channel_id'] == 'channel456'

    @freeze_time("2025-01-15 10:30:00")
    def test_store_pending_setup_sets_ttl(self, mock_dynamodb_tables):
        """Test that pending setup has 5-minute TTL."""
        store_pending_setup(
            setup_id='user123_guild456',
            role_id='role123',
            channel_id='channel456',
            allowed_domains=['test.edu'],
            custom_message='Test message'
        )

        response = mock_dynamodb_tables['sessions'].get_item(
            Key={'user_id': 'user123_guild456', 'guild_id': 'PENDING_SETUP'}
        )

        expected_ttl = int((datetime.utcnow() + timedelta(minutes=5)).timestamp())
        assert response['Item']['ttl'] == expected_ttl

    def test_get_pending_setup(self, mock_dynamodb_tables):
        """Test retrieving pending setup configuration."""
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123_guild456',
            'guild_id': 'PENDING_SETUP',
            'role_id': 'role123',
            'channel_id': 'channel456',
            'allowed_domains': ['test.edu'],
            'custom_message': 'Test'
        })

        result = get_pending_setup('user123_guild456')

        assert result['role_id'] == 'role123'
        assert result['channel_id'] == 'channel456'

    def test_get_pending_setup_not_found(self, mock_dynamodb_tables):
        """Test retrieving non-existent pending setup returns None."""
        result = get_pending_setup('nonexistent')

        assert result is None

    def test_delete_pending_setup(self, mock_dynamodb_tables):
        """Test deleting pending setup."""
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123_guild456',
            'guild_id': 'PENDING_SETUP',
            'role_id': 'role123'
        })

        delete_pending_setup('user123_guild456')

        # Verify deletion
        response = mock_dynamodb_tables['sessions'].get_item(
            Key={'user_id': 'user123_guild456', 'guild_id': 'PENDING_SETUP'}
        )
        assert 'Item' not in response


# ==============================================================================
# Pending Message Capture Tests
# ==============================================================================

@pytest.mark.unit
class TestPendingMessageCapture:
    """Tests for pending message capture state management."""

    @freeze_time("2025-01-15 10:30:00")
    def test_store_pending_message_capture(self, mock_dynamodb_tables):
        """Test storing pending message capture state."""
        store_pending_message_capture(
            capture_id='user123_guild456',
            role_id='role123',
            channel_id='channel456',
            allowed_domains=['test.edu'],
            listening_channel='listen_channel_789'
        )

        response = mock_dynamodb_tables['sessions'].get_item(
            Key={'user_id': 'user123_guild456', 'guild_id': 'PENDING_MESSAGE_CAPTURE'}
        )

        assert 'Item' in response
        assert response['Item']['listening_channel'] == 'listen_channel_789'

    def test_get_pending_message_capture(self, mock_dynamodb_tables):
        """Test retrieving pending message capture state."""
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123_guild456',
            'guild_id': 'PENDING_MESSAGE_CAPTURE',
            'listening_channel': 'listen789'
        })

        result = get_pending_message_capture('user123_guild456')

        assert result['listening_channel'] == 'listen789'

    def test_delete_pending_message_capture(self, mock_dynamodb_tables):
        """Test deleting pending message capture."""
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123_guild456',
            'guild_id': 'PENDING_MESSAGE_CAPTURE',
            'role_id': 'role123'
        })

        delete_pending_message_capture('user123_guild456')

        response = mock_dynamodb_tables['sessions'].get_item(
            Key={'user_id': 'user123_guild456', 'guild_id': 'PENDING_MESSAGE_CAPTURE'}
        )
        assert 'Item' not in response


# ==============================================================================
# Rate Limiting Tests
# ==============================================================================

@pytest.mark.unit
class TestRateLimiting:
    """Tests for check_rate_limit() function."""

    @freeze_time("2025-01-15 10:30:00")
    def test_first_request_allowed(self, mock_dynamodb_tables):
        """Test that first request is allowed."""
        # First request should be allowed
        is_allowed, seconds_remaining = check_rate_limit('user123', 'guild456')

        assert is_allowed is True
        assert seconds_remaining == 0

    @freeze_time("2025-01-15 10:30:00")
    def test_rapid_requests_blocked_per_guild(self, mock_dynamodb_tables, fixed_uuid):
        """Test that rapid requests to same guild are blocked."""
        # Create a session to simulate existing verification
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'guild456',
            'created_at': datetime.utcnow().isoformat(),
            'state': 'awaiting_code'
        })

        # Immediate retry should be blocked (60s cooldown)
        is_allowed, seconds_remaining = check_rate_limit('user123', 'guild456', cooldown_seconds=60)

        assert is_allowed is False
        assert seconds_remaining > 0

    @freeze_time("2025-01-15 10:30:00")
    def test_cooldown_period_respected(self, mock_dynamodb_tables):
        """Test that cooldown period is respected."""
        # Create session 30 seconds ago
        past_time = datetime.utcnow() - timedelta(seconds=30)
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'guild456',
            'created_at': past_time.isoformat(),
            'state': 'awaiting_code'
        })

        # 30 seconds into 60 second cooldown - should be blocked
        is_allowed, seconds_remaining = check_rate_limit('user123', 'guild456', cooldown_seconds=60)

        assert is_allowed is False
        assert 25 < seconds_remaining < 35  # Around 30 seconds remaining

    @freeze_time("2025-01-15 10:30:00")
    def test_after_cooldown_allowed(self, mock_dynamodb_tables):
        """Test that requests after cooldown are allowed."""
        # Create session 70 seconds ago (past 60s cooldown)
        past_time = datetime.utcnow() - timedelta(seconds=70)
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'guild456',
            'created_at': past_time.isoformat(),
            'state': 'awaiting_code'
        })

        # Past cooldown - should be allowed
        is_allowed, seconds_remaining = check_rate_limit('user123', 'guild456', cooldown_seconds=60)

        assert is_allowed is True
        assert seconds_remaining == 0

    @freeze_time("2025-01-15 10:30:00")
    def test_global_rate_limit_blocks_across_guilds(self, mock_dynamodb_tables):
        """Test that global rate limit blocks requests across different guilds."""
        # Create global rate limit marker
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'GLOBAL_RATE_LIMIT',
            'created_at': datetime.utcnow().isoformat(),
            'ttl': int((datetime.utcnow() + timedelta(seconds=300)).timestamp())
        })

        # Try different guild - should still be blocked
        is_allowed, seconds_remaining = check_rate_limit('user123', 'different_guild', global_cooldown=300)

        assert is_allowed is False
        assert seconds_remaining > 0

    def test_rate_limit_error_handling(self, mock_dynamodb_tables):
        """Test that errors during rate limit check fail closed (deny)."""
        # Patch get_verification_session to raise exception
        with patch('dynamodb_operations.get_verification_session', side_effect=Exception("DynamoDB error")):
            is_allowed, seconds_remaining = check_rate_limit('user123', 'guild456')

            # Should deny on error (fail-safe)
            assert is_allowed is False
            assert seconds_remaining == 60  # Conservative cooldown on error


# ==============================================================================
# Integration Tests
# ==============================================================================

@pytest.mark.unit
class TestVerificationWorkflow:
    """Integration tests for complete verification workflows."""

    @freeze_time("2025-01-15 10:30:00")
    def test_complete_verification_flow(self, mock_dynamodb_tables, fixed_uuid):
        """Test complete verification lifecycle."""
        # 1. Create session
        vid = create_verification_session(
            user_id='user123',
            guild_id='guild456',
            email='test@auburn.edu',
            code='123456'
        )

        # 2. Get session
        session = get_verification_session('user123', 'guild456')
        assert session is not None
        assert session['code'] == '123456'

        # 3. User not verified yet
        assert is_user_verified('user123', 'guild456') is False

        # 4. Increment attempt (wrong code)
        attempts = increment_attempts(vid, 'user123', 'guild456')
        assert attempts == 1

        # 5. Mark verified (correct code)
        mark_verified(vid, 'user123', 'guild456')

        # 6. Verify user is now verified
        assert is_user_verified('user123', 'guild456') is True

        # 7. Session should be deleted
        session = get_verification_session('user123', 'guild456')
        assert session is None

    @freeze_time("2025-01-15 10:30:00")
    def test_multiple_users_independent(self, mock_dynamodb_tables, fixed_uuid):
        """Test that multiple users can verify independently."""
        # Create sessions for two users
        with patch('uuid.uuid4', return_value=MagicMock(hex='uuid1', __str__=lambda self: 'uuid1')):
            vid1 = create_verification_session(
                user_id='user1',
                guild_id='guild456',
                email='user1@auburn.edu',
                code='111111'
            )

        with patch('uuid.uuid4', return_value=MagicMock(hex='uuid2', __str__=lambda self: 'uuid2')):
            vid2 = create_verification_session(
                user_id='user2',
                guild_id='guild456',
                email='user2@auburn.edu',
                code='222222'
            )

        # Verify user1
        mark_verified(vid1, 'user1', 'guild456')

        # user1 should be verified, user2 should not
        assert is_user_verified('user1', 'guild456') is True
        assert is_user_verified('user2', 'guild456') is False

        # user2 session should still exist
        session2 = get_verification_session('user2', 'guild456')
        assert session2 is not None
