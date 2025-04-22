import datetime
from mongoengine import Document, DateTimeField, ObjectIdField, ListField, \
    StringField, EmbeddedDocument, IntField, EmbeddedDocumentListField


class CalculatingLogType:
    LOG = 'PipcaLog'
    WARNING = 'PipcaWarningLogAccrual'
    STATISTICS = 'PipcaLogStatistics'
    ACTION = 'PipcaActionLog'
    ERROR = 'PipcaErrorLogAccrual'


class CalculatingWarningType:
    ZERO_HOUSE_CONSUMPTION = 'PipcaLogZeroHouseConsumption'
    BIG_CONSUMPTION = 'PipcaLogBigConsumption'
    BIG_ACCRUAL = 'PipcaLogBigAccrual'
    BIG_RECALCULATION = 'PipcaLogBigRecalculation'
    NEGATIVE_ACCRUAL = 'PipcaLogNegativeAccrual'


class CalculatingErrorType:
    UNKNOWN_FORMULA = 'PipcaLogUnknownFormula'
    INVALID_ARGUMENT = 'PipcaLogInvalidArgument'
    LOOPING = 'PipcaLogLooping'
    FORCED_SAVE = 'PipcaLogForcedSave'
    OFFSETS_FAIL = 'PipcaLogOffsetsFail'


CALCULATING_TYPES_CHOICES = (
    (CalculatingLogType.LOG, 'Лог расчета'),
    (CalculatingLogType.WARNING, 'Предупреждение'),
    (
        CalculatingWarningType.ZERO_HOUSE_CONSUMPTION,
        'Нет показаний домового прибора',
    ),
    (CalculatingLogType.STATISTICS, 'Статистика расчета'),
    (CalculatingLogType.ACTION, 'Действие пользователя'),
    (CalculatingLogType.ERROR, 'Ошибка расчета'),
    (CalculatingWarningType.BIG_CONSUMPTION, 'Расход сильно превышает среднее'),
    (CalculatingWarningType.BIG_ACCRUAL, 'Большая сумма начисления'),
    (CalculatingWarningType.BIG_RECALCULATION, 'Большая сумма перерасчёта'),
    (CalculatingWarningType.NEGATIVE_ACCRUAL, 'Отрицательное начисление'),
    (CalculatingErrorType.UNKNOWN_FORMULA, 'Ошибка в формуле'),
    (CalculatingErrorType.INVALID_ARGUMENT, 'Неправильный параметр'),
    (CalculatingErrorType.LOOPING, 'Зацикливание формулы'),
    (CalculatingErrorType.FORCED_SAVE, 'Принудительное сохранение'),
    (CalculatingErrorType.OFFSETS_FAIL, 'Пени посчитать не удалось'),
)
WARNING_MAX_RATIO = 5
WARNING_MAX_ACCRUAL = 300000
WARNING_MAX_RECALCULATION = 300000


class CalculatingLogMixin:
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'PipcaLog',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'doc',
            'datetime',
        ],
    }

    _type = ListField(StringField())
    author = ObjectIdField()
    datetime = DateTimeField(
        required=True,
        default=datetime.datetime.now,
        verbose_name='Дата создания записи',
    )
    doc = ObjectIdField()

    def log_type_is(self, type_name):
        return type_name in self._type


class CalculatingWarning(CalculatingLogMixin, Document):
    """
    Предупреждения о расчёте
    """
    tenants = ListField(ObjectIdField())
    descriptions = ListField(StringField())

    def save(self, *args, **kwargs):
        if CalculatingLogType.WARNING not in self._type:
            self._type.append(CalculatingLogType.WARNING)
        return super().save(*args, **kwargs)


class MeasuredStatistics(EmbeddedDocument):
    service_code = StringField()
    total = IntField()
    meter = IntField()
    given = IntField()


class CalculatingStatistics(CalculatingLogMixin, Document):
    """
    Статистика расчёта
    """
    measured_data = EmbeddedDocumentListField(MeasuredStatistics)

    def save(self, *args, **kwargs):
        self._type = [CalculatingLogType.STATISTICS]
        return super().save(*args, **kwargs)


class CalculatingAction(CalculatingLogMixin, Document):
    """
    Действия пользователя
    """
    action = StringField(required=True)
    service_type = ObjectIdField()
    seconds = IntField()
    tenants = ListField(ObjectIdField())
    created = DateTimeField(default=datetime.datetime.now)

    def save(self, *args, **kwargs):
        self._type = [CalculatingLogType.ACTION]
        return super().save(*args, **kwargs)


class CalculatingError(CalculatingLogMixin, Document):
    """
    Ошибки
    """
    service_name = StringField()
    formula = StringField()

    def save(self, *args, **kwargs):
        if CalculatingLogType.ERROR not in self._type:
            self._type.append(CalculatingLogType.ERROR)
        return super().save(*args, **kwargs)
