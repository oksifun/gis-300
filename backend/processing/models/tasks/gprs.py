import datetime

from dateutil.relativedelta import relativedelta
from mongoengine import Document, ObjectIdField, StringField, DateTimeField, \
    EmbeddedDocumentField, EmbeddedDocument, ListField, DictField, BooleanField, \
    IntField

# Ассортимент счетчиков
from app.meters.models.meter import HouseMeter

METERS_RANGE = (
    'vkt7',
    'spt943',
    'tsrv032',
    'tsrv030',
    'tsrv026',
    'tsrv024',
    'tsrv023',
    'spt941',
    'spt961',
    "vkt5",
)
HEAT_REPORT_TYPES = ('daily', 'monthly', 'hourly', 'tuning')


class GprsTaskStatusType:
    NEW = 'new'  # новая задача
    WIP = 'wip'  # начат обмен с тепловычислителем
    FALSE = 'false'  # обмен с тепловычислителем неудачен
    READY = 'ready'  # данные с тепловычислителя успешно получены
    FINISHED = 'finished'  # данные обработаны
    CANCEL = 'cancel'  # отменена
    RETRY = 'retry'  # опрос провалился, но будет взят еще
    CALL = 'call'  # звонок выполнен


GRPS_TASK_STATUS_CHOICES = (
    (GprsTaskStatusType.NEW, 'new'),
    (GprsTaskStatusType.WIP, 'wip'),
    (GprsTaskStatusType.FALSE, 'false'),
    (GprsTaskStatusType.READY, 'ready'),
    (GprsTaskStatusType.FINISHED, 'finished'),
    (GprsTaskStatusType.CANCEL, 'cancel'),
    (GprsTaskStatusType.RETRY, 'retry'),
    (GprsTaskStatusType.CALL, 'call'),
)


class GprsTaskError(Exception):
    pass


def raise_not_tuned_error():
    raise GprsTaskError("Прибор еще не настроен!")


class AdapterEmbedded(EmbeddedDocument):
    imei = StringField(verbose_name="IMEI модема")
    phone = StringField(verbose_name="Тел. номер сим-карты")
    operator = StringField(verbose_name="Оператор сим-карты")


class GprsTask(Document):
    """
    Модель задачи на на опрос тепловычислителей по GPRS
    """
    meta = {
        "db_alias": "queue-db",
        'collection': 'gprs',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'meter',
            'adapter.imei'
        ]
    }
    meter = ObjectIdField(verbose_name="ID счетчика")
    house = ObjectIdField(verbose_name="ID дома")
    provider = ObjectIdField(verbose_name="ID организации")
    date_from = DateTimeField(
        verbose_name="Начало периода показаний"
    )
    date_till = DateTimeField(
        verbose_name="Конец периода показаний"
    )
    adapter = EmbeddedDocumentField(
        AdapterEmbedded, verbose_name="Инофрмация об адаптере"
    )
    meter_model = StringField(
        required=True,
        verbose_name="Модель тепловычислителя",
        choices=METERS_RANGE
    )
    status = StringField(
        verbose_name="Статус задачи",
        choices=GRPS_TASK_STATUS_CHOICES,
        default='new'
    )
    report_type = StringField(
        verbose_name="Статус задачи",
        choices=HEAT_REPORT_TYPES,
        default='daily')
    logs = ListField(
        ObjectIdField(),
        verbose_name="ID логов в gprs_task_log")

    result = DictField(verbose_name="Результат")
    statistics = DictField(verbose_name="Статистика прибора")
    warnings = ListField(StringField(), verbose_name='Сообщения-предупреждения')
    is_manual = BooleanField()
    tries = IntField(verbose_name='Количество попыток', default=0)

    created = DateTimeField(default=datetime.datetime.now)
    updated = DateTimeField()
    not_validation = BooleanField(
        verbose_name="Валидация не требуется",
        default=False
    )

    def save(self, *arg, **kwargs):
        if not all([self.date_from, self.date_till]):
            self.date_till = datetime.datetime.now()
            self.date_from = self.date_till - relativedelta(days=1)
        self.set_auto_fields()
        self.updated = datetime.datetime.now()
        self.validation()
        super().save(*arg, **kwargs)

    def set_auto_fields(self):
        if self._created:
            self.set_auto_fields_from_meter()

    def set_auto_fields_from_meter(self):
        meter = HouseMeter.objects(
            id=self.meter,
            _type='HouseMeter',
        ).only(
            'id',
            'house.id',
        ).as_pymongo().get()
        self.house = meter['house']['_id']

    def validation(self):
        if not self.not_validation:
            period_limit = 5 if self.report_type == 'hourly' else 10
            if (self.date_till - self.date_from).days > period_limit:
                raise GprsTaskError("Такой большой диапазон опроса запрещен!")
