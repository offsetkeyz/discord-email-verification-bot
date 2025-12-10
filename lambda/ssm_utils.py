"""
AWS Systems Manager Parameter Store utilities.
Loads configuration and secrets from SSM.
"""
import os
import boto3
from functools import lru_cache


ssm_client = boto3.client('ssm', region_name=os.environ.get('AWS_REGION', 'us-east-1'))


@lru_cache(maxsize=32)
def get_parameter(name: str) -> str:
    """
    Get SSM parameter with caching.

    Args:
        name: Parameter name (e.g., '/discord-bot/token')

    Returns:
        Parameter value
    """
    try:
        response = ssm_client.get_parameter(Name=name, WithDecryption=True)
        return response['Parameter']['Value']
    except Exception as e:
        print(f"Error getting parameter {name}: {e}")
        return ""
