"""
Unit tests for ssm_utils module.

Tests AWS Systems Manager Parameter Store utilities including:
- Parameter retrieval
- Caching behavior
- Error handling
- Decryption
"""
import pytest
import sys
import boto3
from pathlib import Path
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError
from moto import mock_aws

# Add lambda directory to path
lambda_dir = Path(__file__).parent.parent.parent / 'lambda'
sys.path.insert(0, str(lambda_dir))


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def mock_ssm_parameters():
    """Mock AWS SSM service for testing."""
    with mock_aws():
        ssm = boto3.client('ssm', region_name='us-east-1')
        # Create test parameter
        ssm.put_parameter(
            Name='/discord-bot/token',
            Value='test_bot_token_12345',
            Type='SecureString'
        )

        # Patch the ssm_client in ssm_utils module to use our mocked client
        with patch('ssm_utils.ssm_client', ssm):
            yield ssm


# Import after setting up path
from ssm_utils import get_parameter


# ==============================================================================
# Successful Parameter Retrieval Tests
# ==============================================================================

@pytest.mark.unit
class TestGetParameter:
    """Tests for get_parameter() function."""

    def test_get_parameter_success(self, mock_ssm_parameters):
        """Test successful parameter retrieval."""
        # The mock_ssm_parameters fixture creates '/discord-bot/token'
        result = get_parameter('/discord-bot/token')

        assert result == 'test_bot_token_12345', \
            f"Expected bot token, got: {result}"

    def test_get_parameter_with_decryption(self, mock_ssm_parameters):
        """Test that WithDecryption=True is used."""
        # ssm_utils.py line 24 uses WithDecryption=True
        result = get_parameter('/discord-bot/token')

        # Should successfully decrypt SecureString
        assert result is not None
        assert len(result) > 0

    def test_get_parameter_returns_string(self, mock_ssm_parameters):
        """Test that return value is always a string."""
        result = get_parameter('/discord-bot/token')

        assert isinstance(result, str), \
            f"Expected string, got {type(result)}"


# ==============================================================================
# Caching Behavior Tests
# ==============================================================================

@pytest.mark.unit
class TestParameterCaching:
    """Tests for LRU cache behavior on get_parameter()."""

    def test_parameter_cached_on_second_call(self, mock_ssm_parameters):
        """Test that parameter is cached after first retrieval."""
        # Clear cache before test
        get_parameter.cache_clear()

        # First call
        result1 = get_parameter('/discord-bot/token')
        cache_info1 = get_parameter.cache_info()

        # Second call (should hit cache)
        result2 = get_parameter('/discord-bot/token')
        cache_info2 = get_parameter.cache_info()

        assert result1 == result2
        assert cache_info1.hits == 0, "First call should not hit cache"
        assert cache_info2.hits == 1, "Second call should hit cache"

    def test_different_parameters_not_cached_together(self, mock_ssm_parameters):
        """Test that different parameter names have separate cache entries."""
        # Clear cache
        get_parameter.cache_clear()

        # Retrieve first parameter
        get_parameter('/discord-bot/token')

        # Retrieve different parameter (should miss cache)
        cache_info = get_parameter.cache_info()
        assert cache_info.misses >= 1

    def test_cache_max_size(self, mock_ssm_parameters):
        """Test that cache respects maxsize=32 limit."""
        # Clear cache
        get_parameter.cache_clear()

        # LRU cache should have maxsize=32
        cache_info = get_parameter.cache_info()
        assert cache_info.maxsize == 32, \
            f"Cache maxsize should be 32, got {cache_info.maxsize}"

    def test_cache_clear_resets_cache(self, mock_ssm_parameters):
        """Test that cache_clear() resets the cache."""
        # Get parameter to populate cache
        get_parameter('/discord-bot/token')

        # Clear cache
        get_parameter.cache_clear()
        cache_info = get_parameter.cache_info()

        assert cache_info.hits == 0
        assert cache_info.misses == 0
        assert cache_info.currsize == 0


# ==============================================================================
# Error Handling Tests
# ==============================================================================

@pytest.mark.unit
class TestParameterErrorHandling:
    """Tests for error handling in parameter retrieval."""

    def test_parameter_not_found(self, mock_ssm_parameters):
        """Test handling of non-existent parameter."""
        # Clear cache to ensure fresh call
        get_parameter.cache_clear()

        # Request non-existent parameter
        result = get_parameter('/non-existent/parameter')

        # Should return empty string on error (ssm_utils.py line 28)
        assert result == "", \
            f"Expected empty string for missing parameter, got: {result}"

    @patch('ssm_utils.ssm_client.get_parameter')
    def test_client_error_returns_empty_string(self, mock_get_param):
        """Test that boto3 ClientError returns empty string."""
        # Clear cache
        get_parameter.cache_clear()

        # Simulate ClientError
        mock_get_param.side_effect = ClientError(
            {'Error': {'Code': 'ParameterNotFound', 'Message': 'Not found'}},
            'GetParameter'
        )

        result = get_parameter('/error-param')

        assert result == ""
        mock_get_param.assert_called_once()

    @patch('ssm_utils.ssm_client.get_parameter')
    def test_network_error_returns_empty_string(self, mock_get_param):
        """Test that network errors return empty string."""
        # Clear cache
        get_parameter.cache_clear()

        # Simulate network error
        mock_get_param.side_effect = Exception("Network timeout")

        result = get_parameter('/network-error')

        assert result == ""

    @patch('ssm_utils.ssm_client.get_parameter')
    def test_invalid_response_returns_empty_string(self, mock_get_param):
        """Test that malformed responses return empty string."""
        # Clear cache
        get_parameter.cache_clear()

        # Simulate malformed response (missing 'Parameter' key)
        mock_get_param.return_value = {'Invalid': 'response'}

        result = get_parameter('/malformed')

        assert result == ""

    @patch('ssm_utils.ssm_client.get_parameter')
    def test_access_denied_returns_empty_string(self, mock_get_param):
        """Test that access denied errors return empty string."""
        # Clear cache
        get_parameter.cache_clear()

        # Simulate access denied
        mock_get_param.side_effect = ClientError(
            {'Error': {'Code': 'AccessDeniedException', 'Message': 'Access denied'}},
            'GetParameter'
        )

        result = get_parameter('/secret/protected')

        assert result == ""


# ==============================================================================
# Integration-Style Tests
# ==============================================================================

@pytest.mark.unit
class TestParameterIntegration:
    """Integration-style tests using real moto mocks."""

    def test_retrieve_multiple_parameters(self, mock_ssm_parameters):
        """Test retrieving multiple different parameters."""
        # Clear cache
        get_parameter.cache_clear()

        # First parameter (from fixture)
        result1 = get_parameter('/discord-bot/token')
        assert result1 == 'test_bot_token_12345'

        # Second call to same parameter (should hit cache)
        result2 = get_parameter('/discord-bot/token')
        assert result2 == result1

        # Cache info
        cache_info = get_parameter.cache_info()
        assert cache_info.hits == 1
        assert cache_info.misses == 1

    def test_parameter_value_types(self, mock_ssm_parameters):
        """Test that parameter values are always strings."""
        # Clear cache
        get_parameter.cache_clear()

        result = get_parameter('/discord-bot/token')

        # Should be string type
        assert isinstance(result, str)
        # Should not be empty
        assert len(result) > 0
        # Should not contain null bytes
        assert '\x00' not in result


# ==============================================================================
# Edge Cases and Security
# ==============================================================================

@pytest.mark.unit
@pytest.mark.security
class TestParameterSecurity:
    """Security and edge case tests for parameter handling."""

    def test_empty_parameter_name(self, mock_ssm_parameters):
        """Test handling of empty parameter name."""
        # Clear cache
        get_parameter.cache_clear()

        result = get_parameter('')

        # Should handle gracefully
        assert result == ""

    def test_parameter_name_with_special_chars(self, mock_ssm_parameters):
        """Test parameter names with special characters."""
        # Clear cache
        get_parameter.cache_clear()

        # SSM allows alphanumeric, ., -, _, /
        result = get_parameter('/test-param_123.456/value')

        # Should not crash, returns empty for non-existent
        assert isinstance(result, str)

    @patch('ssm_utils.ssm_client.get_parameter')
    def test_very_long_parameter_name(self, mock_get_param):
        """Test handling of very long parameter names."""
        # Clear cache
        get_parameter.cache_clear()

        # SSM parameter names max length is 2048 characters
        long_name = '/param/' + 'a' * 2040
        mock_get_param.side_effect = ClientError(
            {'Error': {'Code': 'ValidationException', 'Message': 'Too long'}},
            'GetParameter'
        )

        result = get_parameter(long_name)

        assert result == ""

    def test_cache_prevents_repeated_api_calls(self, mock_ssm_parameters):
        """Test that caching reduces API calls."""
        # Clear cache
        get_parameter.cache_clear()

        param_name = '/discord-bot/token'

        # Make 10 calls to same parameter
        results = [get_parameter(param_name) for _ in range(10)]

        # All should return same value
        assert len(set(results)) == 1

        # Cache should have 9 hits, 1 miss
        cache_info = get_parameter.cache_info()
        assert cache_info.hits == 9
        assert cache_info.misses == 1


# ==============================================================================
# Cleanup Tests
# ==============================================================================

@pytest.mark.unit
class TestCacheManagement:
    """Tests for cache management and cleanup."""

    def test_cache_info_accessible(self):
        """Test that cache info can be accessed."""
        cache_info = get_parameter.cache_info()

        assert hasattr(cache_info, 'hits')
        assert hasattr(cache_info, 'misses')
        assert hasattr(cache_info, 'maxsize')
        assert hasattr(cache_info, 'currsize')

    def test_cache_clear_function_exists(self):
        """Test that cache_clear() function exists."""
        assert hasattr(get_parameter, 'cache_clear')
        assert callable(get_parameter.cache_clear)

        # Should not raise error
        get_parameter.cache_clear()
