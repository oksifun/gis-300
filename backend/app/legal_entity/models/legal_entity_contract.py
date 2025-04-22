from datetime import datetime

from bson import ObjectId
from mongoengine import (BooleanField, DateTimeField, Document,
                         EmbeddedDocument, EmbeddedDocumentField,
                         EmbeddedDocumentListField, ObjectIdField, StringField)

from processing.models.billing.files import Files
from processing.models.billing.own_contract import OWN_CONTRACT_STATES
from processing.models.choices import LEGAL_DOCUMENT_TYPE_CHOICES


class EntityContractFiles(EmbeddedDocument):
    original = EmbeddedDocumentField(
        Files,
        default=Files,
        verbose_name='Оригинал .doc'
    )
    scan = EmbeddedDocumentField(
        Files,
        default=Files,
        verbose_name='Скан .pdf'
    )


class EntityAgreement(EmbeddedDocument):
    id = ObjectIdField(db_field='_id', default=ObjectId)
    number = StringField(verbose_name='Номер соглашения')
    date = DateTimeField(verbose_name='Дата соглашения')
    date_till = DateTimeField(
        verbose_name='Дата окончания соглашения',
        null=True
    )
    closed = BooleanField(
        default=False,
        verbose_name='Закрыто ли соглашение'
    )
    file = EmbeddedDocumentField(
        EntityContractFiles,
        verbose_name='Оригинал и скан документа'
    )
    state = StringField(null=True, choices=OWN_CONTRACT_STATES)
    lock_state = StringField(
        choices=(
            'blocked',
            'edit'
        ),
        verbose_name='Заблокирован ли документ'
    )


class LegalEntityContract(Document):
    """
    Договоры провайдеров и юр.лиц
    """
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'LegalEntityContract2',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'entity',
            ('provider', 'closed'),
        ],
    }

    provider = ObjectIdField(
        required=True,
        verbose_name='Провайдер (организация-клиент)'
    )

    entity = ObjectIdField(
        required=True,
        verbose_name='Организация'
    )
    _type = StringField(
        verbose_name='Тип документа',
        choices=LEGAL_DOCUMENT_TYPE_CHOICES
    )
    number = StringField(verbose_name='Номер договора')
    name = StringField(required=True, verbose_name='Наименование договора')
    date = DateTimeField(verbose_name='Дата договора')
    agreements = EmbeddedDocumentListField(
        EntityAgreement,
        verbose_name='Соглашения к договору'
    )
    closed = BooleanField(
        default=False,
        verbose_name='Закрыт ли договор'
    )
    created = DateTimeField(default=datetime.now, null=True)
    date_closed = DateTimeField(null=True)
    phone = StringField(verbose_name='Номер телефона')

    @classmethod
    def get_or_create(cls, entity, provider):
        entity_pk = entity.id if isinstance(entity, Document) else entity
        provider_pk = provider.id if isinstance(provider,
                                                Document) else provider
        if not (bool(entity_pk) & bool(provider_pk)):
            return
        contract = cls.objects(
            entity=entity_pk,
            provider=provider_pk,
        ).first()
        if not contract:
            contract = cls(
                entity=entity_pk,
                provider=provider_pk,
                name="Основной договор",
            )
            contract.save()
        return contract

    def save(self, *args, **kwargs):
        super_save = super().save(*args, **kwargs)
        return super_save
