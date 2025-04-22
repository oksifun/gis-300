
class TariffFormulaArgumentType:
    HOUSE = 'house'
    FEATURE = 'feature'
    COEFFICIENT = 'coefficient'
    FORMULA = 'formula'
    VALUE = 'value'
    TERRITORY = 'territory'
    COMMUNAL_RESOURCE = 'communal_resource'
    CONSUMPTION_TYPE = 'consumption_type'
    SUM_CODE = 'sum_code'
    LAST_MONTH = 'last_month'
    SUM_HOUSE_GROUP = 'sum_house_group'
    SUM_CODE_SINGLE = 'sum_code_single'
    CONDITION_TEXT = 'condition_text'
    METER_SERIAL_NUMBER = 'meter_serial_number'
    METER_DESCRIPTION = 'meter_description'
    BUFFER_NAME = 'buffer_name'
    BUFFER_OWN = 'buffer_own'
    HOUSE_GROUP = 'house_group'


TARIFF_FORMULA_ARGUMENT_TYPES_CHOICES = (
    (TariffFormulaArgumentType.HOUSE, 'Адрес'),
    (TariffFormulaArgumentType.FEATURE, 'Кв.признак'),
    (TariffFormulaArgumentType.COEFFICIENT, 'Кв.коэффициент'),
    (TariffFormulaArgumentType.FORMULA, 'Формула'),
    (TariffFormulaArgumentType.VALUE, 'Значение'),
    (TariffFormulaArgumentType.TERRITORY, 'Территория'),
    (TariffFormulaArgumentType.COMMUNAL_RESOURCE, 'Комм.ресурс'),
    (TariffFormulaArgumentType.CONSUMPTION_TYPE, 'Тип расчёта расхода'),
    (TariffFormulaArgumentType.SUM_CODE, 'Объект суммирования'),
    (TariffFormulaArgumentType.LAST_MONTH, 'Предыдущий месяц'),
    (
        TariffFormulaArgumentType.SUM_HOUSE_GROUP,
        'Суммировать результат по группе домов',
    ),
    (TariffFormulaArgumentType.SUM_CODE_SINGLE, 'Объект суммирования упрощ.'),
    (TariffFormulaArgumentType.CONDITION_TEXT, 'Условие'),
    (TariffFormulaArgumentType.METER_SERIAL_NUMBER, 'Серийный номер'),
    (TariffFormulaArgumentType.METER_DESCRIPTION, 'Описание содержит'),
    (TariffFormulaArgumentType.BUFFER_NAME, 'Наименование буфера'),
    (TariffFormulaArgumentType.BUFFER_OWN, 'Внутренний буфер'),
    (TariffFormulaArgumentType.HOUSE_GROUP, 'Группа домов'),
)
TARIFF_FORMULA_ARGUMENT_TYPES_CHOICES_AS_DICT = {
    v[0]: v[1]
    for v in TARIFF_FORMULA_ARGUMENT_TYPES_CHOICES
}


class TariffFunction:
    HOUSE_METER_CONSUMPTION_TOTAL = 'ДСЧО'
    HOUSE_METER_CONSUMPTION = 'ДСЧ'
    SUM_CONDITIONAL = 'ОСУМУ'
    SUM = 'ОСУМ'
    COEFFICIENT_AREA = 'ККВ'
    COEFFICIENT = 'К'
    BUFFER = 'БУФЕР'
    FUNCTIONS = 'Ф'
    VALUES = 'Т'
    HAS_FEATURE = 'П'
    HOUSE_IS = 'ДОМ'
    HOUSE_IS_IN_GROUP = 'ДОМВГРУППЕ'
    ADDRESS_CONTAINS_TERRITORY = 'ТЕР'
    CONSUMPTION_TYPE_IS = 'ТИПРАСХОДА'
    CONSUMPTION_TYPE_CALCULATED_IS = 'РАСЧТИПРАСХОДА'
    HAS_NOT_FEATURE = '!П'
    HOUSE_IS_NOT = '!ДОМ'
    HOUSE_IS_NOT_IN_GROUP = '!ДОМВГРУППЕ'
    ADDRESS_DO_NOT_CONTAIN_TERRITORY = '!ТЕР'
    CONSUMPTION_TYPE_IS_NOT = '!ТИПРАСХОДА'
    CONSUMPTION_TYPE_CALCULATED_IS_NOT = '!РАСЧТИПРАСХОДА'


class CommunalResource:
    COLD_WATER = 'cold_water'
    HOT_WATER = 'hot_water'
    ELECTRICITY_REGULAR = 'electricity_regular'
    ELECTRICITY_DAY = 'electricity_day'
    ELECTRICITY_NIGHT = 'electricity_night'
    ELECTRICITY_PEAK = 'electricity_peak'
    ELECTRICITY_SEMI_PEAK = 'electricity_semi_peak'
    HEAT = 'heat'
    GAS = 'gas'


COMMUNAL_RESOURCES_CHOICES = (
    (CommunalResource.COLD_WATER, 'Холодная вода'),
    (CommunalResource.HOT_WATER, 'Горячая вода'),
    (CommunalResource.ELECTRICITY_REGULAR, 'Электроэнергия однотар.'),
    (CommunalResource.ELECTRICITY_DAY, 'Электроэнергия день'),
    (CommunalResource.ELECTRICITY_NIGHT, 'Электроэнергия ночь'),
    (CommunalResource.ELECTRICITY_PEAK, 'Электроэнергия пик.'),
    (CommunalResource.ELECTRICITY_SEMI_PEAK, 'Электроэнергия полупик.'),
    (CommunalResource.HEAT, 'Тепловая энергия'),
    (CommunalResource.GAS, 'Газ'),
)
RESOURCE_CODES_CHOICES = (
    (CommunalResource.COLD_WATER, 'ХВС'),
    (CommunalResource.HOT_WATER, 'ГВС'),
    (CommunalResource.ELECTRICITY_REGULAR, 'ЭЛ'),
    (CommunalResource.ELECTRICITY_DAY, 'ЭЛД'),
    (CommunalResource.ELECTRICITY_PEAK, 'ЭЛП'),
    (CommunalResource.ELECTRICITY_SEMI_PEAK, 'ЭПП'),
    (CommunalResource.ELECTRICITY_NIGHT, 'ЭЛН'),
    (CommunalResource.HEAT, 'ТПЛ'),
    (CommunalResource.GAS, 'ГАЗ'),
)
TARIFF_FUNCTIONS_ARG_TYPES = {
    TariffFunction.HOUSE_METER_CONSUMPTION_TOTAL: (
        TariffFormulaArgumentType.HOUSE,
        TariffFormulaArgumentType.METER_SERIAL_NUMBER,
        TariffFormulaArgumentType.METER_DESCRIPTION,
        TariffFormulaArgumentType.COMMUNAL_RESOURCE,
    ),
    TariffFunction.HOUSE_METER_CONSUMPTION: (
        TariffFormulaArgumentType.METER_SERIAL_NUMBER,
        TariffFormulaArgumentType.METER_DESCRIPTION,
        TariffFormulaArgumentType.COMMUNAL_RESOURCE,
    ),
    TariffFunction.SUM_CONDITIONAL: (
        TariffFormulaArgumentType.SUM_CODE_SINGLE,
        TariffFormulaArgumentType.CONDITION_TEXT,
    ),
    TariffFunction.SUM: (
        TariffFormulaArgumentType.SUM_CODE,
        TariffFormulaArgumentType.LAST_MONTH,
        TariffFormulaArgumentType.SUM_HOUSE_GROUP,
    ),
    TariffFunction.COEFFICIENT_AREA: (
        TariffFormulaArgumentType.COEFFICIENT,
    ),
    TariffFunction.COEFFICIENT: (
        TariffFormulaArgumentType.COEFFICIENT,
    ),
    TariffFunction.BUFFER: (
        TariffFormulaArgumentType.BUFFER_NAME,
        TariffFormulaArgumentType.BUFFER_OWN,
    ),
    TariffFunction.FUNCTIONS: (
        TariffFormulaArgumentType.FORMULA,
    ),
    TariffFunction.VALUES: (
        TariffFormulaArgumentType.VALUE,
    ),
    TariffFunction.HAS_FEATURE: (
        TariffFormulaArgumentType.FEATURE,
    ),
    TariffFunction.HOUSE_IS: (
        TariffFormulaArgumentType.HOUSE,
    ),
    TariffFunction.HOUSE_IS_IN_GROUP: (
        TariffFormulaArgumentType.HOUSE_GROUP,
    ),
    TariffFunction.ADDRESS_CONTAINS_TERRITORY: (
        TariffFormulaArgumentType.TERRITORY,
    ),
    TariffFunction.CONSUMPTION_TYPE_IS: (
        TariffFormulaArgumentType.COMMUNAL_RESOURCE,
        TariffFormulaArgumentType.CONSUMPTION_TYPE,
    ),
    TariffFunction.CONSUMPTION_TYPE_CALCULATED_IS: (
        TariffFormulaArgumentType.COMMUNAL_RESOURCE,
        TariffFormulaArgumentType.CONSUMPTION_TYPE,
    ),
    TariffFunction.HAS_NOT_FEATURE: (
        TariffFormulaArgumentType.FEATURE,
    ),
    TariffFunction.HOUSE_IS_NOT: (
        TariffFormulaArgumentType.HOUSE,
    ),
    TariffFunction.HOUSE_IS_NOT_IN_GROUP: (
        TariffFormulaArgumentType.HOUSE_GROUP,
    ),
    TariffFunction.ADDRESS_DO_NOT_CONTAIN_TERRITORY: (
        TariffFormulaArgumentType.TERRITORY,
    ),
    TariffFunction.CONSUMPTION_TYPE_IS_NOT: (
        TariffFormulaArgumentType.COMMUNAL_RESOURCE,
        TariffFormulaArgumentType.CONSUMPTION_TYPE,
    ),
    TariffFunction.CONSUMPTION_TYPE_CALCULATED_IS_NOT: (
        TariffFormulaArgumentType.COMMUNAL_RESOURCE,
        TariffFormulaArgumentType.CONSUMPTION_TYPE,
    ),
}


class TariffType:
    URBAN = 'urban'
    MANUAL = 'manual'
    ADVANCED = 'advanced'


TARIFF_TYPES_CHOICES = (
    (TariffType.URBAN, 'Городской'),
    (TariffType.MANUAL, 'Ручной'),
    (TariffType.ADVANCED, 'Ручной'),
)


class PrivilegeCalculationType:
    OWN = 'own'
    REGIONAL = 'regional'


PRIVILEGE_CALCULATION_TYPES_CHOICES = (
    (PrivilegeCalculationType.OWN, 'Свои настройки'),
    (PrivilegeCalculationType.REGIONAL, 'Региональные настройки'),
)


class TariffRulesParentRelation:
    THEN = 'then'
    ELSE = 'else'


TARIFF_RULES_PARENT_RELATIONS_CHOICES = (
    (TariffRulesParentRelation.THEN, 'При выполнении'),
    (TariffRulesParentRelation.ELSE, 'При невыполнении'),
)


class TariffRuleActionParamType:
    REFER_FORMULA = 'refer_formula'
    REFER_VALUE = 'refer_value'
    FORMULA = 'formula'
    VALUE = 'value'


TARIFF_RULE_ACTION_PARAM_TYPES_CHOICES = (
    (TariffRuleActionParamType.REFER_FORMULA, 'Указание на готовую формулу'),
    (TariffRuleActionParamType.REFER_VALUE, 'Указание на готовое значение'),
    (TariffRuleActionParamType.FORMULA, 'Ручная формула'),
    (TariffRuleActionParamType.VALUE, 'Значение, указанное вручную'),
)


class TariffRuleAction:
    MAIN_FORMULA = 'main_formula'
    CONSUMPTION_FORMULA = 'consumption_formula'
    TARIFF = 'tariff'
    TARIFF_FORMULA = 'tariff_formula'
    TARIFF_CEIL = 'tariff_ceil'
    NORMA = 'norma'
    NORMA_FORMULA = 'norma_formula'
    NORM_NO_MONTHS_HOLES = 'norm_no_months_holes'
    RETURN_WHOLE_MONTH_FOR_HOLES = 'return_whole_month_for_holes'
    AREA_SOCIAL = 'area_social'
    AREA_LIVING = 'area_living'
    AREA_OWN = 'area_own'
    AREA_TOTAL = 'area_total'


TARIFF_RULE_ACTIONS_CHOICES = (
    (
        TariffRuleAction.MAIN_FORMULA,
        'Изменить формулу расчёта',
    ),
    (
        TariffRuleAction.CONSUMPTION_FORMULA,
        'Изменить формулу расхода',
    ),
    (
        TariffRuleAction.TARIFF,
        'Установить тариф',
    ),
    (
        TariffRuleAction.TARIFF_FORMULA,
        'Установить тариф (выбрать или рассчитать)',
    ),
    (
        TariffRuleAction.TARIFF_CEIL,
        'Рассчитать тариф по формуле в руб./коп.',
    ),
    (
        TariffRuleAction.NORMA,
        'Установить норматив',
    ),
    (
        TariffRuleAction.NORMA_FORMULA,
        'Установить норматив (выбрать или рассчитать)',
    ),
    (
        TariffRuleAction.NORM_NO_MONTHS_HOLES,
        'Установить месяц расчёта без ПУ равным месяцу учёта показаний',
    ),
    (
        TariffRuleAction.RETURN_WHOLE_MONTH_FOR_HOLES,
        'Делать возврат только полного месяца',
    ),
    (
        TariffRuleAction.AREA_SOCIAL,
        'Рассчитать социальную норму площади по формуле',
    ),
    (
        TariffRuleAction.AREA_LIVING,
        'Использовать жилую площадь по умолчанию',
    ),
    (
        TariffRuleAction.AREA_OWN,
        'Использовать площадь в собственности по умолчанию',
    ),
    (
        TariffRuleAction.AREA_TOTAL,
        'Использовать общую площадь по умолчанию',
    ),
)


class TariffsSumValueSettingsType:
    REGIONAL = 'regional'
    MANUAL = 'manual'
    ADVANCED = 'advanced'


TARIFFS_SUM_VALUES_SETTINGS_TYPES_CHOICES = (
    (TariffsSumValueSettingsType.REGIONAL, 'Системные настройки региона'),
    (TariffsSumValueSettingsType.MANUAL, 'Ручные настройки'),
    (TariffsSumValueSettingsType.ADVANCED, 'Ручные настройки'),
)
