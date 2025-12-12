# Contributing to Discord Email Verification Bot

Thank you for your interest in contributing! This bot is designed to be extended by student and community members. This guide will help you get started.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Testing Your Changes](#testing-your-changes)
- [AWS Permissions for Testing](#aws-permissions-for-testing)
- [Code Guidelines](#code-guidelines)
- [Pull Request Process](#pull-request-process)
- [Common Tasks](#common-tasks)

## Getting Started

### Prerequisites

- **Python 3.11+** installed locally
- **Git** for version control
- **AWS Account** (for testing Lambda functions)
- **Discord Application** (for testing bot interactions)
- Basic familiarity with Python, AWS Lambda, and Discord bots

### First-Time Contributors

1. **Fork the repository** to your GitHub account
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/discord-email-verification-bot.git
   cd discord-email-verification-bot
   ```
3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/offsetkeyz/discord-email-verification-bot.git
   ```

## Development Setup

### 1. Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```bash
# Discord Configuration
DISCORD_APP_ID=your_app_id
DISCORD_PUBLIC_KEY=your_public_key
DISCORD_TOKEN=your_bot_token

# AWS Configuration (for local testing)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key

# Table names (use test tables if available)
DYNAMODB_SESSIONS_TABLE=discord-verification-sessions-test
DYNAMODB_RECORDS_TABLE=discord-verification-records-test
DYNAMODB_GUILD_CONFIGS_TABLE=discord-guild-configs-test

# Email configuration
FROM_EMAIL=test@example.com
```

### 3. Set Up Pre-commit Hooks (Optional)

```bash
pip install pre-commit
pre-commit install
```

This automatically runs linters and formatters before each commit.

## Project Structure

```
discord-email-verification-bot/
├── lambda/                      # Lambda function code
│   ├── handlers.py             # Verification flow handlers
│   ├── setup_handler.py        # /setup command handlers
│   ├── lambda_function.py      # Main entry point
│   ├── dynamodb_operations.py  # Database operations
│   ├── discord_api.py          # Discord API calls
│   ├── ses_email.py            # Email sending
│   └── guild_config.py         # Guild configuration
├── tests/                       # Test suite
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── e2e/                    # End-to-end tests
├── scripts/                     # Deployment/utility scripts
├── docs/                        # Documentation
└── .github/workflows/          # CI/CD workflows
```

### Key Files to Know

- **`lambda/handlers.py`**: Main verification flow (email submission, code verification)
- **`lambda/setup_handler.py`**: Admin setup command handlers
- **`lambda/lambda_function.py`**: Request routing and entry point
- **`lambda/dynamodb_operations.py`**: All database operations
- **`lambda/guild_config.py`**: Guild configuration management

## Development Workflow

### 1. Create a Feature Branch

```bash
# Update your main branch
git checkout main
git pull upstream main

# Create feature branch
git checkout -b feature/your-feature-name
```

### 2. Make Your Changes

- Write clean, documented code
- Follow existing code patterns
- Add tests for new features
- Update documentation if needed

### 3. Run Tests Locally

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=lambda --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_handlers.py -v
```

### 4. Commit Your Changes

```bash
git add .
git commit -m "feat: Add new feature description"
```

**Commit Message Format:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Test additions/changes
- `refactor:` Code refactoring
- `chore:` Maintenance tasks

## Testing Your Changes

### Local Testing

#### 1. Unit Tests (No AWS Required)

```bash
# Run unit tests only
pytest tests/unit/ -v
```

Unit tests mock all AWS services and don't require AWS credentials.

#### 2. Integration Tests (Requires AWS)

```bash
# Requires AWS credentials configured
pytest tests/integration/ -v
```

Integration tests interact with real AWS services (DynamoDB, SES).

### AWS Testing Environment

#### Option 1: Use Test Tables (Recommended)

Create separate DynamoDB tables for testing:

```bash
# Create test tables
aws dynamodb create-table \
  --table-name discord-verification-sessions-test \
  --attribute-definitions \
    AttributeName=user_guild_id,AttributeType=S \
  --key-schema \
    AttributeName=user_guild_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1

# Repeat for other tables (records, configs)
```

#### Option 2: Use LocalStack (No AWS Account)

```bash
# Install LocalStack
pip install localstack

# Start LocalStack
localstack start

# Configure tests to use LocalStack
export AWS_ENDPOINT_URL=http://localhost:4566
```

### Testing in Discord

1. **Create a Test Discord Server**
2. **Invite your test bot** to the server
3. **Configure webhook URL** to point to your test Lambda function
4. **Run `/setup`** to configure your test server
5. **Test the verification flow** end-to-end

## AWS Permissions for Testing

### Minimal Testing Permissions

For contributors who want to test changes in AWS, you need these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/discord-verification-*-test"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "ses:SendEmail",
        "ses:SendRawEmail"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "lambda:CreateFunction",
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration",
        "lambda:InvokeFunction",
        "lambda:GetFunction",
        "lambda:DeleteFunction"
      ],
      "Resource": "arn:aws:lambda:*:*:function:discord-verification-*-test"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:PutParameter"
      ],
      "Resource": "arn:aws:ssm:*:*:parameter/discord-bot-test/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:log-group:/aws/lambda/discord-verification-*-test:*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "iam:GetRole",
        "iam:PassRole"
      ],
      "Resource": "arn:aws:iam::*:role/discord-verification-*-test"
    }
  ]
}
```

### Setting Up Your AWS Test Environment

1. **Create test DynamoDB tables** (see above)
2. **Deploy test Lambda function**:
   ```bash
   # Package Lambda function
   cd lambda
   zip -r ../lambda-test.zip *.py
   cd ..

   # Deploy to AWS
   aws lambda create-function \
     --function-name discord-verification-handler-test \
     --runtime python3.11 \
     --handler lambda_function.lambda_handler \
     --zip-file fileb://lambda-test.zip \
     --role arn:aws:iam::YOUR_ACCOUNT:role/discord-verification-lambda-role-test \
     --region us-east-1
   ```
3. **Configure environment variables** in Lambda console
4. **Set up test Discord bot** with Function URL or API Gateway

### Cost Considerations

Testing should cost less than $1/month:
- **DynamoDB**: Pay-per-request pricing (minimal for testing)
- **Lambda**: Free tier covers ~1M requests/month
- **SES**: Sandbox mode is free (limited recipients)

## Code Guidelines

### Python Style

- Follow **PEP 8** style guide
- Use **type hints** where appropriate
- Maximum line length: **100 characters**
- Use **docstrings** for functions and classes

```python
def handle_verification(user_id: str, guild_id: str) -> dict:
    """
    Handle email verification for a user.

    Args:
        user_id: Discord user ID
        guild_id: Discord guild ID

    Returns:
        Response dict for Discord interaction
    """
    # Implementation
```

### Testing Standards

- **Write tests** for new features
- Maintain **minimum 80% code coverage**
- Use **descriptive test names**:
  ```python
  def test_user_cannot_verify_without_edu_email():
      # Test implementation
  ```

### Security Practices

- **Never commit secrets** (use environment variables)
- **Validate all user input**
- **Sanitize email addresses and Discord content**
- **Use parameterized queries** for DynamoDB
- **Log suspicious activity**

### Error Handling

- Use **specific exception types**
- Provide **helpful error messages** to users
- **Log errors** with context for debugging
- **Fail gracefully** - don't crash the bot

## Pull Request Process

### Before Submitting

1. ✅ All tests pass locally
2. ✅ Code follows style guidelines
3. ✅ Added tests for new features
4. ✅ Updated documentation if needed
5. ✅ No merge conflicts with main branch

### Submitting a Pull Request

1. **Push your branch** to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Open a Pull Request** on GitHub:
   - Use a clear, descriptive title
   - Reference any related issues
   - Describe what changed and why
   - Include testing instructions

3. **PR Template**:
   ```markdown
   ## Summary
   Brief description of changes

   ## Changes
   - Added X feature
   - Fixed Y bug
   - Updated Z documentation

   ## Testing
   - [ ] Unit tests pass
   - [ ] Integration tests pass (if applicable)
   - [ ] Manually tested in Discord

   ## Screenshots (if applicable)
   [Add screenshots of UI changes]
   ```

### Review Process

- Maintainers will review your PR within a few days
- Address any requested changes
- Once approved, your PR will be merged!

## Common Tasks

### Adding a New Slash Command

1. Define command in `register_slash_commands.py`
2. Add handler in `lambda/setup_handler.py` or create new handler file
3. Route command in `lambda/lambda_function.py`
4. Add tests in `tests/unit/`
5. Update documentation

### Adding a New Database Field

1. Update schema in `lambda/dynamodb_operations.py`
2. Add getter/setter functions
3. Update tests
4. Create migration script if needed (for production)

### Adding a New Email Template

1. Update `lambda/ses_email.py`
2. Add template rendering function
3. Test email sending
4. Update documentation

### Debugging Lambda Function

```bash
# View recent logs
aws logs tail /aws/lambda/discord-verification-handler-test --follow

# Invoke function manually
aws lambda invoke \
  --function-name discord-verification-handler-test \
  --payload '{"body": "{}"}' \
  response.json
```

## Getting Help

- **Issues**: Open a GitHub issue for bugs or feature requests
- **Discussions**: Use GitHub Discussions for questions
- **Discord**: Join our Discord server for real-time help (if available)
- **Documentation**: Check the `docs/` directory

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers and help them get started
- Provide constructive feedback
- Focus on what's best for the community

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

---

**Thank you for contributing!** 🎉

Every contribution, no matter how small, helps make this bot better for everyone.
