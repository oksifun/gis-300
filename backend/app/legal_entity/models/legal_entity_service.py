from datetime import datetime

from mongoengine import (BooleanField, DateTimeField, Document,
                         EmbeddedDocument, EmbeddedDocumentField, IntField,
                         ObjectIdField, StringField, ValidationError)

from app.legal_entity.tasks.update_vendor import \
    vendor_apply_to_offsets
from processing.models.billing.own_contract import CONTRACT_SELECT_TYPES, \
    ContractSelectTypes
from processing.models.choices import ACCRUAL_SECTOR_TYPE_CHOICES, \
    LEGAL_CONTRACT_CHOICES, ServicesProvisionServiceType
from .legal_entity_contract import LegalEntityContract
from .logs import VendorServiceApplyLog

_UPDATED_FIELDS = ('date_from', 'date_till', 'service', 'service_select_type')


class EmbeddedServicesProvision(EmbeddedDocument):
    measurement = StringField(
        choices=LEGAL_CONTRACT_CHOICES,
        verbose_name='в чем измеряется услуга',
        default=ServicesProvisionServiceType.PER_MONTH,
    )
    value = IntField(
        verbose_name='Значение',
        default=0
    )


class EntityAgreementService(Document):
    """
    Договоры провайдеров и юр.лиц
    """
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'LegalEntityService',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            ('provider', 'house', 'service_select_type'),
            'contract',
        ]
    }

    service = ObjectIdField(
        verbose_name='Ссылка на справочник услуг',
        required=True
    )
    service_select_type = StringField(
        default=ContractSelectTypes.SERVICE,
        choices=CONTRACT_SELECT_TYPES,
        verbose_name='Тип выбранной услуги',
    )
    contract = ObjectIdField(
        verbose_name='Ссылка на договор',
        required=True
    )
    agreement = ObjectIdField(
        verbose_name='Ссылка на соглашение',
        required=True
    )
    entity = ObjectIdField(
        verbose_name='Ссылка на поставщика',
        required=True
    )
    provider = ObjectIdField(
        verbose_name='Ссылка на провайдера',
        required=True
    )
    sector = StringField(
        choices=ACCRUAL_SECTOR_TYPE_CHOICES,
        verbose_name='Направление начислений',
        null=True
    )
    date_from = DateTimeField(
        verbose_name='Дата начала'
    )
    date_till = DateTimeField(
        null=True,
        verbose_name='Дата окончания'
    )
    house = ObjectIdField(
        null=True,
        verbose_name='Дом',
    )
    living_areas = BooleanField(
        null=True,
        verbose_name='Включая квартиры',
    )
    type_provision = EmbeddedDocumentField(
        EmbeddedServicesProvision,
        verbose_name='Измерения услуг',
        required=False,
        default=EmbeddedServicesProvision()
    )
    not_living_areas = BooleanField(
        null=True,
        verbose_name='Включая нежилые помещения',
    )
    parking_areas = BooleanField(
        null=True,
        verbose_name='Включая машиноместа паркинга',
    )
    consider_developer = BooleanField(
        default=False,
        verbose_name='Учитывать ли ЛС застройщика '
                     'при выставлении документов в 1С'
    )
    is_deleted = BooleanField(
        default=False
    )

    def validate_dates(self, date_from=None, date_till=None, **kwargs):
        """
        Проверка, что даты оказания услуг в диапазоне дат соглашения
        """
        contract = LegalEntityContract.objects(
            pk=self.contract
        ).as_pymongo().get()
        if not date_from:
            date_from = self.date_from
        if not date_till:
            date_till = datetime.max
        if date_till and date_till < date_from:
            raise ValidationError('Дата окончания оказания услуг должна '
                                  'быть больше даты начала')
        for agreement in contract['agreements']:
            if self.agreement == agreement['_id']:
                if not agreement['date'] <= date_from <= date_till:
                    raise ValidationError(
                        'Дата начала оказания услуги должна '
                        'находиться в диапазоне дат соглашения'
                    )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        VendorServiceApplyLog.write_log(
            self.entity,
            f'EntityAgreementService {self.id} saved',
        )

    def update(self, **kwargs):
        super().update(**kwargs)
        VendorServiceApplyLog.write_log(
            self.entity,
            f'EntityAgreementService {self.id} updated',
        )
        self.reload()
        fields = set(kwargs).intersection(set(_UPDATED_FIELDS))
        if fields:
            vendor_apply_to_offsets.delay(self.id)
        return self

    @classmethod
    def mark_deleted(cls, agreement=None, contract=None):
        """ Помечает услугу как удаленную при удалении договора/соглашения """
        if agreement:
            query = {'agreement': agreement}
            VendorServiceApplyLog.write_log(
                contract,
                f'EntityAgreementService deleting by agreement {agreement}',
            )
        elif contract:
            query = {'contract': contract}
            VendorServiceApplyLog.write_log(
                contract,
                f'EntityAgreementService deleting by contract {contract}',
            )
            for service in cls.objects(__raw__=query):
                vendor_apply_to_offsets.delay(service.id, delete_mode=True)
        else:
            return
        cls.objects(__raw__=query).update(
            __raw__={'$set': {'is_deleted': True}}
        )
