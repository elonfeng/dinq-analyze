"""
Email Service

This module provides email sending functionality using Resend service.
"""

import logging
import json
import os
import smtplib
from email.message import EmailMessage
from typing import Dict, Any, Optional
from server.config.env_loader import get_env_var

try:
    import resend  # type: ignore
except Exception:  # noqa: BLE001
    resend = None

# Configure logging
logger = logging.getLogger(__name__)

# Get base URL from environment variables
BASE_URL = get_env_var('DINQ_API_DOMAIN', 'http://localhost:5001')

# Resend configuration
RESEND_API_KEY = get_env_var("RESEND_API_KEY", "re_YbAkp7LA_KV11v3ZDmAVb2Fm2wnrU6S5t")
FROM_EMAIL = "DINQ <support@dinq.io>"


def _email_backend() -> str:
    return str(os.getenv("DINQ_EMAIL_BACKEND", "resend")).strip().lower()


def _append_outbox(entry: Dict[str, Any]) -> None:
    """
    测试辅助：把邮件写入本地 outbox（JSONL），方便离线/CI 验证而不依赖外部邮件服务。
    """
    path = os.getenv("DINQ_TEST_EMAIL_OUTBOX_PATH")
    if not path:
        return
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to write email outbox: %s", exc)


def _send_via_smtp(*, subject: str, html: str, to_email: str) -> bool:
    host = os.getenv("DINQ_SMTP_HOST", "localhost")
    try:
        port = int(os.getenv("DINQ_SMTP_PORT", "1025"))
    except (TypeError, ValueError):
        port = 1025

    msg = EmailMessage()
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content("This email requires an HTML-capable client.")
    msg.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("SMTP send failed: %s", exc)
        return False


class EmailService:
    """Service for sending emails"""

    def __init__(self):
        """Initialize email service"""
        if resend is not None:
            resend.api_key = RESEND_API_KEY
        logger.info("Email service initialized (backend=%s)", _email_backend())
        logger.info("Using BASE_URL: %s", BASE_URL)

    def send_verification_email(self, to_email: str, verification_code: str, email_type: str, user_name: str = None, user_id: str = None) -> bool:
        """
        Send email verification code

        Args:
            to_email: Recipient email address
            verification_code: 6-digit verification code
            email_type: Type of email verification (edu_email, company_email, etc.)
            user_name: User's name for personalization

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Determine email content based on type
            subject, html_content = self._get_verification_email_content(
                verification_code, email_type, user_name, to_email, user_id
            )

            backend = _email_backend()
            _append_outbox(
                {
                    "kind": "verification",
                    "backend": backend,
                    "to": to_email,
                    "subject": subject,
                    "email_type": email_type,
                    "user_id": user_id,
                    "verification_code": verification_code,
                }
            )

            if backend in ("noop", "file"):
                logger.info("Email backend=%s; skip sending verification email to %s", backend, to_email)
                return True

            if backend == "smtp":
                ok = _send_via_smtp(subject=subject, html=html_content, to_email=to_email)
                if ok:
                    logger.info("Verification email sent via SMTP to %s", to_email)
                return ok

            # Default: resend
            if resend is None:
                logger.error("resend SDK not available (backend=resend)")
                return False

            params = {"from": FROM_EMAIL, "to": [to_email], "subject": subject, "html": html_content}
            response = resend.Emails.send(params)
            if response and response.get("id"):
                logger.info("Verification email sent successfully to %s, ID: %s", to_email, response)
                return True
            logger.error("Failed to send verification email to %s: %s", to_email, response)
            return False

        except Exception as e:
            logger.error(f"Error sending verification email to {to_email}: {e}")
            return False

    def _get_verification_email_content(self, verification_code: str, email_type: str, user_name: str = None, to_email: str = None, user_id: str = None) -> tuple[str, str]:
        """
        Get email content based on verification type

        Returns:
            Tuple of (subject, html_content)
        """
        # Default greeting
        greeting = f"Hello {user_name}," if user_name else "Hello,"

        # Email type specific content
        if email_type == "edu_email":
            subject = "Verify Your Educational Email - DINQ"
            purpose = "verify your educational email address"
            context = "This verification confirms your academic affiliation and helps us provide you with relevant opportunities."
        elif email_type == "company_email":
            subject = "Verify Your Company Email - DINQ"
            purpose = "verify your company email address"
            context = "This verification confirms your professional affiliation and helps us connect you with relevant opportunities."
        elif email_type == "recruiter_company_email":
            subject = "Verify Your Company Email - DINQ Recruiter"
            purpose = "verify your company email address"
            context = "This verification confirms your organization and enables you to post opportunities on our platform."
        else:
            subject = "Email Verification - DINQ"
            purpose = "verify your email address"
            context = "This verification helps us ensure the security of your account."

        # HTML email template
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Email Verification - DINQ</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f8f9fa;
                }}
                .container {{
                    background-color: white;
                    padding: 40px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 30px;
                }}
                .logo {{
                    font-size: 28px;
                    font-weight: bold;
                    color: #2563eb;
                    margin-bottom: 10px;
                }}
                .verification-code {{
                    background-color: #f3f4f6;
                    border: 2px dashed #d1d5db;
                    border-radius: 8px;
                    padding: 20px;
                    text-align: center;
                    margin: 30px 0;
                }}
                .code {{
                    font-size: 32px;
                    font-weight: bold;
                    color: #2563eb;
                    letter-spacing: 4px;
                    font-family: 'Courier New', monospace;
                }}
                .button {{
                    display: inline-block;
                    background-color: #2563eb;
                    color: white;
                    padding: 12px 24px;
                    text-decoration: none;
                    border-radius: 6px;
                    font-weight: 500;
                    margin: 20px 0;
                }}
                .footer {{
                    margin-top: 40px;
                    padding-top: 20px;
                    border-top: 1px solid #e5e7eb;
                    font-size: 14px;
                    color: #6b7280;
                    text-align: center;
                }}
                .warning {{
                    background-color: #fef3c7;
                    border-left: 4px solid #f59e0b;
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 4px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">DINQ</div>
                    <h1>Email Verification</h1>
                </div>

                <p>{greeting}</p>

                <p>Thank you for joining DINQ! To {purpose}, please use the verification code below:</p>

                <div class="verification-code">
                    <div class="code">{verification_code}</div>
                </div>

                <p>{context}</p>

                <div style="text-align: center;">
                    <a href="{BASE_URL}/verify-email?code={verification_code}&email={to_email}&type={email_type}&user_id={user_id}" class="button">
                        Verify Email Address
                    </a>
                </div>

                <div class="warning">
                    <strong>Important:</strong> This verification code will expire in 15 minutes.
                    If you didn't request this verification, please ignore this email.
                </div>

                <p>If you have any questions or need assistance, please don't hesitate to contact our support team.</p>

                <div class="footer">
                    <p>Best regards,<br>The DINQ Team</p>
                    <p>
                        <a href="https://dinq.io">dinq.io</a> |
                        <a href="mailto:support@dinq.io">support@dinq.io</a>
                    </p>
                    <p style="font-size: 12px; margin-top: 20px;">
                        This email was sent to {to_email}. If you believe this was sent in error,
                        please contact us at support@dinq.io.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        return subject, html_content

    def send_welcome_email(self, to_email: str, user_name: str, user_type: str) -> bool:
        """
        Send welcome email after successful verification

        Args:
            to_email: Recipient email address
            user_name: User's name
            user_type: Type of user (job_seeker or recruiter)

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            subject = "Welcome to DINQ - Your Verification is Complete!"

            # Customize content based on user type
            if user_type == "job_seeker":
                role_specific_content = """
                <p>As a verified job seeker, you now have access to:</p>
                <ul>
                    <li>🔍 Browse exclusive research and academic opportunities</li>
                    <li>🎯 Get matched with positions that fit your expertise</li>
                    <li>📊 Access detailed insights about potential employers</li>
                    <li>🤝 Connect with verified recruiters and hiring managers</li>
                </ul>
                """
                next_steps = """
                <p><strong>Next Steps:</strong></p>
                <ol>
                    <li>Complete your profile to improve matching accuracy</li>
                    <li>Set up job alerts for your preferred positions</li>
                    <li>Start exploring available opportunities</li>
                </ol>
                """
            else:  # recruiter
                role_specific_content = """
                <p>As a verified recruiter, you now have access to:</p>
                <ul>
                    <li>📝 Post job opportunities and research positions</li>
                    <li>🔍 Search our database of verified candidates</li>
                    <li>📊 Access candidate analytics and insights</li>
                    <li>💬 Direct messaging with potential candidates</li>
                </ul>
                """
                next_steps = """
                <p><strong>Next Steps:</strong></p>
                <ol>
                    <li>Set up your company profile</li>
                    <li>Post your first job opportunity</li>
                    <li>Start searching for qualified candidates</li>
                </ol>
                """

            html_content = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Welcome to DINQ</title>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                        background-color: #f8f9fa;
                    }}
                    .container {{
                        background-color: white;
                        padding: 40px;
                        border-radius: 8px;
                        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
                    }}
                    .header {{
                        text-align: center;
                        margin-bottom: 30px;
                    }}
                    .logo {{
                        font-size: 28px;
                        font-weight: bold;
                        color: #2563eb;
                        margin-bottom: 10px;
                    }}
                    .success-badge {{
                        background-color: #10b981;
                        color: white;
                        padding: 8px 16px;
                        border-radius: 20px;
                        font-size: 14px;
                        font-weight: 500;
                        display: inline-block;
                        margin-bottom: 20px;
                    }}
                    .button {{
                        display: inline-block;
                        background-color: #2563eb;
                        color: white;
                        padding: 12px 24px;
                        text-decoration: none;
                        border-radius: 6px;
                        font-weight: 500;
                        margin: 20px 0;
                    }}
                    .footer {{
                        margin-top: 40px;
                        padding-top: 20px;
                        border-top: 1px solid #e5e7eb;
                        font-size: 14px;
                        color: #6b7280;
                        text-align: center;
                    }}
                    ul, ol {{
                        padding-left: 20px;
                    }}
                    li {{
                        margin-bottom: 8px;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <div class="logo">DINQ</div>
                        <div class="success-badge">✓ Verification Complete</div>
                        <h1>Welcome to DINQ, {user_name}!</h1>
                    </div>

                    <p>Congratulations! Your account has been successfully verified and you're now part of the DINQ community.</p>

                    {role_specific_content}

                    {next_steps}

                    <div style="text-align: center;">
                        <a href="{BASE_URL}/dashboard" class="button">
                            Go to Dashboard
                        </a>
                    </div>

                    <p>If you have any questions or need assistance getting started, our support team is here to help.</p>

                    <div class="footer">
                        <p>Best regards,<br>The DINQ Team</p>
                        <p>
                            <a href="https://dinq.io">dinq.io</a> |
                            <a href="mailto:support@dinq.io">support@dinq.io</a>
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """

            backend = _email_backend()
            _append_outbox(
                {
                    "kind": "welcome",
                    "backend": backend,
                    "to": to_email,
                    "subject": subject,
                    "user_name": user_name,
                    "user_type": user_type,
                }
            )

            if backend in ("noop", "file"):
                logger.info("Email backend=%s; skip sending welcome email to %s", backend, to_email)
                return True

            if backend == "smtp":
                ok = _send_via_smtp(subject=subject, html=html_content, to_email=to_email)
                if ok:
                    logger.info("Welcome email sent via SMTP to %s", to_email)
                return ok

            if resend is None:
                logger.error("resend SDK not available (backend=resend)")
                return False

            params = {"from": FROM_EMAIL, "to": [to_email], "subject": subject, "html": html_content}
            response = resend.Emails.send(params)
            if response and response.get("id"):
                logger.info("Welcome email sent successfully to %s, ID: %s", to_email, response)
                return True
            logger.error("Failed to send welcome email to %s: %s", to_email, response)
            return False

        except Exception as e:
            logger.error(f"Error sending welcome email to {to_email}: {e}")
            return False

# Global service instance
email_service = EmailService()
