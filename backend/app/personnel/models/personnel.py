import datetime
import itertools
import logging
from typing import Union

from bson import ObjectId
from mongoengine import (
    EmbeddedDocument,
    ObjectIdField,
    ListField,
    StringField,
    DateTimeField,
    EmbeddedDocumentField,
    BooleanField,
    Document,
    EmailField,
    IntField,
    DynamicField,
    queryset_manager,
    ValidationError,
    DoesNotExist,
)

from app.caching.models.account_groups import (
    SimilarWorkerGroup,
    WorkersFIOGroup,
)
from app.personnel.models.choices import SYSTEM_POSITION_UNIQUE_CODES
from app.personnel.models.denormalization.worker import SystemDepartmentEmbedded
from app.personnel.models.department import Department
from processing.models.billing.account import (
    generate_unique_account_number,
    EmailsManipulatorMixin,
)
from processing.models.billing.base import (
    FilesDeletionMixin,
    BindedModelMixin,
    BindsPermissions,
    ProviderBinds,
    ForeignDenormalizeModelMixin,
)
from app.personnel.models.denormalization.caller import (
    AccountEmbeddedDepartment,
    AccountEmbeddedPosition,
    WorkerCallEmbedded,
)
from processing.models.billing.files import Files
from app.personnel.models.system_department import SystemDepartment
from processing.models.choices import (
    TICKET_ACCESS_LEVEL,
    TicketAccessLevelCode,
    GENDER_TYPE_CHOICES,
    GenderType,
)
from processing.models.exceptions import CustomValidationError
from processing.models.mixins import WithPhonesMixin

logger = logging.getLogger('c300')


class AccountEmbeddedProvider(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    business_types = ListField(ObjectIdField())
    str_name = StringField(verbose_name="Название организации", null=True)
    secured_ip = ListField(StringField())


class AccountEmbeddedElection(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")
    date_from = DateTimeField()  # Date,
    date_till = DateTimeField()  # Date,


class AccountEmbeddedSettings(EmbeddedDocument):
    tickets_access_level = StringField(
        choices=TICKET_ACCESS_LEVEL,
        verbose_name='Уровень доступа к тикетам',
        default=TicketAccessLevelCode.BASIC,
    )


class DocCopies(EmbeddedDocument):
    """
    Копии документов.
    """
    id = ObjectIdField(db_field='_id')
    snils = EmbeddedDocumentField(Files, null=True)
    inn = EmbeddedDocumentField(Files, null=True)
    employment_contract = EmbeddedDocumentField(Files, null=True)
    identity_card = EmbeddedDocumentField(Files, null=True)


class WorkerSupportTimer(EmbeddedDocument):
    stopped_at = DateTimeField(verbose_name="дата конца отсчета")
    started_at = DateTimeField(verbose_name="дата начала отсчета")
    elapsed = IntField(verbose_name="затраченное время в секундах")

    def start(self):
        pass

    def stop(self):
        if self.started_at and not self.stopped_at:
            self.stopped_at = datetime.datetime.now()
            self.elapsed = (self.stopped_at - self.started_at).total_seconds()


class Worker(
    ForeignDenormalizeModelMixin,
    FilesDeletionMixin,
    BindedModelMixin,
    WithPhonesMixin,
    EmailsManipulatorMixin,
    Document,
):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Account',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            ('_binds_permissions.hg', '_type'),
        ],
    }

    # системные поля
    _type = ListField(StringField(required=True))
    is_deleted = BooleanField()
    is_dismiss = BooleanField(
        default=False,
        verbose_name="Уволен ли сотрудник",
    )
    dismiss_date = DateTimeField(
        null=True,
        verbose_name='Дата увольнения',
    )
    is_super = BooleanField(default=False)
    monitoring_enabled = BooleanField(default=False)

    # общие поля Account
    inn = StringField(verbose_name="ИНН", null=True)
    email = StringField(verbose_name="Пользовательский эл. адрес", null=True)
    avatar = ObjectIdField(verbose_name="Пользовательское изображение")
    number = StringField(
        required=True,
        regex='\d{0,13}',
        verbose_name="Номер ЛС"
    )
    comment = StringField(verbose_name="Примечания", null=True)
    str_name = StringField(verbose_name="Строка имени")
    provider = EmbeddedDocumentField(
        AccountEmbeddedProvider,
        verbose_name="Организация"
    )
    has_access = BooleanField(
        null=True,
        default=False,
        verbose_name="Имеет доступ в систему")
    get_access_date = DateTimeField(
        verbose_name="Дата получения доступа в систему"
    )
    created_at = DateTimeField(verbose_name="Дата регистрации в системе")
    old_numbers = ListField(
        StringField(),
        verbose_name="Список старых номеров ЛС, "
                     "унаследованных от прошлых версий системы"
    )
    additional_email = EmailField(verbose_name="Дополнительный email-адрес")
    password = StringField(verbose_name="Пароль")
    activation_code = StringField()
    activation_step = IntField()
    activation_tries = IntField(
        required=False,
        default=0,
        verbose_name="Количество попыток активации"
    )
    password_reset_code = StringField()
    user = ObjectIdField(verbose_name="Старый user_id")
    news_count = IntField(
        default=0,
        verbose_name="кол-во прочитанных новостей"
    )
    delivery_disabled = BooleanField(
        null=True,
        default=False,
        verbose_name="отказ от рассылки"
    )
    snils = StringField(verbose_name="СНИЛС", null=True)

    # поля сотрудника организации
    timer = EmbeddedDocumentField(WorkerSupportTimer, null=True)
    settings = EmbeddedDocumentField(AccountEmbeddedSettings)
    position = EmbeddedDocumentField(AccountEmbeddedPosition)
    department = EmbeddedDocumentField(AccountEmbeddedDepartment)
    employee_id = StringField(null=True)
    is_autoapi = BooleanField()
    is_invalid = BooleanField()
    doc_copies = EmbeddedDocumentField(
        DocCopies,
        verbose_name='Копиии документов сотрудника',
    )
    control_info = DynamicField()
    tenants = ListField(ObjectIdField())
    election_history = ListField(
        EmbeddedDocumentField(AccountEmbeddedElection)
    )

    # поля человеческого существа
    sex = StringField(
        choices=GENDER_TYPE_CHOICES,
        verbose_name="Пол",
        null=True,
        default=GenderType.FEMALE,
    )
    photo = EmbeddedDocumentField(
        Files,
        verbose_name="Фотография работника (для карточки в системе)",
        null=True,
    )
    short_name = StringField()
    birth_date = DateTimeField(verbose_name="Дата рождения", null=True)
    first_name = StringField(verbose_name="Имя")
    last_name = StringField(verbose_name="Фамилия", null=True)
    patronymic_name = StringField(verbose_name="Отчество", null=True)

    _binds_permissions = EmbeddedDocumentField(
        BindsPermissions,
        verbose_name='Права на привязки',
    )
    _binds = EmbeddedDocumentField(
        ProviderBinds,
        verbose_name='Права на привязки',
    )

    # поля-ошибки
    identity_card = DynamicField()
    task = DynamicField()

    @property
    def is_authenticated(self):
        """
        Django compatibility:
        https://docs.djangoproject.com/en/4.0/ref/contrib/auth/#django.contrib.auth.models.User.is_authenticated
        """
        return True

    @property
    def is_anonymous(self):
        """Django compatibility"""
        return False

    @queryset_manager
    def objects(doc_cls, queryset):
        return queryset.filter(_type='Worker')

    @queryset_manager
    def active_workers(doc_cls, queryset):
        """Возвращает всех активных сотрудников."""
        return queryset.filter(
            _type='Worker',
            is_deleted__ne=True,
            is_dismiss__ne=True,
        )

    @property
    def get_worker_add_number(self):
        """Возвращает добавочный номер сотрудника."""
        add_numbers = list({phone.add for phone in self.phones} - {None})
        if add_numbers:
            return add_numbers[0]

    def get_actor(self):
        from app.auth.models.actors import Actor
        return Actor.get_or_create_actor_from_account(self)

    def as_phone_talker(self, phone_number: str) -> dict:
        """Возвращает словарь звонящего/отвечающего работника на вызов."""
        return WorkerCallEmbedded(
            id=self.id,
            name=self.str_name,
            position=self.position._data,
            department=self.department._data,
            phone_number=phone_number,
            provider={
                'str_name': self.provider.str_name,
                '_id': self.provider.id,
            },
        ).to_mongo()

    _FOREIGN_DENORMALIZE_FIELDS = [
        'str_name',
        'short_name',
        'department',
        'position',
    ]

    def save(self, *args, **kwargs):
        self.restrict_changes()
        self.custom_validate_fields()
        self._fill_autofields()
        self._denormalize_own_data()
        self._custom_restrict_changes()
        tickets_access_level_changed = self._is_key_dirty('settings')
        if not self._binds_permissions:
            self._generate_binds_permissions()
        self.access_trigger()
        position_code_changed = ('code' in self.position._get_changed_fields())
        denormalize_fields = self._get_fields_for_foreign_denormalize()
        self.sync_phones_with_actor()
        if denormalize_fields:
            denormalize_tasks = \
                self._create_denormalize_tasks(denormalize_fields)
        else:
            denormalize_tasks = None
        result = super().save(*args, **kwargs)
        if denormalize_tasks:
            self._run_denormalize_tasks(denormalize_tasks)
        if tickets_access_level_changed:
            from app.permissions.tasks.binds_permissions import \
                process_account_binds_models
            process_account_binds_models.delay(self.id)
        self.remove_worker_group()
        self._foreign_denormalize_provider(position_code_changed)
        if not self._binds_permissions.ac:  # Случай создания нового сотрудника
            result.update(_binds_permissions__ac=self.id)
            result._binds_permissions__ac = self.id
            self._binds_permissions__ac = self.id
        return result

    def activate(self, code):
        logger.debug('activate method starts')
        if 'Tenant' in self._type:
            logger.error('Этот метод не создан для активации жителей!')
            return

        if self.activation_code is None:
            return

        if code != self.activation_code:
            raise ValueError('Неверный код активации')

        from app.auth.models.actors import Actor
        try:
            actor: Actor = Actor.objects.get(owner__id=self.id)
        except DoesNotExist as dne:
            logger.error('Actor with owner %s does not exist: %s', self.id, dne)
            raise

        actor.activation_code = self.activation_code = None
        actor.activation_step = self.activation_step = None

        password = self.generate_new_password()
        hashed_password = self.password_hash(password)
        self.password = actor.password = hashed_password
        self.save()
        actor.save()
        self.send_password_mail(password)

    @classmethod
    def process_provider_binds(cls, provider_id, **kwargs):
        pulled = cls.objects(
            provider__id__ne=provider_id,
            _binds__pr=provider_id,
        ).update(pull___binds__pr=provider_id)
        pushed = cls.objects(
            provider__id=provider_id,
        ).update(add_to_set___binds__pr=provider_id)
        return pushed, pulled

    def sync_phones_with_actor(self):
        if not self._created and self._is_triggers(['phones']):
            actor = self.get_actor()
            actor.owner.phones = self.phones
            actor.save()

    def access_trigger(self):
        if self._is_triggers(['email', 'is_dismiss']) and self.has_access:
            self.has_access = False
        if self.is_dismiss and self.has_access:
            self.has_access = False
        super().access_trigger()

    def _custom_restrict_changes(self):
        if not self._created and self._is_triggers(['provider']):
            raise ValidationError("Field 'provider' is read only")
        if self._is_triggers(['position', 'is_dismiss']) and self.position.code:
            for unique_codes in SYSTEM_POSITION_UNIQUE_CODES:
                if self.position.code not in unique_codes:
                    continue
                other_labors = Worker.objects(
                    position__code__in=unique_codes,
                    is_deleted__ne=True,
                    provider__id=self.provider.id,
                    is_dismiss__ne=True,
                ).only(
                    'id',
                ).as_pymongo()
                other_labors = [
                    l['_id'] for l in other_labors if l['_id'] != self.id
                ]
                if other_labors:
                    raise CustomValidationError(
                        'Сотрудник на такой должности уже существует',
                    )
        if self._is_triggers(['is_dismiss']) and self.is_dismiss:
            if not self.dismiss_date:
                raise CustomValidationError('Необходимо указать дату уволнения')

    def _get_provider_id(self):
        return self.department.provider

    def _denormalize_provider(self):
        from processing.models.billing.provider.main import Provider
        provider = Provider.objects(
            id=self.provider.id
        ).as_pymongo().first()
        self.provider.str_name = provider['str_name']
        self.provider.secured_ip = provider.get('secured_ip', [])
        self.provider.business_types = provider['business_types']

    def custom_validate_fields(self):
        if not self.department or not self.department.id:
            raise CustomValidationError('Не задан отдел')
        if not self.position or not self.position.id:
            raise CustomValidationError('Не задана должность')
        if not self.provider or not self.provider.id:
            raise ValidationError("Field 'provider.id' is required")
        if not self.settings:
            self.settings = AccountEmbeddedSettings()

    def _denormalize_department_and_position(self):
        department = Department.objects(
            id=self.department.id,
            provider=self.provider.id,
        ).as_pymongo().get()
        self.department.name = department['name']
        self.department.provider = department['provider']
        if (
                department.get("system_department")
                and department["system_department"].get("_id")
        ):
            self.department.system_department = SystemDepartmentEmbedded(
                id=department["system_department"]["_id"],
                code=department["system_department"].get('code', None)
            )
        for position in department.get("positions", []):
            if position['_id'] != self.position.id:
                continue
            self.position.name = position.get('name')
            self.position.code = position.get('code')
            if position.get("system_position"):
                self.position.system_position = position["system_position"]

    @property
    def is_activated(self):
        return all((
            not getattr(self, 'activation_code', False),
            not getattr(self, 'activation_step', False),
            getattr(self, 'has_access', False)
        ))

    ACCESS_CONTROL_FIELDS = ('has_access', 'email', 'is_dismiss', 'password')

    def restrict_changes(self):
        if self.is_super and self._created:
            raise ValueError('"is_super" is unrestricted field')
        if self.is_super or self._is_key_dirty('is_super'):
            old = Worker.objects(pk=self.id).only('is_super').as_pymongo().get()
            if not old.get('is_super'):
                raise ValueError('"is_super" is unrestricted field')
            if self._is_triggers(list(self.ACCESS_CONTROL_FIELDS)):
                raise ValueError('"is_super" is unrestricted field')
        super().restrict_changes()

    def _fill_autofields(self):
        if self._is_triggers(['last_name', 'first_name', 'patronymic_name']):
            self._fill_name_autofields()
        if not self.number:
            self.number = generate_unique_account_number()
        if self._created:
            self._binds = ProviderBinds(pr=[self.provider.id])
            self._type = ['Worker']

    def _denormalize_own_data(self):
        if self._created:
            self._denormalize_provider()
        if self._is_triggers(['department', 'position']):
            self._denormalize_department_and_position()

    def _fill_name_autofields(self):
        self.str_name = ' '.join(
            filter(
                None,
                [
                    self.last_name,
                    self.first_name,
                    self.patronymic_name,
                ],
            ),
        )
        self.short_name = '{} {}.{}.'.format(
            self.last_name,
            (self.first_name or '')[0:1],
            (self.patronymic_name or '')[0:1]
        ).strip()

    _CHIEF_SYSTEM_CODES = ("ch1", "ch2", "ch3",)
    _ACCOUNTANT_SYSTEM_CODES = ("acc1",)

    def _foreign_denormalize_provider(self, code_changed_flag):
        if (
                code_changed_flag or
                self._is_triggers(['is_dismiss']) or
                self.position.code
        ):
            self._update_worker_in_provider()

    def _update_worker_in_provider(self):
        removed_worker_type = None
        updated_worker_type = None

        from processing.models.billing.provider.main import Provider
        from processing.models.billing.provider.embeddeds import (
            EmbeddedMajorWorker,
        )
        provider = Provider.objects(id=self.provider.id).get()

        #  Если был удалён код или был уволен сотрудник,
        #  удалим запись из провайдера

        if not self.position.code or self.is_dismiss:
            if provider.chief and provider.chief.id == self.id:
                removed_worker_type = 'chief'
            elif provider.accountant and provider.accountant.id == self.id:
                removed_worker_type = 'accountant'
            else:
                return

        elif self.position.code in self._CHIEF_SYSTEM_CODES:
            updated_worker_type = 'chief'
        elif self.position.code in self._ACCOUNTANT_SYSTEM_CODES:
            updated_worker_type = 'accountant'

        if removed_worker_type:
            provider.update(
                **{
                    removed_worker_type: None
                }
            )

        if updated_worker_type:
            embedded_worker = EmbeddedMajorWorker(
                id=self.id,
                _type=self._type,
                last_name=self.last_name,
                first_name=self.first_name,
                email=self.email,
                phones=self.phones,
                patronymic_name=self.patronymic_name,
                str_name=self.str_name,
                short_name=self.short_name,
                position = self.position
            )
            if updated_worker_type == 'chief':
                provider.chief = embedded_worker
            elif updated_worker_type == 'accountant':
                provider.accountant = embedded_worker
            provider.save()

    def delete(self, signal_kwargs=None, **write_concern):
        self.is_deleted = True
        return self.save()

    def _generate_binds_permissions(self):
        if not self._binds_permissions:
            self._binds_permissions = BindsPermissions()
        self._binds_permissions.pr = self.department.provider
        self._binds_permissions.dt = self.department.id
        self._binds_permissions.ac = self.id
        self._binds_permissions.hg = self._get_own_house_group()
        self._binds_permissions.po = self.position.code

    def _get_own_house_group(self):
        from processing.models.permissions import Permissions
        from processing.models.billing.house_group import HouseGroup

        acc_permission = Permissions.objects(
            __raw__={
                '_id': 'Account:{}'.format(self.id),
            },
        ).as_pymongo().first()
        if not acc_permission:
            return None
        house_permissions = acc_permission.get(
            'granular',
            dict(),
        ).get(
            'House',
        )
        if not house_permissions:
            return None
        houses = [ObjectId(key) for key in house_permissions]
        houses.sort()
        house_group = HouseGroup.objects(
            houses=houses,
            hidden=True,
            is_total__ne=True,
        ).only(
            'id',
        ).as_pymongo().first()
        if house_group:
            return house_group['_id']
        hg_id = ObjectId()
        HouseGroup(
            id=hg_id,
            houses=houses,
            title='{} {}'.format(
                len(houses),
                'домов' if str(len(houses))[-1] == '1' else 'дом',
            ),
            provider=self.provider.id,
            hidden=True,
        ).save()
        return hg_id

    def get_similar_workers(self):
        """
        Поиск похожих работников, которые работают в других организациях.
        Поиск происходит только по позициям ChiefPosition и AccountantPosition
        """

        from app.personnel.models.system_department import \
            EmbeddedSystemPosition

        # все возможные позиции, по которым осуществляется поиск
        position_codes = EmbeddedSystemPosition.get_chef_position_codes()

        query = {
            'provider._id': {'$ne': self.provider.id},
            'position.code': {'$in': position_codes},
        }

        match_conditions = []

        # Если есть имя и фамилия, ищем совпадения по ним. Отчество учитывается,
        # если есть и в исходном и в искомом
        if self.last_name and self.first_name:
            match_conditions.append({
                'last_name': self.last_name,
                'first_name': self.first_name,
                '$or': [
                    {'patronymic_name': self.patronymic_name},
                    {'patronymic_name': {'$exists': False}},
                    {'patronymic_name': ''}
                ]
            })

        # Если есть список телефонов пользователя,
        # у которых есть не пустой номер и код,
        # ищем совпадения по любому из них
        valid_phones = [
            phone
            for phone in self.phones
            if phone.code and phone.number
        ]
        if valid_phones:
            match_conditions.append({
                '$or': [
                    {'phones.number': phone.number, 'phones.code': phone.code}
                    for phone in valid_phones
                ]
            })

        # Ищем все совпадения по электронной почте при ее наличии
        if self.email:
            match_conditions.append({
                'email': self.email
            })

        # Если есть хоть одно условий для поиска
        if match_conditions:
            query.update({'$or': match_conditions})
            return list(Worker.objects(__raw__=query))

        else:
            return []

    def get_worker_fio_group(self):

        from app.personnel.models.system_department import \
            EmbeddedSystemPosition

        # все возможные позиции, по которым осуществляется поиск
        position_codes = EmbeddedSystemPosition.get_chef_position_codes()

        query = {
            'provider._id': {'$ne': self.provider.id},
            'position.code': {'$in': position_codes},
            'last_name': self.last_name
        }

        or_conditions = []

        if self.first_name and self.patronymic_name:
            or_conditions.append(
                {
                    'first_name': {
                        '$regex': '^{}'.format(self.first_name[0:2]),
                        '$options': 'i'
                    },
                    'patronymic_name': {
                        '$regex': '^{}'.format(self.patronymic_name[0:2]),
                        '$options': 'i'
                    },
                }
            )

        if self.email:
            or_conditions.append({'email': self.email})

        valid_phones = [
            phone
            for phone in self.phones
            if phone.code and phone.number
        ]
        if valid_phones:
            or_conditions.append({
                '$or': [
                    {'phones.number': phone.number, 'phones.code': phone.code}
                    for phone in valid_phones
                ]
            })

        if or_conditions:
            query.update({'$or': or_conditions})
            return list(Worker.objects(__raw__=query))
        else:
            return []

    def _extend_similar_worker_group(self, group_set, get_group_func):
        """
        Рекурсивно добавляет в group_set всех похожих работников
        :param group_set: Множество worker.id
        :return: group_set
        """

        if 'Worker' not in self._type:
            raise ValueError(
                'call _extend_similar_worker_group() '
                'method for non-worker account'
            )

        for worker in getattr(self, get_group_func)():
            if worker.id not in group_set:
                group_set.add(worker.id)
                group_set = worker._extend_similar_worker_group(
                    group_set,
                    get_group_func
                )

        return group_set

    def remove_worker_group(self):
        SimilarWorkerGroup.objects(workers=self.id).delete()
        WorkersFIOGroup.objects(workers=self.id).delete()

    def get_worker_group(self, group_cls, group_code):
        return (
            # Возвращаем закешированную группу
                group_cls.objects(
                    group_code=group_code,
                    workers=self.id
                ).first()
                or
                # Или создаем и возвращаем новую
                group_cls(
                    group_code=group_code,
                    workers=self._extend_similar_worker_group(
                        {self.id},
                        group_cls.get_group
                    )
                ).save()
        )

    @staticmethod
    def get_workers_groups(workers, group_cls, group_code):
        available_groups = list(group_cls.objects(
            workers__in=workers,
            group_code=group_code,
        ))
        workers_with_groups = set(itertools.chain(*[
            group.workers
            for group in available_groups
        ]))
        workers_id_wo_groups = (
                set(workers)
                -
                workers_with_groups
        )
        return (
                list(available_groups)
                +
                [
                    Worker.objects.get(
                        id=worker
                    ).get_worker_group(
                        group_cls, group_code
                    )
                    for worker in workers
                    if worker in workers_id_wo_groups
                ]
        )

    @staticmethod
    def get_workers_by_system_position_codes(
            system_position_codes,
            providers_id
    ):

        chief_system_positions = set((itertools.chain(*[
            [
                position.id
                for position in positions
                if position.code in system_position_codes
            ]
            for positions in [
                sys_dept.positions
                for sys_dept in SystemDepartment.objects(
                    positions__code__in=system_position_codes
                )
            ]
        ])))

        # TODO INDEX
        # Department.positions.system_position

        chief_positions = set((itertools.chain(*[
            [
                position.id
                for position in positions
                if position.code in system_position_codes
            ]
            for positions in [
                dept.positions
                for dept in Department.objects(
                    positions__system_position__in=chief_system_positions,
                    provider__in=providers_id,
                )
            ]
        ])))

        # TODO INDEX
        # {"is_deleted" : 1}

        return Worker.objects(
            provider__id__in=providers_id,
            _type='Worker',
            position__id__in=chief_positions,
            is_deleted__ne=True,
        ).distinct('id')


class MessengerTemplate(
    Document,
):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'MessengerTemplate',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'worker_id',
        ],
    }

    worker_id = ObjectIdField(
        verbose_name='Worker ObjectId',
        unique=True,
    )
    message = StringField(
        verbose_name='Шаблонное сообщение',
        default='Добрый день, прошу Вас связаться со мной',
    )

    @classmethod
    def get_or_create(
            cls,
            worker_id: Union[ObjectId, str],
    ) -> 'MessengerTemplate':
        instance = cls.objects(worker_id=worker_id).first()
        if not instance:
            instance = cls(worker_id=worker_id).save()
        return instance

    @classmethod
    def upsert(
            cls,
            worker_id: Union[ObjectId, str],
            message: str,
    ) -> 'MessengerTemplate':
        instance = cls.objects(worker_id=worker_id).first()
        if not instance:
            return cls(
                worker_id=worker_id,
                message=message,
            ).save()
        instance.update(message=message)
        return instance.reload()

