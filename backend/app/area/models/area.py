from datetime import datetime

from bson import ObjectId
from mongoengine import (
    BooleanField, DateTimeField, Document, EmbeddedDocument,
    EmbeddedDocumentField, EmbeddedDocumentListField, FloatField, IntField,
    ListField, ObjectIdField, StringField, ValidationError
)

from processing.models.billing.base import HouseGroupBinds, BindedModelMixin
from processing.models.billing.common_methods import get_area_house_groups, \
    get_area_number
from processing.models.billing.embeddeds.house import DenormalizedHouseWithFias
from processing.models.choice.area_passport import (
    KITCHEN_LIGHTING_CHOICES, KITCHEN_LOCATION_CHOICES, ROOM_BALCONY_CHOICES,
    ROOM_DEFECTS_CHOICES, ROOM_ENGINEERING_STATUS_CHOICES, ROOM_ENTRY_CHOICES,
    ROOM_FLOOR_CHOICES, ROOM_FORM_CHOICES, ROOM_PLAN_CHOICES,
    ROOM_REPAIR_CHOICES, ROOM_TYPE_CHOICES, WC_TYPE_CHOICES,
    RoomType,
)
from processing.models.choices import (
    AREA_COMMUNICATIONS_CHOICES, AREA_INTERCOM_CHOICES,
    AREA_TOTAL_CHANGE_REASON_CHOICES, PRIVILEGE_TYPES_CHOICES,
    STOVE_TYPE_CHOICES,
    AreaCommunicationsType, AreaIntercomType, AreaType,
)


_SQUARE_FIELDS_CHANGE_TRIGGER = [
    'area_total_history',
    'area_total',
    'area_living',
]
_NUMBER_FIELDS_CHANGE_TRIGGER = [
    'number',
    'num_letter',
    'num_alt',
    'num_desc',
    '_type',
]


class AreaTeleComunication(EmbeddedDocument):
    """
    Изменение в количестве вводов теле-коммуникации
    """
    value = IntField(
        required=True,
        verbose_name='Количество вводов',
    )
    date = DateTimeField(verbose_name='Дата изменения')
    # TODO Удалить после мигарции
    comment = StringField(verbose_name='Комментарий', null=True)
    id = ObjectIdField(db_field="_id", default=ObjectId)


class AreaEmbeddedRoom(EmbeddedDocument):
    """
    Комната в квартире
    """
    id = ObjectIdField(db_field='_id', default=ObjectId)

    # SubArea
    number = IntField(null=True, verbose_name='Номер')
    square = FloatField(required=True, verbose_name='Площадь')
    gis_uid = StringField(
        null=True,
        verbose_name='Уникальный номер помещения в ГИС ЖКХ'
    )
    cadastral_number = StringField(null=True, verbose_name='Кадастровый номер')

    # Room
    antenna_count = ListField(
        EmbeddedDocumentField(AreaTeleComunication),
        verbose_name='История установки антенн',
    )
    radio_count = ListField(
        EmbeddedDocumentField(AreaTeleComunication),
        verbose_name='История установки радиоточки',
    )
    type = StringField(
        choices=ROOM_TYPE_CHOICES,
        verbose_name='Тип комнаты',
        null=True,
        default=RoomType.LIVING,
    )
    plan = StringField(
        choices=ROOM_PLAN_CHOICES,
        null=True,
        verbose_name='Планировка комнат',
    )
    form = StringField(
        choices=ROOM_FORM_CHOICES,
        null=True,
        verbose_name='Форма комнат'
    )
    entry = StringField(
        choices=ROOM_ENTRY_CHOICES,
        null=True,
        verbose_name='Вход в помещение',
    )
    balcony = StringField(
        choices=ROOM_BALCONY_CHOICES,
        null=True,
        verbose_name='Балкон'
    )
    floor = StringField(
        choices=ROOM_FLOOR_CHOICES,
        null=True,
        verbose_name='Пол'
    )
    repair = StringField(
        choices=ROOM_REPAIR_CHOICES,
        null=True,
        verbose_name='Ремонт'
    )
    engineering_status = StringField(
        choices=ROOM_ENGINEERING_STATUS_CHOICES,
        null=True,
        verbose_name='Техническое состояние комнаты',
    )
    description = StringField(verbose_name='Описание', null=True)
    kitchen_location = StringField(
        choices=KITCHEN_LOCATION_CHOICES,
        null=True,
        verbose_name='Расположение кухни',
    )
    kitchen_lighting = StringField(
        choices=KITCHEN_LIGHTING_CHOICES,
        null=True,
        verbose_name='Освещение кухни',
    )
    wc_type = StringField(
        choices=WC_TYPE_CHOICES,
        null=True,
        verbose_name='Тип санузла'
    )
    defects = StringField(
        choices=ROOM_DEFECTS_CHOICES,
        null=True,
        verbose_name='Дефекты'
    )


class CommunicationsEmbedded(EmbeddedDocument):
    """ Вложенное поле о заведенных коммуникациях """
    id = ObjectIdField(db_field="_id", required=True, default=ObjectId)
    description = StringField(verbose_name='Комментарий', default='')
    meter_type = StringField(
        choices=AREA_COMMUNICATIONS_CHOICES,
        verbose_name='Тип коммунального ресурса для сопоставления со счётчиком',
        required=True,
    )
    room = ObjectIdField(
        null=True,
        verbose_name='Привязка к комнате'
    )
    is_active = BooleanField(verbose_name='Активный/Неактивный', default=True)
    standpipe = ObjectIdField(
        null=True,
        verbose_name='Ссылка на домовой стояк'
    )
    is_bonded = BooleanField(
        null=True,
        verbose_name='Является ли коммуникация привязанной'
    )


class AreaTotalHistory(EmbeddedDocument):
    """
    Изменение общей площади помещения
    """
    # TODO Нужно будет удалить и провести миграцию
    id = ObjectIdField(db_field='_id', default=ObjectId)
    date = DateTimeField(
        required=True,
        default=lambda: datetime(2000, 1, 1),
        verbose_name='Дата изменения'
    )
    value = FloatField(
        required=True,
        default=0.0,
        verbose_name='Значение площади'
    )
    change_reason = StringField(
        null=True,
        choices=AREA_TOTAL_CHANGE_REASON_CHOICES,
        verbose_name='Основание изменения',
    )


class RosreestrParams(EmbeddedDocument):
    """
    verified_with_tenants: если у всех жителей стоит True, то поле тоже True.
    Если хоть у одного жителя стоит False, то результат False. В остальном None
    """
    area = FloatField(
        null=True,
        verbose_name='Площадь из росреестра'
    )
    verified_with_rosreestr = BooleanField(
        null=True,
        verbose_name='Площадь квартиры сверена с площадью в Rosreestr'
    )
    verified_with_tenants = BooleanField(
        null=True,
        verbose_name='Результат сверки данных жителей с росреестром'
    )
    last_update = DateTimeField(
        null=True,
        verbose_name='Дата последнего обновления данных из росреестра'
    )


class Binds(EmbeddedDocument):
    HG = ListField(ObjectIdField(verbose_name='Привязка к группе домов'))


class Area(Document, BindedModelMixin):
    """
    Помещения в домах: квартиры, нежилые помещения, паркинг
    """
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Area',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            '_binds.hg',
            ('_binds.hg', 'str_number'),
            ('cadastral_number', 'is_deleted')
        ],
    }

    _type = ListField(StringField())
    is_deleted = BooleanField()

    # BaseArea
    rooms = ListField(
        EmbeddedDocumentField(AreaEmbeddedRoom),
        verbose_name='Список комнат',
    )
    has_bath = BooleanField(default=True, verbose_name='Есть ванная')
    area_loggias = FloatField(default=0.0, verbose_name='Площадь лоджий')
    area_balconies = FloatField(default=0.0, verbose_name='Площадь балконов')
    area_pantries = FloatField(default=0.0, verbose_name='Площадь кладовых')
    area_cupboards = FloatField(default=0.0, verbose_name='Площадь шкафов')
    area_corridors = FloatField(default=0.0, verbose_name='Площадь коридоров')

    # Area
    house = EmbeddedDocumentField(
        DenormalizedHouseWithFias,
        required=True,
        verbose_name='Дом',
    )
    porch = ObjectIdField(null=True, verbose_name='Ссылка на парадную в доме')
    floor = IntField(null=True, verbose_name='Этаж')
    number = IntField(required=True, verbose_name='Номер помещения')
    num_letter = StringField(
        null=True,
        verbose_name='Литера в номере'
    )
    num_alt = IntField(
        null=True,
        verbose_name='Дробь (дополнительный номер)'
    )
    num_desc = StringField(
        null=True,
        verbose_name='Свободное дополнение к номеру'
    )
    str_number = StringField(
        verbose_name='Краткое наименование помещения на основе номера',
    )
    str_number_full = StringField(
        verbose_name='Полное наименование помещения на основе номера',
    )
    order = IntField(
        verbose_name='Порядковый номер помещения в доме для упорядочивания',
    )
    area_height = FloatField(default=0.0, verbose_name='Высота стен')
    area_total = FloatField(
        default=0.0,
        verbose_name='Текущая общая площадь'
    )
    area_total_history = EmbeddedDocumentListField(
        AreaTotalHistory,
        default=[AreaTotalHistory()],
        verbose_name='История изменения общей площади',
    )
    stove_type = StringField(
        null=True,
        choices=STOVE_TYPE_CHOICES,
        verbose_name='Тип плиты',
    )
    has_hw = BooleanField(
        null=True,
        required=True,
        default=True,
        verbose_name='Наличие ГВС',
    )
    has_cw = BooleanField(
        null=True,
        required=True,
        default=True,
        verbose_name='Наличие ХВС',
    )
    has_ch = BooleanField(
        null=True,
        required=True,
        default=True,
        verbose_name='Наличие отопления',
    )
    has_lift = BooleanField(
        null=True,
        required=True,
        default=True,
        verbose_name='Оплата лифта',
    )
    has_boiler = BooleanField(
        null=True,
        required=True,
        default=False,
        verbose_name='Наличие водогрея',
    )
    is_shared = BooleanField(
        null=True,
        default=False,
        verbose_name='Коммунальная квартира',
    )
    is_rent = BooleanField(default=False, verbose_name='Сдаётся в аренду')
    is_allowed_meters = BooleanField(
        required=True,
        default=True,
        verbose_name='Возможна установка ПУ',
    )
    cadastral_number = StringField(
        null=True,
        default='',
        verbose_name='Кадастровый номер',
    )
    gis_uid = StringField(
        null=True,
        verbose_name='Уникальный номер помещения в ГИС ЖКХ'
    )
    communications = ListField(
        EmbeddedDocumentField(CommunicationsEmbedded),
        verbose_name='Вводы коммуникаций',
    )
    intercom = StringField(
        choices=AREA_INTERCOM_CHOICES,
        default=AreaIntercomType.INTERCOM,
        verbose_name='Наличие/тип домофона/замка',
    )

    # NotLivingArea
    is_parking = BooleanField(
        default=False,
        verbose_name='Помещение является паркингом',
    )
    common_property = BooleanField(
        default=False,
        verbose_name='Является общедомовым имуществом',
    )

    # LivingArea
    area_living = FloatField(
        default=0.0,
        verbose_name='Жилая площадь',
    )
    area_common = FloatField(
        default=0.0,
        verbose_name='Площадь мест общего пользования'
    )

    # ParkingArea
    parent_area = ObjectIdField(
        null=True,
        verbose_name='Ссылка на нежилое помещение, '
                     'в котором находится паркоместо'
    )

    _binds = EmbeddedDocumentField(
        HouseGroupBinds,
        verbose_name='Привязки к группе домов'
    )

    rosreestr = EmbeddedDocumentField(
        RosreestrParams,
        default=None,
        verbose_name='Данные из росреестра'
    )

    # ненужные поля
    property_type = StringField(
        default="private",
        choices=PRIVILEGE_TYPES_CHOICES
    )
    has_chute = BooleanField(
         required=True,
         default=False,
         verbose_name='Наличие мусоропровода',
    )

    @staticmethod
    def suffix_of(kind: str) -> str:
        """Суффикс номера (типа) помещения"""
        if kind == AreaType.PARKING_AREA:
            return 'П'
        elif kind == AreaType.NOT_LIVING_AREA:
            return 'Н'
        else:  # AreaType.LIVING_AREA?
            return ''

    @property
    def kind(self) -> str:
        """Вид помещения (жилое, нежилое, паркинг)"""
        return self._type[0] if self._type else None

    @property
    def full_number(self) -> str:
        """Полный номер помещения"""
        # WARN num_letter не имеет отношения к виду помещения (Н, П)
        return f"{self.number}{self.num_letter or ''}" \
            f"{f'/{self.num_alt}' if self.num_alt else ''}"  # WARN без num_desc

    @property
    def fullest_number(self) -> str:
        """Полный номер помещения с описанием"""
        if isinstance(self.num_desc, str):
            # WARN описание (номера) помещения может содержать литеру
            description: str = self.num_desc.strip()
            if description:
                return f"{self.full_number} {description}"

        return self.full_number

    @property
    def prefix(self) -> str:
        """Префикс номера (типа) помещения"""
        if self.kind == AreaType.PARKING_AREA:
            return 'м/м.'
        elif self.kind == AreaType.NOT_LIVING_AREA:
            return 'пом.'
        else:  # AreaType.LIVING_AREA?
            return 'кв.'

    @property
    def suffix(self) -> str:
        """Суффикс номера (типа) помещения"""
        return self.suffix_of(self.kind)

    @property
    def default_order(self) -> int:
        """Порядковый номер помещения"""
        if self.kind == AreaType.PARKING_AREA:
            type_factor = 60
        elif self.kind == AreaType.NOT_LIVING_AREA:
            type_factor = 30
        else:  # AreaType.LIVING_AREA?
            type_factor = 0

        return self.number * 10 + type_factor * 1000000

    def parse_description(self, update_number: bool = False) -> tuple:
        """Разложить описание помещения на составляющие (номер, литеру,...)"""
        if isinstance(self.num_desc, str) and len(self.num_desc.strip()) == 0:
            self.num_desc = None

        parsed: tuple = get_area_number(self.num_desc)  # или пустой

        if parsed and update_number:  # описание (номера) помещения разложено?
            prefix, number, annex, suffix, kind = parsed
            if not self.number:  # None или 0
                self.number = int(number)  # номер обязателен при разложении
            elif self.number != int(number):
                # print('PARSED NUMBER', number, 'NOT AS AREA',
                #     self.id, 'NUMBER', self.number)  # TODO raise?
                pass

            if not self.num_alt and annex is not None:
                self.num_alt = int(annex)

            if suffix is not None and len(suffix) == 1:  # литера?
                self.num_letter = suffix

            if suffix is not None and len(suffix) > 1:  # не литера?
                self.num_desc = suffix
            # TODO elif prefix is not None: self.num_desc = prefix
            else:  # литера номера извлечена из описания!
                self.num_desc = None  # WARN очищаем описание номера

        # TODO self.kind = type_of(kind)

        return parsed

    def provider_bind(self, provider_id: ObjectId):
        """Привязка помещения к (домам) организации"""
        assert self.id, "Необходим идентификатор привязываемого помещения"

        from processing.models.billing.area_bind import AreaBind
        area_bind: AreaBind = AreaBind.objects(__raw__={
            'area': self.id,  # индекс
            'provider': provider_id,  # индекс
            'closed': None,  # : datetime
        }).order_by('-created').first()  # первая с конца - последняя
        if area_bind is None:  # привязка не найдена?
            area_bind = AreaBind(area=self.id, provider=provider_id,
                created=datetime.now())  # closed=None по умолчанию
            area_bind.save()  # сохраняем созданную привязку к организации

        return area_bind

    def save(self, *args,  **kwargs):
        self.restrict_changes()
        self._fill_problem_fields()
        self._fill_automatic_fields()
        self._check_communication()
        self._check_house_binds()
        if not self._created and self._is_triggers(['cadastral_number']):
            from app.rosreestr.services.verify_cadastral_number import \
                 check_cadastral_number
            check_cadastral_number(self.cadastral_number)
        if self._created:
            denormalize_fields = []
        else:
            denormalize_fields = self._has_foreign_denormalizing_changes()
        rosreestr_data_changed = self._check_cad_numbers()
        result = super().save(*args,  **kwargs)
        if denormalize_fields:
            for field in denormalize_fields:
                self._foreign_denormalize(field)
        if rosreestr_data_changed:
            from app.rosreestr.model.tasks import RosreestrAreaExchangeTask
            no_sq = 'cadastral_number' in rosreestr_data_changed
            RosreestrAreaExchangeTask(
                area=self.pk,
                check_square=not no_sq,
            ).save()
        return result

    def delete(self, signal_kwargs=None, **write_concern):
        from processing.models.billing.accrual import Accrual
        from app.offsets.models.offset import Offset
        from processing.models.billing.payment import Payment
        accruals = Accrual.objects(account__area__id=self.id)
        payments = Payment.objects(account__area__id=self.id)
        offsets = Offset.objects(refer__account__area__id=self.id)
        if accruals or payments or offsets:
            raise ValidationError(
                'Нельзя удалить помещение у которого есть начисления!'
            )
        if not self.is_deleted:
            self.is_deleted = True
            self.save()
            self._delete_meters()
            self._delete_tenants()

    def _delete_meters(self):
        from app.meters.models.meter import AreaMeter
        AreaMeter.objects(
            area__id=self.id,
            is_deleted__ne=True
        ).update(set__is_deleted=True)

    def _delete_tenants(self):
        from processing.models.billing.account import Tenant
        Tenant.objects(
            area__id=self.id,
            is_deleted__ne=True
        ).update(set__is_deleted=True)

    def _fill_problem_fields(self):
        """
        Заполнение полей значениями по умолчанию,
        которые установлены в этих полях.
        Так как ME не хочет этого делать в некоторых случаях!
        """
        fields = (
            'has_ch',
            'has_hw',
            'has_cw',
            'has_lift',
            'has_boiler',
            'area_total_history'
        )
        for field in fields:
            if getattr(self, field) is None:
                setattr(self, field, self._fields[field].default)

    _FOREIGN_DENORMALIZE_FIELDS = [
        'number',
        'str_number_full',
        'str_number',
        'order',
        'is_shared',
        'house.address',
        'house.id',
        '_type',
    ]

    def _has_foreign_denormalizing_changes(self):
        return self._is_triggers(self._FOREIGN_DENORMALIZE_FIELDS)

    def _foreign_denormalize(self, field):
        from app.caching.tasks.denormalization import foreign_denormalize_data
        foreign_denormalize_data.delay(
            model_from=Area,
            field_name=field,
            object_id=self.pk,
        )

    def _check_communication(self):
        """ Проверка коммуникационных вводов """

        if self._created:
            if not self.communications or len(self.communications) == 0:
                self._fill_default_communications()
        else:
            self._validate_communications()

    def _check_house_binds(self):
        """ Добавляет группы домов, к которым принадлежит помещение """

        if not self._binds:
            if not self.id:
                self.id = ObjectId()
                self._created = True
            hgb = get_area_house_groups(self.id, self.house.id)
            self._binds = HouseGroupBinds(hg=hgb)

    def _validate_communications(self):
        """ Проверки корректности коммуникационных вводов """

        area_before_save = Area.objects(pk=self.pk).get()
        comms_before_save = area_before_save.communications
        # Получаем id вводов, которые удаляются
        cur_ids = [n_c.id for n_c in self.communications]
        deleted_comms = [
            c.id for c in comms_before_save
            if c.id not in cur_ids
        ]
        if deleted_comms:
            from app.meters.models.meter import AreaMeter
            meters = AreaMeter.objects(
                area__id=self.pk,
                communication__in=deleted_comms,
                is_deleted__ne=True,
            ).as_pymongo().first()
            if meters:
                raise ValidationError(
                    'Нельзя удалить ввод, к которому привязан счетчик!'
                )

    def _denormalize_number(self):
        """ Денормализация всех полей, связанных с номером квартиры """

        def get_base_str_number():
            return '{}{}{}{}'.format(
                self.number,
                self.num_letter or '',
                '/{}'.format(self.num_alt) if self.num_alt else '',
                self.num_desc or ''
            )

        def get_order(area_type_coef):
            return area_type_coef * 1000000 + self.number * 10

        if self._type[0] == 'ParkingArea':
            self.str_number = '{}П'.format(get_base_str_number())
            self.str_number_full = 'м/м. {}'.format(self.str_number)
            self.order = get_order(60)
        elif self._type[0] == 'NotLivingArea':
            self.str_number = '{}Н'.format(get_base_str_number())
            self.str_number_full = 'пом. {}'.format(self.str_number)
            self.order = get_order(30)
        else:
            self.str_number = get_base_str_number()
            self.str_number_full = 'кв. {}'.format(self.str_number)
            self.order = get_order(0)

    def _denormalize_square(self):
        """Денормализация площади квартиры"""
        # сортируем историю площадей по дате (новые идентификаторы)
        self.area_total_history.sort(key=lambda rec: rec.date)

        last_total: AreaTotalHistory = self.area_total_history[-1]
        if self.area_total != last_total.value:
            self.area_total = last_total.value

        if self.area_total < 0:  # (временно) допускается 0
            raise ValidationError(
                "Общая площадь помещения не может быть отрицательной"
            )
        elif self.area_living > self.area_total > 0:  # (временно) допускается 0
            raise ValidationError(
                "Жилая площадь помещения не может быть больше общей"
            )

        if (self.kind == AreaType.LIVING_AREA and
                self.area_total > self.area_living > 0):
            self.area_common = self.area_total - self.area_living

    def _fill_default_communications(self):
        """ Введение базовых коммуникационных вводов """

        self.communications = [
            CommunicationsEmbedded(
                id=ObjectId(),
                description='ХВС1',
                meter_type=AreaCommunicationsType.COLD_WATER,
            ),
            CommunicationsEmbedded(
                id=ObjectId(),
                description='ГВС1',
                meter_type=AreaCommunicationsType.HOT_WATER,
            ),
            CommunicationsEmbedded(
                id=ObjectId(),
                description='Отопление',
                meter_type=AreaCommunicationsType.HEAT,
            ),
            CommunicationsEmbedded(
                id=ObjectId(),
                description='Электричество',
                meter_type=AreaCommunicationsType.ELECTRICITY,
            ),
        ]

    def _denormalize_virtual_room_square(self):
        """ Денормализация площади в зависимости от данных о комнатах """

        for room in self.rooms:
            if room.number is None:
                squares = [
                    room.square
                    for room in self.rooms
                    if room.number is not None
                ]
                room.square = self.area_total - round(sum(squares), 2)
                return

    def _denormalize_house(self):
        """ Получение данных о доме из имеющегося id """

        from app.house.models.house import House

        fields = 'fias_addrobjs', 'address'
        hs = House.objects(id=self.house.id).only(*fields).as_pymongo().get()
        self.house.address = hs['address']
        self.house.fias_addrobjs = hs['fias_addrobjs']

    def _fill_automatic_fields(self):
        """ Пересборка автоматических полей (денормализация) """

        if self._is_triggers(_SQUARE_FIELDS_CHANGE_TRIGGER):
            self._denormalize_square()

        if self._is_triggers(_NUMBER_FIELDS_CHANGE_TRIGGER):
            self._denormalize_number()

        if self._is_triggers(['house']):
            self._denormalize_house()

        self._denormalize_virtual_room_square()

    @classmethod
    def process_house_binds(cls, house_id):
        """ Обновление привязок у всех квартир дома """

        areas = cls.objects(house__id=house_id).distinct('id')
        # Группируем квартиры по привязкам
        binds_groups = {}
        for area in areas:
            groups = binds_groups.setdefault(
                tuple(get_area_house_groups(area, house_id)), list()
            )
            groups.append(area)
        # Обновим квартиры каждой группы привязок разом
        for hg in binds_groups:
            cls.objects(pk__in=binds_groups[hg]).update(set___binds__hg=hg)

    @classmethod
    def update_gis_data(cls, area_id: ObjectId, unified_number: str):
        """Обновить идентификатор ГИС ЖКХ помещения"""
        cls.objects(id=area_id).update_one(
            set__gis_uid=unified_number,
            upsert=False  # не создавать новые документы
        )

    def _check_cad_numbers(self):
        if self._created:
            if self.cadastral_number:
                result = ['cadastral_number']
            else:
                result = []
        else:
            result = self._is_triggers(
                ['cadastral_number', 'area_total']
            )
        return result


class ActorAreaEmbedded(EmbeddedDocument):
    """Embedded-поле для помещения в акторе."""

    id = ObjectIdField(db_field='_id')
    str_number = StringField()
