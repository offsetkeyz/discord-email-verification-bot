# Technical Specification: Custom Completion Messages

**For Backend Development Team**

---

## Overview

This document provides detailed technical specifications for implementing customizable verification completion messages in the Discord verification bot.

**Objective:** Allow server administrators to customize the message displayed when users successfully complete email verification.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Discord User Flow                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  1. User clicks "Start Verification"                                 │
│  2. User submits email                                               │
│  3. User receives code via SES                                       │
│  4. User submits code                                                │
│  5. ✓ CODE VERIFIED                                                  │
│       ↓                                                               │
│       handlers.py:handle_code_verification()                         │
│       ↓                                                               │
│       guild_config.py:get_guild_completion_message(guild_id)         │
│       ↓                                                               │
│       DynamoDB:discord-guild-configs → completion_message            │
│       ↓                                                               │
│       Return ephemeral_response(custom_or_default_message)          │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                      Admin Setup Flow                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  1. Admin runs /setup                                                │
│  2. Admin selects role & channel                                     │
│  3. Admin clicks "Continue"                                          │
│  4. Admin submits domains (modal)                                    │
│  5. Admin submits trigger message link (modal)                       │
│  6. NEW: Admin submits completion message (modal)                    │
│       ↓                                                               │
│       setup_handler.py:show_completion_message_modal()               │
│       ↓                                                               │
│       User enters custom message or skips                            │
│       ↓                                                               │
│       setup_handler.py:handle_completion_message_modal_submit()      │
│       ↓                                                               │
│       Store in DynamoDB pending setup (5 min TTL)                    │
│       ↓                                                               │
│  7. Admin sees preview (trigger + completion messages)               │
│  8. Admin approves                                                    │
│       ↓                                                               │
│       setup_handler.py:handle_setup_approve()                        │
│       ↓                                                               │
│       guild_config.py:save_guild_config(... completion_message)      │
│       ↓                                                               │
│       DynamoDB:discord-guild-configs (permanent storage)             │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### Table: `discord-guild-configs`

**Partition Key:** `guild_id` (String)

**Schema (Updated):**

```python
{
    'guild_id': str,                    # Discord guild ID (PK)
    'role_id': str,                     # Role to assign on verification
    'channel_id': str,                  # Channel for verification message
    'allowed_domains': list[str],       # Allowed email domains
    'custom_message': str,              # Verification trigger message
    'completion_message': str,          # ← NEW: Verification success message
    'setup_by': str,                    # User ID who configured
    'setup_timestamp': str,             # ISO 8601 timestamp
    'last_updated': str                 # ISO 8601 timestamp
}
```

**Example Item:**

```json
{
    "guild_id": "704494754129510431",
    "role_id": "849471214711996486",
    "channel_id": "768351579773468672",
    "allowed_domains": ["student.sans.edu", "auburn.edu"],
    "custom_message": "Click the button below to verify your email address.",
    "completion_message": "🎉 Welcome to the SANS Student Discord! You now have access to all channels.",
    "setup_by": "123456789012345678",
    "setup_timestamp": "2025-12-10T14:30:00.000000",
    "last_updated": "2025-12-10T14:30:00.000000"
}
```

**Field Specifications:**

| Field | Type | Required | Max Length | Default | Notes |
|-------|------|----------|------------|---------|-------|
| `completion_message` | String | No | 2000 | Default message | Empty = use default |

**Indexing:** No new indexes required (field accessed via primary key lookup)

**Query Pattern:**
```python
response = configs_table.get_item(Key={'guild_id': guild_id})
completion_message = response.get('Item', {}).get('completion_message', DEFAULT_MESSAGE)
```

---

## API Changes

### Modified Functions

#### 1. `guild_config.py:save_guild_config()`

**Signature Change:**

```python
# BEFORE:
def save_guild_config(
    guild_id: str,
    role_id: str,
    channel_id: str,
    setup_by_user_id: str,
    allowed_domains: Optional[list] = None,
    custom_message: Optional[str] = None
) -> bool:

# AFTER:
def save_guild_config(
    guild_id: str,
    role_id: str,
    channel_id: str,
    setup_by_user_id: str,
    allowed_domains: Optional[list] = None,
    custom_message: Optional[str] = None,
    completion_message: Optional[str] = None  # ← NEW PARAMETER
) -> bool:
```

**Implementation:**

```python
def save_guild_config(
    guild_id: str,
    role_id: str,
    channel_id: str,
    setup_by_user_id: str,
    allowed_domains: Optional[list] = None,
    custom_message: Optional[str] = None,
    completion_message: Optional[str] = None
) -> bool:
    """
    Save or update guild configuration.

    Args:
        guild_id: Discord guild ID
        role_id: Verification role ID
        channel_id: Channel ID for verification message
        setup_by_user_id: User ID who ran setup
        allowed_domains: Optional list of allowed email domains
        custom_message: Optional custom verification trigger message
        completion_message: Optional custom completion message

    Returns:
        True if saved successfully, False otherwise
    """
    try:
        now = datetime.utcnow()

        # Apply defaults
        if allowed_domains is None:
            allowed_domains = ['auburn.edu', 'student.sans.edu']

        if custom_message is None:
            custom_message = "Click the button below to verify your email address."

        if completion_message is None:
            completion_message = "🎉 **Verification complete!** You now have access to the server.\n\nWelcome! 👋"

        # Build config item
        config_item = {
            'guild_id': guild_id,
            'role_id': role_id,
            'channel_id': channel_id,
            'allowed_domains': allowed_domains,
            'custom_message': custom_message,
            'completion_message': completion_message,  # ← NEW
            'setup_by': setup_by_user_id,
            'setup_timestamp': now.isoformat(),
            'last_updated': now.isoformat()
        }

        # Save to DynamoDB
        configs_table.put_item(Item=config_item)
        print(f"Saved config for guild {guild_id}: role={role_id}, channel={channel_id}, completion_msg_len={len(completion_message)}")
        return True

    except Exception as e:
        print(f"Error saving guild config: {e}")
        return False
```

**Error Handling:**
- Invalid guild_id: Log error, return False
- DynamoDB unavailable: Log error, return False
- Message too long: Truncate to 2000 chars (validated in modal)

---

#### 2. `guild_config.py:get_guild_completion_message()` (NEW)

**Signature:**

```python
def get_guild_completion_message(guild_id: str) -> str:
```

**Implementation:**

```python
def get_guild_completion_message(guild_id: str) -> str:
    """
    Get the custom completion message for a guild.

    Args:
        guild_id: Discord guild ID

    Returns:
        Custom completion message or default if not configured

    Notes:
        - Returns default message if guild not found
        - Returns default message if field missing (backward compatibility)
        - Returns default message if field is empty string
    """
    # Default message constant
    DEFAULT_COMPLETION_MESSAGE = "🎉 **Verification complete!** You now have access to the server.\n\nWelcome! 👋"

    try:
        # Fetch guild config
        config = get_guild_config(guild_id)

        # Check if config exists
        if not config:
            print(f"No config found for guild {guild_id}, using default completion message")
            return DEFAULT_COMPLETION_MESSAGE

        # Check if completion_message field exists and is non-empty
        completion_message = config.get('completion_message', '').strip()

        if completion_message:
            print(f"Using custom completion message for guild {guild_id} (length: {len(completion_message)})")
            return completion_message
        else:
            print(f"Completion message empty for guild {guild_id}, using default")
            return DEFAULT_COMPLETION_MESSAGE

    except Exception as e:
        print(f"Error getting completion message for guild {guild_id}: {e}")
        # Fail safe: return default
        return DEFAULT_COMPLETION_MESSAGE
```

**Edge Cases:**
- Guild not found → Default message
- Field missing → Default message
- Field is empty string → Default message
- Field is whitespace only → Default message
- DynamoDB error → Default message (with error log)

**Performance:**
- Caching: No (simple key lookup, ~10ms)
- Called once per verification (low frequency)
- No batch operations needed

---

#### 3. `handlers.py:handle_code_verification()` (MODIFIED)

**Location:** Line ~378-381

**Current Code:**

```python
if success:
    return ephemeral_response(
        "🎉 **Verification complete!** You now have access to the server.\n\n"
        "Welcome! 👋"
    )
```

**New Code:**

```python
if success:
    # Get custom completion message from guild config
    from guild_config import get_guild_completion_message
    completion_message = get_guild_completion_message(guild_id)

    return ephemeral_response(completion_message)
else:
    return ephemeral_response(
        "✅ Verification successful, but I encountered an issue assigning your role.\n\n"
        "Please contact a server administrator."
    )
```

**Alternative (with error handling):**

```python
if success:
    try:
        from guild_config import get_guild_completion_message
        completion_message = get_guild_completion_message(guild_id)
    except Exception as e:
        print(f"Error fetching completion message, using default: {e}")
        completion_message = "🎉 **Verification complete!** You now have access to the server.\n\nWelcome! 👋"

    return ephemeral_response(completion_message)
```

**Testing:**
- Mock `get_guild_completion_message()` to return test messages
- Verify ephemeral_response receives correct message
- Test error path (exception handling)

---

#### 4. `dynamodb_operations.py:store_pending_setup()` (MODIFIED)

**Signature Change:**

```python
# BEFORE:
def store_pending_setup(
    setup_id: str,
    user_id: str,
    guild_id: str,
    role_id: str,
    channel_id: str,
    allowed_domains: list,
    custom_message: str
):

# AFTER:
def store_pending_setup(
    setup_id: str,
    user_id: str,
    guild_id: str,
    role_id: str,
    channel_id: str,
    allowed_domains: list,
    custom_message: str,
    completion_message: str = ""  # ← NEW PARAMETER (default empty)
):
```

**Implementation:**

```python
def store_pending_setup(
    setup_id: str,
    user_id: str,
    guild_id: str,
    role_id: str,
    channel_id: str,
    allowed_domains: list,
    custom_message: str,
    completion_message: str = ""
):
    """
    Store pending setup configuration temporarily (5 minute TTL).

    Args:
        setup_id: Unique UUID for this setup session
        user_id: Discord user ID of the admin performing setup
        guild_id: Discord guild ID
        role_id: Discord role ID
        channel_id: Discord channel ID
        allowed_domains: List of allowed email domains
        custom_message: Custom verification trigger message
        completion_message: Custom completion message (optional)
    """
    try:
        from datetime import datetime, timedelta

        ttl = int((datetime.utcnow() + timedelta(minutes=5)).timestamp())

        sessions_table.put_item(
            Item={
                'user_id': f"setup_{setup_id}",
                'guild_id': guild_id,
                'setup_id': setup_id,
                'admin_user_id': user_id,
                'role_id': role_id,
                'channel_id': channel_id,
                'allowed_domains': allowed_domains,
                'custom_message': custom_message,
                'completion_message': completion_message,  # ← NEW
                'ttl': ttl,
                'created_at': datetime.utcnow().isoformat()
            }
        )
        print(f"Stored pending setup for {setup_id} with completion_message (length: {len(completion_message)})")
    except Exception as e:
        print(f"Error storing pending setup: {e}")
```

---

## Setup Wizard Implementation

### New Modal: Completion Message

**Custom ID:** `setup_completion_modal_{setup_id}`

**Modal Specification:**

```python
{
    'type': InteractionResponseType.MODAL,
    'data': {
        'custom_id': f'setup_completion_modal_{setup_id}',
        'title': 'Completion Message',
        'components': [
            {
                'type': ComponentType.ACTION_ROW,
                'components': [
                    {
                        'type': ComponentType.TEXT_INPUT,
                        'custom_id': 'completion_message',
                        'label': 'Message shown after verification',
                        'style': 2,  # Paragraph (multi-line)
                        'placeholder': '🎉 Verification complete! Welcome to {{server}}!',
                        'required': False,  # Optional field
                        'min_length': 0,
                        'max_length': 2000  # Discord message limit
                    }
                ]
            }
        ]
    }
}
```

**Field Properties:**

| Property | Value | Reason |
|----------|-------|--------|
| `style` | 2 (Paragraph) | Allows multi-line messages |
| `required` | False | Users can skip to use default |
| `max_length` | 2000 | Discord message character limit |
| `placeholder` | Helpful example | Shows formatting possibilities |

---

### New Handler: `handle_completion_message_modal_submit()`

**Flow:**

```python
def handle_completion_message_modal_submit(interaction: dict) -> dict:
    """
    Handle completion message modal submission and show preview.

    Flow:
    1. Extract setup_id from custom_id (with validation)
    2. Retrieve pending setup config from DynamoDB
    3. Extract completion_message from modal input
    4. Apply default if empty
    5. Update pending setup with completion_message
    6. Show preview with both trigger and completion messages
    7. Provide approve/cancel buttons

    Args:
        interaction: Discord interaction payload

    Returns:
        Preview response dict
    """
    # Extract IDs
    member = interaction.get('member', {})
    guild_id = interaction.get('guild_id')
    user_id = member.get('user', {}).get('id')

    custom_id = interaction['data']['custom_id']
    setup_id = extract_setup_id_from_custom_id(custom_id, 'setup_completion_modal')

    if not setup_id:
        return ephemeral_response("❌ Invalid state. Please run /setup again.")

    # Get pending config
    from dynamodb_operations import get_pending_setup, store_pending_setup

    config = get_pending_setup(setup_id, guild_id)
    if not config:
        return ephemeral_response("❌ Setup session expired. Please run /setup again.")

    # Extract completion message from modal
    components = interaction['data']['components']
    completion_message = components[0]['components'][0].get('value', '').strip()

    # Use default if empty
    if not completion_message:
        completion_message = "🎉 **Verification complete!** You now have access to the server.\n\nWelcome! 👋"

    # Validate length (should be enforced by Discord, but double-check)
    if len(completion_message) > 2000:
        completion_message = completion_message[:2000]
        print(f"Warning: Completion message truncated to 2000 chars for guild {guild_id}")

    # Update pending setup
    store_pending_setup(
        setup_id=setup_id,
        user_id=config['admin_user_id'],
        guild_id=guild_id,
        role_id=config['role_id'],
        channel_id=config['channel_id'],
        allowed_domains=config['allowed_domains'],
        custom_message=config['custom_message'],
        completion_message=completion_message
    )

    # Show preview
    return show_setup_preview_with_completion(
        setup_id,
        guild_id,
        config,
        completion_message
    )
```

---

### Updated Preview Display

**Function:** `show_setup_preview_with_completion()`

```python
def show_setup_preview_with_completion(
    setup_id: str,
    guild_id: str,
    config: dict,
    completion_message: str
) -> dict:
    """
    Show complete preview with all configuration including completion message.

    Args:
        setup_id: Setup session UUID
        guild_id: Discord guild ID
        config: Pending setup configuration
        completion_message: Custom completion message

    Returns:
        Preview response with approve/cancel buttons
    """
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'type': InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
            'data': {
                'content': (
                    f"## 👀 Preview Your Configuration\n\n"
                    f"**Settings:**\n"
                    f"• Role: <@&{config['role_id']}>\n"
                    f"• Channel: <#{config['channel_id']}>\n"
                    f"• Allowed Domains: {', '.join(config['allowed_domains'])}\n\n"
                    f"**Verification Trigger Message** (shown in channel):\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"{config['custom_message']}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"**Completion Message** (shown to user after success):\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"{completion_message}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"Ready to save? Click 'Approve & Save' to activate this configuration."
                ),
                'flags': MessageFlags.EPHEMERAL,
                'components': [
                    {
                        'type': ComponentType.ACTION_ROW,
                        'components': [
                            {
                                'type': ComponentType.BUTTON,
                                'style': ButtonStyle.SUCCESS,
                                'label': '✅ Approve & Save',
                                'custom_id': f'setup_approve_{setup_id}'
                            },
                            {
                                'type': ComponentType.BUTTON,
                                'style': ButtonStyle.DANGER,
                                'label': '❌ Cancel',
                                'custom_id': 'setup_cancel'
                            }
                        ]
                    }
                ]
            }
        })
    }
```

**Preview Layout:**

```
┌─────────────────────────────────────────────┐
│ 👀 Preview Your Configuration               │
│                                             │
│ Settings:                                   │
│ • Role: @Verified                           │
│ • Channel: #verification                    │
│ • Allowed Domains: student.sans.edu         │
│                                             │
│ Verification Trigger Message:               │
│ ━━━━━━━━━━━━━━━━━━━━━━━━                   │
│ Click the button below to verify your       │
│ email address.                              │
│ ━━━━━━━━━━━━━━━━━━━━━━━━                   │
│                                             │
│ Completion Message:                         │
│ ━━━━━━━━━━━━━━━━━━━━━━━━                   │
│ 🎉 Welcome to SANS Student Discord!        │
│ You now have access to all channels.        │
│ ━━━━━━━━━━━━━━━━━━━━━━━━                   │
│                                             │
│ [✅ Approve & Save]  [❌ Cancel]            │
└─────────────────────────────────────────────┘
```

---

### Updated Approval Handler

**Function:** `handle_setup_approve()` (existing, modified)

**Changes:**

```python
def handle_setup_approve(interaction: dict) -> dict:
    """
    Handle approval button click - saves config and posts message.

    Changes:
    - Extract completion_message from config_data
    - Pass completion_message to save_guild_config()
    """
    # ... existing code ...

    try:
        role_id = config_data['role_id']
        channel_id = config_data['channel_id']
        allowed_domains = config_data['allowed_domains']
        custom_message = config_data['custom_message']
        completion_message = config_data.get('completion_message', None)  # ← NEW

    except KeyError as e:
        print(f"Error retrieving config: {e}")
        return ephemeral_response("❌ Invalid configuration data. Please run /setup again.")

    # Save configuration with completion message
    success = save_guild_config(
        guild_id,
        role_id,
        channel_id,
        user_id,
        allowed_domains,
        custom_message,
        completion_message  # ← NEW PARAMETER
    )

    # ... rest of existing code ...
```

---

## Setup Flow Routing

### Updated Router in `lambda_function.py`

**Add new handler route:**

```python
# In handle_modal_submit()
if custom_id.startswith('setup_completion_modal_'):
    from setup_handler import handle_completion_message_modal_submit
    return handle_completion_message_modal_submit(interaction)
```

---

## Validation & Sanitization

### Input Validation

**Completion Message:**
- **Max Length:** 2000 characters (enforced by Discord modal)
- **Min Length:** 0 (optional field)
- **Allowed Characters:** Any Unicode (Discord handles rendering)
- **Format:** Plain text with Discord markdown support

**Sanitization:**
```python
completion_message = components[0]['components'][0].get('value', '').strip()

# Truncate if somehow exceeds limit
if len(completion_message) > 2000:
    completion_message = completion_message[:2000]

# Empty message → use default
if not completion_message:
    completion_message = DEFAULT_MESSAGE
```

**Discord Markdown Support:**
- `**bold**` → bold text
- `*italic*` → italic text
- `__underline__` → underlined text
- `~~strikethrough~~` → strikethrough
- `\n\n` → new paragraph
- Emoji codes (🎉, 👋, etc.)
- No HTML or dangerous content (Discord handles this)

---

## Error Handling

### Error Scenarios

| Error | Cause | Handling | User Impact |
|-------|-------|----------|-------------|
| DynamoDB unavailable | AWS outage | Return default message, log error | Users see default message |
| Guild config missing | New guild | Return default message | Works seamlessly |
| Field missing | Old config | Return default message | Backward compatible |
| Setup timeout | 5 min TTL expired | Show error, prompt re-run | Admin must restart setup |
| Invalid setup_id | Malicious/corrupted ID | Return error message | Admin must restart setup |
| Message too long | Bug in validation | Truncate to 2000 chars | Message truncated |

### Error Logging

```python
# Standard error log format
print(f"ERROR: [completion_message] {error_type}: {error_message} (guild_id={guild_id})")

# Examples:
print(f"ERROR: [completion_message] DynamoDB unavailable: {e} (guild_id={guild_id})")
print(f"ERROR: [completion_message] Invalid setup_id: {setup_id} (guild_id={guild_id})")
print(f"ERROR: [completion_message] Message too long: {len(message)} chars (guild_id={guild_id})")
```

### Fail-Safe Strategy

**Always prefer degradation over failure:**

```python
try:
    completion_message = get_guild_completion_message(guild_id)
except Exception as e:
    print(f"ERROR getting completion message, using default: {e}")
    completion_message = DEFAULT_COMPLETION_MESSAGE

return ephemeral_response(completion_message)
```

---

## Testing Specifications

### Unit Test Coverage

**File:** `tests/unit/test_completion_message.py`

**Required Tests:**

```python
# Database operations
test_save_guild_config_with_completion_message()
test_save_guild_config_without_completion_message()
test_get_completion_message_custom()
test_get_completion_message_default()
test_get_completion_message_empty_string()
test_get_completion_message_whitespace_only()
test_get_completion_message_missing_guild()
test_get_completion_message_missing_field()

# Validation
test_completion_message_max_length_2000()
test_completion_message_truncation()
test_completion_message_unicode_support()
test_completion_message_markdown_support()

# Error handling
test_completion_message_dynamodb_error()
test_completion_message_malformed_config()

# Backward compatibility
test_legacy_guild_without_completion_field()
```

### Integration Test Coverage

**File:** `tests/integration/test_completion_message_flow.py`

**Required Tests:**

```python
# Complete verification flow
test_verification_with_custom_completion_message()
test_verification_with_default_completion_message()

# Setup wizard flow
test_setup_wizard_with_completion_message()
test_setup_wizard_skip_completion_message()
test_setup_wizard_empty_completion_message()

# Modal interactions
test_completion_modal_display()
test_completion_modal_submit()
test_completion_modal_preview()
```

### Mock Requirements

**Mocks needed:**

```python
# DynamoDB
@mock_dynamodb
def test_function():
    # Mock discord-guild-configs table
    pass

# Discord API
@patch('discord_api.assign_role')
def test_function(mock_assign_role):
    mock_assign_role.return_value = True

# SES
@patch('ses_email.send_verification_email')
def test_function(mock_ses):
    mock_ses.return_value = True
```

---

## Performance Considerations

### Database Operations

**Read Performance:**
- Single `get_item` operation per verification
- No scan or query operations
- Avg latency: ~10ms

**Write Performance:**
- Single `put_item` during setup
- No impact on verification flow
- Avg latency: ~15ms

**Cost Impact:**
- Minimal (one additional field per guild)
- No new indexes → no additional read costs
- Storage: ~100 bytes per guild (negligible)

### Lambda Execution

**Memory Impact:**
- Minimal (string field, <2KB)
- No impact on Lambda memory configuration

**Execution Time:**
- Added latency: <5ms (single DB lookup)
- No impact on Lambda timeout

---

## Deployment Steps

### Pre-Deployment Checklist

- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Code review completed (2+ reviewers)
- [ ] Documentation updated
- [ ] Backup current Lambda function

### Deployment Commands

```bash
# 1. Create deployment package
cd /home/offsetkeyz/claude_coding_projects/au-discord-bot
python3 -m zipfile -c lambda-deployment.zip lambda/*.py

# 2. Backup current deployment
aws lambda get-function --function-name discord-verification-handler \
  --query 'Code.Location' --output text | xargs wget -O lambda-backup.zip

# 3. Deploy new version
aws lambda update-function-code \
  --function-name discord-verification-handler \
  --zip-file fileb://lambda-deployment.zip

# 4. Wait for update to complete
aws lambda wait function-updated \
  --function-name discord-verification-handler

# 5. Publish new version
aws lambda publish-version \
  --function-name discord-verification-handler \
  --description "Add custom completion messages feature"

# 6. Monitor logs
aws logs tail /aws/lambda/discord-verification-handler --follow
```

### Post-Deployment Verification

```bash
# Check Lambda status
aws lambda get-function --function-name discord-verification-handler \
  --query 'Configuration.State' --output text

# Test basic functionality
# (Run /setup in Discord test server)

# Monitor for errors
aws logs filter-pattern \
  --log-group-name /aws/lambda/discord-verification-handler \
  --filter-pattern "ERROR" \
  --start-time $(date -u -d '5 minutes ago' +%s)000

# Check guild configs
aws dynamodb scan --table-name discord-guild-configs \
  --projection-expression "guild_id,completion_message" \
  --max-items 5
```

---

## Rollback Procedure

**If deployment fails:**

```bash
# 1. Identify last working version
aws lambda list-versions-by-function \
  --function-name discord-verification-handler \
  --query 'Versions[?Version!=`$LATEST`].Version' \
  --output text

# 2. Update alias to previous version
aws lambda update-alias \
  --function-name discord-verification-handler \
  --name production \
  --function-version PREVIOUS_VERSION

# OR restore from backup
aws lambda update-function-code \
  --function-name discord-verification-handler \
  --zip-file fileb://lambda-backup.zip

# 3. Verify rollback
aws logs tail /aws/lambda/discord-verification-handler --follow

# 4. Test in Discord
# Run /setup and verification flow
```

---

## Monitoring & Observability

### CloudWatch Metrics

**Custom Metrics:**

```python
# In get_guild_completion_message()
import boto3
cloudwatch = boto3.client('cloudwatch')

# Track custom vs default usage
cloudwatch.put_metric_data(
    Namespace='DiscordBot',
    MetricData=[
        {
            'MetricName': 'CompletionMessageType',
            'Value': 1,
            'Unit': 'Count',
            'Dimensions': [
                {'Name': 'MessageType', 'Value': 'custom' if is_custom else 'default'}
            ]
        }
    ]
)
```

### CloudWatch Logs Insights Queries

**Find guilds using custom messages:**

```
fields guild_id, completion_msg_len
| filter @message like /Using custom completion message/
| stats count() by guild_id
```

**Track errors:**

```
fields @timestamp, guild_id, error
| filter @message like /ERROR.*completion_message/
| sort @timestamp desc
```

**Performance monitoring:**

```
fields @duration
| filter @message like /get_guild_completion_message/
| stats avg(@duration), max(@duration), min(@duration)
```

---

## Security Considerations

### Input Validation
- Discord enforces max length (2000 chars) in modal
- Backend double-checks and truncates if needed
- No SQL injection risk (DynamoDB NoSQL)
- No XSS risk (Discord renders markdown safely)

### Access Control
- Only admins with ADMINISTRATOR permission can run /setup
- Permission check in `handle_setup_command()`
- Setup sessions expire after 5 minutes (TTL)
- Setup_id is UUID v4 (unguessable)

### Data Privacy
- Completion messages don't contain user data
- No PII in messages
- Messages stored per-guild, not per-user
- No sensitive data exposure

---

## Constants

**File:** `lambda/guild_config.py`

```python
# Default completion message (module-level constant)
DEFAULT_COMPLETION_MESSAGE = (
    "🎉 **Verification complete!** You now have access to the server.\n\n"
    "Welcome! 👋"
)

# Character limit for completion messages
COMPLETION_MESSAGE_MAX_LENGTH = 2000  # Discord limit
```

---

## Backward Compatibility Matrix

| Scenario | Behavior | Impact |
|----------|----------|--------|
| Existing guild without field | Uses DEFAULT_COMPLETION_MESSAGE | None - seamless |
| New guild setup | Admin can set custom or use default | New feature |
| Update existing guild | Admin can update completion message | Works |
| Old Lambda + new DB field | Ignores field, uses hardcoded message | None |
| New Lambda + old DB items | Uses default message | None - graceful |

---

## Code Review Checklist

- [ ] Function signatures updated with new parameter
- [ ] Default values applied correctly
- [ ] Error handling for all edge cases
- [ ] Logging added for debugging
- [ ] Comments and docstrings updated
- [ ] Type hints correct (Optional[str])
- [ ] Backward compatibility maintained
- [ ] No hardcoded guild IDs or test data
- [ ] Constants used instead of magic strings
- [ ] DynamoDB operations efficient (no scans)

---

## Additional Resources

- **Full Feature Plan:** `/home/offsetkeyz/claude_coding_projects/au-discord-bot/FEATURE_PLAN_CUSTOM_COMPLETION_MESSAGES.md`
- **Summary:** `/home/offsetkeyz/claude_coding_projects/au-discord-bot/FEATURE_IMPLEMENTATION_SUMMARY.md`
- **Current Code:** `/home/offsetkeyz/claude_coding_projects/au-discord-bot/lambda/`
- **Tests:** `/home/offsetkeyz/claude_coding_projects/au-discord-bot/tests/`

---

**Document Status:** Ready for Implementation
**Version:** 1.0
**Last Updated:** December 10, 2025
