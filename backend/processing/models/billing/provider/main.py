# -*- coding: utf-8 -*-
from secrets import token_urlsafe
from mongoengine import (
    Document, StringField, DictField, ListField, ReferenceField,
    EmbeddedDocumentField, DateTimeField, BooleanField, ObjectIdField,
    DynamicField, EmbeddedDocumentListField, ValidationError, signals,
)
from app.personnel.models.department import \
    DepartmentEmbeddedPosition
from app.personnel.models.system_department import SystemDepartment
import settings
from app.personnel.models.department import Department
from processing.models.billing.base import BindsPermissions, CustomQueryMixin, \
    ForeignDenormalizeModelMixin
from processing.models.billing.embeddeds.location import Location
from processing.models.billing.house_group import HouseGroup
from processing.models.choices import (
    PRINT_RECEIPT_TYPE_CHOICES,
    PrintReceiptType,
    ProviderTicketRate,
    RegistryStringFormat,
    PROVIDER_TICKET_RATES_CHOICES,
    CalcSoftwareType, ACCRUAL_LANGUAGE,
    SBER_REGISTRY_NAME_CHOICES,
    REGISTRY_STRING_FORMAT_CHOICES,
)
from processing.models.mixins import WithPhonesMixin
from processing.permissions.bind import Bind
from lib.address import get_location_by_fias, construct_address
from lib.address import get_street_location_by_fias
from processing.models.billing.provider.embeddeds import (
    BicEmbedded,
    EmbeddedSalesProviderStatus,
    EmbeddedMajorWorker,
    EmbeddedTelephonySettings,
    BankAccount,
    BankContract,
    MailingEmbedded,
    CashOnlineEmbedded,
    ProviderProcessingEmbedded,
    ProviderCallEmbedded,
    ProviderRelationsEmbedded,
    ProviderEmbedded,
    AnsweringPersonEmbedded,
    SaleTaskAnsweringPersonEmbedded,
)
from processing.models.billing.provider.mixins import BankAndProviderMixin
from django.conf import settings as django_settings
from app.crm.models.crm import CRM


class DoubleAgentProviderCache(Document):
    meta = {
        'db_alias': 'cache-db',
        'collection': 'provider_cache',
        'index': {'expireAfterSeconds': 3600}
    }

    provider = ObjectIdField()

    ceo_in_providers = EmbeddedDocumentListField(EmbeddedSalesProviderStatus)
    cao_in_providers = EmbeddedDocumentListField(EmbeddedSalesProviderStatus)


class Provider(
    ForeignDenormalizeModelMixin,
    WithPhonesMixin,
    BankAndProviderMixin,
    Document,
):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Provider',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'delivery_keys',
            "chief.id",
            "accountant.id",
            ("reform_id", "inn"),
            "crm_last_action.id",
            "crm_last_event.id",
            "bank_accounts.number",
            "bank_accounts.service_codes",
            "business_types",
            "crm_last_action.date",
            ("name", "crm_last_action.date"),
            "telephony_settings.token",
        ],
    }

    accountant = EmbeddedDocumentField(
        EmbeddedMajorWorker,
        verbose_name="глав. бух"
    )
    chief = EmbeddedDocumentField(
        EmbeddedMajorWorker,
        verbose_name="директор/председатель"
    )
    receipt_type = StringField(
        choices=PRINT_RECEIPT_TYPE_CHOICES,
        default=PrintReceiptType.UNKNOWN,
        verbose_name="печать квитанций"
    )
    language = StringField(
        choices=ACCRUAL_LANGUAGE,
        default='RU'
    )
    telephony_settings = EmbeddedDocumentField(
        EmbeddedTelephonySettings
    )
    bank_accounts = ListField(EmbeddedDocumentField(BankAccount))
    banks_contracts = EmbeddedDocumentListField(BankContract)
    balance_registry_string_format = StringField(
        verbose_name="Формат строки реестра Сальдо",
        choices=REGISTRY_STRING_FORMAT_CHOICES,
        default=RegistryStringFormat.BY_DEFAULT,
    )
    managers = ListField(
        ObjectIdField(),
        verbose_name='Кто работает с организацией',
        default=[]
    )  # TODO delete this field
    online_cash = EmbeddedDocumentField(
        CashOnlineEmbedded,
        verbose_name="Сведения о Dreamkas кассе (онлайн касса)"
    )
    mailing = EmbeddedDocumentField(
        MailingEmbedded,
        verbose_name="Рассылки"
    )
    ticket_rate = StringField(
        choices=PROVIDER_TICKET_RATES_CHOICES,
        default=ProviderTicketRate.LOW,
        verbose_name="Кол-во обращений от организации"
    )  # TODO delete this field
    allow_processing = BooleanField(default=True)
    processing = EmbeddedDocumentField(
        ProviderProcessingEmbedded,
        verbose_name='Настройки эквайринга',
    )
    disable_when_debtor = BooleanField(default=True)
    delivery_keys = ListField(
        StringField(),
        verbose_name='Ключи доступа к новостям',
    )
    _binds_permissions = EmbeddedDocumentField(
        BindsPermissions,
        verbose_name='Привязки к организации и группе домов (P,HG и D)'
    )
    gis_online_changes = BooleanField(
        default=False,
        verbose_name="Выгружать изменения в ГИС ЖКХ?",
    )
    module_1c = BooleanField(
        default=False,
        verbose_name="Подключен модуль 1С?",
    )
    qr_with_els = BooleanField(
        default=False,
        verbose_name="Единый лицевой счет (ГИС ЕЛС) в UIN QR кода?",
    )
    sber_registry_name_format = StringField(
        choices=SBER_REGISTRY_NAME_CHOICES,
        null=True,
        verbose_name="Формат имени при скачивании реестра сбербанка"
    )
    sber_fee_bank_statement = BooleanField(
        default=False,
        verbose_name="Сверка выписки по реестрам от Сбера с комиссией ",
    )
    # ненужные поля
    _type = ListField(StringField())
    sber_online = BooleanField()

    _crm: CRM = None

    @property
    def crm(self) -> CRM:
        """Взаимоотношения с клиентом"""
        if not self._crm:
            assert self.id, \
                "Доступен статус клиента только сохраненного провайдера"

            self._crm = CRM.of(self)

        if self.crm_status != self._crm.status:  # статус экземпляра отличается?
            self.crm_status = self._crm.status  # обновляем без сохранения

        return self._crm

    @property
    def legal_quoted_name(self):
        """
        Полное название организации: ОПФ и наименование.
        """
        _quoted_legal_forms = ('ЖСК', 'ИП',)
        if self.legal_form in _quoted_legal_forms:
            pattern = '{} "{}"'
        else:
            pattern = '{} {}'
        return pattern.format(self.legal_form or '', self.name)

    @property
    def has_access(self):
        return True  # КОСТЫЛЬ

    @property
    def has_mailing_settings(self):
        if not self.mailing or not (self.mailing.slip or self.mailing.notify):
            return False

        return True

    def get_url(self):
        if self.url_managers:
            url = self.url_managers
        else:
            url = settings.DEFAULT_URL
        return f"{settings.DEFAULT_PROTOCOL}://{url}".rstrip('/')

    def get_cabinet_url(self):
        if 'url' in self and self.url:
            url = self.url
        else:
            url = settings.DEFAULT_CABINET_URL
        return f"{settings.DEFAULT_PROTOCOL}://{url}".rstrip('/')

    def get_cabinet_url_no_cyrilic(self):
        if 'url' in self and self.url:
            url = self.url
        else:
            url = settings.DEFAULT_CABINET_URL_NO_CYR
        return f"{settings.DEFAULT_PROTOCOL}://{url}".rstrip('/')

    def as_phone_talker(self, phone_number: str) -> dict:
        """Возвращает словарь для провайдера звонящего/отвечающего на вызов."""
        return ProviderCallEmbedded(
            id=self.id,
            str_name=self.str_name,
            phone_number=phone_number,
        ).to_mongo()

    @property
    def provider_phones(self):
        """Возвращает телефонные номера провайдера для дозвона."""
        phone_types = ['work', 'mobile']
        provider_phones = list(
            ''.join(('8', phone.str_number)) for phone in self.phones
            if phone.phone_type in phone_types)
        providers = list(ProviderCallEmbedded(id=self.id,
                                              str_name=self.str_name,
                                              phone_number=phone)
                         for phone in provider_phones)
        return list(
            SaleTaskAnsweringPersonEmbedded(provider=provider)
            for provider in providers)

    @property
    def accountant_phones(self):
        """Возвращает информацию о бухгалтере для дозвона."""
        if not self.accountant:
            return []
        provider = ProviderEmbedded(
            id=self.id,
            str_name=self.str_name,
        )
        accountant_phones = list(''.join(('8',
                                          phone.code or '812',
                                          phone.number
                                          ))
                                 for phone in self.accountant.phones
                                 if phone.number)
        persons = list(AnsweringPersonEmbedded(
            id=getattr(self.accountant, '_id', None),
            name=self.accountant.str_name,
            position=getattr(self.accountant.position, 'name', 'Бухгалтер'),
            phone_number=phone,
            provider=provider,
        ) for phone in accountant_phones)
        return list(
            SaleTaskAnsweringPersonEmbedded(person=person)
            for person in persons)

    @property
    def chief_phones(self):
        """Возвращает информацию о руководителе для дозвона."""
        if not self.chief:
            return []
        provider = ProviderEmbedded(
            id=self.id,
            str_name=self.str_name,
        )
        chief_phones = list(''.join(('8',
                                     phone.code or '812',
                                     phone.number
                                     ))
                            for phone in self.chief.phones
                            if phone.number)
        persons = list(AnsweringPersonEmbedded(
            id=getattr(self.chief, '_id', None),
            name=self.chief.str_name,
            position=getattr(self.chief.position, 'name', 'Руководитель'),
            phone_number=phone,
            provider=provider,
        ) for phone in chief_phones)
        return list(
            SaleTaskAnsweringPersonEmbedded(person=person)
            for person in persons)

    def get_bank_account(self, house_id, accrual_sector_code) -> BankAccount:
        """
        Найти банковский счет дома (УК) для назначения платежа
        """
        from processing.models.billing.settings import Settings

        house_settings = Settings.objects.only('sectors') \
            .as_pymongo().get(house=house_id, provider=self.id)
        sector_settings = [
            setting
            for setting in house_settings['sectors']
            if setting['sector_code'] == accrual_sector_code
        ]
        if len(sector_settings) != 1:
            raise ValidationError(
                f"Назначение платежа {accrual_sector_code}"
                f" дома {house_id} не определено"
            )
        accrual_settings = sector_settings[0]

        bank_accounts = [
            account
            for account in self.bank_accounts
            if account['number'] == accrual_settings['bank_account']
        ]
        if len(bank_accounts) != 1:
            raise ValidationError(
                f"Не определен банковский счет"
                f" {accrual_settings['bank_account']} дома {house_id}"
            )

        return bank_accounts[0]

    def check_binds_permissions(self):
        # Избыточно, привязка должна быть создана после создания в
        # CRUD-контроллере
        if not self._binds_permissions and self.id:
            self._binds_permissions = BindsPermissions(pr=self.id)
        elif self._binds_permissions and not self._binds_permissions.pr:
            self._binds_permissions.pr = self.id

    def save(self, *args, **kwargs):
        # TODO: убрать, когда не нужен будет core
        self._type = ['Provider']
        if self.chief and not isinstance(self.chief, EmbeddedMajorWorker):
            self.denormalize_chief()
        if (
                self.accountant
                and not isinstance(self.accountant, EmbeddedMajorWorker)
        ):
            self.denormalize_accountant()
        self._fill_auto_fields()
        self.check_binds_permissions()
        if self._is_triggers(['address']):
            self.denormalize_addresses()
        if self._is_triggers(['inn', 'str_name']):
            from app.caching.tasks.denormalization import \
                denormalize_provider_to_cabinets
            denormalize_provider_to_cabinets.delay(provider_id=self.id)
        denormalize_fields = self._get_fields_for_foreign_denormalize()
        result = super().save(*args, **kwargs)
        crm_obj = CRM.get_or_create(self)
        crm_obj.update_provider_info(self)
        if denormalize_fields:
            self._foreign_denormalize(denormalize_fields)
        if result['id']:
            self.get_provider_system_positions()
        return result

    def get_provider_system_positions(self):
        director_codes = ('ch1', 'ch2', 'ch3')
        position_names = {
            'ch1': ('Правление', 'Председатель Правления'),
            'ch2': ('Руководящий состав', 'Генеральный директор'),
        }
        accountant_code = 'acc1'
        housing_compains = ('ЖСК', 'ТСЖ',)
        # получаем исходные данные
        depts = Department.objects.filter(
            provider=self.id,
            is_deleted__ne=True,
        )
        s_depts = list(SystemDepartment.objects.all().as_pymongo())
        ch_positions = {}
        acc_positions = {}
        sys_positions = {}
        for d in s_depts:
            for p in d['positions']:
                if p.get('code') in director_codes:
                    ch_positions[p['code']] = (d['_id'], p['_id'])
                    sys_positions[p['code']] = (d['_id'], p['_id'])
                elif p.get('code') == accountant_code:
                    acc_positions[p['code']] = (d['_id'], p['_id'])
                    sys_positions[p['code']] = (d['_id'], p['_id'])
        # пробуем найти существующие в организации системные должности
        exist = {}
        for d in depts._iter_results():
            if not d.system_department or not d.system_department.id:
                continue
            for p_code, dept_pos in sys_positions.items():
                if dept_pos[0] == d.system_department.id:
                    for p in d.positions:
                        if not p.system_position:
                            continue
                        if dept_pos[1] == p.system_position:
                            exist[p_code] = (d, p)
                            break
        # выбираем бухгалтера, добавляем, если нет
        result = {}
        if accountant_code in exist:
            result['accountant'] = exist[accountant_code]
        else:
            position = DepartmentEmbeddedPosition(
                is_active=True,
                system_position=acc_positions[accountant_code][1],
                name='Главный бухгалтер',
                code=accountant_code,
                inherit_parent_rights=False,
            )
            dept = Department(
                provider=self.id,
                system_department={'_id': acc_positions[accountant_code][0]},
                name='Бухгалтерский отдел',
                settings={'access_without_email': False},
                inherit_parent_rights=False,
                positions=[position]
            )
            dept.save()
            result['accountant'] = (dept, position)
        # выбираем одного руководителя, добавляем, если нет
        found_codes = list(set(director_codes) & set(exist.keys()))
        if found_codes:
            result['chief'] = exist[found_codes[0]]
        else:
            ch_code = 'ch1' if self.legal_form in housing_compains else 'ch2'
            position = DepartmentEmbeddedPosition(
                is_active=True,
                system_position=ch_positions[ch_code][1],
                name=position_names[ch_code][1],
                code=ch_code,
                inherit_parent_rights=False,
            )
            dept = Department(
                provider=self.id,
                system_department={'_id': ch_positions[ch_code][0]},
                name=position_names[ch_code][0],
                settings={'access_without_email': False},
                inherit_parent_rights=False,
                positions=[position]
            )
            dept.save()
            result['chief'] = (dept, position)
        return result

    def _fill_auto_fields(self):
        if not self.receipt_type:
            # нужно так как в базе есть невалидные данные
            self.receipt_type = PrintReceiptType.UNKNOWN
        if not self.calc_software:
            # нужно так как в базе есть невалидные данные
            self.calc_software = CalcSoftwareType.OTHER
        if self._is_triggers(['name', 'legal_form']):
            self.str_name = f'{self.legal_form} "{self.name}"'

    def denormalize_chief(self):
        self.chief = self._get_worker_denormalization_dict(self.chief)

    def denormalize_accountant(self):
        self.accountant = self._get_worker_denormalization_dict(self.accountant)

    def _get_worker_denormalization_dict(self, worker):
        result = EmbeddedMajorWorker()
        for key in ('email', 'last_name', 'first_name', 'patronymic_name',
                    'str_name', 'short_name', 'phones', 'position', "id",
                    "_type"):
            setattr(result, key, getattr(worker, key))
        return result

    def denormalize_addresses(self):
        if not self.address:
            return
        attr_names = ['real', 'postal', 'correspondence']
        locations = {}
        if self.pk:
            old_data = Provider.objects(
                pk=self.pk,
            ).only(
                'address',
            ).get()
            if old_data.address:
                for attr_name in attr_names:
                    new = getattr(self.address, attr_name)
                    old = getattr(old_data.address, attr_name)
                    if (
                            old
                            and
                            new.fias_house_guid
                            and
                            new.fias_house_guid == old.fias_house_guid
                    ):
                        locations[old.fias_house_guid] = old.to_json()
        for attr_name in attr_names:
            field = getattr(self.address, attr_name)
            if not field:
                continue
            if field.fias_house_guid in locations:
                location = Location.from_json(locations[field.fias_house_guid])
                location.area_number = field.area_number
                setattr(
                    self.address,
                    attr_name,
                    location,
                )
            elif field.fias_house_guid:
                location = get_location_by_fias(
                    field.fias_house_guid,
                    area_number=field.area_number,
                )
                setattr(
                    self.address,
                    attr_name,
                    location,
                )
                setattr(
                    self,
                    f'{attr_name}_address',
                    location.extra['address_full'],
                )
                locations[field.fias_house_guid] = location.to_json()
            elif field.fias_street_guid:
                location = get_street_location_by_fias(
                    field.fias_street_guid
                )
                setattr(
                    self.address,
                    attr_name,
                    location,
                )
                setattr(
                    self,
                    f'{attr_name}_address',
                    location.extra['address_full'],
                )
            else:
                setattr(self.address, attr_name, None)

    def get_address_string(self, address_type, include_postal_code=True):
        """
        Строковое представление указаного адреса организации
        :param address_type: тип адреса (почтовый/реальный)
        :param include_postal_code: добавлять ли почтовый индекс
        """
        if address_type not in ('postal', 'real', 'correspondence'):
            raise AttributeError()
        addr_attr = getattr(self.address, address_type)
        return construct_address(
            street_address=addr_attr.location,
            house_number_full=addr_attr.house_number,
            postal_code=addr_attr.postal_code if include_postal_code else None,
            area_number=addr_attr.area_number,
        )

    @staticmethod
    def get_address_string_by_dict(provider_as_dict, address_type,
                                   include_postal_code=True):
        """
        Строковое представление указаного адреса организации
        :param provider_as_dict: провайдер в виде словаря
        :param address_type: тип адреса (почтовый/реальный)
        :param include_postal_code: добавлять ли почтовый индекс
        """
        if address_type not in ('postal', 'real', 'correspondence'):
            raise AttributeError()
        if not provider_as_dict.get('address'):
            return ''
        addr_attr = provider_as_dict['address'].get(address_type)
        if not addr_attr:
            return ''
        if include_postal_code:
            postal_code = addr_attr.get('postal_code')
        else:
            postal_code = None
        return construct_address(
            street_address=addr_attr.get('location'),
            house_number_full=addr_attr.get('house_number'),
            postal_code=postal_code,
            area_number=addr_attr.get('area_number'),
        )

    @classmethod
    def generate_telephony_token(cls):
        return token_urlsafe(64)

    @classmethod
    def generate_provider_binds_hg(cls, provider_id):
        from processing.data_producers.associated.base import get_binded_houses
        pr_houses = get_binded_houses(provider_id)
        house_group = HouseGroup.objects(
            provider=provider_id,
            is_total=True,
            is_deleted__ne=True
        ).first()
        if house_group:
            house_group.houses = pr_houses
        else:
            house_group = HouseGroup(
                houses=pr_houses,
                title=f"Домов: {len(pr_houses)}",
                provider=provider_id,
                is_total=True,
                hidden=True,
            )
        house_group.save()
        cls(
            pk=provider_id,
        ).update(
            __raw__={
                '$set': {
                    '_binds_permissions.hg': house_group.id,
                },
            },
        )

        return house_group


class BankProvider(BankAndProviderMixin, CustomQueryMixin, Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'BankProvider',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            "bic_body.BIC",
            "settings_payments.doc",
        ],
    }

    _type = ListField(StringField())
    NAMEN = StringField()
    NEWNUM = ListField(StringField())
    KSNP = StringField()
    NAMEP = StringField()
    DATE_IN = DateTimeField()

    receipt_type = StringField(
        choices=PRINT_RECEIPT_TYPE_CHOICES,
        default=PrintReceiptType.SELF,
        verbose_name="печать квитанций"
    )
    # legacy = Optional(Date)
    import_statements_begin_date = DateTimeField(
        verbose_name="Дата начала загрузки выписок, "
                     "все документы в выписке до этой даты игнорируются"
    )
    # CRUTCH:
    # В старых моделях у BankProvider и Provider разные схемы settings_payments
    # settings_payments = ListField(EmbeddedDocumentField(
    #     SettingsPayments,
    #     verbose_name="настройки оплат"
    # ))
    # CRUTCH END

    # legacy - Required([Bic.Id])
    bic = ListField(
        ObjectIdField(),
        required=True
    )
    bic_body = EmbeddedDocumentListField(
        BicEmbedded,
        required=False,
        verbose_name='Подгруженные данные из BicNew'
    )
    is_agent = BooleanField(required=True, default=False)

    # удалить поля
    allow_processing = DynamicField()
    processing = DynamicField()

    def __str__(self):
        return self.NAMEP

    def current_bic(self, latest: bool = True):
        """Получить текущий БИК банка"""
        # bank = cls.objects.only('bic_body').as_pymongo().get(id=bank_id)

        index = -1 if latest else 0
        if not self.bic_body or not self.bic_body[index].BIC:
            raise ValidationError(f"Для банка {self.id} не задан БИК")

        return self.bic_body[index].BIC


class ProviderPublicCode(Document):
    """
    Код организации-клиента для получения публичных данных
    """
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'ProviderPublicCode'
    }

    provider = ReferenceField(Provider, required=True)
    code = StringField(required=True)

    def save(self, *args, **kwargs):
        result = super().save(*args, **kwargs)
        # Делаем новую привязку в коллекции Bind
        # получение _id создаваемого документа
        # в коллекции ProviderPublicCode
        new_document_id = self.id
        bind_data = dict(obj=new_document_id, col='ProviderPublicCode')
        new_bind = Bind(**bind_data)
        # вставляем новый документ в коллекцию Bind
        new_bind.save()
        return result


class ProviderRelations(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'ProviderRelations',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'provider',
            'slaves.provider',
        ],
    }
    provider = ObjectIdField(verbose_name='Главенствующая организация')
    slaves = EmbeddedDocumentListField(
        ProviderRelationsEmbedded,
        verbose_name='Подконтрольные организации'
    )

    @classmethod
    def get_allowed_houses(cls, master_id, slave_id):
        relations = cls.objects(
            provider=master_id,
        ).only('slaves').as_pymongo().first()
        if relations:
            for slave in relations['slaves']:
                if slave['provider'] == slave_id:
                    return slave['houses']
        return []

    @classmethod
    def get_slaves(cls, provider_id, house_id):
        relations = cls.objects(provider=provider_id).as_pymongo().first()
        if relations and relations.get('slaves'):
            return [
                x['provider']
                for x in relations['slaves'] if house_id in x['houses']
            ]
        return []

    @classmethod
    def add_slave(cls, master_id, slave_id, houses_ids):
        relations = cls.objects(provider=master_id).first()
        if not relations:
            relations = cls(provider=master_id, slaves=[])
        for slave in relations.slaves:
            if slave.provider == slave_id:
                slave.houses = list(set(slave.houses) | set(houses_ids))
                relations.save()
                return relations
        relations.slaves.append(ProviderRelationsEmbedded(
            provider=slave_id,
            houses=houses_ids,
        ))
        relations.save()
        return relations


class ProviderCounter(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'ProviderCounter'
    }
    provider = ObjectIdField()
    ticket = DictField(db_field='Ticket')

    @classmethod
    def get_next_number(cls, year, provider_id):
        updater = 'inc__ticket__number__{}'.format(year)
        cls.objects(provider=provider_id).upsert_one(**{updater: 1})
        counter = cls.objects(
            provider=provider_id
        ).only(updater.lstrip('inc__')).as_pymongo().get()
        return counter['Ticket']['number'][str(year)]
