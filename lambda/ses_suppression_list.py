"""
SES Email Suppression List Management.

Manages a DynamoDB table tracking bounced/complained emails to prevent
repeated sends to problematic addresses.
"""
import os
from datetime import datetime
from decimal import Decimal
import boto3
from typing import Optional, Dict, Any


# DynamoDB client
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'))
suppression_table_name = os.environ.get('SUPPRESSION_LIST_TABLE', 'ses-email-suppression-list')

try:
    suppression_table = dynamodb.Table(suppression_table_name)
except Exception as e:
    print(f"Warning: Suppression table not found: {e}")
    suppression_table = None


def add_to_suppression_list(email: str, reason: str, bounce_type: str, details: Optional[Dict[str, Any]] = None):
    """
    Add email to suppression list.

    Args:
        email: Email address to suppress
        reason: 'bounce' or 'complaint'
        bounce_type: 'Permanent', 'Transient', or 'Complaint'
        details: Additional metadata
    """
    if not suppression_table:
        print("ERROR: Suppression table not configured")
        return False

    try:
        item = {
            'email': email.lower(),
            'reason': reason,
            'bounce_type': bounce_type,
            'added_at': Decimal(str(datetime.utcnow().timestamp())),
            'added_date': datetime.utcnow().isoformat()
        }

        if details:
            item['details'] = str(details)

        suppression_table.put_item(Item=item)
        print(f"Added {email} to suppression list (reason: {reason}, type: {bounce_type})")
        return True
    except Exception as e:
        print(f"ERROR adding {email} to suppression list: {e}")
        return False


def is_suppressed(email: str) -> bool:
    """
    Check if email is on suppression list.

    Args:
        email: Email address to check

    Returns:
        True if email is suppressed, False otherwise
    """
    if not suppression_table:
        # If table doesn't exist, allow send (fail open for development)
        return False

    try:
        response = suppression_table.get_item(
            Key={'email': email.lower(), 'reason': 'bounce'}
        )
        if 'Item' in response:
            print(f"Email {email} is on bounce suppression list")
            return True

        response = suppression_table.get_item(
            Key={'email': email.lower(), 'reason': 'complaint'}
        )
        if 'Item' in response:
            print(f"Email {email} is on complaint suppression list")
            return True

        return False
    except Exception as e:
        print(f"ERROR checking suppression list for {email}: {e}")
        # Fail open - allow send on error
        return False


def remove_from_suppression_list(email: str, reason: str = 'bounce'):
    """
    Remove email from suppression list (admin action).

    Args:
        email: Email address to remove
        reason: 'bounce' or 'complaint'
    """
    if not suppression_table:
        return False

    try:
        suppression_table.delete_item(
            Key={'email': email.lower(), 'reason': reason}
        )
        print(f"Removed {email} from {reason} suppression list")
        return True
    except Exception as e:
        print(f"ERROR removing {email} from suppression list: {e}")
        return False


def get_suppression_stats() -> Dict[str, int]:
    """
    Get statistics about suppression list.

    Returns:
        Dictionary with bounce and complaint counts
    """
    if not suppression_table:
        return {'bounces': 0, 'complaints': 0}

    try:
        # Scan for bounces
        bounce_response = suppression_table.scan(
            FilterExpression='reason = :reason',
            ExpressionAttributeValues={':reason': 'bounce'},
            Select='COUNT'
        )

        complaint_response = suppression_table.scan(
            FilterExpression='reason = :reason',
            ExpressionAttributeValues={':reason': 'complaint'},
            Select='COUNT'
        )

        return {
            'bounces': bounce_response.get('Count', 0),
            'complaints': complaint_response.get('Count', 0)
        }
    except Exception as e:
        print(f"ERROR getting suppression stats: {e}")
        return {'bounces': 0, 'complaints': 0}
