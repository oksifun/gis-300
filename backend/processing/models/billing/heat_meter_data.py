from mongoengine import Document, DictField, StringField, DateTimeField, \
    ReferenceField, ObjectIdField, BooleanField, ListField, \
    EmbeddedDocumentField, EmbeddedDocument, FloatField

from app.meters.models.meter import HouseMeter
from processing.models.billing.meter_handbook import METER_MODEL


class HeatMeterReportTypes(object):
    HOURLY = 'hourly'
    DAILY = 'daily'
    MONTHLY = 'monthly'
    TOTAL = 'total'
    CURRENT = 'current'
    STATISTICS = 'statistics'


HEAT_METER_REPORT_TYPES = (
    (HeatMeterReportTypes.HOURLY, 'Часовой'),
    (HeatMeterReportTypes.DAILY, 'Суточный'),
    (HeatMeterReportTypes.MONTHLY, 'Месячный'),
    (HeatMeterReportTypes.TOTAL, 'Тотальные данные'),
    (HeatMeterReportTypes.CURRENT, 'Текущие данные'),
    (HeatMeterReportTypes.STATISTICS, 'Статистические данные'),
)
HEAT_METER_REPORT_CORRECTION_TYPES = (
    ('arithmetic', 'по арифметике'),
    ('average', 'по среднему'),
    ('manual', 'вручную'),
    ('not_changed', 'не изменено'),
)


class HeatSystemData(EmbeddedDocument):
    time = FloatField(verbose_name='Tи')
    NS = FloatField(verbose_name='НС')
    M1 = FloatField(verbose_name='M1')
    M2 = FloatField(verbose_name='M2')
    dM_1 = FloatField(verbose_name='dM(M1-M2)')
    T1 = FloatField(verbose_name='T1')
    T2 = FloatField(verbose_name='T2')
    dT = FloatField(verbose_name='dT')
    P1 = FloatField(verbose_name='P1')
    P2 = FloatField(verbose_name='P2')
    Qo = FloatField(verbose_name='Qотопл')
    M3 = FloatField(verbose_name='M3')
    M4 = FloatField(verbose_name='M4')
    dM_2 = FloatField(verbose_name='dM(M3-M4)')
    V3 = FloatField(verbose_name='V3')
    V4 = FloatField(verbose_name='V4')
    dV = FloatField(verbose_name='dV(излив)')
    Vp = FloatField(verbose_name='Vподпит')
    T3 = FloatField(verbose_name='T3')
    T4 = FloatField(verbose_name='T4')
    Qg = FloatField(verbose_name='Qгвс.общ')
    Q_1 = FloatField(verbose_name='Qгвс.изл')
    Q_2 = FloatField(verbose_name='Qтех.гвс')
    Q = FloatField(verbose_name='Qобщ.от+гвс')


class HeatSystem(EmbeddedDocument):
    name = StringField()
    data = EmbeddedDocumentField(HeatSystemData)


class HeatHouseMeterData(Document):
    """
    Подробные данные жителя
    """
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'MeterData',
    }

    _type = ListField(StringField())
    raw = DictField(verbose_name='Сырые данные')
    report_type = StringField(
        choices=HEAT_METER_REPORT_TYPES,
        verbose_name='Тип архива'
    )
    datetime = DateTimeField(verbose_name='Дата')
    meter = ReferenceField(
        HouseMeter,
        verbose_name='Ссылка на тепловой счетчик'
    )
    task = ObjectIdField(verbose_name='Ссылка на задачу получения данных')

    meter_model = StringField(choises=METER_MODEL, verbose_name='Модель УУТЭ')
    parsed = ListField(
        EmbeddedDocumentField(HeatSystem),
        verbose_name='Разобранные данные'
    )
    lock = BooleanField(verbose_name='Блокировка отчёта на изменения')
    current = DictField()  # используется для ТСРВ-022/023/032, current_raw - previous_raw
    correction = StringField(
        choices=HEAT_METER_REPORT_CORRECTION_TYPES,
        default='not_changed',
        verbose_name='Перерасчет по среднему',
    )
    editable = BooleanField()

