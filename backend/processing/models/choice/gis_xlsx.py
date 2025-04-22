
# TODO Вынести все CHOICE в processing/models/choices.py


class LivingAreaGisTypes:

    PRIVATE = 'private'
    HOSTEL = 'hostel'
    COMMUNAL = 'communal'


LIVING_AREA_GIS_TYPES_CHOICES = (
    (LivingAreaGisTypes.PRIVATE, 'Отдельная квартира'),
    (LivingAreaGisTypes.COMMUNAL, 'Квартира коммунального заселения'),
    (LivingAreaGisTypes.HOSTEL, 'Общежитие'),
)


class MeterGisTypes:

    INDIVIDUAL = 'individual'
    HOUSE_METER = 'house_meter'
    AREA_METER = 'area_meter'
    ROOM_METER = 'room_meter'


METER_GIS_TYPES_CHOICES = (
    (MeterGisTypes.INDIVIDUAL, 'Индивидуальный'),
    (MeterGisTypes.HOUSE_METER, 'Коллективный (общедомовой)'),
    (MeterGisTypes.AREA_METER, 'Общий (квартирный)'),
    (MeterGisTypes.ROOM_METER, 'Комнатный'),
)


class MeterRatioGisTypes:

    ONE = 'one'
    TWO = 'two'
    THREE = 'three'


METER_RATIO_GIS_TYPES_CHOICES = (
    (MeterRatioGisTypes.ONE, 'Однотарифный'),
    (MeterRatioGisTypes.TWO, 'Двухтарифный'),
    (MeterRatioGisTypes.THREE, 'Трехтарифный'),
)
