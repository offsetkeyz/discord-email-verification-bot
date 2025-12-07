"""
Unit tests for ses_email module.

Tests Amazon SES email functionality including:
- Email sending with verification codes
- HTML and text body generation
- Error handling for SES failures
- Logging integration
"""
import pytest
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from botocore.exceptions import ClientError

# Add lambda directory to path
lambda_dir = Path(__file__).parent.parent.parent / 'lambda'
sys.path.insert(0, str(lambda_dir))


# ==============================================================================
# Test Fixtures
# ==============================================================================

@pytest.fixture
def mock_ses_client():
    """Mock SES client for testing."""
    with patch('ses_email.ses_client') as mock_client:
        # Configure successful response
        mock_client.send_email.return_value = {
            'MessageId': 'test-message-id-12345'
        }
        yield mock_client


@pytest.fixture
def mock_logging():
    """Mock logging_utils to isolate email tests."""
    with patch('ses_email.log_email_event') as mock_log:
        yield mock_log


# Import after mocking to avoid initialization issues
from ses_email import send_verification_email


# ==============================================================================
# Successful Email Sending Tests
# ==============================================================================

@pytest.mark.unit
class TestSuccessfulEmailSending:
    """Tests for successful email sending scenarios."""

    def test_send_email_success_returns_true(self, mock_ses_client, mock_logging):
        """Test that successful email send returns True."""
        with patch.dict('os.environ', {'FROM_EMAIL': 'test@example.com'}):
            result = send_verification_email('student@university.edu', '123456')

            assert result is True

    def test_send_email_calls_ses_client(self, mock_ses_client, mock_logging):
        """Test that SES client send_email is called correctly."""
        with patch.dict('os.environ', {'FROM_EMAIL': 'test@example.com'}):
            send_verification_email('student@university.edu', '123456')

            # Verify send_email was called
            mock_ses_client.send_email.assert_called_once()

            # Get the call arguments
            call_args = mock_ses_client.send_email.call_args

            assert call_args[1]['Source'] == 'test@example.com'
            assert call_args[1]['Destination']['ToAddresses'] == ['student@university.edu']

    def test_send_email_uses_default_from_email(self, mock_ses_client, mock_logging):
        """Test that default FROM_EMAIL is used when env var not set."""
        with patch.dict('os.environ', {}, clear=True):
            send_verification_email('student@university.edu', '123456')

            call_args = mock_ses_client.send_email.call_args
            assert call_args[1]['Source'] == 'verificationcode.noreply@thedailydecrypt.com'


# ==============================================================================
# Email Content Validation Tests
# ==============================================================================

@pytest.mark.unit
class TestEmailContentValidation:
    """Tests for email content structure and formatting."""

    def test_email_subject_correct(self, mock_ses_client, mock_logging):
        """Test that email subject is set correctly."""
        with patch.dict('os.environ', {}):
            send_verification_email('student@university.edu', '123456')

            call_args = mock_ses_client.send_email.call_args
            subject = call_args[1]['Message']['Subject']['Data']

            assert subject == 'Discord Verification Code'

    def test_verification_code_in_text_body(self, mock_ses_client, mock_logging):
        """Test that verification code appears in text body."""
        test_code = '789012'

        with patch.dict('os.environ', {}):
            send_verification_email('student@university.edu', test_code)

            call_args = mock_ses_client.send_email.call_args
            text_body = call_args[1]['Message']['Body']['Text']['Data']

            assert test_code in text_body
            assert 'Your verification code is:' in text_body
            assert '15 minutes' in text_body

    def test_verification_code_in_html_body(self, mock_ses_client, mock_logging):
        """Test that verification code appears in HTML body."""
        test_code = '456789'

        with patch.dict('os.environ', {}):
            send_verification_email('student@university.edu', test_code)

            call_args = mock_ses_client.send_email.call_args
            html_body = call_args[1]['Message']['Body']['Html']['Data']

            assert test_code in html_body
            assert 'Discord Server Verification' in html_body
            assert '15 minutes' in html_body
            assert '<html>' in html_body

    def test_email_charset_utf8(self, mock_ses_client, mock_logging):
        """Test that email uses UTF-8 charset."""
        with patch.dict('os.environ', {}):
            send_verification_email('student@university.edu', '123456')

            call_args = mock_ses_client.send_email.call_args
            message = call_args[1]['Message']

            assert message['Subject']['Charset'] == 'UTF-8'
            assert message['Body']['Text']['Charset'] == 'UTF-8'
            assert message['Body']['Html']['Charset'] == 'UTF-8'

    def test_email_contains_both_text_and_html(self, mock_ses_client, mock_logging):
        """Test that email contains both text and HTML versions."""
        with patch.dict('os.environ', {}):
            send_verification_email('student@university.edu', '123456')

            call_args = mock_ses_client.send_email.call_args
            body = call_args[1]['Message']['Body']

            assert 'Text' in body
            assert 'Html' in body
            assert body['Text']['Data'] != ''
            assert body['Html']['Data'] != ''


# ==============================================================================
# Error Handling Tests
# ==============================================================================

@pytest.mark.unit
class TestEmailErrorHandling:
    """Tests for error handling in email sending."""

    def test_client_error_returns_false(self, mock_ses_client, mock_logging):
        """Test that SES ClientError returns False."""
        # Configure mock to raise ClientError
        mock_ses_client.send_email.side_effect = ClientError(
            {'Error': {'Code': 'MessageRejected', 'Message': 'Email address not verified'}},
            'SendEmail'
        )

        with patch.dict('os.environ', {}):
            result = send_verification_email('student@university.edu', '123456')

            assert result is False

    def test_client_error_logged(self, mock_ses_client, mock_logging):
        """Test that ClientError is logged via log_email_event."""
        mock_ses_client.send_email.side_effect = ClientError(
            {'Error': {'Code': 'MessageRejected', 'Message': 'Email address not verified'}},
            'SendEmail'
        )

        with patch.dict('os.environ', {}):
            send_verification_email('student@university.edu', '123456')

            # Verify logging was called
            mock_logging.assert_called_once()
            call_args = mock_logging.call_args[0]

            assert call_args[0] == 'sent'
            assert call_args[1] == 'student@university.edu'
            assert call_args[2] is False
            assert 'SES Error' in call_args[3]

    def test_quota_exceeded_error_returns_false(self, mock_ses_client, mock_logging):
        """Test that SES quota exceeded error returns False."""
        mock_ses_client.send_email.side_effect = ClientError(
            {'Error': {'Code': 'Throttling', 'Message': 'Maximum sending rate exceeded'}},
            'SendEmail'
        )

        with patch.dict('os.environ', {}):
            result = send_verification_email('student@university.edu', '123456')

            assert result is False

    def test_generic_exception_returns_false(self, mock_ses_client, mock_logging):
        """Test that generic exceptions return False."""
        mock_ses_client.send_email.side_effect = Exception("Network error")

        with patch.dict('os.environ', {}):
            result = send_verification_email('student@university.edu', '123456')

            assert result is False


# ==============================================================================
# Logging Integration Tests
# ==============================================================================

@pytest.mark.unit
class TestLoggingIntegration:
    """Tests for integration with logging_utils."""

    def test_successful_send_logged(self, mock_ses_client, mock_logging):
        """Test that successful email send is logged."""
        with patch.dict('os.environ', {}):
            send_verification_email('student@university.edu', '123456')

            # Verify log_email_event was called
            mock_logging.assert_called_once()
            call_args = mock_logging.call_args[0]

            assert call_args[0] == 'sent'
            assert call_args[1] == 'student@university.edu'
            assert call_args[2] is True
            assert 'MessageId: test-message-id-12345' in call_args[3]

    def test_message_id_captured(self, mock_ses_client, mock_logging):
        """Test that SES MessageId is captured in logs."""
        mock_ses_client.send_email.return_value = {
            'MessageId': 'unique-message-id-xyz'
        }

        with patch.dict('os.environ', {}):
            send_verification_email('student@university.edu', '123456')

            call_args = mock_logging.call_args[0]
            assert 'unique-message-id-xyz' in call_args[3]

    def test_failure_logged_with_error_details(self, mock_ses_client, mock_logging):
        """Test that email failures are logged with error details."""
        mock_ses_client.send_email.side_effect = ClientError(
            {'Error': {'Code': 'InvalidParameterValue', 'Message': 'Invalid email address'}},
            'SendEmail'
        )

        with patch.dict('os.environ', {}):
            send_verification_email('invalid-email', '123456')

            call_args = mock_logging.call_args[0]
            assert call_args[2] is False
            assert 'Invalid email address' in call_args[3]


# ==============================================================================
# Edge Cases and Security Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.security
class TestEdgeCasesAndSecurity:
    """Tests for edge cases and security considerations."""

    def test_empty_code_handled(self, mock_ses_client, mock_logging):
        """Test that empty verification code is handled."""
        with patch.dict('os.environ', {}):
            result = send_verification_email('student@university.edu', '')

            # Should still send (validation happens elsewhere)
            assert result is True
            call_args = mock_ses_client.send_email.call_args
            text_body = call_args[1]['Message']['Body']['Text']['Data']
            assert 'Your verification code is: ' in text_body

    def test_special_characters_in_email(self, mock_ses_client, mock_logging):
        """Test email with special characters."""
        email_with_special = 'user+test@university.edu'

        with patch.dict('os.environ', {}):
            result = send_verification_email(email_with_special, '123456')

            assert result is True
            call_args = mock_ses_client.send_email.call_args
            assert call_args[1]['Destination']['ToAddresses'] == [email_with_special]

    def test_long_code_handled(self, mock_ses_client, mock_logging):
        """Test that very long codes are handled."""
        long_code = '1234567890' * 10  # 100 characters

        with patch.dict('os.environ', {}):
            result = send_verification_email('student@university.edu', long_code)

            assert result is True
            call_args = mock_ses_client.send_email.call_args
            html_body = call_args[1]['Message']['Body']['Html']['Data']
            assert long_code in html_body

    def test_unicode_characters_in_code(self, mock_ses_client, mock_logging):
        """Test that unicode characters in code are handled."""
        unicode_code = '世界123'

        with patch.dict('os.environ', {}):
            result = send_verification_email('student@university.edu', unicode_code)

            # Should successfully encode with UTF-8
            assert result is True


# ==============================================================================
# Email Template Tests
# ==============================================================================

@pytest.mark.unit
class TestEmailTemplate:
    """Tests for email template structure and styling."""

    def test_html_template_has_discord_branding(self, mock_ses_client, mock_logging):
        """Test that HTML template includes Discord branding color."""
        with patch.dict('os.environ', {}):
            send_verification_email('student@university.edu', '123456')

            call_args = mock_ses_client.send_email.call_args
            html_body = call_args[1]['Message']['Body']['Html']['Data']

            # Discord brand color #5865F2
            assert '#5865F2' in html_body

    def test_html_template_responsive_design(self, mock_ses_client, mock_logging):
        """Test that HTML template has responsive max-width."""
        with patch.dict('os.environ', {}):
            send_verification_email('student@university.edu', '123456')

            call_args = mock_ses_client.send_email.call_args
            html_body = call_args[1]['Message']['Body']['Html']['Data']

            assert 'max-width: 600px' in html_body

    def test_text_body_has_expiration_warning(self, mock_ses_client, mock_logging):
        """Test that text body includes expiration warning."""
        with patch.dict('os.environ', {}):
            send_verification_email('student@university.edu', '123456')

            call_args = mock_ses_client.send_email.call_args
            text_body = call_args[1]['Message']['Body']['Text']['Data']

            assert 'expire in 15 minutes' in text_body

    def test_security_disclaimer_in_both_bodies(self, mock_ses_client, mock_logging):
        """Test that security disclaimer appears in both email bodies."""
        with patch.dict('os.environ', {}):
            send_verification_email('student@university.edu', '123456')

            call_args = mock_ses_client.send_email.call_args
            text_body = call_args[1]['Message']['Body']['Text']['Data']
            html_body = call_args[1]['Message']['Body']['Html']['Data']

            assert 'did not request' in text_body
            assert 'did not request' in html_body
