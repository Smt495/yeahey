"""Send the daily briefing HTML report via SMTP email."""
from __future__ import annotations
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
import pytz

from briefing.config import TIMEZONE

log = logging.getLogger(__name__)
ET = pytz.timezone(TIMEZONE)

SESSION_LABELS = {
    "pre_market":  "盘前简报",
    "open":        "开盘快照",
    "midday":      "盘中更新",
    "close":       "收盘汇总",
    "after_hours": "盘后异动",
}


def send_email(report_path: str, session: str) -> bool:
    """
    Email the HTML report as both inline body and attachment.
    Reads credentials from environment variables:
      SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, NOTIFY_EMAIL
    Returns True on success, False on failure.
    """
    smtp_host  = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port  = int(os.getenv("SMTP_PORT", "587"))
    smtp_user  = os.getenv("SMTP_USER", "")
    smtp_pass  = os.getenv("SMTP_PASS", "")
    notify_to  = os.getenv("NOTIFY_EMAIL", smtp_user)

    if not smtp_user or not smtp_pass:
        log.warning("Email not configured — set SMTP_USER and SMTP_PASS in .env")
        return False

    now        = datetime.now(ET)
    label      = SESSION_LABELS.get(session, session)
    date_str   = now.strftime("%Y-%m-%d")
    time_str   = now.strftime("%H:%M ET")
    subject    = f"📊 美股每日简报 [{label}] {date_str} {time_str}"

    try:
        with open(report_path, "r", encoding="utf-8") as f:
            html_body = f.read()
    except OSError as e:
        log.error("Cannot read report file: %s", e)
        return False

    msg = MIMEMultipart("mixed")
    msg["From"]    = smtp_user
    msg["To"]      = notify_to
    msg["Subject"] = subject

    # Inline HTML body
    alt = MIMEMultipart("alternative")
    plain = (
        f"美股每日简报 — {label}\n"
        f"日期: {date_str}  时间: {time_str}\n\n"
        "请使用支持 HTML 的邮件客户端查看完整报告，或下载附件。\n"
    )
    alt.attach(MIMEText(plain, "plain", "utf-8"))
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)

    # Attach HTML file
    fname = os.path.basename(report_path)
    part  = MIMEBase("text", "html")
    part.set_payload(html_body.encode("utf-8"))
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{fname}"')
    msg.attach(part)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, notify_to, msg.as_string())
        log.info("Email sent to %s  [%s]", notify_to, subject)
        return True
    except Exception as e:
        log.error("Email send failed: %s", e)
        return False
