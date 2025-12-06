"""
Discord REST API operations.
Handles direct API calls to Discord (role assignment, etc.)
"""
import requests


def user_has_role(user_id: str, guild_id: str, role_id: str, bot_token: str) -> bool:
    """
    Check if a user already has a specific role.

    Args:
        user_id: Discord user ID
        guild_id: Discord guild ID
        role_id: Role ID to check
        bot_token: Discord bot token

    Returns:
        True if user has the role, False otherwise
    """
    url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}"
    headers = {
        "Authorization": f"Bot {bot_token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            member_data = response.json()
            user_roles = member_data.get('roles', [])
            has_role = role_id in user_roles
            print(f"User {user_id} {'has' if has_role else 'does not have'} role {role_id}")
            return has_role
        else:
            print(f"Failed to get member info: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print(f"Error checking user role: {e}")
        return False


def assign_role(user_id: str, guild_id: str, role_id: str, bot_token: str) -> bool:
    """
    Assign a role to a user via Discord REST API.

    Args:
        user_id: Discord user ID
        guild_id: Discord guild ID
        role_id: Role ID to assign
        bot_token: Discord bot token

    Returns:
        True if role assigned successfully, False otherwise
    """
    url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}/roles/{role_id}"
    headers = {
        "Authorization": f"Bot {bot_token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.put(url, headers=headers)

        if response.status_code == 204:
            print(f"Successfully assigned role {role_id} to user {user_id}")
            return True
        elif response.status_code == 404:
            print(f"User {user_id} or role {role_id} not found in guild {guild_id}")
            return False
        else:
            print(f"Failed to assign role: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print(f"Error assigning role: {e}")
        return False
