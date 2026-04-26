"""
GmailReader — connexion Gmail OAuth2 et récupération des emails bruts.
Adapté du backend : credentials lus depuis variables d'env (Secret Manager)
au lieu de settings FastAPI. Token rafraîchi réécrit dans Secret Manager.
"""

import base64
import json
import logging
import os
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.cloud import secretmanager
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
GMAIL_NEWER_THAN = "2d"

GCP_PROJECT_ID = os.environ.get("BQ_PROJECT_ID", "")
GMAIL_TOKEN_SECRET_NAME = "gmail-token"


class GmailReader:

    def __init__(self):
        self._service = None
        self._creds = None

    def _get_service(self):
        if self._service:
            return self._service

        credentials_json = os.environ.get("GMAIL_CREDENTIALS_JSON")
        token_json = os.environ.get("GMAIL_TOKEN_JSON")

        if not credentials_json or not token_json:
            raise RuntimeError("GMAIL_CREDENTIALS_JSON ou GMAIL_TOKEN_JSON manquant")

        creds_data = json.loads(credentials_json)
        token_data = json.loads(token_json)

        # Supporte les formats "installed" et "web" de credentials.json
        client_info = creds_data.get("installed") or creds_data.get("web")
        if not client_info:
            raise RuntimeError("Format credentials.json invalide — clé 'installed' ou 'web' manquante")

        self._creds = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=client_info["client_id"],
            client_secret=client_info["client_secret"],
            scopes=SCOPES,
        )

        if self._creds.expired and self._creds.refresh_token:
            logger.info("[GmailReader] Rafraîchissement du token OAuth2...")
            self._creds.refresh(Request())
            self._update_token_secret()

        self._service = build("gmail", "v1", credentials=self._creds)
        return self._service

    def _update_token_secret(self) -> None:
        """Réécrit le token mis à jour dans GCP Secret Manager."""
        if not GCP_PROJECT_ID:
            logger.warning("[GmailReader] BQ_PROJECT_ID manquant — token non mis à jour dans Secret Manager")
            return
        try:
            updated = {
                "token":         self._creds.token,
                "refresh_token": self._creds.refresh_token,
                "token_uri":     self._creds.token_uri,
                "client_id":     self._creds.client_id,
                "client_secret": self._creds.client_secret,
                "scopes":        list(self._creds.scopes) if self._creds.scopes else [],
            }
            client = secretmanager.SecretManagerServiceClient()
            secret_name = f"projects/{GCP_PROJECT_ID}/secrets/{GMAIL_TOKEN_SECRET_NAME}"
            client.add_secret_version(
                request={
                    "parent":  secret_name,
                    "payload": {"data": json.dumps(updated).encode("utf-8")},
                }
            )
            logger.info("[GmailReader] Token Gmail mis à jour dans Secret Manager")
        except Exception as e:
            logger.error(f"[GmailReader] Erreur mise à jour token Secret Manager : {e}", exc_info=True)

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
    
    def dump_html(self, sender_email: str, output_dir: str = "/app/debug") -> None:
        """
        Sauvegarde le HTML brut des emails d'un expéditeur dans output_dir.
        Usage : debug uniquement pour construire les parseurs.
        """
        import os
        os.makedirs(output_dir, exist_ok=True)
        service = self._get_service()
        query = f"from:{sender_email} newer_than:7d"
        try:
            result = service.users().messages().list(
                userId="me", q=query, maxResults=3
            ).execute()
        except Exception as e:
            logger.error(f"[GmailReader] dump_html erreur liste ({sender_email}) : {e}")
            return

        for i, msg in enumerate(result.get("messages", [])):
            try:
                _, _, html = self._get_email_body(service, msg["id"])
                if html:
                    filename = f"{output_dir}/{sender_email.replace('@', '_').replace('.', '_')}_{i}.html"
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(html)
                    logger.info(f"[GmailReader] Dump sauvegardé : {filename}")
            except Exception as e:
                logger.warning(f"[GmailReader] dump_html erreur message {msg['id']} : {e}")

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