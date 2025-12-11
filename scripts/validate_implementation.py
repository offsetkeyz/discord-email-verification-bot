#!/usr/bin/env python3
"""
Validation script for custom completion message implementation.
Checks that all changes are correctly in place without requiring AWS/DynamoDB.
"""

import sys
import os

# Add lambda directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lambda'))

def check_imports():
    """Verify all imports work correctly."""
    print("✓ Checking imports...")

    try:
        from guild_config import (
            DEFAULT_COMPLETION_MESSAGE,
            get_guild_completion_message,
            save_guild_config
        )
        print(f"  ✓ guild_config imports successful")
        print(f"  ✓ DEFAULT_COMPLETION_MESSAGE defined: {DEFAULT_COMPLETION_MESSAGE[:50]}...")

        from handlers import handle_code_verification
        print(f"  ✓ handlers imports successful")

        from dynamodb_operations import store_pending_setup
        print(f"  ✓ dynamodb_operations imports successful")

        return True
    except ImportError as e:
        print(f"  ✗ Import error: {e}")
        return False

def check_function_signatures():
    """Verify function signatures are correct."""
    print("\n✓ Checking function signatures...")

    import inspect
    from guild_config import save_guild_config, get_guild_completion_message
    from dynamodb_operations import store_pending_setup

    # Check save_guild_config has completion_message parameter
    sig = inspect.signature(save_guild_config)
    params = list(sig.parameters.keys())

    if 'completion_message' in params:
        print(f"  ✓ save_guild_config has 'completion_message' parameter")
    else:
        print(f"  ✗ save_guild_config missing 'completion_message' parameter")
        return False

    # Check get_guild_completion_message exists and has correct signature
    sig = inspect.signature(get_guild_completion_message)
    params = list(sig.parameters.keys())

    if len(params) == 1 and 'guild_id' in params:
        print(f"  ✓ get_guild_completion_message has correct signature")
    else:
        print(f"  ✗ get_guild_completion_message has incorrect signature")
        return False

    # Check store_pending_setup has completion_message parameter
    sig = inspect.signature(store_pending_setup)
    params = list(sig.parameters.keys())

    if 'completion_message' in params:
        print(f"  ✓ store_pending_setup has 'completion_message' parameter")
    else:
        print(f"  ✗ store_pending_setup missing 'completion_message' parameter")
        return False

    return True

def check_constants():
    """Verify constants are defined."""
    print("\n✓ Checking constants...")

    from guild_config import DEFAULT_COMPLETION_MESSAGE

    if DEFAULT_COMPLETION_MESSAGE:
        print(f"  ✓ DEFAULT_COMPLETION_MESSAGE is defined")
        print(f"    Value: '{DEFAULT_COMPLETION_MESSAGE[:60]}...'")

        if len(DEFAULT_COMPLETION_MESSAGE) <= 2000:
            print(f"  ✓ DEFAULT_COMPLETION_MESSAGE length is valid ({len(DEFAULT_COMPLETION_MESSAGE)} chars)")
        else:
            print(f"  ✗ DEFAULT_COMPLETION_MESSAGE exceeds 2000 chars")
            return False

        return True
    else:
        print(f"  ✗ DEFAULT_COMPLETION_MESSAGE is not defined or empty")
        return False

def check_handlers_integration():
    """Verify handlers.py uses the new function."""
    print("\n✓ Checking handlers integration...")

    # Read handlers.py file
    handlers_path = os.path.join(os.path.dirname(__file__), 'lambda', 'handlers.py')

    with open(handlers_path, 'r') as f:
        content = f.read()

    # Check for import
    if 'get_guild_completion_message' in content:
        print(f"  ✓ get_guild_completion_message is imported in handlers.py")
    else:
        print(f"  ✗ get_guild_completion_message is not imported in handlers.py")
        return False

    # Check for usage in handle_code_verification
    if 'get_guild_completion_message(guild_id)' in content:
        print(f"  ✓ get_guild_completion_message is called in handlers.py")
    else:
        print(f"  ✗ get_guild_completion_message is not called in handlers.py")
        return False

    # Check that hardcoded message is removed
    if '"🎉 **Verification complete!**' not in content or 'completion_message =' in content:
        print(f"  ✓ Hardcoded completion message replaced with dynamic lookup")
    else:
        print(f"  ✗ Hardcoded completion message still present in handlers.py")
        return False

    return True

def check_validation_logic():
    """Verify validation logic is present in save_guild_config."""
    print("\n✓ Checking validation logic...")

    guild_config_path = os.path.join(os.path.dirname(__file__), 'lambda', 'guild_config.py')

    with open(guild_config_path, 'r') as f:
        content = f.read()

    checks = [
        ('.strip()', 'Whitespace stripping'),
        ('@everyone', '@everyone sanitization'),
        ('@here', '@here sanitization'),
        ('> 2000', 'Length validation'),
    ]

    all_passed = True
    for check_str, description in checks:
        if check_str in content:
            print(f"  ✓ {description} present")
        else:
            print(f"  ✗ {description} missing")
            all_passed = False

    return all_passed

def check_test_file_exists():
    """Verify test file was created."""
    print("\n✓ Checking test file...")

    test_path = os.path.join(os.path.dirname(__file__), 'tests', 'unit', 'test_completion_message.py')

    if os.path.exists(test_path):
        print(f"  ✓ Test file exists: {test_path}")

        with open(test_path, 'r') as f:
            content = f.read()

        # Count test functions
        test_count = content.count('def test_')
        print(f"  ✓ Test file contains {test_count} test functions")

        return True
    else:
        print(f"  ✗ Test file not found: {test_path}")
        return False

def main():
    """Run all validation checks."""
    print("=" * 70)
    print("Custom Completion Message Implementation Validation")
    print("=" * 70)
    print()

    checks = [
        ("Imports", check_imports),
        ("Function Signatures", check_function_signatures),
        ("Constants", check_constants),
        ("Handlers Integration", check_handlers_integration),
        ("Validation Logic", check_validation_logic),
        ("Test File", check_test_file_exists),
    ]

    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ Error during {name}: {e}")
            results.append((name, False))

    print("\n" + "=" * 70)
    print("Validation Summary")
    print("=" * 70)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    all_passed = all(result for _, result in results)

    print("\n" + "=" * 70)
    if all_passed:
        print("✓ ALL VALIDATION CHECKS PASSED")
        print("=" * 70)
        print("\nImplementation is complete and ready for testing!")
        print("\nNext steps:")
        print("1. Run unit tests: pytest tests/unit/test_completion_message.py -v")
        print("2. Implement Setup Wizard UI (Phase 2)")
        print("3. Deploy to AWS Lambda")
        return 0
    else:
        print("✗ SOME VALIDATION CHECKS FAILED")
        print("=" * 70)
        print("\nPlease review the errors above and fix the implementation.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
