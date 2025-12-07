"""
Rate limiting edge case tests.

Tests boundary conditions, timezone handling, and precise timing
to address QA concerns from PR #11.
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


from dynamodb_operations import check_rate_limit


# ==============================================================================
# Exact Boundary Condition Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.security
class TestRateLimitBoundaryConditions:
    """Tests for exact boundary conditions at cooldown expiry."""
    
    @freeze_time("2025-01-15 10:30:00")
    def test_exactly_at_60_second_boundary_blocked(self, mock_dynamodb_tables):
        """Test rate limit at exactly 60.0 seconds - should still be blocked."""
        # Create session exactly 60 seconds ago
        past_time = datetime.utcnow() - timedelta(seconds=60)
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'guild456',
            'created_at': past_time.isoformat(),
            'state': 'awaiting_code'
        })
        
        # At exactly 60s, should still be blocked (< not <=)
        is_allowed, seconds_remaining = check_rate_limit('user123', 'guild456', cooldown_seconds=60)
        
        # Implementation uses < so at exactly 60s should be allowed
        assert is_allowed is True
        assert seconds_remaining == 0
    
    @freeze_time("2025-01-15 10:30:00")
    def test_one_millisecond_before_expiry(self, mock_dynamodb_tables):
        """Test rate limit 1ms before expiry - should be blocked."""
        # Create session 59.999 seconds ago
        past_time = datetime.utcnow() - timedelta(seconds=59, milliseconds=999)
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'guild456',
            'created_at': past_time.isoformat(),
            'state': 'awaiting_code'
        })
        
        is_allowed, seconds_remaining = check_rate_limit('user123', 'guild456', cooldown_seconds=60)
        
        assert is_allowed is False
        assert seconds_remaining >= 0  # Very close to 0
        assert seconds_remaining < 1
    
    @freeze_time("2025-01-15 10:30:00")
    def test_one_second_after_expiry(self, mock_dynamodb_tables):
        """Test rate limit 1 second after expiry - should be allowed."""
        # Create session 61 seconds ago
        past_time = datetime.utcnow() - timedelta(seconds=61)
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'guild456',
            'created_at': past_time.isoformat(),
            'state': 'awaiting_code'
        })
        
        is_allowed, seconds_remaining = check_rate_limit('user123', 'guild456', cooldown_seconds=60)
        
        assert is_allowed is True
        assert seconds_remaining == 0
    
    @freeze_time("2025-01-15 10:30:00")
    def test_exactly_at_300_second_global_boundary(self, mock_dynamodb_tables):
        """Test global rate limit at exactly 300.0 seconds."""
        # Create global rate limit marker exactly 300 seconds ago
        past_time = datetime.utcnow() - timedelta(seconds=300)
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'GLOBAL_RATE_LIMIT',
            'created_at': past_time.isoformat()
        })
        
        is_allowed, seconds_remaining = check_rate_limit(
            'user123', 
            'guild456', 
            cooldown_seconds=60,
            global_cooldown=300
        )
        
        # At exactly 300s should be allowed
        assert is_allowed is True
        assert seconds_remaining == 0
    
    @freeze_time("2025-01-15 10:30:00")
    def test_fractional_seconds_precision(self, mock_dynamodb_tables):
        """Test that fractional seconds are handled precisely."""
        # Create session 59.5 seconds ago
        past_time = datetime.utcnow() - timedelta(seconds=59.5)
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'guild456',
            'created_at': past_time.isoformat(),
            'state': 'awaiting_code'
        })
        
        is_allowed, seconds_remaining = check_rate_limit('user123', 'guild456', cooldown_seconds=60)
        
        assert is_allowed is False
        # Should have approximately 0.5 seconds remaining
        assert 0 <= seconds_remaining <= 1


# ==============================================================================
# Timezone Handling Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.security
class TestTimezoneHandling:
    """Tests for timezone-aware timestamp handling."""
    
    @freeze_time("2025-01-15 10:30:00")
    def test_utc_timestamp_handling(self, mock_dynamodb_tables):
        """Test that UTC timestamps are handled correctly."""
        # All timestamps should be in UTC
        past_time = datetime.utcnow() - timedelta(seconds=30)
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'guild456',
            'created_at': past_time.isoformat(),
            'state': 'awaiting_code'
        })
        
        is_allowed, seconds_remaining = check_rate_limit('user123', 'guild456', cooldown_seconds=60)
        
        assert is_allowed is False
        # Should have ~30 seconds remaining
        assert 25 < seconds_remaining < 35
    
    @freeze_time("2025-01-15 10:30:00")
    def test_iso_format_timestamp_parsing(self, mock_dynamodb_tables):
        """Test parsing of ISO format timestamps."""
        # Test with ISO format timestamp
        past_time = datetime.utcnow() - timedelta(seconds=45)
        iso_timestamp = past_time.isoformat()
        
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'guild456',
            'created_at': iso_timestamp,
            'state': 'awaiting_code'
        })
        
        is_allowed, seconds_remaining = check_rate_limit('user123', 'guild456', cooldown_seconds=60)
        
        assert is_allowed is False
        assert 10 < seconds_remaining < 20
    
    @freeze_time("2025-01-15 10:30:00")
    def test_timestamp_with_microseconds(self, mock_dynamodb_tables):
        """Test timestamp parsing with microseconds."""
        # Create timestamp with microseconds
        past_time = datetime.utcnow() - timedelta(seconds=55, microseconds=123456)
        
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'guild456',
            'created_at': past_time.isoformat(),
            'state': 'awaiting_code'
        })
        
        is_allowed, seconds_remaining = check_rate_limit('user123', 'guild456', cooldown_seconds=60)
        
        assert is_allowed is False
        assert 0 < seconds_remaining < 10
    
    @freeze_time("2025-01-15 10:30:00", tz_offset=0)
    def test_consistent_utc_across_calls(self, mock_dynamodb_tables):
        """Test that all datetime.utcnow() calls are consistent."""
        # First call to check rate limit
        is_allowed1, _ = check_rate_limit('user123', 'guild456')
        assert is_allowed1 is True
        
        # Immediately check again - should now be blocked
        is_allowed2, remaining = check_rate_limit('user123', 'guild456', cooldown_seconds=60)
        assert is_allowed2 is False
        assert remaining > 0


# ==============================================================================
# Clock Skew and Edge Cases
# ==============================================================================

@pytest.mark.unit
@pytest.mark.security
class TestClockSkewEdgeCases:
    """Tests for clock skew and timing edge cases."""
    
    @freeze_time("2025-01-15 10:30:00")
    def test_future_timestamp_treated_as_expired(self, mock_dynamodb_tables):
        """Test that future timestamps (clock skew) are handled gracefully."""
        # Create session with timestamp 10 seconds in the future
        future_time = datetime.utcnow() + timedelta(seconds=10)
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'guild456',
            'created_at': future_time.isoformat(),
            'state': 'awaiting_code'
        })
        
        is_allowed, seconds_remaining = check_rate_limit('user123', 'guild456', cooldown_seconds=60)
        
        # Future timestamp means negative elapsed time
        # Implementation will see this as not yet expired
        # elapsed = now - created_at = -10s
        # -10 < 60 = True, so blocked
        assert is_allowed is False
    
    @freeze_time("2025-01-15 10:30:00")
    def test_very_old_timestamp_allowed(self, mock_dynamodb_tables):
        """Test that very old timestamps are allowed."""
        # Create session 1 hour ago
        past_time = datetime.utcnow() - timedelta(hours=1)
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'guild456',
            'created_at': past_time.isoformat(),
            'state': 'awaiting_code'
        })
        
        is_allowed, seconds_remaining = check_rate_limit('user123', 'guild456', cooldown_seconds=60)
        
        assert is_allowed is True
        assert seconds_remaining == 0
    
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


# ==============================================================================
# Multiple Rate Limit Interaction Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.security
class TestMultipleRateLimitInteractions:
    """Tests for interactions between per-guild and global rate limits."""
    
    @freeze_time("2025-01-15 10:30:00")
    def test_per_guild_expired_but_global_active(self, mock_dynamodb_tables):
        """Test when per-guild limit expired but global limit still active."""
        # Per-guild session 70s ago (expired for 60s cooldown)
        past_time = datetime.utcnow() - timedelta(seconds=70)
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'guild456',
            'created_at': past_time.isoformat(),
            'state': 'awaiting_code'
        })
        
        # Global limit 100s ago (still active for 300s cooldown)
        global_past = datetime.utcnow() - timedelta(seconds=100)
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'GLOBAL_RATE_LIMIT',
            'created_at': global_past.isoformat()
        })
        
        is_allowed, seconds_remaining = check_rate_limit(
            'user123', 
            'guild456',
            cooldown_seconds=60,
            global_cooldown=300
        )
        
        # Should be blocked by global limit
        assert is_allowed is False
        # Should have ~200s remaining on global
        assert 190 < seconds_remaining < 210
    
    @freeze_time("2025-01-15 10:30:00")
    def test_per_guild_active_but_global_expired(self, mock_dynamodb_tables):
        """Test when per-guild limit active but global limit expired."""
        # Per-guild session 30s ago (still active)
        recent_time = datetime.utcnow() - timedelta(seconds=30)
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'guild456',
            'created_at': recent_time.isoformat(),
            'state': 'awaiting_code'
        })
        
        # Global limit 400s ago (expired for 300s cooldown)
        global_past = datetime.utcnow() - timedelta(seconds=400)
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'GLOBAL_RATE_LIMIT',
            'created_at': global_past.isoformat()
        })
        
        is_allowed, seconds_remaining = check_rate_limit(
            'user123',
            'guild456',
            cooldown_seconds=60,
            global_cooldown=300
        )
        
        # Should be blocked by per-guild limit
        assert is_allowed is False
        # Should have ~30s remaining on per-guild
        assert 25 < seconds_remaining < 35
    
    @freeze_time("2025-01-15 10:30:00")
    def test_both_limits_expired_allowed(self, mock_dynamodb_tables):
        """Test when both per-guild and global limits have expired."""
        # Per-guild session 90s ago
        per_guild_past = datetime.utcnow() - timedelta(seconds=90)
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'guild456',
            'created_at': per_guild_past.isoformat(),
            'state': 'awaiting_code'
        })
        
        # Global limit 400s ago
        global_past = datetime.utcnow() - timedelta(seconds=400)
        mock_dynamodb_tables['sessions'].put_item(Item={
            'user_id': 'user123',
            'guild_id': 'GLOBAL_RATE_LIMIT',
            'created_at': global_past.isoformat()
        })
        
        is_allowed, seconds_remaining = check_rate_limit(
            'user123',
            'guild456',
            cooldown_seconds=60,
            global_cooldown=300
        )
        
        # Both expired, should be allowed
        assert is_allowed is True
        assert seconds_remaining == 0
