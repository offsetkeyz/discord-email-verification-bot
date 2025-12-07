"""
Unit tests for discord_api module.

Tests Discord REST API operations including:
- Role checking (user_has_role)
- Role assignment (assign_role)
- Error handling for API failures
- Logging integration
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import responses

# Add lambda directory to path
lambda_dir = Path(__file__).parent.parent.parent / 'lambda'
sys.path.insert(0, str(lambda_dir))


# ==============================================================================
# Test Fixtures
# ==============================================================================

@pytest.fixture
def mock_logging():
    """Mock logging_utils to isolate API tests."""
    with patch('discord_api.log_discord_error') as mock_log:
        yield mock_log


@pytest.fixture
def discord_test_data():
    """Common test data for Discord API calls."""
    return {
        'user_id': '123456789012345678',
        'guild_id': '987654321098765432',
        'role_id': '111222333444555666',
        'bot_token': 'TEST_BOT_TOKEN_FOR_UNIT_TESTS_NOT_REAL'
    }


# Import after mocking to avoid initialization issues
from discord_api import user_has_role, assign_role


# ==============================================================================
# user_has_role() - Success Cases
# ==============================================================================

@pytest.mark.unit
class TestUserHasRoleSuccess:
    """Tests for successful user_has_role() calls."""

    @responses.activate
    def test_user_has_role_returns_true(self, discord_test_data, mock_logging):
        """Test that user_has_role returns True when user has the role."""
        url = f"https://discord.com/api/v10/guilds/{discord_test_data['guild_id']}/members/{discord_test_data['user_id']}"

        responses.add(
            responses.GET,
            url,
            json={'roles': [discord_test_data['role_id'], '777888999000111222']},
            status=200
        )

        result = user_has_role(
            discord_test_data['user_id'],
            discord_test_data['guild_id'],
            discord_test_data['role_id'],
            discord_test_data['bot_token']
        )

        assert result is True

    @responses.activate
    def test_user_does_not_have_role_returns_false(self, discord_test_data, mock_logging):
        """Test that user_has_role returns False when user lacks the role."""
        url = f"https://discord.com/api/v10/guilds/{discord_test_data['guild_id']}/members/{discord_test_data['user_id']}"

        responses.add(
            responses.GET,
            url,
            json={'roles': ['777888999000111222', '333444555666777888']},
            status=200
        )

        result = user_has_role(
            discord_test_data['user_id'],
            discord_test_data['guild_id'],
            discord_test_data['role_id'],
            discord_test_data['bot_token']
        )

        assert result is False

    @responses.activate
    def test_user_has_role_correct_headers(self, discord_test_data, mock_logging):
        """Test that user_has_role sends correct authorization headers."""
        url = f"https://discord.com/api/v10/guilds/{discord_test_data['guild_id']}/members/{discord_test_data['user_id']}"

        responses.add(
            responses.GET,
            url,
            json={'roles': []},
            status=200
        )

        user_has_role(
            discord_test_data['user_id'],
            discord_test_data['guild_id'],
            discord_test_data['role_id'],
            discord_test_data['bot_token']
        )

        # Check request headers
        assert len(responses.calls) == 1
        assert responses.calls[0].request.headers['Authorization'] == f"Bot {discord_test_data['bot_token']}"
        assert responses.calls[0].request.headers['Content-Type'] == 'application/json'


# ==============================================================================
# user_has_role() - Error Cases
# ==============================================================================

@pytest.mark.unit
class TestUserHasRoleErrors:
    """Tests for error handling in user_has_role()."""

    @responses.activate
    def test_user_has_role_not_found_returns_false(self, discord_test_data, mock_logging):
        """Test that 404 response returns False."""
        url = f"https://discord.com/api/v10/guilds/{discord_test_data['guild_id']}/members/{discord_test_data['user_id']}"

        responses.add(
            responses.GET,
            url,
            json={'code': 10007, 'message': 'Unknown Member'},
            status=404
        )

        result = user_has_role(
            discord_test_data['user_id'],
            discord_test_data['guild_id'],
            discord_test_data['role_id'],
            discord_test_data['bot_token']
        )

        assert result is False
        # Verify error was logged
        mock_logging.assert_called_once_with('get_member', 404, 10007)

    @responses.activate
    def test_user_has_role_unauthorized_returns_false(self, discord_test_data, mock_logging):
        """Test that 401 Unauthorized returns False."""
        url = f"https://discord.com/api/v10/guilds/{discord_test_data['guild_id']}/members/{discord_test_data['user_id']}"

        responses.add(
            responses.GET,
            url,
            json={'code': 40001, 'message': 'Unauthorized'},
            status=401
        )

        result = user_has_role(
            discord_test_data['user_id'],
            discord_test_data['guild_id'],
            discord_test_data['role_id'],
            discord_test_data['bot_token']
        )

        assert result is False
        mock_logging.assert_called_once_with('get_member', 401, 40001)

    @responses.activate
    def test_user_has_role_rate_limited_returns_false(self, discord_test_data, mock_logging):
        """Test that rate limit (429) returns False."""
        url = f"https://discord.com/api/v10/guilds/{discord_test_data['guild_id']}/members/{discord_test_data['user_id']}"

        responses.add(
            responses.GET,
            url,
            json={'code': 42900, 'message': 'Rate limited'},
            status=429
        )

        result = user_has_role(
            discord_test_data['user_id'],
            discord_test_data['guild_id'],
            discord_test_data['role_id'],
            discord_test_data['bot_token']
        )

        assert result is False

    @responses.activate
    def test_user_has_role_network_error_returns_false(self, discord_test_data, mock_logging):
        """Test that network errors return False."""
        url = f"https://discord.com/api/v10/guilds/{discord_test_data['guild_id']}/members/{discord_test_data['user_id']}"

        responses.add(
            responses.GET,
            url,
            body=Exception("Connection timeout")
        )

        result = user_has_role(
            discord_test_data['user_id'],
            discord_test_data['guild_id'],
            discord_test_data['role_id'],
            discord_test_data['bot_token']
        )

        assert result is False


# ==============================================================================
# assign_role() - Success Cases
# ==============================================================================

@pytest.mark.unit
class TestAssignRoleSuccess:
    """Tests for successful assign_role() calls."""

    @responses.activate
    def test_assign_role_success_returns_true(self, discord_test_data, mock_logging):
        """Test that assign_role returns True on 204 No Content."""
        url = f"https://discord.com/api/v10/guilds/{discord_test_data['guild_id']}/members/{discord_test_data['user_id']}/roles/{discord_test_data['role_id']}"

        responses.add(
            responses.PUT,
            url,
            status=204
        )

        result = assign_role(
            discord_test_data['user_id'],
            discord_test_data['guild_id'],
            discord_test_data['role_id'],
            discord_test_data['bot_token']
        )

        assert result is True

    @responses.activate
    def test_assign_role_correct_headers(self, discord_test_data, mock_logging):
        """Test that assign_role sends correct authorization headers."""
        url = f"https://discord.com/api/v10/guilds/{discord_test_data['guild_id']}/members/{discord_test_data['user_id']}/roles/{discord_test_data['role_id']}"

        responses.add(
            responses.PUT,
            url,
            status=204
        )

        assign_role(
            discord_test_data['user_id'],
            discord_test_data['guild_id'],
            discord_test_data['role_id'],
            discord_test_data['bot_token']
        )

        # Check request headers
        assert len(responses.calls) == 1
        assert responses.calls[0].request.headers['Authorization'] == f"Bot {discord_test_data['bot_token']}"
        assert responses.calls[0].request.headers['Content-Type'] == 'application/json'


# ==============================================================================
# assign_role() - Error Cases
# ==============================================================================

@pytest.mark.unit
class TestAssignRoleErrors:
    """Tests for error handling in assign_role()."""

    @responses.activate
    def test_assign_role_not_found_returns_false(self, discord_test_data, mock_logging):
        """Test that 404 response returns False."""
        url = f"https://discord.com/api/v10/guilds/{discord_test_data['guild_id']}/members/{discord_test_data['user_id']}/roles/{discord_test_data['role_id']}"

        responses.add(
            responses.PUT,
            url,
            json={'code': 10007, 'message': 'Unknown Member'},
            status=404
        )

        result = assign_role(
            discord_test_data['user_id'],
            discord_test_data['guild_id'],
            discord_test_data['role_id'],
            discord_test_data['bot_token']
        )

        assert result is False

    @responses.activate
    def test_assign_role_forbidden_returns_false(self, discord_test_data, mock_logging):
        """Test that 403 Forbidden returns False."""
        url = f"https://discord.com/api/v10/guilds/{discord_test_data['guild_id']}/members/{discord_test_data['user_id']}/roles/{discord_test_data['role_id']}"

        responses.add(
            responses.PUT,
            url,
            json={'code': 50013, 'message': 'Missing Permissions'},
            status=403
        )

        result = assign_role(
            discord_test_data['user_id'],
            discord_test_data['guild_id'],
            discord_test_data['role_id'],
            discord_test_data['bot_token']
        )

        assert result is False
        mock_logging.assert_called_once_with('assign_role', 403, 50013)

    @responses.activate
    def test_assign_role_rate_limited_returns_false(self, discord_test_data, mock_logging):
        """Test that rate limit (429) returns False."""
        url = f"https://discord.com/api/v10/guilds/{discord_test_data['guild_id']}/members/{discord_test_data['user_id']}/roles/{discord_test_data['role_id']}"

        responses.add(
            responses.PUT,
            url,
            json={'code': 42900, 'message': 'Rate limited'},
            status=429
        )

        result = assign_role(
            discord_test_data['user_id'],
            discord_test_data['guild_id'],
            discord_test_data['role_id'],
            discord_test_data['bot_token']
        )

        assert result is False

    @responses.activate
    def test_assign_role_network_error_returns_false(self, discord_test_data, mock_logging):
        """Test that network errors return False."""
        url = f"https://discord.com/api/v10/guilds/{discord_test_data['guild_id']}/members/{discord_test_data['user_id']}/roles/{discord_test_data['role_id']}"

        responses.add(
            responses.PUT,
            url,
            body=Exception("Connection timeout")
        )

        result = assign_role(
            discord_test_data['user_id'],
            discord_test_data['guild_id'],
            discord_test_data['role_id'],
            discord_test_data['bot_token']
        )

        assert result is False


# ==============================================================================
# API Integration Tests
# ==============================================================================

@pytest.mark.unit
class TestAPIIntegration:
    """Integration-style tests for API workflows."""

    @responses.activate
    def test_check_then_assign_role_workflow(self, discord_test_data, mock_logging):
        """Test complete workflow: check role, then assign if missing."""
        # Setup: User doesn't have role
        check_url = f"https://discord.com/api/v10/guilds/{discord_test_data['guild_id']}/members/{discord_test_data['user_id']}"
        assign_url = f"https://discord.com/api/v10/guilds/{discord_test_data['guild_id']}/members/{discord_test_data['user_id']}/roles/{discord_test_data['role_id']}"

        responses.add(
            responses.GET,
            check_url,
            json={'roles': []},
            status=200
        )

        responses.add(
            responses.PUT,
            assign_url,
            status=204
        )

        # Check role (should be False)
        has_role = user_has_role(
            discord_test_data['user_id'],
            discord_test_data['guild_id'],
            discord_test_data['role_id'],
            discord_test_data['bot_token']
        )

        assert has_role is False

        # Assign role (should succeed)
        assigned = assign_role(
            discord_test_data['user_id'],
            discord_test_data['guild_id'],
            discord_test_data['role_id'],
            discord_test_data['bot_token']
        )

        assert assigned is True

    @responses.activate
    def test_api_v10_endpoint_used(self, discord_test_data, mock_logging):
        """Test that Discord API v10 endpoints are used."""
        url = f"https://discord.com/api/v10/guilds/{discord_test_data['guild_id']}/members/{discord_test_data['user_id']}"

        responses.add(
            responses.GET,
            url,
            json={'roles': []},
            status=200
        )

        user_has_role(
            discord_test_data['user_id'],
            discord_test_data['guild_id'],
            discord_test_data['role_id'],
            discord_test_data['bot_token']
        )

        assert '/api/v10/' in responses.calls[0].request.url

    @responses.activate
    def test_user_already_has_role_no_assign_needed(self, discord_test_data, mock_logging):
        """Test that we can detect when user already has role (no assign needed)."""
        url = f"https://discord.com/api/v10/guilds/{discord_test_data['guild_id']}/members/{discord_test_data['user_id']}"

        responses.add(
            responses.GET,
            url,
            json={'roles': [discord_test_data['role_id']]},
            status=200
        )

        has_role = user_has_role(
            discord_test_data['user_id'],
            discord_test_data['guild_id'],
            discord_test_data['role_id'],
            discord_test_data['bot_token']
        )

        assert has_role is True


# ==============================================================================
# Edge Cases and Security Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.security
class TestEdgeCasesAndSecurity:
    """Tests for edge cases and security considerations."""

    @responses.activate
    def test_empty_roles_list_handled(self, discord_test_data, mock_logging):
        """Test that empty roles list is handled correctly."""
        url = f"https://discord.com/api/v10/guilds/{discord_test_data['guild_id']}/members/{discord_test_data['user_id']}"

        responses.add(
            responses.GET,
            url,
            json={'roles': []},
            status=200
        )

        result = user_has_role(
            discord_test_data['user_id'],
            discord_test_data['guild_id'],
            discord_test_data['role_id'],
            discord_test_data['bot_token']
        )

        assert result is False

    @responses.activate
    def test_missing_roles_key_handled(self, discord_test_data, mock_logging):
        """Test that missing 'roles' key in response is handled."""
        url = f"https://discord.com/api/v10/guilds/{discord_test_data['guild_id']}/members/{discord_test_data['user_id']}"

        responses.add(
            responses.GET,
            url,
            json={'user': {}, 'nick': None},  # No 'roles' key
            status=200
        )

        result = user_has_role(
            discord_test_data['user_id'],
            discord_test_data['guild_id'],
            discord_test_data['role_id'],
            discord_test_data['bot_token']
        )

        # Should return False for missing roles key
        assert result is False

    @responses.activate
    def test_bot_token_not_logged(self, discord_test_data, mock_logging):
        """Test that bot token is not exposed in error messages."""
        url = f"https://discord.com/api/v10/guilds/{discord_test_data['guild_id']}/members/{discord_test_data['user_id']}"

        responses.add(
            responses.GET,
            url,
            json={'code': 40001, 'message': 'Unauthorized'},
            status=401
        )

        user_has_role(
            discord_test_data['user_id'],
            discord_test_data['guild_id'],
            discord_test_data['role_id'],
            discord_test_data['bot_token']
        )

        # Verify token is not in log calls
        if mock_logging.called:
            for call in mock_logging.call_args_list:
                args_str = str(call)
                assert discord_test_data['bot_token'] not in args_str, \
                    "Bot token should not appear in log messages"
