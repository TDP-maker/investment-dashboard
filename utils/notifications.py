"""
Email alert notifications via SMTP.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, ALERT_EMAIL_TO


def send_email_alert(subject: str, body: str, html: bool = False) -> bool:
    """
    Send an email alert via SMTP.

    Returns True if sent successfully, False otherwise.
    """
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD, ALERT_EMAIL_TO]):
        print("Email not configured — skipping alert notification.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[Investment Alert] {subject}"
        msg["From"] = SMTP_USER
        msg["To"] = ALERT_EMAIL_TO

        if html:
            msg.attach(MIMEText(body, "html"))
        else:
            msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

        print(f"Alert email sent: {subject}")
        return True

    except Exception as e:
        print(f"Failed to send email alert: {e}")
        return False


def format_alerts_email(alerts: list) -> tuple[str, str]:
    """Format alerts into an email subject and body."""
    if not alerts:
        return "No alerts", "No threshold alerts triggered."

    count = len(alerts)
    high_count = sum(1 for a in alerts if a.get("severity") == "HIGH")

    subject = f"{count} alert(s) triggered ({high_count} HIGH)"

    lines = [
        f"Investment Dashboard Alert — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"{'=' * 60}",
        "",
    ]

    for alert in sorted(alerts, key=lambda a: a.get("severity", ""), reverse=True):
        lines.append(f"[{alert.get('severity', 'UNKNOWN')}] {alert.get('signal', 'Alert')}")
        lines.append(f"  Condition: {alert.get('condition', 'N/A')}")
        lines.append(f"  Current:   {alert.get('current_value', 'N/A')}")
        lines.append(f"  Triggered: {alert.get('triggered_at', 'N/A')}")
        lines.append("")

    lines.append("---")
    lines.append("Investment Intelligence Dashboard")

    return subject, "\n".join(lines)
