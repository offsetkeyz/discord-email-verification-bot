"""
Amazon SES email service for sending verification codes.
Replaces the SMTP email_service.py from the original bot.
"""
import boto3
import os
from botocore.exceptions import ClientError
from logging_utils import log_email_event
from ses_suppression_list import is_suppressed


# Initialize SES client
ses_client = boto3.client('ses', region_name='us-east-1')
cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')


def publish_email_metric(metric_name: str, value: float = 1.0):
    """Publish custom CloudWatch metric."""
    try:
        cloudwatch.put_metric_data(
            Namespace='DiscordBot/SES',
            MetricData=[{
                'MetricName': metric_name,
                'Value': value,
                'Unit': 'Count'
            }]
        )
    except Exception as e:
        print(f"ERROR publishing metric {metric_name}: {e}")


def send_verification_email(email: str, code: str) -> bool:
    """
    Send verification code via Amazon SES.

    Args:
        email: Recipient's .edu email address
        code: 6-digit verification code

    Returns:
        True if email sent successfully, False otherwise
    """
    # CHECK SUPPRESSION LIST FIRST
    if is_suppressed(email):
        print(f"Email {email} is on suppression list - not sending")
        publish_email_metric('EmailsSuppressed')
        log_email_event("suppressed", email, False, "Email on bounce/complaint suppression list")
        return False

    from_email = os.environ.get('FROM_EMAIL', 'verificationcode.noreply@thedailydecrypt.com')

    subject = 'Discord Verification Code'

    text_body = f"""Discord Server Verification

Your verification code is: {code}

This code will expire in 15 minutes.

If you did not request this verification, please ignore this email.
"""

    html_body = f"""<html>
<head></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #5865F2; color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0;">
        <h1 style="margin: 0;">Discord Server Verification</h1>
    </div>

    <div style="background-color: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px;">
        <p style="font-size: 16px; color: #333;">Your verification code is:</p>

        <div style="background-color: #ffffff; border: 2px solid #5865F2; padding: 20px; text-align: center; font-size: 36px; font-weight: bold; letter-spacing: 8px; margin: 20px 0; border-radius: 8px; color: #5865F2;">
            {code}
        </div>

        <p style="color: #666; font-size: 14px; margin-top: 20px;">
            <strong>This code will expire in 15 minutes.</strong>
        </p>

        <p style="color: #999; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd;">
            If you did not request this verification, please ignore this email.
        </p>
    </div>
</body>
</html>"""

    try:
        response = ses_client.send_email(
            Source=from_email,
            Destination={'ToAddresses': [email]},
            Message={
                'Subject': {
                    'Data': subject,
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Text': {
                        'Data': text_body,
                        'Charset': 'UTF-8'
                    },
                    'Html': {
                        'Data': html_body,
                        'Charset': 'UTF-8'
                    }
                }
            }
        )

        message_id = response['MessageId']
        log_email_event("sent", email, True, f"MessageId: {message_id}")
        publish_email_metric('EmailsSent')
        return True

    except ClientError as e:
        error_message = e.response['Error']['Message']
        log_email_event("sent", email, False, f"SES Error: {error_message}")
        publish_email_metric('EmailsFailed')
        return False
    except Exception as e:
        print(f"Unexpected error sending email: {e}")
        publish_email_metric('EmailsFailed')
        return False
