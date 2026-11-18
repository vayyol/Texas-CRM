"""Modelos SQLAlchemy do TexasCRM."""
from app.models.api_key import APIKey
from app.models.asaas import AsaasCheckout, AsaasWebhookEvent
from app.models.chat import Conversation, Message
from app.models.prompt_template import PromptTemplate
from app.models.subscription import Subscription
from app.models.usage import UsageRecord
from app.models.user import User
from app.models.whatsapp import WhatsAppConsent, WhatsAppConversation, WhatsAppMessage, WhatsAppSession
from app.models.whatsapp_followup import WhatsAppFollowupCursor, WhatsAppFollowupRecord, WhatsAppFollowupSetting

__all__ = [
    "User", "Subscription", "APIKey", "AsaasCheckout", "AsaasWebhookEvent",
    "UsageRecord", "Conversation", "Message", "PromptTemplate",
    "WhatsAppConsent", "WhatsAppSession", "WhatsAppConversation", "WhatsAppMessage",
    "WhatsAppFollowupSetting", "WhatsAppFollowupRecord", "WhatsAppFollowupCursor",
]
