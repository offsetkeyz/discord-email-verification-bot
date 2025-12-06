#!/usr/bin/env python3
"""
Register slash commands with Discord.
This script registers the /setup command globally for the bot.
"""
import requests
import os

# Read .env file manually
def load_env_file(filepath='.env'):
    env_vars = {}
    if os.path.exists(filepath):
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars

env_vars = load_env_file()
APP_ID = env_vars.get('DISCORD_APP_ID')
BOT_TOKEN = env_vars.get('DISCORD_TOKEN')

if not APP_ID or not BOT_TOKEN:
    print("ERROR: DISCORD_APP_ID and DISCORD_TOKEN must be set in .env file")
    exit(1)

# Define the /setup-email-verification command
setup_command = {
    "name": "setup-email-verification",
    "type": 1,  # CHAT_INPUT
    "description": "Configure the email verification bot for this server (Admin only)",
    "default_member_permissions": "8",  # ADMINISTRATOR permission required
    "dm_permission": False  # Cannot be used in DMs
}

# Register command globally
url = f"https://discord.com/api/v10/applications/{APP_ID}/commands"
headers = {
    "Authorization": f"Bot {BOT_TOKEN}",
    "Content-Type": "application/json"
}

print(f"Registering /setup-email-verification command globally for app {APP_ID}...")
response = requests.post(url, headers=headers, json=setup_command)

if response.status_code in [200, 201]:
    print("✅ Successfully registered /setup-email-verification command!")
    print(f"Command ID: {response.json().get('id')}")
    print("\nThe command may take up to 1 hour to appear in all servers.")
    print("To test immediately, invite the bot to a new server.")
else:
    print(f"❌ Failed to register command: {response.status_code}")
    print(response.text)

# List all registered commands
print("\n" + "="*50)
print("Current registered commands:")
print("="*50)

response = requests.get(url, headers=headers)
if response.status_code == 200:
    commands = response.json()
    if commands:
        for cmd in commands:
            print(f"- /{cmd['name']}: {cmd['description']}")
            print(f"  ID: {cmd['id']}")
    else:
        print("No commands registered")
else:
    print(f"Failed to fetch commands: {response.status_code}")
