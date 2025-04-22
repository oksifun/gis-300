from mongoengine import EmbeddedDocumentListField

from processing.models.billing.base import ModelMixin
from processing.models.billing.embeddeds.phone import DenormalizedPhone


class WithPhonesMixin(ModelMixin):
    """Миксин для моделей со списком телефонов."""

    phones = EmbeddedDocumentListField(
        DenormalizedPhone,
        verbose_name="Список телефонов",
    )

    CONNECT_SAVE_FUNCTIONS = True
