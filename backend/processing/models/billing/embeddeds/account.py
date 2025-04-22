# -*- coding: utf-8 -*-
from mongoengine import (
    EmbeddedDocument,
    ObjectIdField,
    StringField,
    IntField,
)


class TenantCallEmbedded(EmbeddedDocument):
    """Вызываемый/Звонящий житель, записанный в истории вызовов."""
    id = ObjectIdField(db_field="_id")
    name = StringField(verbose_name="ФИО жителя")
    address = StringField(
        verbose_name="Адрес",
    )
    phone_number = StringField(
        verbose_name="Номер телефона",
    )


class TelegramChatId(EmbeddedDocument):
    """Chat ID привязанный в телеграм боте для номера телефона."""
    chat_id = IntField()
    phone_number = StringField()
