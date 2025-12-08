"""
Unit tests for logging_utils module.

Tests sensitive data sanitization including:
- PII redaction (emails, tokens, codes)
- Nested structure sanitization
- Pattern matching and regex filtering
- Type safety handling
- Safe logging formatters

Coverage target: 95%+ (currently 63.64%)
"""
import pytest
import sys
import json
from pathlib import Path
from io import StringIO
from unittest.mock import patch

# Add lambda directory to path
lambda_dir = Path(__file__).parent.parent.parent / 'lambda'
sys.path.insert(0, str(lambda_dir))

from logging_utils import (
    sanitize_for_logging,
    sanitize_string,
    log_safe,
    log_email_event,
    log_discord_error,
    SENSITIVE_KEYS
)


# ==============================================================================
# Tests for sanitize_for_logging()
# ==============================================================================

@pytest.mark.unit
class TestSanitizeForLogging:
    """Tests for sanitize_for_logging() function."""

    def test_sanitize_dict_with_sensitive_keys(self):
        """Test dict with sensitive keys gets redacted."""
        data = {
            'email': 'user@example.com',
            'username': 'testuser'
        }
        sanitized = sanitize_for_logging(data)
        assert sanitized['email'] == '***REDACTED***'
        assert sanitized['username'] == 'testuser'

    def test_sanitize_dict_case_insensitive_keys(self):
        """Test sensitive keys are matched case-insensitively."""
        data = {
            'EMAIL': 'user@example.com',
            'Email': 'user2@example.com',
            'eMaIl': 'user3@example.com'
        }
        sanitized = sanitize_for_logging(data)
        assert sanitized['EMAIL'] == '***REDACTED***'
        assert sanitized['Email'] == '***REDACTED***'
        assert sanitized['eMaIl'] == '***REDACTED***'

    def test_sanitize_dict_all_sensitive_keys(self):
        """Test all defined sensitive keys are redacted."""
        data = {
            'email': 'test@example.com',
            'code': '123456',
            'token': 'abc123',
            'password': 'secret',
            'secret': 'mysecret',
            'authorization': 'Bearer token',
            'x-signature-ed25519': 'signature',
            'x-signature-timestamp': '1234567890',
            'bot_token': 'bot_token_here',
            'api_key': 'api_key_here',
            'private_key': 'private_key_here'
        }
        sanitized = sanitize_for_logging(data)
        for key in SENSITIVE_KEYS:
            assert sanitized[key] == '***REDACTED***'

    def test_sanitize_nested_dict(self):
        """Test nested dicts are recursively sanitized."""
        data = {
            'user': {
                'email': 'user@example.com',
                'name': 'John Doe'
            },
            'metadata': {
                'token': 'secret_token'
            }
        }
        sanitized = sanitize_for_logging(data)
        assert sanitized['user']['email'] == '***REDACTED***'
        assert sanitized['user']['name'] == 'John Doe'
        assert sanitized['metadata']['token'] == '***REDACTED***'

    def test_sanitize_list_of_dicts(self):
        """Test list of dicts is recursively sanitized."""
        data = [
            {'email': 'user1@example.com', 'name': 'User 1'},
            {'email': 'user2@example.com', 'name': 'User 2'}
        ]
        sanitized = sanitize_for_logging(data)
        assert sanitized[0]['email'] == '***REDACTED***'
        assert sanitized[0]['name'] == 'User 1'
        assert sanitized[1]['email'] == '***REDACTED***'
        assert sanitized[1]['name'] == 'User 2'

    def test_sanitize_dict_with_list_values(self):
        """Test dict with list values is recursively sanitized."""
        data = {
            'emails': ['user1@example.com', 'user2@example.com'],
            'names': ['User 1', 'User 2']
        }
        sanitized = sanitize_for_logging(data)
        assert sanitized['emails'][0] == '***EMAIL***'
        assert sanitized['emails'][1] == '***EMAIL***'
        assert sanitized['names'][0] == 'User 1'
        assert sanitized['names'][1] == 'User 2'

    def test_sanitize_complex_nested_structure(self):
        """Test deeply nested structure is fully sanitized."""
        data = {
            'level1': {
                'level2': {
                    'level3': {
                        'email': 'deep@example.com',
                        'safe_data': 'visible'
                    }
                }
            }
        }
        sanitized = sanitize_for_logging(data)
        assert sanitized['level1']['level2']['level3']['email'] == '***REDACTED***'
        assert sanitized['level1']['level2']['level3']['safe_data'] == 'visible'

    def test_sanitize_string_with_email(self):
        """Test string containing email is sanitized."""
        data = "User email is user@example.com"
        sanitized = sanitize_for_logging(data)
        assert sanitized == "User email is ***EMAIL***"

    def test_sanitize_string_without_sensitive_data(self):
        """Test string without sensitive data is unchanged."""
        data = "This is a safe log message"
        sanitized = sanitize_for_logging(data)
        assert sanitized == data

    def test_sanitize_primitive_types(self):
        """Test primitive types are returned unchanged."""
        assert sanitize_for_logging(123) == 123
        assert sanitize_for_logging(45.67) == 45.67
        assert sanitize_for_logging(True) is True
        assert sanitize_for_logging(False) is False
        assert sanitize_for_logging(None) is None

    def test_sanitize_empty_dict(self):
        """Test empty dict is handled correctly."""
        assert sanitize_for_logging({}) == {}

    def test_sanitize_empty_list(self):
        """Test empty list is handled correctly."""
        assert sanitize_for_logging([]) == []

    def test_sanitize_empty_string(self):
        """Test empty string is handled correctly."""
        assert sanitize_for_logging("") == ""

    def test_sanitize_dict_with_non_string_values(self):
        """Test dict with non-string values (int, bool, None) are preserved."""
        data = {
            'count': 42,
            'active': True,
            'deleted': False,
            'notes': None,
            'ratio': 3.14
        }
        sanitized = sanitize_for_logging(data)
        assert sanitized['count'] == 42
        assert sanitized['active'] is True
        assert sanitized['deleted'] is False
        assert sanitized['notes'] is None
        assert sanitized['ratio'] == 3.14


# ==============================================================================
# Tests for sanitize_string()
# ==============================================================================

@pytest.mark.unit
class TestSanitizeString:
    """Tests for sanitize_string() function."""

    def test_sanitize_email_simple(self):
        """Test simple email is redacted."""
        text = "Contact us at support@example.com"
        sanitized = sanitize_string(text)
        assert sanitized == "Contact us at ***EMAIL***"

    def test_sanitize_multiple_emails(self):
        """Test multiple emails are redacted."""
        text = "Emails: user1@example.com and user2@test.org"
        sanitized = sanitize_string(text)
        assert "***EMAIL***" in sanitized
        assert "user1@example.com" not in sanitized
        assert "user2@test.org" not in sanitized

    def test_sanitize_email_with_plus(self):
        """Test email with plus addressing is redacted."""
        text = "Email: user+tag@example.com"
        sanitized = sanitize_string(text)
        assert sanitized == "Email: ***EMAIL***"

    def test_sanitize_discord_bot_token(self):
        """Test Discord bot token is redacted."""
        # Need a proper Discord token format: 24+ chars . 6+ chars . 27+ chars
        text = "Token: MTQ0NjU2MjA0Nzk3Mjg1Mzg2NzE0.GK_abc.def123xyz789ABC456def789ghi"
        sanitized = sanitize_string(text)
        assert "Bot ***TOKEN***" in sanitized
        assert "MTQ0NjU2" not in sanitized

    def test_sanitize_discord_bot_token_with_bot_prefix(self):
        """Test Discord bot token with 'Bot ' prefix is redacted."""
        text = "Authorization: Bot MTQ0NjU2MjA0Nzk3Mjg1Mzg2NzE0.GK_abc.def123xyz789ABC456def789ghi"
        sanitized = sanitize_string(text)
        assert "Bot ***TOKEN***" in sanitized

    def test_sanitize_aws_access_key_akia(self):
        """Test AWS access key (AKIA) is redacted."""
        text = "AWS Key: AKIAIOSFODNN7EXAMPLE"
        sanitized = sanitize_string(text)
        assert sanitized == "AWS Key: ***AWS_KEY***"

    def test_sanitize_aws_access_key_asia(self):
        """Test AWS temporary access key (ASIA) is redacted."""
        text = "Temp Key: ASIAIOSFODNN7EXAMPLE"
        sanitized = sanitize_string(text)
        assert sanitized == "Temp Key: ***AWS_KEY***"

    def test_sanitize_verification_code_6_digits(self):
        """Test 6-digit verification code is redacted."""
        text = "Your code is 123456"
        sanitized = sanitize_string(text)
        assert sanitized == "Your code is ***CODE***"

    def test_sanitize_verification_code_7_digits(self):
        """Test 7-digit verification code is redacted."""
        text = "Code: 1234567"
        sanitized = sanitize_string(text)
        assert sanitized == "Code: ***CODE***"

    def test_sanitize_verification_code_8_digits(self):
        """Test 8-digit verification code is redacted."""
        text = "PIN: 12345678"
        sanitized = sanitize_string(text)
        assert sanitized == "PIN: ***CODE***"

    def test_sanitize_verification_code_not_5_digits(self):
        """Test 5-digit number is NOT redacted (too short)."""
        text = "Order #12345"
        sanitized = sanitize_string(text)
        assert sanitized == "Order #12345"

    def test_sanitize_verification_code_not_9_digits(self):
        """Test 9-digit number is NOT redacted (too long)."""
        text = "ID: 123456789"
        sanitized = sanitize_string(text)
        assert sanitized == "ID: 123456789"

    def test_sanitize_all_patterns_combined(self):
        """Test multiple sensitive patterns in one string."""
        text = "Email: user@example.com, Token: Bot MTQ0NjU2MjA0Nzk3Mjg1Mzg2NzE0.GK_abc.def123xyz789ABC456def789ghi, Code: 123456, AWS: AKIAIOSFODNN7EXAMPLE"
        sanitized = sanitize_string(text)
        assert "***EMAIL***" in sanitized
        assert "***TOKEN***" in sanitized
        assert "***CODE***" in sanitized
        assert "***AWS_KEY***" in sanitized
        assert "user@example.com" not in sanitized
        assert "AKIAIOSFODNN7EXAMPLE" not in sanitized

    def test_sanitize_string_no_sensitive_data(self):
        """Test string with no sensitive data is unchanged."""
        text = "This is a normal log message without any sensitive information"
        sanitized = sanitize_string(text)
        assert sanitized == text

    def test_sanitize_string_empty(self):
        """Test empty string is handled correctly."""
        assert sanitize_string("") == ""

    def test_sanitize_string_non_string_type(self):
        """Test non-string type is returned unchanged."""
        assert sanitize_string(123) == 123
        assert sanitize_string(None) is None
        assert sanitize_string([]) == []
        assert sanitize_string({}) == {}

    def test_sanitize_string_unicode_email(self):
        """Test email with unicode characters."""
        text = "Email: test@example.com with unicode"
        sanitized = sanitize_string(text)
        assert "***EMAIL***" in sanitized


# ==============================================================================
# Tests for log_safe()
# ==============================================================================

@pytest.mark.unit
class TestLogSafe:
    """Tests for log_safe() function."""

    def test_log_safe_message_only(self, capsys):
        """Test logging message without data."""
        log_safe("Test message")
        captured = capsys.readouterr()
        assert "Test message" in captured.out

    def test_log_safe_with_dict_data(self, capsys):
        """Test logging with dict data."""
        data = {'user': 'test', 'email': 'user@example.com'}
        log_safe("User data", data)
        captured = capsys.readouterr()
        assert "User data" in captured.out
        assert "***REDACTED***" in captured.out
        assert "user@example.com" not in captured.out

    def test_log_safe_with_list_data(self, capsys):
        """Test logging with list data."""
        data = ['item1@example.com', 'item2']
        log_safe("List data", data)
        captured = capsys.readouterr()
        assert "List data" in captured.out
        assert "***EMAIL***" in captured.out

    def test_log_safe_with_string_data(self, capsys):
        """Test logging with string data."""
        log_safe("Message", "user@example.com sent a request")
        captured = capsys.readouterr()
        assert "Message" in captured.out
        assert "***EMAIL***" in captured.out
        assert "user@example.com" not in captured.out

    def test_log_safe_with_primitive_data(self, capsys):
        """Test logging with primitive data."""
        log_safe("Count", 42)
        captured = capsys.readouterr()
        assert "Count: 42" in captured.out

    def test_log_safe_with_none_data(self, capsys):
        """Test logging with None data."""
        log_safe("No data", None)
        captured = capsys.readouterr()
        # When data is None, should only print message
        assert "No data" in captured.out
        assert ": None" not in captured.out

    def test_log_safe_with_nested_sensitive_data(self, capsys):
        """Test logging with nested sensitive data."""
        data = {
            'request': {
                'user': {
                    'email': 'test@example.com',
                    'token': 'secret_token'
                }
            }
        }
        log_safe("Request received", data)
        captured = capsys.readouterr()
        assert "***REDACTED***" in captured.out
        assert "test@example.com" not in captured.out
        assert "secret_token" not in captured.out

    def test_log_safe_formats_as_json(self, capsys):
        """Test that dict/list data is formatted as JSON."""
        data = {'key': 'value'}
        log_safe("JSON test", data)
        captured = capsys.readouterr()
        # Should be valid JSON format
        assert '{"key": "value"}' in captured.out or '"key": "value"' in captured.out


# ==============================================================================
# Tests for log_email_event()
# ==============================================================================

@pytest.mark.unit
class TestLogEmailEvent:
    """Tests for log_email_event() function."""

    def test_log_email_event_success_no_details(self, capsys):
        """Test logging successful email event without details."""
        log_email_event("sent", "user@auburn.edu", True)
        captured = capsys.readouterr()
        assert "Email sent SUCCESS" in captured.out
        assert "@auburn.edu" in captured.out
        assert "user" not in captured.out  # User part should be hidden

    def test_log_email_event_failure_no_details(self, capsys):
        """Test logging failed email event without details."""
        log_email_event("sent", "user@example.com", False)
        captured = capsys.readouterr()
        assert "Email sent FAILED" in captured.out
        assert "@example.com" in captured.out

    def test_log_email_event_success_with_details(self, capsys):
        """Test logging successful email event with details."""
        log_email_event("validated", "student@auburn.edu", True, "Valid .edu domain")
        captured = capsys.readouterr()
        assert "Email validated SUCCESS" in captured.out
        assert "@auburn.edu" in captured.out
        assert "Valid .edu domain" in captured.out

    def test_log_email_event_failure_with_details(self, capsys):
        """Test logging failed email event with details."""
        log_email_event("sent", "user@test.com", False, "SMTP timeout")
        captured = capsys.readouterr()
        assert "Email sent FAILED" in captured.out
        assert "@test.com" in captured.out
        assert "SMTP timeout" in captured.out

    def test_log_email_event_hides_user_part(self, capsys):
        """Test that user part of email is hidden."""
        log_email_event("sent", "sensitive.user@example.com", True)
        captured = capsys.readouterr()
        assert "sensitive.user" not in captured.out
        assert "@example.com" in captured.out

    def test_log_email_event_invalid_email_format(self, capsys):
        """Test logging with invalid email format (no @)."""
        log_email_event("sent", "notanemail", True)
        captured = capsys.readouterr()
        assert "@unknown" in captured.out

    def test_log_email_event_different_operations(self, capsys):
        """Test different operation names."""
        operations = ["sent", "validated", "verified", "bounced", "rejected"]
        for operation in operations:
            log_email_event(operation, "user@example.com", True)
        captured = capsys.readouterr()
        for operation in operations:
            assert f"Email {operation} SUCCESS" in captured.out


# ==============================================================================
# Tests for log_discord_error()
# ==============================================================================

@pytest.mark.unit
class TestLogDiscordError:
    """Tests for log_discord_error() function."""

    def test_log_discord_error_without_error_code(self, capsys):
        """Test logging Discord error without error code."""
        log_discord_error("assign_role", 403)
        captured = capsys.readouterr()
        assert "Discord API error" in captured.out
        assert "assign_role" in captured.out
        assert "403" in captured.out

    def test_log_discord_error_with_error_code(self, capsys):
        """Test logging Discord error with error code."""
        log_discord_error("get_member", 404, 10007)
        captured = capsys.readouterr()
        assert "Discord API error" in captured.out
        assert "get_member" in captured.out
        assert "404" in captured.out
        assert "10007" in captured.out

    def test_log_discord_error_formats_as_json(self, capsys):
        """Test that error is formatted as JSON."""
        log_discord_error("send_message", 500, 50001)
        captured = capsys.readouterr()
        # Should contain JSON structure
        assert "{" in captured.out
        assert "}" in captured.out
        assert "operation" in captured.out
        assert "status_code" in captured.out
        assert "error_code" in captured.out

    def test_log_discord_error_various_status_codes(self, capsys):
        """Test logging with various HTTP status codes."""
        status_codes = [400, 401, 403, 404, 429, 500, 502, 503]
        for status_code in status_codes:
            log_discord_error("test_operation", status_code)
        captured = capsys.readouterr()
        for status_code in status_codes:
            assert str(status_code) in captured.out

    def test_log_discord_error_various_operations(self, capsys):
        """Test logging with various operation names."""
        operations = ["assign_role", "remove_role", "get_member", "send_message", "get_guild"]
        for operation in operations:
            log_discord_error(operation, 500)
        captured = capsys.readouterr()
        for operation in operations:
            assert operation in captured.out

    def test_log_discord_error_error_code_none(self, capsys):
        """Test logging with None error code."""
        log_discord_error("test_operation", 500, None)
        captured = capsys.readouterr()
        assert "Discord API error" in captured.out
        assert "test_operation" in captured.out
        assert "500" in captured.out
        # None should appear in JSON as null
        assert "null" in captured.out or "None" in captured.out


# ==============================================================================
# Integration Tests
# ==============================================================================

@pytest.mark.unit
class TestSanitizationIntegration:
    """Integration tests for sanitization across functions."""

    def test_end_to_end_dict_sanitization(self, capsys):
        """Test complete sanitization flow with complex data."""
        data = {
            'user_id': '987654321',  # Changed to avoid 6-digit code pattern
            'email': 'user@example.com',
            'verification': {
                'code': '123456',
                'token': 'Bot MTQ0NjU2MjA0Nzk3Mjg1Mzg2NzE0.GK_abc.def123xyz789ABC456def789ghi',
                'aws_key': 'AKIAIOSFODNN7EXAMPLE'
            },
            'messages': [
                'Sent to admin@company.com',
                'Code 789012 was used'
            ]
        }

        log_safe("Complete test", data)
        captured = capsys.readouterr()

        # Verify all sensitive data is redacted
        assert "***REDACTED***" in captured.out
        assert "user@example.com" not in captured.out
        assert "MTQ0NjU2" not in captured.out
        assert "AKIAIOSFODNN7EXAMPLE" not in captured.out
        assert "admin@company.com" not in captured.out

        # Verify safe data is preserved
        assert "987654321" in captured.out  # user_id is safe (9 digits, not redacted)

    def test_list_of_mixed_types_sanitization(self):
        """Test sanitization of list with mixed types."""
        data = [
            {'email': 'test1@example.com'},
            'String with email test2@example.com',
            123,
            ['nested', 'list', 'with', 'email@example.com'],
            None,
            True
        ]

        sanitized = sanitize_for_logging(data)

        assert sanitized[0]['email'] == '***REDACTED***'
        assert '***EMAIL***' in sanitized[1]
        assert sanitized[2] == 123
        assert '***EMAIL***' in sanitized[3][3]
        assert sanitized[4] is None
        assert sanitized[5] is True

    def test_deeply_nested_sanitization(self):
        """Test sanitization of deeply nested structures."""
        data = {
            'level1': [
                {
                    'level2': {
                        'level3': [
                            {
                                'email': 'deep@example.com',
                                'safe': 'data'
                            }
                        ]
                    }
                }
            ]
        }

        sanitized = sanitize_for_logging(data)
        assert sanitized['level1'][0]['level2']['level3'][0]['email'] == '***REDACTED***'
        assert sanitized['level1'][0]['level2']['level3'][0]['safe'] == 'data'

    def test_real_world_lambda_event_sanitization(self):
        """Test sanitization of realistic Lambda event data."""
        event = {
            'headers': {
                'authorization': 'Bot secret_token_here',
                'x-signature-ed25519': 'signature_here',
                'content-type': 'application/json'
            },
            'body': {
                'user': {
                    'id': '987654321012',  # Changed to avoid 6-digit code pattern
                    'email': 'user@example.com'
                },
                'guild_id': '789012345678'  # Changed to avoid 6-digit code pattern
            }
        }

        sanitized = sanitize_for_logging(event)

        assert sanitized['headers']['authorization'] == '***REDACTED***'
        assert sanitized['headers']['x-signature-ed25519'] == '***REDACTED***'
        assert sanitized['headers']['content-type'] == 'application/json'
        assert sanitized['body']['user']['email'] == '***REDACTED***'
        assert sanitized['body']['user']['id'] == '987654321012'
        assert sanitized['body']['guild_id'] == '789012345678'
