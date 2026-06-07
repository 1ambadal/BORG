"""
This module handles email-related operations using the Gmail API.
"""

import os
import pickle
import base64
import logging
import mimetypes
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from googleapiclient.discovery import build
from langchain.tools import tool
from services.google_auth_service import get_google_credentials

logger = logging.getLogger(__name__)


def get_gmail_service():
    """Load the credentials and return the Gmail service."""
    creds = get_google_credentials()
    if not creds:
        raise Exception(
            "Invalid Google credentials. Please run generate_token.py to get valid credentials."
        )

    return build("gmail", "v1", credentials=creds)


def send_gmail_message(
    to: str,
    subject: str,
    message_body: str,
    html_content: str = None,
    attachments: list[str] = None,
    cc: list[str] = None,
    bcc: list[str] = None,
) -> str:
    """
    Internal function to send an email using the Gmail API.
    """
    try:
        service = get_gmail_service()

        message = MIMEMultipart()
        message["to"] = to
        message["subject"] = subject

        if cc:
            message["cc"] = ", ".join(cc)
        if bcc:
            message["bcc"] = ", ".join(bcc)

        # Add body
        message.attach(MIMEText(message_body, "plain"))

        if html_content:
            message.attach(MIMEText(html_content, "html"))

        if attachments:
            for file_path in attachments:
                if not os.path.exists(file_path):
                    logger.warning("Attachment not found: %s", file_path)
                    continue

                content_type, encoding = mimetypes.guess_type(file_path)
                if content_type is None or encoding is not None:
                    content_type = "application/octet-stream"

                main_type, sub_type = content_type.split("/", 1)

                with open(file_path, "rb") as f:
                    file_data = f.read()

                part = MIMEBase(main_type, sub_type)
                part.set_payload(file_data)
                encoders.encode_base64(part)

                filename = os.path.basename(file_path)

                part.add_header(
                    "Content-Disposition", f'attachment; filename="{filename}"'
                )
                message.attach(part)

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        body = {"raw": raw_message}

        service.users().messages().send(userId="me", body=body).execute()
        return "Email sent successfully!"
    except Exception as e:
        logger.error("Failed to send email: %s", e, exc_info=True)
        return f"Failed to send email. Error: {str(e)}"


@tool
def send_email(
    to: str,
    subject: str,
    message_body: str,
    html_content: str = None,
    attachments: list[str] = None,
    cc: list[str] = None,
    bcc: list[str] = None,
) -> str:
    """
    Sends an email using the user's Gmail account with optional HTML content, attachments, CC, and BCC.
    Args:
        to: The email address(es) of the recipient(s). Can be a comma-separated string for multiple.
        subject: The subject of the email.
        message_body: The plain text body content of the email.
        html_content: Optional. The HTML body content of the email.
        attachments: Optional. A list of file paths to attach to the email.
        cc: Optional. A list of email addresses to CC.
        bcc: Optional. A list of email addresses to BCC.
    Returns:
        A success message or an error message.
    """
    return send_gmail_message(
        to, subject, message_body, html_content, attachments, cc, bcc
    )
