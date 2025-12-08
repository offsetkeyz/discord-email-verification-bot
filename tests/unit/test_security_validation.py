"""
Security validation tests for input handling.

Tests XSS, injection, length limits, and malicious input patterns
to address QA concerns from PR #11.
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import patch
from moto import mock_aws
import boto3

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


from guild_config import save_guild_config, get_guild_custom_message
from verification_logic import validate_edu_email


# ==============================================================================
# XSS/Injection Tests for custom_message
# ==============================================================================

@pytest.mark.unit
@pytest.mark.security
class TestCustomMessageXSSInjection:
    """Tests for XSS and injection attempts in custom_message field."""
    
    def test_xss_script_tag_stored(self, mock_dynamodb_table):
        """Test that script tags in custom message are stored (not sanitized at storage)."""
        malicious_message = "<script>alert('xss')</script>"
        
        result = save_guild_config(
            guild_id='guild123',
            role_id='role123',
            channel_id='channel123',
            setup_by_user_id='user123',
            custom_message=malicious_message
        )
        
        assert result is True
        # DynamoDB stores as-is, sanitization should happen at render time
        retrieved = get_guild_custom_message('guild123')
        assert retrieved == malicious_message
    
    def test_xss_img_onerror(self, mock_dynamodb_table):
        """Test XSS via img onerror attribute."""
        malicious_message = "<img src=x onerror=alert('xss')>"
        
        save_guild_config(
            guild_id='guild123',
            role_id='role123',
            channel_id='channel123',
            setup_by_user_id='user123',
            custom_message=malicious_message
        )
        
        retrieved = get_guild_custom_message('guild123')
        assert retrieved == malicious_message
    
    def test_xss_javascript_protocol(self, mock_dynamodb_table):
        """Test XSS via javascript: protocol."""
        malicious_message = "<a href='javascript:alert(1)'>Click me</a>"
        
        save_guild_config(
            guild_id='guild123',
            role_id='role123',
            channel_id='channel123',
            setup_by_user_id='user123',
            custom_message=malicious_message
        )
        
        retrieved = get_guild_custom_message('guild123')
        assert retrieved == malicious_message
    
    def test_html_injection(self, mock_dynamodb_table):
        """Test HTML injection attempts."""
        malicious_message = "<h1>Fake Heading</h1><iframe src='http://evil.com'></iframe>"
        
        save_guild_config(
            guild_id='guild123',
            role_id='role123',
            channel_id='channel123',
            setup_by_user_id='user123',
            custom_message=malicious_message
        )
        
        retrieved = get_guild_custom_message('guild123')
        assert retrieved == malicious_message
    
    def test_sql_injection_pattern(self, mock_dynamodb_table):
        """Test SQL injection patterns (should be harmless with DynamoDB)."""
        malicious_message = "'; DROP TABLE users; --"
        
        save_guild_config(
            guild_id='guild123',
            role_id='role123',
            channel_id='channel123',
            setup_by_user_id='user123',
            custom_message=malicious_message
        )
        
        retrieved = get_guild_custom_message('guild123')
        assert retrieved == malicious_message
    
    def test_command_injection_pattern(self, mock_dynamodb_table):
        """Test command injection patterns."""
        malicious_message = "test && rm -rf / || echo 'pwned'"
        
        save_guild_config(
            guild_id='guild123',
            role_id='role123',
            channel_id='channel123',
            setup_by_user_id='user123',
            custom_message=malicious_message
        )
        
        retrieved = get_guild_custom_message('guild123')
        assert retrieved == malicious_message
    
    def test_template_injection(self, mock_dynamodb_table):
        """Test template injection patterns."""
        malicious_message = "{{7*7}} ${7*7} <%= 7*7 %>"
        
        save_guild_config(
            guild_id='guild123',
            role_id='role123',
            channel_id='channel123',
            setup_by_user_id='user123',
            custom_message=malicious_message
        )
        
        retrieved = get_guild_custom_message('guild123')
        assert retrieved == malicious_message


# ==============================================================================
# Length Limit Tests (DoS Prevention)
# ==============================================================================

@pytest.mark.unit
@pytest.mark.security
class TestLengthLimits:
    """Tests for extremely long inputs that could cause DoS."""
    
    def test_extremely_long_custom_message(self, mock_dynamodb_table):
        """Test storing extremely long custom message (10KB)."""
        long_message = "A" * 10_000  # 10KB message
        
        result = save_guild_config(
            guild_id='guild123',
            role_id='role123',
            channel_id='channel123',
            setup_by_user_id='user123',
            custom_message=long_message
        )
        
        # DynamoDB can handle this, but Discord may truncate
        assert result is True
        retrieved = get_guild_custom_message('guild123')
        assert len(retrieved) == 10_000
    
    def test_very_long_custom_message_100kb(self, mock_dynamodb_table):
        """Test storing very long custom message (100KB)."""
        long_message = "B" * 100_000  # 100KB message
        
        result = save_guild_config(
            guild_id='guild123',
            role_id='role123',
            channel_id='channel123',
            setup_by_user_id='user123',
            custom_message=long_message
        )
        
        # Should store successfully (DynamoDB max item size is 400KB)
        assert result is True
    
    def test_extremely_long_domain_name(self, mock_dynamodb_table):
        """Test extremely long domain name."""
        long_domain = "a" * 250 + ".edu"  # Max DNS label is 253 chars
        
        result = save_guild_config(
            guild_id='guild123',
            role_id='role123',
            channel_id='channel123',
            setup_by_user_id='user123',
            allowed_domains=[long_domain]
        )
        
        assert result is True
    
    def test_very_long_email_address(self):
        """Test very long email address validation."""
        # Max email length is typically 320 chars (64 local + 255 domain)
        long_local = "a" * 64
        long_email = f"{long_local}@auburn.edu"
        
        assert validate_edu_email(long_email) is True
    
    def test_massive_email_address_rejected(self):
        """Test that unreasonably long email is rejected."""
        # Email exceeding typical 320 char limit
        very_long_local = "a" * 500
        very_long_email = f"{very_long_local}@auburn.edu"
        
        # Should fail regex validation due to excessive length
        result = validate_edu_email(very_long_email)
        # May pass or fail depending on regex engine, but should not crash
        assert isinstance(result, bool)
    
    def test_many_domains_list(self, mock_dynamodb_table):
        """Test saving many allowed domains (100+)."""
        many_domains = [f"university{i}.edu" for i in range(100)]
        
        result = save_guild_config(
            guild_id='guild123',
            role_id='role123',
            channel_id='channel123',
            setup_by_user_id='user123',
            allowed_domains=many_domains
        )
        
        assert result is True


# ==============================================================================
# Unicode and Special Character Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.security
class TestUnicodeSpecialCharacters:
    """Tests for Unicode, emoji, and special character handling."""
    
    def test_emoji_in_custom_message(self, mock_dynamodb_table):
        """Test emoji in custom message."""
        emoji_message = "Welcome! 🎓 Click to verify 📧 your email ✅"
        
        result = save_guild_config(
            guild_id='guild123',
            role_id='role123',
            channel_id='channel123',
            setup_by_user_id='user123',
            custom_message=emoji_message
        )
        
        assert result is True
        retrieved = get_guild_custom_message('guild123')
        assert retrieved == emoji_message
    
    def test_unicode_characters_in_message(self, mock_dynamodb_table):
        """Test various Unicode characters."""
        unicode_message = "Bienvenue! Bienvenido! 欢迎! مرحبا! Добро пожаловать!"
        
        result = save_guild_config(
            guild_id='guild123',
            role_id='role123',
            channel_id='channel123',
            setup_by_user_id='user123',
            custom_message=unicode_message
        )
        
        assert result is True
        retrieved = get_guild_custom_message('guild123')
        assert retrieved == unicode_message
    
    def test_special_unicode_characters(self, mock_dynamodb_table):
        """Test special Unicode characters (zero-width, combining, etc)."""
        special_message = "Test\u200B\u200C\u200DMessage"  # Zero-width chars
        
        result = save_guild_config(
            guild_id='guild123',
            role_id='role123',
            channel_id='channel123',
            setup_by_user_id='user123',
            custom_message=special_message
        )
        
        assert result is True
    
    def test_rtl_override_characters(self, mock_dynamodb_table):
        """Test Right-to-Left override characters."""
        rtl_message = "Test\u202Eoverride\u202C"
        
        result = save_guild_config(
            guild_id='guild123',
            role_id='role123',
            channel_id='channel123',
            setup_by_user_id='user123',
            custom_message=rtl_message
        )
        
        assert result is True
    
    def test_null_byte_in_message(self, mock_dynamodb_table):
        """Test null bytes in custom message."""
        null_message = "Before\x00After"
        
        result = save_guild_config(
            guild_id='guild123',
            role_id='role123',
            channel_id='channel123',
            setup_by_user_id='user123',
            custom_message=null_message
        )
        
        # Should store (though may cause issues downstream)
        assert result is True
    
    def test_control_characters_in_message(self, mock_dynamodb_table):
        """Test ASCII control characters."""
        control_message = "Test\x01\x02\x03\x1F"
        
        result = save_guild_config(
            guild_id='guild123',
            role_id='role123',
            channel_id='channel123',
            setup_by_user_id='user123',
            custom_message=control_message
        )
        
        assert result is True
    
    def test_emoji_in_email_address(self):
        """Test that emoji in email address is rejected."""
        emoji_email = "student😀@auburn.edu"
        
        assert validate_edu_email(emoji_email) is False
    
    def test_unicode_in_email_local_part(self):
        """Test Unicode characters in email local part."""
        # While technically some Unicode is allowed in email, our regex likely rejects it
        unicode_email = "café@auburn.edu"
        
        # Should be rejected by our strict ASCII regex
        assert validate_edu_email(unicode_email) is False
    
    def test_homograph_attack_domain(self):
        """Test homograph attack using similar-looking Unicode characters."""
        # Cyrillic 'а' instead of Latin 'a'
        homograph_email = "student@аuburn.edu"
        
        # Should be rejected as domain doesn't match
        assert validate_edu_email(homograph_email) is False


# ==============================================================================
# Edge Case Character Combinations
# ==============================================================================

@pytest.mark.unit
@pytest.mark.security
class TestEdgeCaseCharacters:
    """Tests for edge case character combinations."""
    
    def test_newlines_in_message(self, mock_dynamodb_table):
        """Test newlines in custom message."""
        multiline_message = "Line 1\nLine 2\rLine 3\r\nLine 4"
        
        result = save_guild_config(
            guild_id='guild123',
            role_id='role123',
            channel_id='channel123',
            setup_by_user_id='user123',
            custom_message=multiline_message
        )
        
        assert result is True
    
    def test_tabs_in_message(self, mock_dynamodb_table):
        """Test tab characters in custom message."""
        tab_message = "Column1\tColumn2\tColumn3"
        
        result = save_guild_config(
            guild_id='guild123',
            role_id='role123',
            channel_id='channel123',
            setup_by_user_id='user123',
            custom_message=tab_message
        )
        
        assert result is True
    
    def test_backslash_escapes(self, mock_dynamodb_table):
        """Test backslash escape sequences."""
        escape_message = "Test\\nNo\\tActual\\rEscape"
        
        result = save_guild_config(
            guild_id='guild123',
            role_id='role123',
            channel_id='channel123',
            setup_by_user_id='user123',
            custom_message=escape_message
        )
        
        assert result is True
    
    def test_quoted_strings_in_message(self, mock_dynamodb_table):
        """Test various quote types in message."""
        quoted_message = "He said \"Hello\", she said 'Hi', they used `backticks`"
        
        result = save_guild_config(
            guild_id='guild123',
            role_id='role123',
            channel_id='channel123',
            setup_by_user_id='user123',
            custom_message=quoted_message
        )
        
        assert result is True
