# Good First Issues

Welcome, first-time contributors! 👋

This guide lists beginner-friendly tasks that are perfect for getting started with the codebase.

## Why Start Here?

These tasks are:
- ✅ Well-defined with clear requirements
- ✅ Limited in scope (won't take weeks)
- ✅ Don't require deep AWS knowledge
- ✅ Great for learning the codebase

## Categories

### 📚 Documentation (No Coding Required)

**Perfect for**: Anyone who can write clearly

1. **Add Examples to README**
   - Add real-world use case examples
   - Include screenshots of the setup flow
   - Show example verification messages
   - **Difficulty**: Easy
   - **Files**: `README.md`

2. **Improve Error Message Documentation**
   - Document common error messages users see
   - Add troubleshooting steps
   - **Difficulty**: Easy
   - **Files**: `docs/guides/DISCORD_TESTING_GUIDE.md`

3. **Create Video Tutorial**
   - Record a walkthrough of the setup process
   - Show the verification flow from a user's perspective
   - **Difficulty**: Easy
   - **Files**: New video, link in `README.md`

### 🧪 Testing (Learn the Codebase)

**Perfect for**: Learning Python testing, understanding the code

4. **Add Test Cases for Edge Cases**
   - Test what happens with very long email addresses
   - Test unicode characters in verification codes
   - Test rate limiting edge cases
   - **Difficulty**: Easy-Medium
   - **Files**: `tests/unit/test_handlers.py`, `tests/integration/test_edge_cases.py`

5. **Improve Test Coverage for Setup Handler**
   - Add tests for error scenarios in setup flow
   - Test modal validation
   - **Difficulty**: Medium
   - **Files**: `tests/unit/test_setup_handler.py`

### 🐛 Bug Fixes (Small Code Changes)

**Perfect for**: First Python contributions

6. **Fix Deprecation Warnings**
   - Replace `datetime.utcnow()` with `datetime.now(timezone.utc)`
   - The tests show ~130 deprecation warnings
   - **Difficulty**: Easy
   - **Files**: `lambda/handlers.py`, `lambda/dynamodb_operations.py`, `lambda/guild_config.py`

7. **Improve Error Messages**
   - Make error messages more user-friendly
   - Add helpful hints to common errors
   - **Difficulty**: Easy
   - **Files**: `lambda/handlers.py`, `lambda/setup_handler.py`

8. **Add Input Validation**
   - Validate email format before making API calls
   - Validate role IDs and channel IDs
   - **Difficulty**: Easy-Medium
   - **Files**: `lambda/validation_utils.py`

### ✨ Small Features (New Functionality)

**Perfect for**: Adding something useful without complexity

9. **Add Configurable Code Length**
   - Allow admins to set 4-8 digit verification codes
   - Currently fixed at 6 digits
   - **Difficulty**: Medium
   - **Files**: `lambda/verification_logic.py`, `lambda/guild_config.py`

10. **Add Setup Confirmation Message**
    - Show a summary after `/setup` completes
    - List all configured settings
    - **Difficulty**: Easy
    - **Files**: `lambda/setup_handler.py`

11. **Add Help Command**
    - Create `/verify-help` command
    - Show common FAQs and troubleshooting
    - **Difficulty**: Medium
    - **Files**: `lambda/setup_handler.py`, `register_slash_commands.py`

12. **Add Verification Stats**
    - Show admin how many users verified this month
    - `/verify-stats` command
    - **Difficulty**: Medium
    - **Files**: New handler file, `lambda/dynamodb_operations.py`

### 🎨 UX Improvements (Make It Better)

**Perfect for**: Improving user experience

13. **Better Rate Limit Messages**
    - Show exact time remaining instead of "wait X seconds"
    - Add progress indicator
    - **Difficulty**: Easy
    - **Files**: `lambda/handlers.py`

14. **Improve Setup Wizard Flow**
    - Add "Back" button option
    - Better error recovery
    - **Difficulty**: Medium
    - **Files**: `lambda/setup_handler.py`

15. **Add Setup Preview Mode**
    - Let admins see a preview before posting to channel
    - Test the verification flow without sending real emails
    - **Difficulty**: Medium
    - **Files**: `lambda/setup_handler.py`

## How to Get Started

### 1. Pick a Task

Choose something that interests you from the list above. Start with "Easy" tasks if you're new to the codebase.

### 2. Comment on the Issue

If there's a GitHub issue for the task:
- Comment that you want to work on it
- Ask any questions you have
- Wait for confirmation before starting

If there's no issue yet:
- Create one using the feature request template
- Mention you'd like to work on it

### 3. Follow the Contributing Guide

See **[CONTRIBUTING.md](../CONTRIBUTING.md)** for:
- Setting up your development environment
- How to write tests
- Code style guidelines
- How to submit a pull request

### 4. Ask for Help

Stuck? Don't hesitate to:
- Comment on your PR with specific questions
- Open a GitHub Discussion
- Reference relevant code sections when asking

## Tips for Success

### Before You Start

✅ Read the CONTRIBUTING.md guide
✅ Set up your local development environment
✅ Run the existing tests to make sure everything works
✅ Read through related code to understand the patterns

### While Working

✅ Make small, focused commits
✅ Write tests for your changes
✅ Test manually in Discord if applicable
✅ Keep your branch up to date with main

### Before Submitting

✅ All tests pass (`pytest tests/`)
✅ Code follows style guidelines (`black lambda/ tests/`)
✅ Added documentation for new features
✅ No merge conflicts with main branch

## Example Workflow

```bash
# 1. Fork and clone the repo
git clone https://github.com/YOUR_USERNAME/discord-email-verification-bot.git
cd discord-email-verification-bot

# 2. Create a feature branch
git checkout -b fix/improve-error-messages

# 3. Make your changes
# Edit files...

# 4. Run tests
pytest tests/ -v

# 5. Commit changes
git add .
git commit -m "fix: Improve error messages for invalid emails"

# 6. Push and create PR
git push origin fix/improve-error-messages
# Open PR on GitHub
```

## Resources

- **[CONTRIBUTING.md](../CONTRIBUTING.md)**: Full contribution guide
- **[README.md](../README.md)**: Project overview and setup
- **[Discord API Docs](https://discord.com/developers/docs)**: Discord API reference
- **[AWS Lambda Docs](https://docs.aws.amazon.com/lambda/)**: Lambda documentation
- **[Python Discord Library](https://discordpy.readthedocs.io/)**: Discord.py docs (for reference)

## Still Not Sure Where to Start?

That's okay! Here's what to do:

1. **Read through the codebase**: Explore `lambda/handlers.py` and `lambda/setup_handler.py`
2. **Run the tests**: See what the code does with `pytest tests/unit/ -v`
3. **Try the bot**: Set it up in a test Discord server
4. **Ask questions**: Open a GitHub Discussion or comment on an issue

**Remember**: Every expert was once a beginner. We're here to help! 🎉

---

**Quick Pick for Complete Beginners**:
Start with #6 (Fix Deprecation Warnings) - it's a find-and-replace task that will help you learn the codebase!
