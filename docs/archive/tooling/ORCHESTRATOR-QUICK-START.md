# Quick Start - Phase 3 Orchestrator

Run Phase 3 autonomously while you sleep!

## Prerequisites (One-Time Setup)

```bash
# 1. Install dependencies
npm install

# 2. Set API key
export ANTHROPIC_API_KEY='your-api-key-here'

# 3. Authenticate GitHub CLI (if not already)
gh auth login
```

## Run It

### Easy Mode (Interactive)

```bash
./start-orchestrator.sh
```

The script will:
- Check prerequisites
- Confirm you're ready
- Ask foreground or background
- Start the orchestrator

### Manual Mode

```bash
# Foreground (see output)
node phase3-orchestrator.js

# Background (log to file)
nohup node phase3-orchestrator.js > orchestrator.log 2>&1 &
```

## Monitor Progress

```bash
# Watch the log
tail -f orchestrator.log

# Check created PRs
gh pr list

# See recent commits
git log --oneline -10
```

## What Happens

1. **Project Manager** identifies next Phase 3 task
2. **Developer** writes integration tests
3. **Developer** creates PR
4. **Reviewer** reviews PR
5. If approved → merge and continue
6. If rejected → **Fixer** addresses issues → re-review
7. Repeat until Phase 3 complete

## Safety

- Max 20 iterations
- Max 2 fix attempts per PR
- Creates branches (never force-pushes)
- Runs tests before committing
- Only merges when approved

## Stop It

```bash
# If foreground: Ctrl+C

# If background:
pkill -f phase3-orchestrator
```

## Cost Estimate

Using Sonnet 4.5 (default): **~$2-4 total**

Phase 3 has ~6-10 integration test tasks.

## Common Issues

**"ANTHROPIC_API_KEY not set"**
```bash
export ANTHROPIC_API_KEY='sk-ant-...'
```

**"gh not authenticated"**
```bash
gh auth login
```

**"Uncommitted changes"**
```bash
git stash
# or
git commit -am "wip"
```

## Files Created

- `phase3-orchestrator.js` - Main script
- `package.json` - Dependencies
- `start-orchestrator.sh` - Interactive startup
- `README-ORCHESTRATOR.md` - Full documentation
- This file - Quick reference

## After Completion

```bash
# Run full test suite
pytest --cov=lambda --cov-report=html

# Check coverage
open htmlcov/index.html

# Should be ~87%+ after Phase 3
```

## That's It!

Questions? Read: `README-ORCHESTRATOR.md`
