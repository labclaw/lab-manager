"""IMAP email poller: periodically checks a mailbox for new vendor emails.

Configuration via environment variables:
  EMAIL_IMAP_HOST: IMAP server hostname
  EMAIL_IMAP_USER: IMAP username (email address)
  EMAIL_IMAP_PASSWORD: IMAP password
  EMAIL_FOLDER: Mailbox folder to monitor (default: INBOX)
  EMAIL_POLL_INTERVAL: Polling interval in seconds (default: 300 = 5 min)
"""

from __future__ import annotations

import imaplib
import logging
import os
import time

logger = logging.getLogger(__name__)

# Default polling interval: 5 minutes
DEFAULT_POLL_INTERVAL = 300


def _get_imap_config() -> dict:
    """Read IMAP configuration from environment."""
    host = os.environ.get("EMAIL_IMAP_HOST", "")
    user = os.environ.get("EMAIL_IMAP_USER", "")
    password = os.environ.get("EMAIL_IMAP_PASSWORD", "")
    folder = os.environ.get("EMAIL_FOLDER", "INBOX")
    interval = int(os.environ.get("EMAIL_POLL_INTERVAL", str(DEFAULT_POLL_INTERVAL)))
    return {
        "host": host,
        "user": user,
        "password": password,
        "folder": folder,
        "interval": interval,
    }


def _connect_imap(config: dict) -> imaplib.IMAP4_SSL:
    """Connect and authenticate to IMAP server."""
    conn = imaplib.IMAP4_SSL(config["host"])
    conn.login(config["user"], config["password"])
    return conn


def _fetch_unseen_emails(conn: imaplib.IMAP4_SSL, folder: str) -> list[str]:
    """Fetch unseen email bodies from the specified folder.

    Returns list of raw email strings. Marks fetched emails as Seen.
    """
    conn.select(folder)
    _, msg_nums = conn.search(None, "UNSEEN")

    raw_emails: list[str] = []
    for num in msg_nums[0].split():
        if not num:
            continue
        _, data = conn.fetch(num, "(RFC822)")
        if data and data[0] and isinstance(data[0], tuple):
            raw_bytes = data[0][1]
            if isinstance(raw_bytes, bytes):
                raw_emails.append(raw_bytes.decode("utf-8", errors="replace"))
        # Mark as seen (IMAP fetch with RFC822 already sets \Seen flag)

    return raw_emails


def poll_once() -> int:
    """Poll mailbox once for new emails and process them.

    Returns:
        Number of documents created.
    """
    from lab_manager.database import get_db_session
    from lab_manager.services.email_intake import process_email

    config = _get_imap_config()
    if not config["host"] or not config["user"]:
        logger.debug("Email polling not configured (missing EMAIL_IMAP_HOST/USER)")
        return 0

    total_docs = 0
    try:
        conn = _connect_imap(config)
        try:
            raw_emails = _fetch_unseen_emails(conn, config["folder"])
            logger.info(
                "Found %d unseen emails in %s", len(raw_emails), config["folder"]
            )

            for raw_email in raw_emails:
                try:
                    with get_db_session() as db:
                        docs = process_email(raw_email, db)
                        total_docs += len(docs)
                        if docs:
                            logger.info("Processed email -> %d document(s)", len(docs))
                except Exception:
                    logger.exception("Failed to process email")
        finally:
            try:
                conn.logout()
            except Exception:
                pass
    except Exception:
        logger.exception("IMAP connection failed")

    return total_docs


def run_poller() -> None:
    """Run the email poller in a loop. Blocks forever.

    Intended to be started in a background thread or separate process.
    """
    config = _get_imap_config()
    if not config["host"] or not config["user"]:
        logger.warning(
            "Email poller not starting: EMAIL_IMAP_HOST and EMAIL_IMAP_USER required"
        )
        return

    interval = config["interval"]
    logger.info(
        "Email poller starting: host=%s, user=%s, folder=%s, interval=%ds",
        config["host"],
        config["user"],
        config["folder"],
        interval,
    )

    while True:
        try:
            count = poll_once()
            if count:
                logger.info("Poll cycle: created %d document(s)", count)
        except Exception:
            logger.exception("Error in poll cycle")
        time.sleep(interval)
