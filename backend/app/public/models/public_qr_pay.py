from mongoengine import (
    DateTimeField,
    Document,
    EmbeddedDocument,
    EmbeddedDocumentListField,
    IntField,
    ListField,
    ObjectIdField,
    StringField,
)

from processing.models.choices import ACCRUAL_SECTOR_TYPE_CHOICES


class AddressAndSectorsEmbedded(EmbeddedDocument):
    account_id = ObjectIdField(required=True)
    full_address = StringField(required=True)
    sectors = ListField(
        StringField(choices=ACCRUAL_SECTOR_TYPE_CHOICES),
    )


class SessionPayEmbedded(EmbeddedDocument):
    account_id = ObjectIdField(required=True)
    create = DateTimeField(required=True, verbose_name='Дата оплаты')
    sector = StringField(required=False)
    accrual_id = ObjectIdField(required=False)
    # value заполнится только после того как эквайер пришлет лог оплаты
    value = IntField(required=False, verbose_name='Сумма оплаты')


class PublicPayQr(Document):
    """Лог обращений к платежным сервисам для жителя"""
    meta = {
        'db_alias': 'queue-db',
        'collection': 'tenant_data_public_pay',
    }
    pay_service = StringField(
        required=True,
        verbose_name='Сервис источник оплаты'
    )
    addresses_and_sectors = EmbeddedDocumentListField(
        AddressAndSectorsEmbedded,
        required=False,
        verbose_name="Список адресов и направлений жителя"
    )
    sessions_pay = EmbeddedDocumentListField(
        SessionPayEmbedded,
        required=False,
        verbose_name='Данные оплаты'
    )
    create = DateTimeField(
        required=True,
        verbose_name='Дата запроса на оплату'
    )
    amount_of_possible_spending = IntField(
        required=False,
        verbose_name='Всего адрес+направления'
    )
