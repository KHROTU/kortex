import smtplib
from email.message import EmailMessage
import yaml

def prepare_email(recipient, subject, body=""):
    """
    Prepares an email for review before sending.
    Parameters: {"recipient": "The recipient's email address.", "subject": "The subject line of the email.", "body": "The main content of the email. Can be empty."}
    """
    return "Email drafted. Please review before sending."

def send_email_final(recipient, subject, body, config_path="kortex/config.yaml"):
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        email_config = config.get('services', {}).get('email', {})
        if not email_config.get('enabled'):
            return "Email service is not enabled in settings."

        smtp_server = email_config.get('smtp_server')
        smtp_port = email_config.get('smtp_port')
        sender_email = email_config.get('email_address')
        password = email_config.get('app_password')

        if not all([smtp_server, smtp_port, sender_email, password]):
            return "Email configuration is incomplete in settings."

        msg = EmailMessage()
        msg.set_content(body)
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = recipient

        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender_email, password)
            server.send_message(msg)
        
        return "Email sent successfully."

    except FileNotFoundError:
        return "Configuration file not found."
    except Exception as e:
        return f"Failed to send email. Error: {e}"