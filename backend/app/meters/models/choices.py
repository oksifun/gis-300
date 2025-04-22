class MeterType:
    COLD_WATER_AREA_METER = 'ColdWaterAreaMeter'
    HOT_WATER_AREA_METER = 'HotWaterAreaMeter'
    ELECTRIC_ONE_RATE_AREA_METER = 'ElectricOneRateAreaMeter'
    ELECTRIC_TWO_RATE_AREA_METER = 'ElectricTwoRateAreaMeter'
    ELECTRIC_THREE_RATE_AREA_METER = 'ElectricThreeRateAreaMeter'
    HEAT_AREA_METER = 'HeatAreaMeter'
    HEAT_DISTRIBUTOR_AREA_METER = 'HeatDistributorAreaMeter'
    GAS_AREA_METER = 'GasAreaMeter'
    WASTE_WATER_AREA_METER = 'WasteWaterAreaMeter'
    COLD_WATER_HOUSE_METER = 'ColdWaterHouseMeter'
    HOT_WATER_HOUSE_METER = 'HotWaterHouseMeter'
    ELECTRIC_ONE_RATE_HOUSE_METER = 'ElectricOneRateHouseMeter'
    ELECTRIC_TWO_RATE_HOUSE_METER = 'ElectricTwoRateHouseMeter'
    ELECTRIC_THREE_RATE_HOUSE_METER = 'ElectricThreeRateHouseMeter'
    HEAT_HOUSE_METER = 'HeatHouseMeter'
    GAS_HOUSE_METER = 'GasHouseMeter'
    WASTE_WATER_HOUSE_METER = 'WasteWaterHouseMeter'


class MeterResourceType:
    class Area:
        class Water:
            COLD = MeterType.COLD_WATER_AREA_METER
            HOT = MeterType.HOT_WATER_AREA_METER

            WASTE = MeterType.WASTE_WATER_AREA_METER

            ALL: set = {COLD, HOT, WASTE}

        class Electric:
            ONE_RATE = MeterType.ELECTRIC_ONE_RATE_AREA_METER
            TWO_RATE = MeterType.ELECTRIC_TWO_RATE_AREA_METER
            THREE_RATE = MeterType.ELECTRIC_THREE_RATE_AREA_METER

            ALL: set = {ONE_RATE, TWO_RATE, THREE_RATE}

        HEAT = MeterType.HEAT_AREA_METER
        GAS = MeterType.GAS_AREA_METER

        ALL: set = Water.ALL | Electric.ALL | {HEAT, GAS}

    class House:
        class Water:
            COLD = MeterType.COLD_WATER_HOUSE_METER
            HOT = MeterType.HOT_WATER_HOUSE_METER

            WASTE = MeterType.WASTE_WATER_HOUSE_METER

            ALL: set = {COLD, HOT, WASTE}

        class Electric:
            ONE_RATE = MeterType.ELECTRIC_ONE_RATE_HOUSE_METER
            TWO_RATE = MeterType.ELECTRIC_TWO_RATE_HOUSE_METER
            THREE_RATE = MeterType.ELECTRIC_THREE_RATE_HOUSE_METER

            ALL: set = {ONE_RATE, TWO_RATE, THREE_RATE}

        HEAT = MeterType.HEAT_HOUSE_METER
        GAS = MeterType.GAS_HOUSE_METER

        ALL: set = Water.ALL | Electric.ALL | {HEAT, GAS}

    ALL: set = Area.ALL | House.ALL

    ONE_RATE: set = {Area.Electric.ONE_RATE, House.Electric.ONE_RATE} | \
                    {Area.HEAT, House.HEAT} | {Area.GAS, House.GAS} | \
                    Area.Water.ALL | House.Water.ALL
    TWO_RATE: set = {Area.Electric.TWO_RATE, House.Electric.TWO_RATE}
    THREE_RATE: set = {Area.Electric.THREE_RATE, House.Electric.THREE_RATE}


class MeterTypeNamesShort(MeterType):
    pass


class MeterTypeUnitNames(MeterType):
    pass


class MeterTypeNames(MeterType):
    pass


class ImportReadingsTaskStatus(object):
    NEW = 'new'
    PARSING = 'parsing'
    PARSED = 'parsed'
    SAVING = 'saving'
    FINISHED = 'finished'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


IMPORT_READINGS_TASK_STATUSES_CHOICES = (
    (ImportReadingsTaskStatus.NEW, 'Задача создана'),
    (ImportReadingsTaskStatus.PARSING, "Идет парсинг"),
    (ImportReadingsTaskStatus.PARSED, "Парсинг заверешен"),
    (ImportReadingsTaskStatus.SAVING, "Сохранение результатов"),
    (ImportReadingsTaskStatus.FINISHED, "Выполнено"),
    (ImportReadingsTaskStatus.FAILED, "Ошибка"),
    (ImportReadingsTaskStatus.CANCELLED, "Отменено"),
)


class MeterMeasurementUnits:
    CUBIC_METER = '113'
    KILOWATT_PER_HOUR = '245'
    THOUSAND_CUBIC_METERS = '114'
    GIGACALORIE = '233'
    KILOWATT = '214'
    MEGAWATT = '215'
    MEGAWATT_HOURS = '246'
    GIGAJOULE = 'A056'


METER_MEASUREMENT_UNITS_CHOICES = (
    (MeterMeasurementUnits.CUBIC_METER, 'м3'),
    (MeterMeasurementUnits.KILOWATT_PER_HOUR, 'кВт/ч'),
    (MeterMeasurementUnits.THOUSAND_CUBIC_METERS, 'Тыс м3'),
    (MeterMeasurementUnits.GIGACALORIE, 'Гкал'),
    (MeterMeasurementUnits.KILOWATT, 'кВт'),
    (MeterMeasurementUnits.MEGAWATT, 'МВт'),
    (MeterMeasurementUnits.MEGAWATT_HOURS, 'МВт.ч'),
    (MeterMeasurementUnits.GIGAJOULE, 'ГДж'),
)
METER_MEASUREMENT_UNITS_CHOICES_AS_DICT = {
    v[0]: v[1] for v in METER_MEASUREMENT_UNITS_CHOICES
}
METER_MEASUREMENT_UNITS_CHOICES_DICT = {
    MeterType.COLD_WATER_AREA_METER: (
        (
            MeterMeasurementUnits.CUBIC_METER,
            METER_MEASUREMENT_UNITS_CHOICES_AS_DICT[
                MeterMeasurementUnits.CUBIC_METER
            ],
        ),
    ),
    MeterType.COLD_WATER_HOUSE_METER: (
        (
            MeterMeasurementUnits.CUBIC_METER,
            METER_MEASUREMENT_UNITS_CHOICES_AS_DICT[
                MeterMeasurementUnits.CUBIC_METER
            ],
        ),
    ),
    MeterType.HOT_WATER_AREA_METER: (
        (
            MeterMeasurementUnits.CUBIC_METER,
            METER_MEASUREMENT_UNITS_CHOICES_AS_DICT[
                MeterMeasurementUnits.CUBIC_METER
            ],
        ),
    ),
    MeterType.HOT_WATER_HOUSE_METER: (
        (
            MeterMeasurementUnits.CUBIC_METER,
            METER_MEASUREMENT_UNITS_CHOICES_AS_DICT[
                MeterMeasurementUnits.CUBIC_METER
            ],
        ),
    ),
    MeterType.ELECTRIC_ONE_RATE_AREA_METER: (
        (
            MeterMeasurementUnits.KILOWATT_PER_HOUR,
            METER_MEASUREMENT_UNITS_CHOICES_AS_DICT[
                MeterMeasurementUnits.KILOWATT_PER_HOUR
            ],
        ),
    ),
    MeterType.ELECTRIC_ONE_RATE_HOUSE_METER: (
        (
            MeterMeasurementUnits.KILOWATT_PER_HOUR,
            METER_MEASUREMENT_UNITS_CHOICES_AS_DICT[
                MeterMeasurementUnits.KILOWATT_PER_HOUR
            ],
        ),
    ),
    MeterType.ELECTRIC_TWO_RATE_AREA_METER: (
        (
            MeterMeasurementUnits.KILOWATT_PER_HOUR,
            METER_MEASUREMENT_UNITS_CHOICES_AS_DICT[
                MeterMeasurementUnits.KILOWATT_PER_HOUR
            ],
        ),
    ),
    MeterType.ELECTRIC_TWO_RATE_HOUSE_METER: (
        (
            MeterMeasurementUnits.KILOWATT_PER_HOUR,
            METER_MEASUREMENT_UNITS_CHOICES_AS_DICT[
                MeterMeasurementUnits.KILOWATT_PER_HOUR
            ],
        ),
    ),
    MeterType.ELECTRIC_THREE_RATE_AREA_METER: (
        (
            MeterMeasurementUnits.KILOWATT_PER_HOUR,
            METER_MEASUREMENT_UNITS_CHOICES_AS_DICT[
                MeterMeasurementUnits.KILOWATT_PER_HOUR
            ],
        ),
    ),
    MeterType.ELECTRIC_THREE_RATE_HOUSE_METER: (
        (
            MeterMeasurementUnits.KILOWATT_PER_HOUR,
            METER_MEASUREMENT_UNITS_CHOICES_AS_DICT[
                MeterMeasurementUnits.KILOWATT_PER_HOUR
            ],
        ),
    ),
    MeterType.GAS_AREA_METER: (
        (
            MeterMeasurementUnits.CUBIC_METER,
            METER_MEASUREMENT_UNITS_CHOICES_AS_DICT[
                MeterMeasurementUnits.CUBIC_METER
            ],
        ),
        (
            MeterMeasurementUnits.THOUSAND_CUBIC_METERS,
            METER_MEASUREMENT_UNITS_CHOICES_AS_DICT[
                MeterMeasurementUnits.THOUSAND_CUBIC_METERS
            ],
        ),
    ),
    MeterType.GAS_HOUSE_METER: (
        (
            MeterMeasurementUnits.THOUSAND_CUBIC_METERS,
            METER_MEASUREMENT_UNITS_CHOICES_AS_DICT[
                MeterMeasurementUnits.THOUSAND_CUBIC_METERS
            ],
        ),
        (
            MeterMeasurementUnits.CUBIC_METER,
            METER_MEASUREMENT_UNITS_CHOICES_AS_DICT[
                MeterMeasurementUnits.CUBIC_METER
            ],
        ),
    ),
    MeterType.HEAT_AREA_METER: (
        (
            MeterMeasurementUnits.GIGACALORIE,
            METER_MEASUREMENT_UNITS_CHOICES_AS_DICT[
                MeterMeasurementUnits.GIGACALORIE
            ],
        ),
        (
            MeterMeasurementUnits.KILOWATT,
            METER_MEASUREMENT_UNITS_CHOICES_AS_DICT[
                MeterMeasurementUnits.KILOWATT
            ],
        ),
        (
            MeterMeasurementUnits.MEGAWATT,
            METER_MEASUREMENT_UNITS_CHOICES_AS_DICT[
                MeterMeasurementUnits.MEGAWATT
            ],
        ),
        (
            MeterMeasurementUnits.GIGAJOULE,
            METER_MEASUREMENT_UNITS_CHOICES_AS_DICT[
                MeterMeasurementUnits.GIGAJOULE
            ],
        ),
    ),
    MeterType.HEAT_HOUSE_METER: (
        (
            MeterMeasurementUnits.GIGACALORIE,
            METER_MEASUREMENT_UNITS_CHOICES_AS_DICT[
                MeterMeasurementUnits.GIGACALORIE
            ],
        ),
        (
            MeterMeasurementUnits.MEGAWATT_HOURS,
            METER_MEASUREMENT_UNITS_CHOICES_AS_DICT[
                MeterMeasurementUnits.MEGAWATT_HOURS
            ],
        ),
        (
            MeterMeasurementUnits.GIGAJOULE,
            METER_MEASUREMENT_UNITS_CHOICES_AS_DICT[
                MeterMeasurementUnits.GIGAJOULE
            ],
        ),
    ),
}


METER_TYPE_NAMES_SHORT = (
    (MeterType.COLD_WATER_AREA_METER, 'ХВС'),
    (MeterType.HOT_WATER_AREA_METER, 'ГВС'),
    (MeterType.ELECTRIC_ONE_RATE_AREA_METER, 'ЭЛ'),
    (MeterType.ELECTRIC_TWO_RATE_AREA_METER, 'ЭЛДТ'),
    (MeterType.ELECTRIC_THREE_RATE_AREA_METER, 'ЭЛТТ'),
    (MeterType.HEAT_AREA_METER, 'ТПЛ'),
    (MeterType.GAS_AREA_METER, 'ГАЗ'),
    (MeterType.COLD_WATER_HOUSE_METER, 'ХВС'),
    (MeterType.HOT_WATER_HOUSE_METER, 'ГВС'),
    (MeterType.ELECTRIC_ONE_RATE_HOUSE_METER, 'ЭЛ'),
    (MeterType.ELECTRIC_TWO_RATE_HOUSE_METER, 'ЭЛДТ'),
    (MeterType.ELECTRIC_THREE_RATE_HOUSE_METER, 'ЭЛТТ'),
    (MeterType.HEAT_HOUSE_METER, 'ТПЛ'),
    (MeterType.GAS_HOUSE_METER, 'ГАЗ'),
)
METER_TYPE_UNIT_NAMES = (
    (MeterType.COLD_WATER_AREA_METER, 'м3'),
    (MeterType.HOT_WATER_AREA_METER, 'м3'),
    (MeterType.ELECTRIC_ONE_RATE_AREA_METER, 'КВт/ч'),
    (MeterType.ELECTRIC_TWO_RATE_AREA_METER, 'КВт/ч'),
    (MeterType.ELECTRIC_THREE_RATE_AREA_METER, 'КВт/ч'),
    (MeterType.HEAT_AREA_METER, 'ГКкал'),
    (MeterType.GAS_AREA_METER, 'м3'),
    (MeterType.COLD_WATER_HOUSE_METER, 'м3'),
    (MeterType.HOT_WATER_HOUSE_METER, 'м3'),
    (MeterType.ELECTRIC_ONE_RATE_HOUSE_METER, 'КВт/ч'),
    (MeterType.ELECTRIC_TWO_RATE_HOUSE_METER, 'КВт/ч'),
    (MeterType.ELECTRIC_THREE_RATE_HOUSE_METER, 'КВт/ч'),
    (MeterType.HEAT_HOUSE_METER, 'ГКкал'),
    (MeterType.GAS_HOUSE_METER, 'м3'),
)
METER_TYPE_NAMES = (
    (MeterType.COLD_WATER_AREA_METER, 'Холодной воды'),
    (MeterType.HOT_WATER_AREA_METER, 'Горячей воды'),
    (MeterType.ELECTRIC_ONE_RATE_AREA_METER, 'Электрический однотарифный'),
    (MeterType.ELECTRIC_TWO_RATE_AREA_METER, 'Электрический двухтарифный'),
    (MeterType.ELECTRIC_THREE_RATE_AREA_METER, 'Электрический трёхтарифный'),
    (MeterType.HEAT_AREA_METER, 'Тепла'),
    (MeterType.GAS_AREA_METER, 'Газа'),
    (MeterType.COLD_WATER_HOUSE_METER, 'Холодной воды'),
    (MeterType.HOT_WATER_HOUSE_METER, 'Горячей воды'),
    (MeterType.ELECTRIC_ONE_RATE_HOUSE_METER, 'Электрический однотарифный'),
    (MeterType.ELECTRIC_TWO_RATE_HOUSE_METER, 'Электрический двухтарифный'),
    (MeterType.ELECTRIC_THREE_RATE_HOUSE_METER, 'Электрический трёхтарифный'),
    (MeterType.HEAT_HOUSE_METER, 'Тепла'),
    (MeterType.GAS_HOUSE_METER, 'Газа'),
)


class MeterCloserType:
    SYSTEM = 'system'
    WORKER = 'worker'


METER_CLOSER_TYPES_CHOICES = (
    (MeterCloserType.SYSTEM, 'автоматически'),
    (MeterCloserType.WORKER, 'сотрудником')
)


class MeterExpirationDates:
    YEARS2 = 2
    YEARS3 = 3
    YEARS4 = 4
    YEARS5 = 5
    YEARS6 = 6
    YEARS7 = 7
    YEARS8 = 8
    YEARS9 = 9
    YEARS10 = 10
    YEARS11 = 11
    YEARS12 = 12
    YEARS13 = 13
    YEARS14 = 14
    YEARS15 = 15
    YEARS16 = 16
    YEARS17 = 17
    YEARS18 = 18
    YEARS19 = 19
    YEARS20 = 20
    YEARS21 = 21
    YEARS22 = 22
    YEARS23 = 23
    YEARS24 = 24


WATER_METER_EXPIRATIONS_DATE_CHOISES = (
     (MeterExpirationDates.YEARS2, '2 года'),
     (MeterExpirationDates.YEARS3, '3 года'),
     (MeterExpirationDates.YEARS4, '4 года'),
     (MeterExpirationDates.YEARS5, '5 лет'),
     (MeterExpirationDates.YEARS6, '6 лет'),
     (MeterExpirationDates.YEARS7, '7 лет'),
     (MeterExpirationDates.YEARS8, '8 лет'),
     (MeterExpirationDates.YEARS9, '9 лет'),
     (MeterExpirationDates.YEARS10, '10 лет'),
     (MeterExpirationDates.YEARS11, '11 лет'),
     (MeterExpirationDates.YEARS12, '12 лет'),
     (MeterExpirationDates.YEARS13, '13 лет'),
     (MeterExpirationDates.YEARS14, '14 лет'),
     (MeterExpirationDates.YEARS15, '15 лет'),
     (MeterExpirationDates.YEARS16, '16 лет'),
     (MeterExpirationDates.YEARS17, '17 лет'),
     (MeterExpirationDates.YEARS18, '18 лет'),
     (MeterExpirationDates.YEARS19, '19 лет'),
     (MeterExpirationDates.YEARS20, '20 лет'),
     (MeterExpirationDates.YEARS21, '21 год'),
     (MeterExpirationDates.YEARS22, '22 года'),
     (MeterExpirationDates.YEARS23, '23 года'),
     (MeterExpirationDates.YEARS24, '24 года'),
)

GAS_METER_EXPIRATIONS_DATE_CHOISES = (
     (MeterExpirationDates.YEARS2, '2 года'),
     (MeterExpirationDates.YEARS3, '3 года'),
     (MeterExpirationDates.YEARS4, '4 года'),
     (MeterExpirationDates.YEARS5, '5 лет'),
     (MeterExpirationDates.YEARS6, '6 лет'),
     (MeterExpirationDates.YEARS7, '7 лет'),
     (MeterExpirationDates.YEARS8, '8 лет'),
     (MeterExpirationDates.YEARS9, '9 лет'),
     (MeterExpirationDates.YEARS10, '10 лет'),
     (MeterExpirationDates.YEARS11, '11 лет'),
     (MeterExpirationDates.YEARS12, '12 лет'),
     (MeterExpirationDates.YEARS13, '13 лет'),
     (MeterExpirationDates.YEARS14, '14 лет'),
     (MeterExpirationDates.YEARS15, '15 лет'),
     (MeterExpirationDates.YEARS16, '16 лет'),
)

ELECTRICITY_METER_EXPIRATIONS_DATE_CHOISES = (
     (MeterExpirationDates.YEARS4, '4 года'),
     (MeterExpirationDates.YEARS8, '8 лет'),
     (MeterExpirationDates.YEARS9, '9 лет'),
     (MeterExpirationDates.YEARS10, '10 лет'),
     (MeterExpirationDates.YEARS11, '11 лет'),
     (MeterExpirationDates.YEARS12, '12 лет'),
     (MeterExpirationDates.YEARS13, '13 лет'),
     (MeterExpirationDates.YEARS14, '14 лет'),
     (MeterExpirationDates.YEARS15, '15 лет'),
     (MeterExpirationDates.YEARS16, '16 лет'),
     (MeterExpirationDates.YEARS17, '17 лет'),
     (MeterExpirationDates.YEARS18, '18 лет'),
)


METER_EXPIRATIONS_DATE_CHOISES_DICT = {
    MeterType.COLD_WATER_AREA_METER:
        WATER_METER_EXPIRATIONS_DATE_CHOISES,
    MeterType.HOT_WATER_AREA_METER:
        WATER_METER_EXPIRATIONS_DATE_CHOISES,
    MeterType.GAS_AREA_METER:
        GAS_METER_EXPIRATIONS_DATE_CHOISES,
    MeterType.ELECTRIC_ONE_RATE_AREA_METER:
        ELECTRICITY_METER_EXPIRATIONS_DATE_CHOISES,
    MeterType.ELECTRIC_TWO_RATE_AREA_METER:
        ELECTRICITY_METER_EXPIRATIONS_DATE_CHOISES,
    MeterType.ELECTRIC_THREE_RATE_AREA_METER:
        ELECTRICITY_METER_EXPIRATIONS_DATE_CHOISES
}
