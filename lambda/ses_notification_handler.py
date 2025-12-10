"""
SES Bounce and Complaint Notification Handler.

Processes SNS notifications from SES for bounces and complaints,
adding problematic addresses to suppression list.
"""
import json
import os
import sys
from pathlib import Path

# Add lambda directory to path
lambda_dir = Path(__file__).parent
if str(lambda_dir) not in sys.path:
    sys.path.insert(0, str(lambda_dir))

from ses_suppression_list import add_to_suppression_list


def lambda_handler(event, context):
    """
    Process SES bounce and complaint notifications from SNS.

    Event structure:
    {
        "Records": [{
            "Sns": {
                "Message": "{...SES notification JSON...}"
            }
        }]
    }
    """
    print(f"Processing SES notification event: {len(event.get('Records', []))} records")

    for record in event.get('Records', []):
        try:
            # Parse SNS message
            sns_message = record.get('Sns', {}).get('Message', '{}')
            message = json.loads(sns_message)

            notification_type = message.get('notificationType')
            print(f"Notification type: {notification_type}")

            if notification_type == 'Bounce':
                process_bounce(message)
            elif notification_type == 'Complaint':
                process_complaint(message)
            else:
                print(f"Unknown notification type: {notification_type}")

        except Exception as e:
            print(f"ERROR processing SNS record: {e}")
            # Continue processing other records

    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Processed SES notifications'})
    }


def process_bounce(message: dict):
    """
    Process bounce notification.

    Bounce types:
    - Permanent: Hard bounce (invalid email, doesn't exist)
    - Transient: Soft bounce (mailbox full, temporary issue)
    - Undetermined: Unknown bounce type
    """
    bounce = message.get('bounce', {})
    bounce_type = bounce.get('bounceType')  # Permanent or Transient
    bounce_subtype = bounce.get('bounceSubType', '')

    print(f"Processing bounce: type={bounce_type}, subtype={bounce_subtype}")

    # Get bounced recipients
    bounced_recipients = bounce.get('bouncedRecipients', [])

    for recipient in bounced_recipients:
        email = recipient.get('emailAddress')
        if not email:
            continue

        # Add to suppression list (only permanent bounces)
        if bounce_type == 'Permanent':
            add_to_suppression_list(
                email=email,
                reason='bounce',
                bounce_type=bounce_type,
                details={
                    'subtype': bounce_subtype,
                    'diagnostic_code': recipient.get('diagnosticCode', ''),
                    'timestamp': bounce.get('timestamp')
                }
            )
            print(f"Added {email} to suppression list (permanent bounce)")
        else:
            # Log transient bounces but don't suppress
            print(f"Transient bounce for {email} - not adding to suppression list")


def process_complaint(message: dict):
    """
    Process complaint notification (user marked as spam).

    Complaints are serious - always add to suppression list.
    """
    complaint = message.get('complaint', {})
    complaint_feedback_type = complaint.get('complaintFeedbackType', 'unknown')

    print(f"Processing complaint: type={complaint_feedback_type}")

    # Get complained recipients
    complained_recipients = complaint.get('complainedRecipients', [])

    for recipient in complained_recipients:
        email = recipient.get('emailAddress')
        if not email:
            continue

        # ALWAYS add complaints to suppression list
        add_to_suppression_list(
            email=email,
            reason='complaint',
            bounce_type='Complaint',
            details={
                'feedback_type': complaint_feedback_type,
                'timestamp': complaint.get('timestamp'),
                'user_agent': complaint.get('userAgent', '')
            }
        )
        print(f"Added {email} to suppression list (complaint)")
