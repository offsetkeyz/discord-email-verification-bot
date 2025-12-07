"""
Unit tests for discord_interactions module.

Tests Discord Interactions API utilities including:
- Enum value definitions and constants
- Ed25519 signature verification (SECURITY CRITICAL)
- Replay attack prevention (timestamp validation)
- Error handling for invalid signatures
"""
import pytest
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
from nacl.signing import SigningKey
from nacl.exceptions import BadSignatureError

# Add lambda directory to path
lambda_dir = Path(__file__).parent.parent.parent / 'lambda'
sys.path.insert(0, str(lambda_dir))

from discord_interactions import (
    InteractionType,
    InteractionResponseType,
    MessageFlags,
    ComponentType,
    ButtonStyle,
    verify_discord_signature
)


# ==============================================================================
# Test Fixtures
# ==============================================================================

@pytest.fixture
def discord_keypair():
    """Generate a valid Ed25519 keypair for testing signatures."""
    # Generate a real Ed25519 keypair
    signing_key = SigningKey.generate()
    verify_key = signing_key.verify_key

    return {
        'signing_key': signing_key,
        'verify_key': verify_key,
        'public_key_hex': verify_key.encode().hex()
    }


@pytest.fixture
def valid_signature_data(discord_keypair):
    """Create valid signature test data."""
    timestamp = str(int(time.time()))
    body = '{"type":1}'
    message = f"{timestamp}{body}".encode()

    signature = discord_keypair['signing_key'].sign(message).signature

    return {
        'signature': signature.hex(),
        'timestamp': timestamp,
        'body': body,
        'public_key': discord_keypair['public_key_hex']
    }


# ==============================================================================
# Enum Value Tests
# ==============================================================================

@pytest.mark.unit
class TestEnumDefinitions:
    """Tests for Discord API enum definitions."""

    def test_interaction_type_values(self):
        """Test InteractionType enum has correct values."""
        assert InteractionType.PING == 1
        assert InteractionType.APPLICATION_COMMAND == 2
        assert InteractionType.MESSAGE_COMPONENT == 3
        assert InteractionType.APPLICATION_COMMAND_AUTOCOMPLETE == 4
        assert InteractionType.MODAL_SUBMIT == 5

    def test_interaction_response_type_values(self):
        """Test InteractionResponseType enum has correct values."""
        assert InteractionResponseType.PONG == 1
        assert InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE == 4
        assert InteractionResponseType.DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE == 5
        assert InteractionResponseType.DEFERRED_UPDATE_MESSAGE == 6
        assert InteractionResponseType.UPDATE_MESSAGE == 7
        assert InteractionResponseType.APPLICATION_COMMAND_AUTOCOMPLETE_RESULT == 8
        assert InteractionResponseType.MODAL == 9

    def test_message_flags_values(self):
        """Test MessageFlags enum has correct values."""
        assert MessageFlags.EPHEMERAL == 64

    def test_component_type_values(self):
        """Test ComponentType enum has correct values."""
        assert ComponentType.ACTION_ROW == 1
        assert ComponentType.BUTTON == 2
        assert ComponentType.STRING_SELECT == 3
        assert ComponentType.TEXT_INPUT == 4
        assert ComponentType.USER_SELECT == 5
        assert ComponentType.ROLE_SELECT == 6
        assert ComponentType.MENTIONABLE_SELECT == 7
        assert ComponentType.CHANNEL_SELECT == 8

    def test_button_style_values(self):
        """Test ButtonStyle enum has correct values."""
        assert ButtonStyle.PRIMARY == 1
        assert ButtonStyle.SECONDARY == 2
        assert ButtonStyle.SUCCESS == 3
        assert ButtonStyle.DANGER == 4
        assert ButtonStyle.LINK == 5


# ==============================================================================
# Valid Signature Verification Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.security
class TestValidSignatureVerification:
    """Tests for valid Discord signature verification."""

    def test_valid_signature_returns_true(self, valid_signature_data):
        """Test that a valid signature is accepted."""
        with patch.dict('os.environ', {'DISCORD_PUBLIC_KEY': valid_signature_data['public_key']}):
            result = verify_discord_signature(
                valid_signature_data['signature'],
                valid_signature_data['timestamp'],
                valid_signature_data['body']
            )

            assert result is True

    def test_valid_signature_with_complex_body(self, discord_keypair):
        """Test signature verification with complex JSON body."""
        timestamp = str(int(time.time()))
        body = '{"type":2,"data":{"custom_id":"verify_email","components":[{"type":1}]}}'
        message = f"{timestamp}{body}".encode()

        signature = discord_keypair['signing_key'].sign(message).signature

        with patch.dict('os.environ', {'DISCORD_PUBLIC_KEY': discord_keypair['public_key_hex']}):
            result = verify_discord_signature(
                signature.hex(),
                timestamp,
                body
            )

            assert result is True

    def test_valid_signature_at_time_boundary(self, discord_keypair):
        """Test signature verification at 299 seconds (just under 5 min limit)."""
        # Create timestamp 299 seconds ago (just within the 300 second limit)
        old_timestamp = str(int(time.time()) - 299)
        body = '{"type":1}'
        message = f"{old_timestamp}{body}".encode()

        signature = discord_keypair['signing_key'].sign(message).signature

        with patch.dict('os.environ', {'DISCORD_PUBLIC_KEY': discord_keypair['public_key_hex']}):
            result = verify_discord_signature(
                signature.hex(),
                old_timestamp,
                body
            )

            assert result is True


# ==============================================================================
# Replay Attack Prevention Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.security
class TestReplayAttackPrevention:
    """Tests for timestamp-based replay attack prevention."""

    def test_old_timestamp_rejected(self, discord_keypair):
        """Test that requests older than 5 minutes are rejected."""
        # Create timestamp 301 seconds ago (beyond the 300 second limit)
        old_timestamp = str(int(time.time()) - 301)
        body = '{"type":1}'
        message = f"{old_timestamp}{body}".encode()

        signature = discord_keypair['signing_key'].sign(message).signature

        with patch.dict('os.environ', {'DISCORD_PUBLIC_KEY': discord_keypair['public_key_hex']}):
            result = verify_discord_signature(
                signature.hex(),
                old_timestamp,
                body
            )

            assert result is False

    def test_future_timestamp_rejected(self, discord_keypair):
        """Test that requests with future timestamps are rejected."""
        # Create timestamp 301 seconds in the future
        future_timestamp = str(int(time.time()) + 301)
        body = '{"type":1}'
        message = f"{future_timestamp}{body}".encode()

        signature = discord_keypair['signing_key'].sign(message).signature

        with patch.dict('os.environ', {'DISCORD_PUBLIC_KEY': discord_keypair['public_key_hex']}):
            result = verify_discord_signature(
                signature.hex(),
                future_timestamp,
                body
            )

            assert result is False

    def test_invalid_timestamp_format_rejected(self, valid_signature_data):
        """Test that non-numeric timestamps are rejected."""
        with patch.dict('os.environ', {'DISCORD_PUBLIC_KEY': valid_signature_data['public_key']}):
            result = verify_discord_signature(
                valid_signature_data['signature'],
                'not-a-number',
                valid_signature_data['body']
            )

            assert result is False

    def test_empty_timestamp_rejected(self, valid_signature_data):
        """Test that empty timestamps are rejected."""
        with patch.dict('os.environ', {'DISCORD_PUBLIC_KEY': valid_signature_data['public_key']}):
            result = verify_discord_signature(
                valid_signature_data['signature'],
                '',
                valid_signature_data['body']
            )

            assert result is False


# ==============================================================================
# Invalid Signature Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.security
class TestInvalidSignatures:
    """Tests for invalid signature rejection."""

    def test_wrong_signature_rejected(self, valid_signature_data):
        """Test that an incorrect signature is rejected."""
        # Modify the signature to make it invalid
        wrong_signature = 'a' * 128  # 64 bytes in hex

        with patch.dict('os.environ', {'DISCORD_PUBLIC_KEY': valid_signature_data['public_key']}):
            result = verify_discord_signature(
                wrong_signature,
                valid_signature_data['timestamp'],
                valid_signature_data['body']
            )

            assert result is False

    def test_tampered_body_rejected(self, valid_signature_data):
        """Test that a tampered body is rejected."""
        tampered_body = '{"type":2}'  # Different from signed body

        with patch.dict('os.environ', {'DISCORD_PUBLIC_KEY': valid_signature_data['public_key']}):
            result = verify_discord_signature(
                valid_signature_data['signature'],
                valid_signature_data['timestamp'],
                tampered_body
            )

            assert result is False

    def test_invalid_signature_format_rejected(self, valid_signature_data):
        """Test that invalid signature format is rejected."""
        with patch.dict('os.environ', {'DISCORD_PUBLIC_KEY': valid_signature_data['public_key']}):
            result = verify_discord_signature(
                'not-valid-hex',
                valid_signature_data['timestamp'],
                valid_signature_data['body']
            )

            assert result is False


# ==============================================================================
# Environment Variable Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.security
class TestEnvironmentVariables:
    """Tests for environment variable handling."""

    def test_missing_public_key_rejected(self, valid_signature_data):
        """Test that requests are rejected when DISCORD_PUBLIC_KEY is missing."""
        with patch.dict('os.environ', {}, clear=True):
            result = verify_discord_signature(
                valid_signature_data['signature'],
                valid_signature_data['timestamp'],
                valid_signature_data['body']
            )

            assert result is False

    def test_invalid_public_key_format_rejected(self, valid_signature_data):
        """Test that invalid public key format is rejected."""
        with patch.dict('os.environ', {'DISCORD_PUBLIC_KEY': 'invalid-hex-key'}):
            result = verify_discord_signature(
                valid_signature_data['signature'],
                valid_signature_data['timestamp'],
                valid_signature_data['body']
            )

            assert result is False


# ==============================================================================
# Edge Cases and Security Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.security
class TestEdgeCasesAndSecurity:
    """Tests for edge cases and security scenarios."""

    def test_empty_body_signature_verification(self, discord_keypair):
        """Test signature verification with empty body."""
        timestamp = str(int(time.time()))
        body = ''
        message = f"{timestamp}{body}".encode()

        signature = discord_keypair['signing_key'].sign(message).signature

        with patch.dict('os.environ', {'DISCORD_PUBLIC_KEY': discord_keypair['public_key_hex']}):
            result = verify_discord_signature(
                signature.hex(),
                timestamp,
                body
            )

            # Empty body should still verify correctly if signed
            assert result is True

    def test_unicode_body_signature_verification(self, discord_keypair):
        """Test signature verification with unicode characters in body."""
        timestamp = str(int(time.time()))
        body = '{"message":"Hello 世界 🌍"}'
        message = f"{timestamp}{body}".encode()

        signature = discord_keypair['signing_key'].sign(message).signature

        with patch.dict('os.environ', {'DISCORD_PUBLIC_KEY': discord_keypair['public_key_hex']}):
            result = verify_discord_signature(
                signature.hex(),
                timestamp,
                body
            )

            assert result is True

    def test_exception_handling_returns_false(self, valid_signature_data):
        """Test that unexpected exceptions are caught and return False."""
        # Mock VerifyKey to raise an unexpected exception
        with patch('discord_interactions.VerifyKey') as mock_verify_key:
            mock_verify_key.side_effect = RuntimeError("Unexpected error")

            with patch.dict('os.environ', {'DISCORD_PUBLIC_KEY': valid_signature_data['public_key']}):
                result = verify_discord_signature(
                    valid_signature_data['signature'],
                    valid_signature_data['timestamp'],
                    valid_signature_data['body']
                )

                assert result is False


# ==============================================================================
# Integration-Style Tests
# ==============================================================================

@pytest.mark.unit
class TestSignatureVerificationIntegration:
    """Integration-style tests for signature verification workflow."""

    def test_complete_signature_workflow(self, discord_keypair):
        """Test complete signature generation and verification workflow."""
        # Simulate Discord signing a request
        timestamp = str(int(time.time()))
        body = '{"type":2,"data":{"name":"verify"}}'
        message = f"{timestamp}{body}".encode()

        # Sign with private key (what Discord does)
        signature = discord_keypair['signing_key'].sign(message).signature

        # Verify with public key (what our Lambda does)
        with patch.dict('os.environ', {'DISCORD_PUBLIC_KEY': discord_keypair['public_key_hex']}):
            result = verify_discord_signature(
                signature.hex(),
                timestamp,
                body
            )

            assert result is True

    def test_signature_verification_with_all_interaction_types(self, discord_keypair):
        """Test signature verification works with all interaction types."""
        for interaction_type in InteractionType:
            timestamp = str(int(time.time()))
            body = f'{{"type":{interaction_type.value}}}'
            message = f"{timestamp}{body}".encode()

            signature = discord_keypair['signing_key'].sign(message).signature

            with patch.dict('os.environ', {'DISCORD_PUBLIC_KEY': discord_keypair['public_key_hex']}):
                result = verify_discord_signature(
                    signature.hex(),
                    timestamp,
                    body
                )

                assert result is True, f"Failed for interaction type {interaction_type.name}"
