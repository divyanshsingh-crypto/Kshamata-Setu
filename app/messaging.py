import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("kshamata_setu.messaging")
logging.basicConfig(level=logging.INFO)

class MessagingGateway:
    """
    Twilio Gateway with transparent Mock-Fallback.
    If real TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN are provided in environment,
    transmits real SMS/WhatsApp messages via Twilio REST API.
    Otherwise, logs message safely with masked phone and returns success.
    """
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_phone = os.getenv("TWILIO_PHONE_NUMBER", "+15005550006")
        self.is_live = bool(self.account_sid and self.auth_token)
        self.client = None

        if self.is_live:
            try:
                from twilio.rest import Client
                self.client = Client(self.account_sid, self.auth_token)
                logger.info("Twilio live gateway initialized.")
            except Exception as e:
                logger.warning(f"Twilio initialization failed: {e}. Falling back to mock gateway.")
                self.is_live = False

    def send_sms(self, to_phone: str, body: str) -> Dict[str, Any]:
        from app.security import mask_phone
        masked = mask_phone(to_phone)

        if self.is_live and self.client:
            try:
                message = self.client.messages.create(
                    body=body,
                    from_=self.from_phone,
                    to=to_phone
                )
                logger.info(f"[TWILIO LIVE SMS SENT] sid={message.sid} to={masked}")
                return {
                    "status": "DELIVERED_LIVE",
                    "sid": message.sid,
                    "provider": "twilio_live",
                    "to": masked
                }
            except Exception as e:
                logger.error(f"[TWILIO LIVE ERROR] {e}. Falling back to simulated dispatch.")
                return {
                    "status": "MOCK_FALLBACK_AFTER_ERROR",
                    "error": str(e),
                    "provider": "mock_logger",
                    "to": masked,
                    "simulated_body": body
                }
        else:
            # Mock mode: log clearly for demo audit
            logger.info(f"[SIMULATED OUTREACH] To={masked} | Channel=SMS/WhatsApp | Message: \"{body}\"")
            return {
                "status": "DELIVERED_MOCK",
                "sid": f"mock_msg_{os.urandom(6).hex()}",
                "provider": "mock_logger",
                "to": masked,
                "simulated_body": body
            }

messaging_service = MessagingGateway()
