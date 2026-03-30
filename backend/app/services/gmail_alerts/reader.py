"""
GmailReader — connexion Gmail OAuth2 et récupération des emails bruts.
Aucune logique métier. Retourne uniquement des tuples (sender, email_date, html).
Les credentials sont lus depuis les variables d'environnement (config.py).
"""

import base64
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.core.config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Fenêtre de lecture : 3 jours pour absorber les weekends et délais
GMAIL_NEWER_THAN = "1d"


class GmailReader:

    def __init__(self):
        self._service = None

    def _get_service(self):
        if self._service:
            return self._service

        if not all([settings.gmail_client_id, settings.gmail_client_secret, settings.gmail_refresh_token]):
            raise RuntimeError("Credentials Gmail non configurés (gmail_client_id, gmail_client_secret, gmail_refresh_token)")

        creds = Credentials.from_authorized_user_info(
            {
                "client_id":     settings.gmail_client_id,
                "client_secret": settings.gmail_client_secret,
                "refresh_token": settings.gmail_refresh_token,
                "token_uri":     "https://oauth2.googleapis.com/token",
            },
            SCOPES,
        )

        if creds.expired and creds.refresh_token:
            logger.info("[GmailReader] Rafraîchissement du token OAuth2...")
            creds.refresh(Request())

        self._service = build("gmail", "v1", credentials=creds)
        return self._service

    def fetch_emails(self, sender_email: str, max_results: int = 10) -> list[tuple[str, datetime, str]]:
        """
        Retourne une liste de (sender_email, email_date, body_html)
        pour les emails de sender_email des derniers GMAIL_NEWER_THAN jours.
        """
        service = self._get_service()
        query = f"from:{sender_email} newer_than:{GMAIL_NEWER_THAN}"

        try:
            result = service.users().messages().list(
                userId="me",
                q=query,
                maxResults=max_results,
            ).execute()
        except Exception as e:
            logger.error(f"[GmailReader] Erreur liste messages ({sender_email}) : {e}")
            return []

        messages = result.get("messages", [])
        emails = []

        for msg in messages:
            try:
                subject, email_date, html = self._get_email_body(service, msg["id"])
                if html:
                    emails.append((sender_email, email_date, html))
            except Exception as e:
                logger.warning(f"[GmailReader] Erreur lecture message {msg['id']} : {e}")

        return emails

    def _get_email_body(self, service, msg_id: str) -> tuple[str, datetime, str]:
        msg = service.users().messages().get(
            userId="me",
            id=msg_id,
            format="full",
        ).execute()

        subject = ""
        date_raw = ""
        for header in msg["payload"].get("headers", []):
            if header["name"] == "Subject":
                subject = header["value"]
            elif header["name"] == "Date":
                date_raw = header["value"]

        email_date = datetime.now(timezone.utc)
        if date_raw:
            try:
                email_date = parsedate_to_datetime(date_raw).astimezone(timezone.utc)
            except Exception:
                pass

        html = self._extract_html(msg["payload"])
        return subject, email_date, html

    def _extract_html(self, payload) -> str:
        """Extrait le body HTML depuis le payload Gmail (multipart récursif)."""
        if "parts" in payload:
            for part in payload["parts"]:
                if part["mimeType"] == "text/html":
                    data = part["body"].get("data", "")
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                if "parts" in part:
                    result = self._extract_html(part)
                    if result:
                        return result
        else:
            data = payload["body"].get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        return ""