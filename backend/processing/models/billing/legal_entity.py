from datetime import datetime
from bson import ObjectId
from mongoengine import Document, DateTimeField, StringField, ReferenceField, \
    ObjectIdField, ListField, EmbeddedDocument, EmbeddedDocumentListField, \
    EmbeddedDocumentField, Q, BooleanField, IntField, ValidationError

from processing.models.billing.account import Account
from processing.models.billing.base import BindedModelMixin
from processing.models.billing.embeddeds.phone import DenormalizedPhone
from processing.models.billing.files import Files
from processing.models.billing.own_contract import OWN_CONTRACT_STATES, \
    CONTRACT_SELECT_TYPES, ContractSelectTypes
from processing.models.choices import LEGAL_FORM_TYPE_CHOICES, \
    ACCRUAL_SECTOR_TYPE_CHOICES, LEGAL_DOCUMENT_TYPE_CHOICES, \
    LEGAL_CONTRACT_CHOICES

from processing.models.billing.provider.main import BankProvider
from processing.models.choices import LegalFormType

from app.legal_entity.tasks.update_vendor import vendor_apply_to_offsets


class LegalEntityDetailsEmbedded(EmbeddedDocument):
    """
    Реквизиты юр.лиц
    """
    date_from = DateTimeField(required=True, verbose_name='Начиная с')
    full_name = StringField(required=True, verbose_name='Полное наименование')
    short_name = StringField(required=True, verbose_name='Краткое наименование')
    legal_form = StringField(required=True, choices=LEGAL_FORM_TYPE_CHOICES)
    inn = StringField(required=True, verbose_name='ИНН')

    created = DateTimeField()
    closed = DateTimeField()


class LegalEntityBankAccountEmbedded(EmbeddedDocument):
    """
    Расчётные счета юр.лиц
    """

    bank = ObjectIdField(required=False, verbose_name='Банк')
    bic = StringField(required=True, verbose_name='БИК')
    number = StringField(required=True, verbose_name='Номер счета')
    corr_number = StringField(default="")
    date_from = DateTimeField(verbose_name='Дата открытия')
    active_till = DateTimeField(verbose_name='Активен по')

    created = DateTimeField()
    closed = DateTimeField()


class CurrentDetails(EmbeddedDocument):
    current_name = StringField(verbose_name='Текущее наименование')
    current_inn = StringField(verbose_name='Текущий ИНН')
    created = DateTimeField()
    closed = DateTimeField()


class LegalEntity(Document):
    """
    Юридические лица
    """
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'LegalEntity',
        'index_background': True,
        'auto_create_index': False,
    }
    bank_account = EmbeddedDocumentListField(
        LegalEntityBankAccountEmbedded,
        verbose_name='Расчётные счета'
    )
    details = EmbeddedDocumentListField(
        LegalEntityDetailsEmbedded,
        required=True,
        verbose_name='Реквизиты',
    )
    phones = EmbeddedDocumentListField(
        DenormalizedPhone, verbose_name="Список телефонов")
    ogrn = StringField(required=True, verbose_name='ОГРН')
    current_details = EmbeddedDocumentField(
        CurrentDetails,
        verbose_name='Текущие реквизиты'
    )
    created = DateTimeField(default=datetime.now)

    def save(self, *args, **kwargs):
        self.get_current_details()
        super().save(*args, **kwargs)

    def update(self, **kwargs):
        super().update(
            current_details=self.get_current_details(),
            **kwargs
        )

    def get_current_details(self):
        current_details = CurrentDetails(
            current_name=self.details[-1].full_name,
            current_inn=self.details[-1].inn,
            created=self.details[-1].created,
            closed=self.details[-1].closed,
        )
        if self._created:
            current_details.date_from = self.details[-1].created
        self.current_details = current_details
        return self.current_details

    @classmethod
    def create_new_by_inn(cls, inn, name, date_from=None):
        entity = cls(
            ogrn='',
            created=datetime.now(),
            details=[LegalEntityDetailsEmbedded(
                date_from=datetime.now() if not date_from else date_from,
                full_name=name,
                short_name=name,
                legal_form='',
                inn=inn,
                created=datetime.now(),
            )]
        )
        entity.save()
        return entity


class ProviderBinds(EmbeddedDocument):
    pr = ListField(ObjectIdField())
    REQUIRED_BINDS = ('pr',)


class LegalEntityDetails(Document):
    """
    Реквизиты юр.лиц
    """
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'LegalEntityDetails',
    }
    entity = ReferenceField(
        'processing.models.billing.legal_entity.LegalEntity',
        required=True,
        verbose_name="Организация"
    )
    date_from = DateTimeField(required=True, verbose_name='Начиная с')
    full_name = StringField(required=True, verbose_name='Полное наименование')
    short_name = StringField(required=True, verbose_name='Краткое наименование')
    legal_form = StringField(required=True, choices=LEGAL_FORM_TYPE_CHOICES)
    inn = StringField(verbose_name='ИНН')
    created = DateTimeField()
    closed = DateTimeField()


class LegalEntityBankAccount(Document):
    """
    Расчётные счета юр.лиц
    """
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'LegalEntityBankAccount',
    }
    entity = ReferenceField(
        'processing.models.billing.legal_entity.LegalEntity',
        required=True,
        verbose_name="Организация"
    )
    bank = ReferenceField(
        'processing.models.billing.provider.Provider',
        required=True,
        verbose_name='Ссылка на банк'
    )
    number = StringField(required=True, verbose_name='Номер счета')
    date_from = DateTimeField(verbose_name='Дата открытия')
    active_till = DateTimeField(verbose_name='Активен по')
    created = DateTimeField()
    closed = DateTimeField()


class LegalEntityProviderBind(Document, BindedModelMixin):
    """
    Привязки провайдеров и юр.лиц. Клиенты не обращаются в LegalEntity напрямую,
    а только через эти привязки.
    """
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'LegalEntityProviderBind',
    }

    provider = ObjectIdField(
        required=True,
        verbose_name='Провайдер (организация-клиент)'
    )

    entity = ObjectIdField(
        required=True,
        verbose_name='Организация'
    )
    entity_details = EmbeddedDocumentListField(
        LegalEntityDetailsEmbedded,
        required=True,
        verbose_name='Реквизиты',
    )
    phones = EmbeddedDocumentListField(
        DenormalizedPhone, verbose_name="Список телефонов")
    entity_bank_accounts = EmbeddedDocumentListField(
        LegalEntityBankAccountEmbedded,
        verbose_name='Расчётные счета'
    )

    created = DateTimeField()
    closed = DateTimeField()

    _binds = EmbeddedDocumentField(
        ProviderBinds,
        verbose_name='Привязки к организации'
    )

    @classmethod
    def get_or_create(cls, entity, provider):
        if not(bool(entity) & bool(provider)):
            return
        entity = entity if isinstance(entity, Document) else LegalEntity.objects(id=entity).first()
        provider_pk = provider.id if isinstance(provider, Document) else provider
        if not(bool(entity) & bool(provider_pk)):
            return
        bind = cls.objects(
            entity=entity.id,
            provider=provider_pk,
        ).first()
        if not bind:
            bind = cls(
                entity=entity.id,
                provider=provider_pk,
                entity_details=entity.details,
            )
            bind.save()
        return bind

    @classmethod
    def get_binds_query(cls, binds_permissions, raw: bool = False):
        """
        Метод для преобразования переданной привязки в нужный для модели вид
        :param raw: если нужен в виде словоря
        :param binds_permissions: переданные привязки
        :return: dict, Q
        """
        result = super().get_binds_query(binds_permissions, raw)
        if raw:
            return result
        else:
            return result & Q()

    def _get_providers_binds(self):
        return [self.provider]

    def denormalize_legal_entity(self):
        legal_entity = LegalEntity.objects(id=self.entity).first()
        if legal_entity:
            legal_entity.phones = self.phones
            legal_entity.details = self.entity_details
            legal_entity.save()

    def save(self, *args, **kwargs):
        if not self._binds:
            self._binds = ProviderBinds(pr=self._get_providers_binds())
        super_save = super().save(*args, **kwargs)
        self.denormalize_legal_entity()
        return super_save

    @classmethod
    def create_new_legal_binds(
        cls,
        legal_provider,
        legal_inn,
        legal_name,
        short_name=None,
        legal_form='',
        ogrn='',
        phones=None,
        bank_accounts=None
    ):
        """
        Функция создает новые привязки у юр. лица, елси юр. лица не существует то,

        создает и юр лицо
        :param legal_provider: id провайдера с которым у Юр лица составлен договор
        :param legal_inn: ИНН юридического лица
        :param legal_name: Название Юр. лица
        :param short_name: Коротое название организации если есть, по умолчанию None
        :param legal_form: Форма юр. лица по умолчанию ''
        :param ogrn: ОГРН по умолчанию ''
        :param phones: список телефонный номеров юр лица
        :param bank_accounts список банквоский реквизитов
        """
        if not phones:
            phones = []
        if not bank_accounts:
            bank_accounts = []
        legal_form_list = [e for _, e in LegalFormType.__dict__.items()]
        if legal_form not in legal_form_list:
            return f'Такой "{legal_form}" формы организации не существует'
        legal_entity = LegalEntity.objects(
            current_details__current_inn=legal_inn
        ).first()
        if not legal_entity:
            legal_entity = cls.create_new_legal_entity(
                legal_inn,
                legal_name,
                legal_form,
                short_name,
                ogrn,
                phones,
                bank_accounts
            )
        if not LegalEntityProviderBind.objects(entity=legal_entity.id).first():
            provider_bind = LegalEntityProviderBind(
                entity=legal_entity.id,
                provider=legal_provider,
                created=datetime.now(),
                entity_details=legal_entity.details,
                entity_bank_accounts=legal_entity.bank_account,
                phones=[DenormalizedPhone(**phone) for phone in phones]
            )
            try:
                provider_bind.save()
            except:
                return 'Параметры переданы неверно'
        else:
            return 'Привязки для этой организации существуют'

    @staticmethod
    def create_new_legal_entity(
        legal_inn,
        legal_name,
        legal_form,
        short_name,
        ogrn,
        phones,
        bank_accounts
    ):
        legal_entity = LegalEntity(
            ogrn=ogrn,
            phones=[DenormalizedPhone(**phone) for phone in phones]
        )
        details = LegalEntityDetailsEmbedded(
            inn=legal_inn,
            full_name=legal_name,
            short_name=short_name if short_name else legal_name,
            date_from=datetime.now(),
            legal_form=legal_form,
            created=datetime.now(),
        )
        if bank_accounts:
            for bank_account in bank_accounts:
                bank = BankProvider.objects(
                    bic_body__BIC=bank_account['bic']
                ).as_pymongo().first()
                if bank and bank.get('_id'):
                    bank_account['bank'] = bank['_id']
                    bank_account['date_from'] = bank.get('bic_body')[-1].get('DateIn')

        bank_accounts = [
            LegalEntityBankAccountEmbedded(**bank_account)
            for bank_account in bank_accounts
        ]
        legal_entity.details = [details]
        legal_entity.bank_account = bank_accounts

        legal_entity.save()
        # except:
        #     raise ValidationError('Неверные параметры')
        return legal_entity


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


class EmbeddedServicesProvision(EmbeddedDocument):
    measurement = StringField(
        choices=LEGAL_CONTRACT_CHOICES,
        verbose_name='в чем измеряется услуга'
    )
    value = IntField(
        verbose_name='Значение'
    )


class EntityAgreementService(EmbeddedDocument):
    id = ObjectIdField(db_field='_id', default=ObjectId)
    service = ObjectIdField(
        verbose_name='Ссылка на справочник услуг',
    )
    service_select_type = StringField(
        default=ContractSelectTypes.SERVICE,
        choices=CONTRACT_SELECT_TYPES,
        verbose_name='Тип выбранной услуги',
    )
    sector = StringField(
        choices=ACCRUAL_SECTOR_TYPE_CHOICES,
        verbose_name='Направление начислений',
    )
    date_from = DateTimeField(verbose_name='Дата начала')
    date_till = DateTimeField(
        null=True,
        verbose_name='Дата окончания',
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


class EntityAgreement(EmbeddedDocument):
    id = ObjectIdField(db_field='_id', default=ObjectId)
    number = StringField(verbose_name='Номер соглашения')
    date = DateTimeField(verbose_name='Дата соглашения')
    date_till = DateTimeField(
        null=True,
        verbose_name='Дата окончания соглашения',
    )
    closed = BooleanField(
        default=False,
        verbose_name='Закрыто ли соглашение'
    )
    services = EmbeddedDocumentListField(
        EntityAgreementService,
        default=[],
        verbose_name='Услуги',
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
        'collection': 'LegalEntityContract',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'entity',
            {
                'fields': [
                    'provider',
                    'agreements.services.house',
                ],
            },
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

    @classmethod
    def get_or_create(cls, entity, provider):
        entity_pk = entity.id if isinstance(entity, Document) else entity
        provider_pk = provider.id if isinstance(provider, Document) else provider
        if not(bool(entity_pk) & bool(provider_pk)):
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
        self.try_to_save_service()
        super_save = super().save(*args, **kwargs)
        tenants_ids = self._add_relatied_accounts()
        # Отправка в Celery
        # add_account_to_sync.delay(self.provider, tenants_ids)
        vendor_apply_to_offsets.delay(self.id)
        # self.validate_services()
        return super_save

    def try_to_save_service(self):
        for agreement in self.agreements:
            for service in agreement.services:
                if (
                    service.service_select_type == ContractSelectTypes.SERVICE
                    and not service.service
                ):
                    raise ValidationError('Не выбрана услуга')

    def _add_relatied_accounts(self):
        # Найти всех жителей, которых затронуло изменение контракта
        tenants_ids = Account.objects(
            _type="LegalTenant",
            entity_contract=self.id,
            provider__id=self.provider,
        ).as_pymongo().distinct("_id")
        return tenants_ids

    def validate_services(self):

        if any([
            service.service is None
            for agreement in self.agreements
            for service in agreement.services
        ]):
            raise ValidationError(
                f'В договоре {self.number} не указана услуга!')
