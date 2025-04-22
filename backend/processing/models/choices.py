from processing.models.choice.gis_xlsx import LivingAreaGisTypes


def get_choice_str(choices, choice, default=None):
    matches = [c[1] for c in choices if c[0] == choice]
    return (
        matches[0]
        if matches
        else get_choice_str(choices, default) if default else None
    )


def get_constant_dict(reformat_constants):
    return {v[0]: v[1] for v in reformat_constants}


def get_choices_key_by_value(choices, value):
    for val in choices:
        if val[1] == value:
            return val[0]


class AreaLocations(object):
    WC = 'wc'
    HALL = 'hall'
    GARAGE = 'garage'
    TOILET = 'toilet'
    STOREY = 'storey'
    LIVING = 'living'
    KITCHEN = 'kitchen'
    CORRIDOR = 'corridor'
    BATHROOM = 'bathroom'
    PANTRY = 'pantry'

    CHOICES = (
        (WC, 'санузел'),
        (HALL, 'прихожая'),
        (GARAGE, 'гараж'),
        (TOILET, 'туалет'),
        (STOREY, 'этажная площадка'),
        (LIVING, 'жилая комната'),
        (KITCHEN, 'кухня'),
        (CORRIDOR, 'коридор'),
        (BATHROOM, 'ванная'),
        (PANTRY, 'кладовка')
    )


class RequestSamplesType:
    BODY = 'body'
    DELAYED = 'delayed'
    PERFORMED = 'performed'
    ABANDONMENT = 'abandonment'
    REFUSAL = 'refusal'


REQUEST_SAMPLES_TYPES_CHOICES = (
    (
        RequestSamplesType.BODY,
        'Шаблон заявки',
    ),
    (
        RequestSamplesType.DELAYED,
        'Шаблон описания для статуса «Отложена»',
    ),
    (
        RequestSamplesType.PERFORMED,
        'Шаблон описания для статуса «Выполнена»',
    ),
    (
        RequestSamplesType.ABANDONMENT,
        'Шаблон описания для статуса «Отказ в исполнении»',
    ),
    (
        RequestSamplesType.REFUSAL,
        'Шаблон описания для статуса «Отказ от заявки»',
    ),
)


class LegalDocumentType(object):
    AGENT = 'agent'
    WORK_DONE = 'work_done'
    SERVICE = 'service'


LEGAL_DOCUMENT_TYPE_CHOICES = (
    (LegalDocumentType.AGENT, "Агентский"),
    (LegalDocumentType.WORK_DONE, "Выполнения работ"),
    (LegalDocumentType.SERVICE, "Оказания услуг")
)


class AgentDocumentServiceType(object):
    PERCENT_OF_PAYMENT = 'percent_of_payment'
    PERCENT_OF_ACCRUAL = 'percent_of_accrual'
    PER_MONTH = 'per_month'


AGENT_DOCUMENT_SERVICE_TYPE = (
    (AgentDocumentServiceType.PER_MONTH, 'в месяц'),
    (AgentDocumentServiceType.PERCENT_OF_PAYMENT, '% от оплаты'),
    (AgentDocumentServiceType.PERCENT_OF_ACCRUAL, '% от начисления')
)


class ServicesProvisionServiceType(object):
    PER_MONTH = 'per_month'
    PER_SQUARE_METER = 'per_square_meter'
    PER_ONE = 'per_one'


SERVICES_PROVISION_SERVICE_TYPE_CHOICES = (
    (ServicesProvisionServiceType.PER_MONTH, 'в месяц'),
    (ServicesProvisionServiceType.PER_SQUARE_METER, 'с кв. м.'),
    (ServicesProvisionServiceType.PER_ONE, 'за шт')
)


class WorkDoneProvisionServiceType(object):
    PER_MONTH = 'per_month'
    PER_SQUARE_METER = 'per_square_meter'


WORK_DONE_SERVICE_TYPE_CHOICES = (
    (WorkDoneProvisionServiceType.PER_MONTH, 'в месяц'),
    (WorkDoneProvisionServiceType.PER_SQUARE_METER, 'с кв. м.'),
)

LEGAL_CONTRACT_CHOICES = (
    *AGENT_DOCUMENT_SERVICE_TYPE,
    *WORK_DONE_SERVICE_TYPE_CHOICES,
    *SERVICES_PROVISION_SERVICE_TYPE_CHOICES,

)


class AccrualDocumentTotalsCode(object):
    pass


ACCRUAL_DOCUMENT_TOTALS_CODES = (
    (
        'РХВ',
        'Общий расход ХВ по всем ЛС документа с уч.перерасчётов',
    ),
    (
        'РХВН',
        'Общий расход ХВ по всем ЛС документа без уч.перерасчётов',
    ),
    (
        'РХВЖП',
        'Общий расход ХВ по ЛС жил.пом. документа с уч.перерасчётов',
    ),
    (
        'РХВНЖП',
        'Общий расход ХВ по ЛС жил.пом. документа без уч.перерасчётов',
    ),
    (
        'РХВНП',
        'Общий расход ХВ по ЛС нежил.пом. документа с уч.перерасчётов',
    ),
    (
        'РХВННП',
        'Общий расход ХВ по ЛС нежил.пом. документа без уч.перерасчётов',
    ),
    (
        'РХВПАРК',
        'Общий расход ХВ по ЛС паркинга документа с уч.перерасчётов',
    ),
    (
        'РХС',
        'Общий расход ХВ по ЛС документа пом. со счётчиками с уч.перерасчётов',
    ),
    (
        'РХН',
        'Общий расход ХВ по ЛС документа пом. без счётчиков с уч.перерасчётов',
    ),
    (
        'ОХВ',
        'Авторасход ХВ на ОДН по всем ЛС документа с уч.перерасчётов',
    ),
    (
        'ОХВН',
        'Авторасход ХВ на ОДН по всем ЛС документа без уч.перерасчётов',
    ),
    (
        'РГВ',
        'Общий расход ГВ по всем ЛС документа с уч.перерасчётов',
    ),
    (
        'РГВН',
        'Общий расход ГВ по всем ЛС документа без уч.перерасчётов',
    ),
    (
        'РГВЖП',
        'Общий расход ГВ по ЛС жил.пом. документа с уч.перерасчётов',
    ),
    (
        'РГВНЖП',
        'Общий расход ГВ по ЛС жил.пом. документа без уч.перерасчётов',
    ),
    (
        'РГВНП',
        'Общий расход ГВ по ЛС нежил.пом. документа с уч.перерасчётов',
    ),
    (
        'РГВННП',
        'Общий расход ГВ по ЛС нежил.пом. документа без уч.перерасчётов',
    ),
    (
        'РГВПАРК',
        'Общий расход ГВ по ЛС паркинга документа с уч.перерасчётов',
    ),
    (
        'РГС',
        'Общий расход ГВ по ЛС документа пом. со счётчиками с уч.перерасчётов',
    ),
    (
        'РГН',
        'Общий расход ГВ по ЛС документа пом. без счётчиков с уч.перерасчётов',
    ),
    (
        'ОГВ',
        'Авторасход ГВ на ОДН по всем ЛС документа с уч.перерасчётов',
    ),
    (
        'ОГВН',
        'Авторасход ГВ на ОДН по всем ЛС документа без уч.перерасчётов',
    ),
    (
        'РГВБП',
        'Общ.расход ГВ по всем ЛС документа с уч.перер. без уч.перехода',
    ),
    (
        'РГВЖПБП',
        'Общ.расход ГВ по ЛС жил.пом. документа с уч.перер. без уч.перехода',
    ),
    (
        'РГВНПБП',
        'Общ.расход ГВ по ЛС нежил.пом. документа с уч.перер. без уч.перехода',
    ),
    (
        'РГВПАРКБП',
        'Общ.расход ГВ по ЛС паркинга документа с уч.перер. без уч.перехода',
    ),
    (
        'РОТ',
        'Общий расход тепла по всем ЛС документа без уч.перерасчётов',
    ),
    (
        'РОТЖП',
        'Общий расход тепла по ЛС жил.пом. документа без уч.перерасчётов',
    ),
    (
        'РОТНП',
        'Общий расход тепла по ЛС нежил.пом. документа без уч.перерасчётов',
    ),
    (
        'РОТПАРК',
        'Общий расход тепла по ЛС паркинга документа без уч.перерасчётов',
    ),
    (
        'РОТП',
        'Общий расход тепла по всем ЛС документа с уч.перерасчётов',
    ),
    (
        'РОТПЖП',
        'Общий расход тепла по ЛС жил.пом. документа с уч.перерасчётов',
    ),
    (
        'РОТПНП',
        'Общий расход тепла по ЛС нежил.пом. документа с уч.перерасчётов',
    ),
    (
        'РОТППАРК',
        'Общий расход тепла по ЛС паркинга документа с уч.перерасчётов',
    ),
    (
        'ООТ',
        'Авторасход тепла на ОДН по всем ЛС документа без уч.перерасчётов',
    ),
    (
        'ООТП',
        'Авторасход тепла на ОДН по всем ЛС документа с уч.перерасчётов',
    ),
    (
        'КЧД',
        'Общее количество проживающих по всем ЛС документа',
    ),
    (
        'КЧД1',
        'Общее количество проживающих по всем ЛС не менее 1 человека',
    ),
    (
        'КЧДХС',
        'Общее количество проживающих по ЛС документа пом. со счётчиками ХВ',
    ),
    (
        'КЧДХН',
        'Общее количество проживающих по ЛС документа пом. без счётчиков ХВ',
    ),
    (
        'КЧДГС',
        'Общее количество проживающих по ЛС документа пом. со счётчиками ГВ',
    ),
    (
        'КЧДГН',
        'Общее количество проживающих по ЛС документа пом. без счётчиков ГВ',
    ),
    (
        'ПЛД',
        'Общая площадь помещений по всем ЛС документа',
    ),
    (
        'ПЛДЖП',
        'Общая площадь помещений по ЛС документа жилых пом.',
    ),
    (
        'ПЛДНП',
        'Общая площадь помещений по ЛС документа нежилых пом.',
    ),
    (
        'ПЛДПАРК',
        'Общая площадь помещений по ЛС документа паркинга',
    ),
    (
        'РЭД',
        'Общий расход Эл.Эн день по всем ЛС документа с уч.перерасчётов',
    ),
    (
        'РЭДН',
        'Общий расход Эл.Эн день по всем ЛС документа без уч.перерасчётов',
    ),
    (
        'РЭДЖП',
        'Общий расход Эл.Эн день по ЛС жил.пом. документа с уч.перерасчётов',
    ),
    (
        'РЭДНП',
        'Общий расход Эл.Эн день по ЛС нежил.пом. документа с уч.перерасчётов',
    ),
    (
        'РЭДПАРК',
        'Общий расход Эл.Эн день по ЛС паркинга документа с уч.перерасчётов',
    ),
    (
        'РДС',
        'Общий расход Эл.Эн день по ЛС документа пом. со счётчиками '
        'с уч.перерасчётов',
    ),
    (
        'РДН',
        'Общий расход Эл.Эн день по ЛС документа пом. без счётчиков '
        'с уч.перерасчётов',
    ),
    (
        'РЭН',
        'Общий расход Эл.Эн ночь по всем ЛС документа с уч.перерасчётов',
    ),
    (
        'РЭНН',
        'Общий расход Эл.Эн ночь по всем ЛС документа без уч.перерасчётов',
    ),
    (
        'РЭНЖП',
        'Общий расход Эл.Эн ночь по ЛС жил.пом. документа с уч.перерасчётов',
    ),
    (
        'РЭННП',
        'Общий расход Эл.Эн ночь по ЛС нежил.пом. документа с уч.перерасчётов',
    ),
    (
        'РЭНПАРК',
        'Общий расход Эл.Эн ночь по ЛС паркинга документа с уч.перерасчётов',
    ),
    (
        'РНС',
        'Общий расход Эл.Эн ночь по ЛС документа пом. со счётчиками '
        'с уч.перерасчётов',
    ),
    (
        'РНН',
        'Общий расход Эл.Эн ночь по ЛС документа пом. без счётчиков '
        'с уч.перерасчётов',
    ),
    (
        'РЭЛ',
        'Общий расход Эл.Эн однотар. по всем ЛС документа с уч.перерасчётов',
    ),
    (
        'РЭЛН',
        'Общий расход Эл.Эн однотар. по всем ЛС документа без уч.перерасчётов',
    ),
    (
        'РЭЛЖП',
        'Общий расход Эл.Эн однотар. по ЛС жил.пом. документа '
        'с уч.перерасчётов',
    ),
    (
        'РЭЛНП',
        'Общий расход Эл.Эн однотар. по ЛС нежил.пом. документа '
        'с уч.перерасчётов',
    ),
    (
        'РЭЛПАРК',
        'Общий расход Эл.Эн однотар. по ЛС паркинга документа '
        'с уч.перерасчётов',
    ),
    (
        'РЛС',
        'Общий расход Эл.Эн однотар. по ЛС документа пом. со счётчиками '
        'с уч.перерасчётов',
    ),
    (
        'РЛН',
        'Общий расход Эл.Эн однотар. по ЛС документа пом. без счётчиков '
        'с уч.перерасчётов',
    ),
    (
        'РЭП',
        'Общий расход Эл.Эн пик.зоны по всем ЛС документа с уч.перерасчётов',
    ),
    (
        'РЭПН',
        'Общий расход Эл.Эн пик.зоны по всем ЛС документа без уч.перерасчётов',
    ),
    (
        'РЭПЖП',
        'Общий расход Эл.Эн пик.зоны по ЛС жил.пом. документа,'
        'с уч.перерасчётов',
    ),
    (
        'РЭПНП',
        'Общий расход Эл.Эн пик.зоны по ЛС нежил.пом. документа '
        'с уч.перерасчётов',
    ),
    (
        'РЭППАРК',
        'Общий расход Эл.Эн пик.зоны по ЛС паркинга документа '
        'с уч.перерасчётов',
    ),
    (
        'РПС',
        'Общий расход Эл.Эн пик.зоны по ЛС документа пом. со счётчиками '
        'с уч.перерасчётов',
    ),
    (
        'РПН',
        'Общий расход Эл.Эн пик.зоны по ЛС документа пом. без счётчиков '
        'с уч.перерасчётов',
    ),
    (
        'РЭПП',
        'Общий расход Эл.Эн полупик.зоны по всем ЛС документа '
        'с уч.перерасчётов',
    ),
    (
        'РЭППН',
        'Общий расход Эл.Эн полупик.зоны по всем ЛС документа '
        'без уч.перерасчётов',
    ),
    (
        'РЭППЖП',
        'Общий расход Эл.Эн полупик.зоны по ЛС жил.пом. документа '
        'с уч.перерасчётов',
    ),
    (
        'РЭППНП',
        'Общий расход Эл.Эн полупик.зоны по ЛС нежил.пом. документа '
        'с уч.перерасчётов',
    ),
    (
        'РЭПППАРК',
        'Общий расход Эл.Эн полупик.зоны по ЛС паркинга документа '
        'с уч.перерасчётов',
    ),
    (
        'РППС',
        'Общий расход Эл.Эн полупик.зоны по ЛС документа пом. со счётчиками '
        'с уч.перерасчётов',
    ),
    (
        'РППН',
        'Общий расход Эл.Эн полупик.зоны по ЛС документа пом. без счётчиков '
        'с уч.перерасчётов',
    ),
    (
        'РХВД',
        'Сумма общих расходов с кодом РХВ других документов организации',
    ),
    (
        'РХВЖПД',
        'Сумма общих расходов с кодом РХВЖП других документов организации',
    ),
    (
        'РХВНПД',
        'Сумма общих расходов с кодом РХВНП других документов организации',
    ),
    (
        'РХВПАРКД',
        'Сумма общих расходов с кодом РХВПАРК других документов организации',
    ),
    (
        'РХВНД',
        'Сумма общих расходов с кодом РХВН других документов организации',
    ),
    (
        'РГВД',
        'Сумма общих расходов с кодом РГВ других документов организации',
    ),
    (
        'РГВЖПД',
        'Сумма общих расходов с кодом РГВЖП других документов организации',
    ),
    (
        'РГВНПД',
        'Сумма общих расходов с кодом РГВНП других документов организации',
    ),
    (
        'РГВПАРКД',
        'Сумма общих расходов с кодом РГВПАРК других документов организации',
    ),
    (
        'РГВНД',
        'Сумма общих расходов с кодом РГВН других документов организации',
    ),
    (
        'РОТД',
        'Сумма общих расходов с кодом РОТ других документов организации',
    ),
    (
        'РОТЖПД',
        'Сумма общих расходов с кодом РОТЖП других документов организации',
    ),
    (
        'РОТНПД',
        'Сумма общих расходов с кодом РОТНП других документов организации',
    ),
    (
        'РОТПАРКД',
        'Сумма общих расходов с кодом РОТПАРК других документов организации',
    ),
    (
        'РОТПД',
        'Сумма общих расходов с кодом РОТП других документов организации',
    ),
    (
        'ПГВД',
        'Сумма общих расходов с кодом ПГВ других документов организации',
    ),
    (
        'ПГВЖПД',
        'Сумма общих расходов с кодом ПГВЖП других документов организации',
    ),
    (
        'ПГВНПД',
        'Сумма общих расходов с кодом ПГВНП других документов организации',
    ),
    (
        'ПГВПАРКД',
        'Сумма общих расходов с кодом ПГВПАРК других документов организации',
    ),
    (
        'ПГВНД',
        'Сумма общих расходов с кодом ПГВН других документов организации',
    ),
    (
        'РЭЛД',
        'Сумма общих расходов с кодом РЭЛ других документов организации',
    ),
    (
        'РЭЛЖПД',
        'Сумма общих расходов с кодом РЭЛЖП других документов организации',
    ),
    (
        'РЭЛНПД',
        'Сумма общих расходов с кодом РЭЛНП других документов организации',
    ),
    (
        'РЭЛПАРКД',
        'Сумма общих расходов с кодом РЭЛПАРК других документов организации',
    ),
    (
        'РЭЛНД',
        'Сумма общих расходов с кодом РЭЛН других документов организации',
    ),
    (
        'РЭДД',
        'Сумма общих расходов с кодом РЭД других документов организации',
    ),
    (
        'РЭДЖПД',
        'Сумма общих расходов с кодом РЭДЖП других документов организации',
    ),
    (
        'РЭДНПД',
        'Сумма общих расходов с кодом РЭДНП других документов организации',
    ),
    (
        'РЭДПАРКД',
        'Сумма общих расходов с кодом РЭДПАРК других документов организации',
    ),
    (
        'РЭДНД',
        'Сумма общих расходов с кодом РЭДН других документов организации',
    ),
    (
        'РЭНД',
        'Сумма общих расходов с кодом РЭН других документов организации',
    ),
    (
        'РЭНЖПД',
        'Сумма общих расходов с кодом РЭНЖП других документов организации',
    ),
    (
        'РЭННПД',
        'Сумма общих расходов с кодом РЭННП других документов организации',
    ),
    (
        'РЭНПАРКД',
        'Сумма общих расходов с кодом РЭНПАРК других документов организации',
    ),
    (
        'РЭННД',
        'Сумма общих расходов с кодом РЭНН других документов организации',
    ),
    (
        'РЭПД',
        'Сумма общих расходов с кодом РЭП других документов организации',
    ),
    (
        'РЭПЖПД',
        'Сумма общих расходов с кодом РЭПЖП других документов организации',
    ),
    (
        'РЭПНПД',
        'Сумма общих расходов с кодом РЭПНП других документов организации',
    ),
    (
        'РЭППАРКД',
        'Сумма общих расходов с кодом РЭППАРК других документов организации',
    ),
    (
        'РЭПНД',
        'Сумма общих расходов с кодом РЭПН других документов организации',
    ),
    (
        'РЭППД',
        'Сумма общих расходов с кодом РЭПП других документов организации',
    ),
    (
        'РЭППЖПД',
        'Сумма общих расходов с кодом РЭППЖП других документов организации',
    ),
    (
        'РЭППНПД',
        'Сумма общих расходов с кодом РЭППНП других документов организации',
    ),
    (
        'РЭПППАРКД',
        'Сумма общих расходов с кодом РЭПППАРК других документов организации',
    ),
    (
        'РЭППНД',
        'Сумма общих расходов с кодом РЭППН других документов организации',
    ),
    (
        'ПГВ',
        'Общий расход тепла на подогрев ГВ по всем ЛС документа '
        'с учётом перерасчётов',
    ),
    (
        'ПГВН',
        'Общий расход тепла на подогрев ГВ по всем ЛС документа '
        'без учёта перерасчётов',
    ),
    (
        'ПГВНП',
        'Тепловая энергия на подогрев ГВ в нежилых помещений '
        'за вычетом перерасчетов',
    ),
    (
        'ПГВЖП',
        'Тепловая энергия на подогрев ГВ в жилых помещениях '
        'за вычетом перерасчетов',
    ),
    (
        'ПГВБГ',
        'Общ.расх.тепла на подогрев ГВ по всем ЛС документа '
        'с уч.перер. без уч.перехода',
    ),
    (
        'ПГВНПБГ',
        'Тепл.энергия на подогрев ГВ в неж.пом. за выч.перер. без уч.перехода',
    ),
    (
        'ПГВЖПБГ',
        'Тепл.энергия на подогрев ГВ в жил.пом. за выч.перер. без уч.перехода',
    ),
    (
        'ПГВПАРКБГ',
        'Тепл.энергия на подогрев ГВ в паркинге за выч.перер. без уч.перехода',
    ),
)
ACCRUAL_DOCUMENT_TOTALS_CODES_AS_DICT = get_constant_dict(
    ACCRUAL_DOCUMENT_TOTALS_CODES
)


class AccrualsSectorType(object):
    RENT = 'rent'
    SOCIAL_RENT = 'social_rent'
    CAPITAL_REPAIR = 'capital_repair'
    HEAT_SUPPLY = 'heat_supply'
    WATER_SUPPLY = 'water_supply'
    WASTE_WATER = 'waste_water'
    CABLE_TV = 'catv'
    GARBAGE = 'garbage'
    TARGET_FEE = 'reg_fee'
    LEASE = 'lease'
    COMMERCIAL = 'commercial'
    GAS_SUPPLY = 'gas_supply'
    COMMUNAL = 'communal'
    COLD_WATER_PUBLIC = 'cold_water_public'


ACCRUAL_SECTOR_TYPE_CHOICES = (
    # Порядок имеет значение
    (AccrualsSectorType.RENT, 'Квартплата'),
    (AccrualsSectorType.SOCIAL_RENT, 'Социальный найм'),
    (AccrualsSectorType.CAPITAL_REPAIR, 'Капитальный ремонт'),
    (AccrualsSectorType.HEAT_SUPPLY, 'Теплоснабжение'),
    (AccrualsSectorType.WATER_SUPPLY, 'Водоснабжение'),
    (AccrualsSectorType.WASTE_WATER, 'Водоотведение'),
    (AccrualsSectorType.CABLE_TV, 'Кабельное ТВ'),
    (AccrualsSectorType.GARBAGE, 'Вывоз мусора'),
    (AccrualsSectorType.TARGET_FEE, 'Целевой взнос'),
    (AccrualsSectorType.LEASE, 'Аренда'),
    (AccrualsSectorType.COMMERCIAL, 'Платные услуги'),
    (AccrualsSectorType.GAS_SUPPLY, 'Газоснабжение'),
    (AccrualsSectorType.COMMUNAL, 'Коммунальные услуги'),
    (AccrualsSectorType.COLD_WATER_PUBLIC, 'Холодное водоснабжение ОДН'),
)
ACCRUAL_SECTOR_TYPE_CHOICES_AS_DICT = get_constant_dict(
    ACCRUAL_SECTOR_TYPE_CHOICES
)


class PayReasonType(object):
    COMMERCIAL_CATALOGUE = 'commercial_catalogue'


PAY_REASON_TYPE_CHOICES = (
    (PayReasonType.COMMERCIAL_CATALOGUE, 'Коммерческие услуги из каталога'),
) + ACCRUAL_SECTOR_TYPE_CHOICES


class AccrualLanguage(object):
    RU = 'RU'
    KZ = 'KZ'


ACCRUAL_LANGUAGE = (
    (AccrualLanguage.RU, 'Русский'),
    (AccrualLanguage.KZ, 'Қазақ')
)


class RegistryStringFormat:
    FIAS_WITH_AREA_NUMBER = 'fias_with_area_number'
    BY_DEFAULT = 'default'


REGISTRY_STRING_FORMAT_CHOICES = (
    (
        RegistryStringFormat.FIAS_WITH_AREA_NUMBER,
        'Новый формат (ЛС;ЕЛС;ФИАС,№помещения;город,улица,дом,'
        '№помещения;ЛС;сумма;дата...)',
    ),
    (
        RegistryStringFormat.BY_DEFAULT,
        'По умолчанию (ЛС;ЕЛС;ФИАС;город,улица,дом,'
        '№помещения;ЛС;сумма;дата...)',
    )
)


class TenantContractType:
    HEAT_SUPPLY = 'heat_supply'
    WATER_SUPPLY = 'water_supply'
    WASTE_WATER = 'wastewater'
    MANAGEMENT = 'management'
    ELECTRIC_SUPPLY = 'electric_supply'
    CATV = 'catv'
    RENT = 'rent'
    COLD_WATER_PUBLIC = 'cold_water_public'


TENANT_CONTRACT_TYPE_CHOICES = (
    (TenantContractType.HEAT_SUPPLY, 'теплоснабжение'),
    (TenantContractType.WATER_SUPPLY, 'водоснабжение'),
    (TenantContractType.WASTE_WATER, 'водоотведение'),
    (TenantContractType.MANAGEMENT, 'управление'),
    (TenantContractType.ELECTRIC_SUPPLY, 'электроснабжение'),
    (TenantContractType.CATV, 'кабельное телевидение'),
    (TenantContractType.RENT, 'аренда'),
    (TenantContractType.COLD_WATER_PUBLIC, 'холодное водоснабжение ОДН'),
)


class TenantGracePeriod(object):
    MOBILIZATION = 'mobilization_2022'
    BANKRUPT = 'bankrupt_tenant'
    AGREEMENT_WITH_PROV = 'agreement_with_provider'


REASON_RESPONSIBLE_TENANT_GRACE_PERIOD = (
    (TenantGracePeriod.MOBILIZATION, 'Мобилизация 2022'),
    (TenantGracePeriod.BANKRUPT, 'Банкрот'),
    (TenantGracePeriod.AGREEMENT_WITH_PROV, 'Договорённость о не начислении')

)


class RecalculationReasonType(object):
    MANUAL = 'manual'
    METER = 'meter'
    METER_HEATED = 'meter_heated'
    BANK = 'bank'
    DISCOUNT = 'discount'
    PUBLIC_COMMUNAL_RETURN = 'public_communal'


RECALCULATION_REASON_TYPE_CHOICES = (
    (RecalculationReasonType.MANUAL, 'ручной'),
    (RecalculationReasonType.METER, 'по счетчику'),
    (RecalculationReasonType.METER_HEATED,
     'по счетчику ГВ с учтённым подогревом'),
    (RecalculationReasonType.BANK, 'по проценту банка'),
    (RecalculationReasonType.DISCOUNT, 'скидка'),
    (RecalculationReasonType.PUBLIC_COMMUNAL_RETURN, 'возврат ОДН'),
)


class ConsumptionType(object):
    METER = 'meter'
    AVERAGE = 'average'
    NORMA = 'norma'
    NORMA_WOM = 'norma_wom'
    METER_WO = 'meter_wo'
    NOTHING = 'nothing'
    HOUSE_METER = 'house_meter'


CONSUMPTION_TYPE_CHOICES = (
    (ConsumptionType.METER, 'по ИПУ'),
    (ConsumptionType.AVERAGE, 'среднее'),
    (ConsumptionType.NORMA, 'норматив'),
    (ConsumptionType.NORMA_WOM, 'норматив без счетчика'),
    (ConsumptionType.METER_WO, 'без счетчика'),
    (ConsumptionType.NOTHING, 'отсутствует'),
    (ConsumptionType.HOUSE_METER, 'по ОПУ'),
)
CONSUMPTION_TYPE_CHOICES_AS_DICT = get_constant_dict(CONSUMPTION_TYPE_CHOICES)


class AccrualDocumentType(object):
    MAIN = 'main'
    ADD = 'add'
    PER = 'per'
    ADV = 'adv'
    ADJ = 'adj'
    SLD = 'sld'
    PEN = 'pen'


ACCRUAL_DOCUMENT_TYPE_CHOICES = (
    (AccrualDocumentType.MAIN, 'основной за месяц'),
    (AccrualDocumentType.ADD, 'дополнительный за месяц'),
    (AccrualDocumentType.PER, 'за произвольный период'),
    (AccrualDocumentType.ADV, 'авансовый'),
    (AccrualDocumentType.ADJ, 'корректировочный'),
    (AccrualDocumentType.SLD, 'входящие остатки'),
    (AccrualDocumentType.PEN, 'пени'),
)


class AccrualDocumentStatus(object):
    WORK_IN_PROGRESS = 'wip'
    READY = 'ready'
    EDIT = 'edit'
    FUTURE = 'future'


ACCRUAL_DOCUMENT_STATUS_CHOICES = (
    (AccrualDocumentStatus.WORK_IN_PROGRESS, 'в работе'),
    (AccrualDocumentStatus.READY, 'готов'),
    (AccrualDocumentStatus.EDIT, 'на редактировании'),
    (AccrualDocumentStatus.FUTURE, 'предварительный')
)


# TODO: remove this sodomy codes. REMOVE. R-E-M-O-V-E.
class Code(object):
    SАЗ = 'SАЗ'
    SАН = 'SАН'
    SАХ = 'SАХ'
    SБП = 'SБП'
    SВМ = 'SВМ'
    SГВ = 'SГВ'
    SГЗ = 'SГЗ'
    SГК = 'SГК'
    SГО = 'SГО'
    SКВ = 'SКВ'
    SКГ = 'SКГ'
    SКХ = 'SКХ'
    SЛФ = 'SЛФ'
    SМП = 'SМП'
    SОТ = 'SОТ'
    SПЕ = 'SПЕ'
    SПЗ = 'SПЗ'
    SРД = 'SРД'
    SСТ = 'SСТ'
    SТО = 'SТО'
    SТП = 'SТП'
    SТР = 'SТР'
    SУЛ = 'SУЛ'
    SХВ = 'SХВ'
    SХК = 'SХК'
    SХХ = 'SХХ'
    SЭД = 'SЭД'
    SЭЛ = 'SЭЛ'
    SЭН = 'SЭН'
    ЭЛП = 'ЭЛП'
    ЭПП = 'ЭПП'
    SЭС = 'SЭС'
    ОГВ = 'ОГВ'
    ОКВ = 'ОКВ'
    ООТ = 'ООТ'
    ОХВ = 'ОХВ'
    ОЭД = 'ОЭД'
    ОЭН = 'ОЭН'
    ПГВ = 'ПГВ'
    ПУЭ = 'ПУЭ'
    ПУТ = 'ПУТ'
    ПУХ = 'ПУХ'
    RNA = 'RNA'
    ЦГВ = 'ЦГВ'
    ОПГ = 'ОПГ'
    ОКХ = 'ОКХ'
    ОКГ = 'ОКГ'
    ОЭО = 'ОЭО'


CODE_CHOICES = (
    (Code.SАЗ, 'АППЗ'),
    (Code.SАН, 'Антенна'),
    (Code.SАХ, 'АХР/АУР'),
    (Code.SБП, 'Банк (процент)'),
    (Code.SВМ, 'Вывоз мусора'),
    (Code.SГВ, 'Гор.вода'),
    (Code.SГЗ, 'Газ'),
    (Code.SГК, 'ГВ+канализ.(ГВ)'),
    (Code.SГО, 'Сод.газ.оборуд.'),
    (Code.SКВ, 'Канализация воды'),
    (Code.SКГ, 'Канализация ГВ'),
    (Code.SКХ, 'Канализация ХВ'),
    (Code.SЛФ, 'Лифт'),
    (Code.SМП, 'Мусоропровод'),
    (Code.SОТ, 'Отопление'),
    (Code.SПЕ, 'Пени'),
    (Code.SПЗ, 'ПЗУ/Домофон'),
    (Code.SРД, 'Радио'),
    (Code.SСТ, 'Сод.территории'),
    (Code.SТО, 'Сод.дома/ТО'),
    (Code.SТП, 'Тепловой счетчик'),
    (Code.SТР, 'Текущий ремонт'),
    (Code.SУЛ, 'Уборка лестниц'),
    (Code.SХВ, 'ХВ без канализации'),
    (Code.SХК, 'ХВ+канализ.(сумм.)'),
    (Code.SХХ, 'ХВ+канализ.(ХВ)'),
    (Code.SЭД, 'Электричество ДН'),
    (Code.SЭЛ, 'Электричество'),
    (Code.SЭН, 'Электричество НЧ'),
    (Code.ЭЛП, 'Электричество Пиковое'),
    (Code.ЭПП, 'Электричество Полупиковое'),
    (Code.SЭС, 'Электричество (сумм)'),
    (Code.ОГВ, 'ГВС МОП'),
    (Code.ОКВ, 'Водоотведение МОП'),
    (Code.ООТ, 'Отопление МОП'),
    (Code.ОХВ, 'ХВС МОП'),
    (Code.ОЭД, 'Освещение МОП ДН'),
    (Code.ОЭН, 'Освещение МОП НЧ'),
    (Code.ПГВ, 'Подогрев ГВС'),
    (Code.ПУЭ, 'УзУчЭл/Эн'),
    (Code.ПУТ, 'УзУчТепЭн'),
    (Code.ПУХ, 'УзУчХВС'),
    (Code.RNA, 'Ручное начисление'),
    (Code.ЦГВ, 'Циркуляция'),
    (Code.ПГВ, 'Самостоятельный подогрев ГВ'),
    (Code.ОПГ, 'Самостоятельный подогрев ГВС на ОДН'),
    (Code.ОКХ, 'Канализация ХВ на ОДН'),
    (Code.ОКГ, 'Канализация ГВ на ОДН'),
    (Code.ОЭО, 'Общая электроэнергия МОП')
)


class PhoneType(object):
    CELL = 'cell'
    WORK = 'work'
    DISPATCHER = 'dispatcher'
    HOME = 'home'
    FAX = 'fax'


PHONE_TYPE_CHOICES = (
    (PhoneType.CELL, 'мобильный'),
    (PhoneType.WORK, 'рабочий'),
    (PhoneType.DISPATCHER, 'диспетчерский'),
    (PhoneType.HOME, 'домашний'),
    (PhoneType.FAX, 'факс'),
)


class LegalFormType(object):
    OOO = 'ООО'
    TSJ = 'ТСЖ'
    JSK = 'ЖСК'
    JK = 'ЖК'
    GUP = 'ГУП'
    ZAO = 'ЗАО'
    OAO = 'ОАО'
    IP = 'ИП'
    GU = 'ГУ'
    PAO = 'ПАО'
    PJSK = 'ПЖСК'
    TSN = 'ТСН'
    NKO = 'НКО'
    NKO_RK = 'НКО РК'
    MUP = 'МУП'
    CNT = 'СНТ'
    DNP = 'ДНП'
    AO = 'АО'
    GSK = 'ГСК'
    PK = 'ПК'
    NAO = 'НАО'
    FGKU = 'ФГКУ'
    FGUP = 'ФГУП'
    FGBU = 'ФГБУ'
    TSNJ = 'ТСН(Ж)'
    MP = 'МП'
    JSEK = 'ЖСЭК'
    MKP = 'МКП'
    GPK = 'ГПК'
    CHDOU = 'ЧДОУ'
    JPK = 'ЖПК'
    JEK = 'ЖЭК'
    PJEK = 'ПЖЭК'
    PJSEK = 'ПЖСЭК'
    OJEK = 'ОЖЭК'
    none = ''


LEGAL_FORM_TYPE_CHOICES = (
    (LegalFormType.OOO, 'ООО'),
    (LegalFormType.TSJ, 'ТСЖ'),
    (LegalFormType.JSK, 'ЖСК'),
    (LegalFormType.JK, 'ЖК'),
    (LegalFormType.GUP, 'ГУП'),
    (LegalFormType.ZAO, 'ЗАО'),
    (LegalFormType.OAO, 'ОАО'),
    (LegalFormType.IP, 'ИП'),
    (LegalFormType.GU, 'ГУ'),
    (LegalFormType.PAO, 'ПАО'),
    (LegalFormType.PJSK, 'ПЖСК'),
    (LegalFormType.TSN, 'ТСН'),
    (LegalFormType.NKO, 'НКО'),
    (LegalFormType.NKO_RK, 'НКО РК'),
    (LegalFormType.MUP, 'МУП'),
    (LegalFormType.CNT, 'СНТ'),
    (LegalFormType.DNP, 'ДНП'),
    (LegalFormType.AO, 'АО'),
    (LegalFormType.GSK, 'ГСК'),
    (LegalFormType.PK, 'ПК'),
    (LegalFormType.NAO, 'НАО'),
    (LegalFormType.FGKU, 'ФГКУ'),
    (LegalFormType.FGUP, 'ФГУП'),
    (LegalFormType.FGBU, 'ФГБУ'),
    (LegalFormType.TSNJ, 'ТСН(Ж)'),
    (LegalFormType.MP, 'МП'),
    (LegalFormType.JSEK, 'ЖСЭК'),
    (LegalFormType.MKP, 'МКП'),
    (LegalFormType.GPK, 'ГПК'),
    (LegalFormType.CHDOU, 'ЧДОУ'),
    (LegalFormType.JPK, 'ЖПК'),
    (LegalFormType.JEK, 'ЖЭК'),
    (LegalFormType.PJEK, 'ПЖЭК'),
    (LegalFormType.PJSEK, 'ПЖСЭК'),
    (LegalFormType.OJEK, 'ОЖЭК'),
    (LegalFormType.none, ''),

)


class TenantType(object):
    PRIVATE_TENANT = 'PrivateTenant'
    LEGAL_TENANT = 'LegalTenant'
    OTHER_TENANT = 'OtherTenant'


TENANT_TYPE_CHOICES = (
    (TenantType.PRIVATE_TENANT, 'Физическое лицо'),
    (TenantType.LEGAL_TENANT, 'Юридическое лицо'),
    (TenantType.OTHER_TENANT, 'Иное лицо'),
)


class GenderType(object):
    MALE = 'male'
    FEMALE = 'female'


GENDER_TYPE_CHOICES = (
    (GenderType.MALE, 'мужской'),
    (GenderType.FEMALE, 'женский'),
)


class CopyDocumentType(object):
    INN = 'inn'
    EMPLOYMENT_CONTRACT = 'employment_contract'
    SNILS = 'snils'
    IDENTITY_CARD = 'identity_card'


COPY_DOCUMENT_TYPE = (
    (CopyDocumentType.INN, 'Документ ИНН'),
    (CopyDocumentType.EMPLOYMENT_CONTRACT, 'Трудовой довор'),
    (CopyDocumentType.SNILS, 'Документ СНИЛС'),
    (CopyDocumentType.IDENTITY_CARD, 'Документ удостоверяющий личность'),
)


class RentingContractType(object):
    SOCIAL_RENT = 'social_rent'
    RENT = 'rent'


RENTING_CONTRACT_TYPE_CHOICES = (
    (RentingContractType.SOCIAL_RENT, 'Социального найма'),
    (RentingContractType.RENT, 'Найма'),
)


class Nationality(object):
    RUSSIAN = 'russian'


NATIONALITY_CHOICES = (
    (Nationality.RUSSIAN, 'русский'),
)


class PrintReceiptType(object):
    UNKNOWN = 'unknown'
    SELF = 'self'
    VCKP = 'vzkp'
    ELLIS = 'ellis'
    SBERBANK = 'sberbank'
    ZAO_OTDEL = 'zaotdel'
    OTHER = 'other'
    EIS_JKH = 'eisjkh'
    EIRC_LO = 'eirclo'
    INARI = 'inari'
    R200 = 'r200'
    KOTOLUP = 'kotolup'


PRINT_RECEIPT_TYPE_CHOICES = (
    (PrintReceiptType.UNKNOWN, 'Не задано'),
    (PrintReceiptType.SELF, 'Самостоятельно'),
    (PrintReceiptType.VCKP, 'ВЦКП'),
    (PrintReceiptType.ELLIS, 'Эллис'),
    (PrintReceiptType.SBERBANK, 'Домоплат'),
    (PrintReceiptType.ZAO_OTDEL, 'ЗАО «Отдел»'),
    (PrintReceiptType.OTHER, 'Иное'),
    (PrintReceiptType.EIS_JKH, 'ЕИС ЖКХ'),
    (PrintReceiptType.EIRC_LO, 'АО "ЕИРЦ ЛО"'),
    (PrintReceiptType.INARI, 'ООО "Инари Технологии"'),
    (PrintReceiptType.R200, 'Квадо'),
    (PrintReceiptType.KOTOLUP, 'ИП Котолуп'),
)


class CalcSoftwareType(object):
    ONE_C = '1C'
    KVARTAL = 'kvartal'
    JSK_PROF = 'zhsk-prof'
    C300 = 'c300'
    OTHER = 'other'
    NOTHING = 'nothing'
    QUADO = 'quado'
    ELLIS_SPB = 'ellis_spb'
    QUARTPLATA24 = 'quartplata24'
    DOMOVLADELETS = 'domovladelets'
    BURMISTR = 'burmistr'
    INARI_JH = 'inari_jh'
    STEK_JKH = 'stek_jkh'
    STEK_DIVO = 'stek_divo'
    BRIS_JKH = 'bris_jkh'
    OWN = 'own'
    AIS_GOROD = 'ais_gorod'
    MKD_ONLINE = 'mkd_online'
    INSOC = 'insoc'
    JKH_IT = 'jkh_it'
    PK_BONUS = 'pk_bonus'
    PULS_PRO = 'puls_pro'
    KONTUR_JKH = 'kontur_jkh'
    ABONENT_PLUS = 'abonent_plus'
    JIL_STANDARD = 'jil_standard'
    SUPER_MKD = 'super_mkd'


CALC_SOFTWARE_TYPE_CHOICES = (
    (CalcSoftwareType.ONE_C, 'Продукты 1С'),
    (CalcSoftwareType.KVARTAL, 'Квартал'),
    (CalcSoftwareType.JSK_PROF, 'ЖСК-проф'),
    (CalcSoftwareType.C300, 'Система С300'),
    (CalcSoftwareType.OTHER, 'Иная'),
    (CalcSoftwareType.NOTHING, 'Не используется'),
    (CalcSoftwareType.QUADO, 'Квадо'),
    (CalcSoftwareType.ELLIS_SPB, 'Эллис СПб'),
    (CalcSoftwareType.QUARTPLATA24, 'Квартплата 24'),
    (CalcSoftwareType.DOMOVLADELETS, 'Домовладелец'),
    (CalcSoftwareType.BURMISTR, 'Бурмистр'),
    (CalcSoftwareType.INARI_JH, 'Инари ЖХ'),
    (CalcSoftwareType.STEK_JKH, 'Стек-ЖКХ'),
    (CalcSoftwareType.STEK_DIVO, 'Стек-Диво'),
    (CalcSoftwareType.BRIS_JKH, 'БРИС ЖКХ'),
    (CalcSoftwareType.OWN, 'Самописная'),
    (CalcSoftwareType.AIS_GOROD, 'АИС-Город'),
    (CalcSoftwareType.MKD_ONLINE, 'МКД-онлайн'),
    (CalcSoftwareType.INSOC, 'ИНСОЦ'),
    (CalcSoftwareType.JKH_IT, 'ЖКХ-ИТ'),
    (CalcSoftwareType.PK_BONUS, 'ПК Бонус'),
    (CalcSoftwareType.PULS_PRO, 'Пульс Про'),
    (CalcSoftwareType.KONTUR_JKH, 'Контур ЖКХ'),
    (CalcSoftwareType.ABONENT_PLUS, 'Абонент+'),
    (CalcSoftwareType.JIL_STANDARD, 'Жилищный Стандарт'),
    (CalcSoftwareType.SUPER_MKD, 'Супер МКД'),

)


class DocType(object):
    CERTIFICATE_OF_COMPLETION = "certificate_of_completion"
    QUESTIONNAIRE = "questionnaire"
    CONTRACT = "contract"
    ADDITIONAL_AGREEMENTS = "additional_agreements"
    LETTER = "letter"
    ACCOUNT = 'account'
    NOTICE = 'notice'


DOC_TYPE = (
    (DocType.CERTIFICATE_OF_COMPLETION, "Акт выполненных работ"),
    (DocType.QUESTIONNAIRE, "Анкета"),
    (DocType.CONTRACT, "Договор"),
    (DocType.ADDITIONAL_AGREEMENTS, "Доп. соглашение"),
    (DocType.LETTER, "Письмо"),
    (DocType.ACCOUNT, 'Счет'),
    (DocType.NOTICE, 'Уведомление'),
)


class WorkerStatus(object):
    OK = 'ok'
    MAINTENANCE = 'maintenance'


WORKER_STATUS_CHOICE = (
    (WorkerStatus.OK, 'Работает'),
    (WorkerStatus.MAINTENANCE, 'Обслуживание'),
)


class PropertyShareRecord:
    SALE_CONTRACT = 'sale_contract'
    QUALIFICATION = 'qualification'


PROPERTY_SHARE_CHANGE_REASON = (
    (PropertyShareRecord.SALE_CONTRACT, "договор купли-продажи"),
    (PropertyShareRecord.QUALIFICATION, "уточнение")
)


class PropertyShareMathOp:
    INC = 'inc'
    RED = 'red'
    TOTAL = 'total'


PROPERTY_SHARE_MATH_OP = (
    (PropertyShareMathOp.INC, "увеличение"),
    (PropertyShareMathOp.RED, "уменьшение"),
    (PropertyShareMathOp.TOTAL, "установление"),
)



class WorkerQueue(object):
    MAINTENANCE = 'maintenance'
    GENERAL = 'general'
    REQUEST_TASK = 'request_task'


WORKER_QUEUE_CHOICE = (
    (WorkerQueue.MAINTENANCE, 'Очередь обслуживания процессинговой системы'),
    (WorkerQueue.GENERAL, 'Основная очередь'),
    (WorkerQueue.REQUEST_TASK, 'Очередь разбора запросов'),
)


class PrivateDocumentsTypes:
    """
    Названия типов (какие возможно) взяты из имен классов models.passport_office
    """

    RussianPassport = 'RussianPassport'  # legacy field
    USSRPassport = 'USSRPassport'  # legacy field
    ForeignCitizenPassport = 'ForeignCitizenPassport'
    ForeignPassport = 'ForeignPassport'  # legacy field
    NavyForeignPassport = 'NavyForeignPassport'
    DiplomaticPassport = 'DiplomaticPassport'
    SailorPassport = 'SailorPassport'
    MilitaryRegistration = 'MilitaryRegistration'  # legacy field
    MilitaryRegistration_AlternateID = 'MilitaryRegistration_AlternateID'
    OfficerID = 'OfficerID'
    CertificateBirth = 'CertificateBirth'  # legacy field
    RefugeeReviewCertificate = 'RefugeeReviewCertificate'
    ResidenceID = 'ResidenceID'
    JailReleaseCerteficate = 'JailReleaseCerteficate'
    RussianSitizenTransientID = 'RussianSitizenTransientID'
    ForcedMigrantID = 'ForcedMigrantID'
    TemporaryResidencePermissionID = 'TemporaryResidencePermissionID'
    RefugeeID = 'RefugeeID'
    ForcedMigrantReviewCertificate = 'ForcedMigrantReviewCertificate'
    TemporaryAsylumCertificate = 'TemporaryAsylumCertificate'
    OtherDocuments = 'OtherDocuments'

    # Отсутствует в списке ГИСа:
    IdentificationPassport = 'IdentificationPassport'  # legacy field
    CertificatePension = 'CertificatePension'  # legacy field


PRIVATE_DOCUMENTS_TYPE_CHOICES = (
    (PrivateDocumentsTypes.RussianPassport,
     'Паспорт гражданина Российской Федерации'),  # legacy field
    (PrivateDocumentsTypes.USSRPassport, 'Паспорт гражданина СССР'),
    # legacy field
    (PrivateDocumentsTypes.ForeignCitizenPassport,
     'Паспорт гражданина иностранного государства'),
    (PrivateDocumentsTypes.ForeignPassport,
     'Общегражданский заграничный паспорт'),  # legacy field
    (PrivateDocumentsTypes.NavyForeignPassport,
     'Заграничный паспорт Министерства морского флота'),
    (PrivateDocumentsTypes.DiplomaticPassport, 'Дипломатический паспорт'),
    (PrivateDocumentsTypes.SailorPassport,
     'Паспорт моряка (удостоверение личности моряка)'),
    (PrivateDocumentsTypes.MilitaryRegistration,
     'Военный билет военнослужащего'),  # legacy field
    (PrivateDocumentsTypes.MilitaryRegistration_AlternateID,
     'Временное удостоверение, выданное взамен военного билета'),
    (PrivateDocumentsTypes.OfficerID,
     'Удостоверение личности офицера Министерства обороны Российской Федерации, Министерства внутренних дел Российской Федерации и других воинских формирований с приложением справки о прописке (регистрации) Ф-33'),
    (PrivateDocumentsTypes.CertificateBirth, 'Свидетельство о рождении'),
    # legacy field
    (PrivateDocumentsTypes.RefugeeReviewCertificate,
     'Свидетельство о рассмотрении ходатайства о признании беженцем на территории Российской Федерации по существу'),
    (PrivateDocumentsTypes.ResidenceID,
     'Вид на жительство иностранного гражданина или лица без гражданства'),
    (PrivateDocumentsTypes.JailReleaseCerteficate,
     'Справка об освобождении из мест лишения свободы'),
    (PrivateDocumentsTypes.RussianSitizenTransientID,
     'Временное удостоверение личности гражданина Российской Федерации'),
    (PrivateDocumentsTypes.ForcedMigrantID,
     'Удостоверение вынужденного переселенца'),
    (PrivateDocumentsTypes.TemporaryResidencePermissionID,
     'Разрешение на временное проживание в Российской Федерации'),
    (PrivateDocumentsTypes.RefugeeID,
     'Удостоверение беженца в Российской Федерации'),
    (PrivateDocumentsTypes.ForcedMigrantReviewCertificate,
     'Свидетельство о рассмотрении ходатайства о признании лица вынужденным переселенцем'),
    (PrivateDocumentsTypes.TemporaryAsylumCertificate,
     'Свидетельство о предоставлении временного убежища на территории Российской Федерации'),
    (PrivateDocumentsTypes.OtherDocuments,
     'Иные документы, предусмотренные законодательством Российской Федерации или признаваемые в соответствии с международным договором Российской Федерации в качестве документов, удостоверяющих личность'),

    # Отсутствует в списке ГИСа:
    (PrivateDocumentsTypes.IdentificationPassport, 'Удостоверение личности'),
    # legacy field
    (PrivateDocumentsTypes.CertificatePension, 'Пенсионное удостоверение'),
    # legacy field
)


class TenantDocument:
    BIRTH = 'birth'
    WARRIOR_OFFICER = 'warrior_officer'
    WARRIOR_OFFICER_RESERVE = 'warrior_officer_reserve'
    WARRIOR_SOLDIER = 'warrior_soldier'
    TRAVEL = 'travel'
    ALIEN_PASSPORT = 'alien_passport'
    USSR = 'ussr'
    ALIEN_BIRTH = 'alien_birth'
    ALIEN_GUEST = 'alien_guest'
    OTHER = 'other'


TENANT_DOCUMENT_TYPES = (
    (TenantDocument.BIRTH, 'Свидетельство о рождении'),
    (TenantDocument.WARRIOR_OFFICER, 'Удостоверение офицера'),
    (TenantDocument.WARRIOR_OFFICER_RESERVE, 'Военный билет офицера запаса'),
    (
        TenantDocument.WARRIOR_SOLDIER,
        'Военный билет солдата (матроса, сержанта, старшины)'
    ),
    (TenantDocument.TRAVEL, 'Загранпаспорт гражданина РФ'),
    (TenantDocument.ALIEN_PASSPORT, 'Паспорт иностранного гражданина'),
    (TenantDocument.USSR, 'Паспорт гражданина СССР'),
    (
        TenantDocument.ALIEN_BIRTH,
        'Свидетельство о рождении иностранного государства'
    ),
    (TenantDocument.ALIEN_GUEST, 'Вид на жительство'),
    (TenantDocument.OTHER, 'Иные документы'),
)


class Passport:
    RussianPassport = 'RussianPassport'
    USSRPassport = 'USSRPassport'
    ForeignPassport = 'ForeignPassport'


PASSPORT = (
    (Passport.RussianPassport, 'Паспорт гражданина России'),
    (Passport.USSRPassport, 'Паспорт гражданина СССР'),
    (Passport.ForeignPassport, 'Заграничный паспорт')
)


class PassportReasonReplacement:
    REACHE_AGE_20 = 'reach_age_20'
    REACHE_AGE_45 = 'reach_age_45'
    EXPIRY = 'expiry'
    LOSS = 'loss'


REASON_REPLACEMENT = (
    (
        PassportReasonReplacement.REACHE_AGE_20,
        "Замена в связи с достижением 20 лет"
    ),
    (
        PassportReasonReplacement.REACHE_AGE_45,
        "Замена в связи с достижением 45 лет"
    ),
    (
        PassportReasonReplacement.EXPIRY,
        "Замена в связи с истечением срока действия"
    ),
    (
        PassportReasonReplacement.LOSS,
        "Замена в связи с утратой"
    )

)


INTERCOM_STATUS_CHOICES = (
    ('urgent', 'urgent'),
    ('current', 'current'),
    ('planned', 'planned'),
    ('acceptance', 'acceptance'),
    ('prophylaxis', 'prophylaxis'),
)

LIVING_AREA_NSI_CODES_CHOICES = (
    (LivingAreaGisTypes.PRIVATE, 1),
    (LivingAreaGisTypes.COMMUNAL, 2),
    (LivingAreaGisTypes.HOSTEL, 3),
)


class PrivilegeScope(object):
    FAMILY = 'family'
    PERSON = 'person'


PRIVILEGE_SCOPES_CHOICES = (
    (PrivilegeScope.FAMILY, 'семья'),
    (PrivilegeScope.PERSON, 'льготник'),
)


class PrivilegeCalcOption(object):
    NONE = 'none'
    SOCIAL_NORMA = 'social_norma'
    CONSUMPTION_NORMA = 'consumption_norma'
    SOCIAL_CONSUMPTION_NORMA = 'social_consumption_norma'
    CONSUMPTION_NORMA_MANUAL = 'consumption_norma_manual'
    SOCIAL_CONSUMPTION_NORMA_MANUAL = 'social_consumption_norma_manual'
    PROPERTY_SHARE = 'property_share'


PRIVILEGE_CALC_OPTIONS_CHOICES = (
    (PrivilegeCalcOption.NONE, 'нет'),
    (PrivilegeCalcOption.SOCIAL_NORMA, 'социальная норма'),
    (PrivilegeCalcOption.CONSUMPTION_NORMA, 'норматив расхода'),
    (
        PrivilegeCalcOption.SOCIAL_CONSUMPTION_NORMA,
        'норматив расхода/социальная норма',
    ),
    (
        PrivilegeCalcOption.CONSUMPTION_NORMA_MANUAL,
        'норматив расхода вручную',
    ),
    (
        PrivilegeCalcOption.SOCIAL_CONSUMPTION_NORMA_MANUAL,
        'норматив расхода/социальная норма вручную',
    ),
    (PrivilegeCalcOption.PROPERTY_SHARE, 'доля собственности'),
)


class SystemPrivilege(object):
    DISABLED_17 = 'disabled_17'
    DISABLED_31 = 'disabled_31'
    DISABLED_KID_FEDERAL = 'disabled_kid_federal'
    VETERAN_14 = 'veteran_14'
    VETERAN_15 = 'veteran_15'
    VETERAN_16 = 'veteran_16'
    VETERAN_17 = 'veteran_17'
    VETERAN_18 = 'veteran_18'
    VETERAN_19 = 'veteran_19'
    VETERAN_20 = 'veteran_20'
    VETERAN_21 = 'veteran_21'
    VETERAN_23 = 'veteran_23'
    CHERNOBYL_14 = 'chernobyl_14'
    ORPHAN_1 = 'orphan_1'
    ORPHAN_2 = 'orphan_2'
    REHABILITATED = 'rehabilitated'
    REHABILITATED_DEPENDENT = 'rehabilitated_dependent'
    CONCENTRATION_CAMP = 'concentration_camp'
    HERO = 'hero'
    HERO_WORKER = 'hero_worker'
    HERO_WIDOW = 'hero_widow'

    LARGE_FAMILY = 'large_family'
    INTELLECTUAL = 'intellectual'
    LABOUR_VETERAN = 'labour_veteran'
    SOCIAL_WORKER = 'social_worker'

    DISABLED_KID = 'disabled_kid'
    DISABLED_WITH_PROPERTY = 'disabled_with_property'
    EARNER_LOST = 'earner_lost'

    MSK_LARGE_FAMILY = 'msk_large_family'
    MSK_ALONE_80 = 'msk_alone_80'
    MSK_ALONE_70 = 'msk_alone_70'
    MSK_LABOUR_VETERAN = 'msk_labour_veteran'
    MSK_REPRESSION = 'msk_repression'
    MSK_REPRESSION_OLD = 'msk_repression_old'
    MSK_DONOR = 'msk_donor'
    MSK_ALONE_850 = 'msk_alone_850'
    MSK_HERO_850_2_1 = 'msk_hero_850_2_1'
    MSK_HOUSE_ELDER = 'msk_house_elder'


SYSTEM_PRIVILEGES_CHOICES = (

    # Федеральные
    (SystemPrivilege.DISABLED_17, 'Федеральная. Закон об инвалидах. Статья 17'),
    (
        SystemPrivilege.DISABLED_31,
        'Федеральная. Закон об инвалидах. Статья 31',
    ),
    (
        SystemPrivilege.DISABLED_KID_FEDERAL,
        'Федеральная. Закон об инвалидах. Дети инвалиды',
    ),
    (SystemPrivilege.VETERAN_14, 'Федеральная. Закон о ветеранах. Статья 14'),
    (SystemPrivilege.VETERAN_15, 'Федеральная. Закон о ветеранах. Статья 15'),
    (SystemPrivilege.VETERAN_16, 'Федеральная. Закон о ветеранах. Статья 16'),
    (SystemPrivilege.VETERAN_17, 'Федеральная. Закон о ветеранах. Статья 17'),
    (SystemPrivilege.VETERAN_18, 'Федеральная. Закон о ветеранах. Статья 18'),
    (SystemPrivilege.VETERAN_19, 'Федеральная. Закон о ветеранах. Статья 19'),
    (SystemPrivilege.VETERAN_20, 'Федеральная. Закон о ветеранах. Статья 20'),
    (SystemPrivilege.VETERAN_21, 'Федеральная. Закон о ветеранах. Статья 21'),
    (SystemPrivilege.VETERAN_23, 'Федеральная. Закон о ветеранах. Статья 23'),
    (SystemPrivilege.CHERNOBYL_14,
     'Федеральная. Закон о "чернобыльцах". Статья 14'),
    (SystemPrivilege.ORPHAN_1, 'Федеральная. Сирота'),
    (SystemPrivilege.ORPHAN_2, 'Федеральная. Сирота (на иждивении)'),
    (SystemPrivilege.REHABILITATED, 'Федеральная. Реабилитированные'),
    (SystemPrivilege.REHABILITATED_DEPENDENT,
     'Федеральная. Реабилитированные (иждивенец)'),
    (SystemPrivilege.CONCENTRATION_CAMP, 'Федеральная. Узники концлагерей'),
    (SystemPrivilege.HERO, 'Федеральная. Герои РФ, СССР'),
    (SystemPrivilege.HERO_WORKER, 'Федеральная. Герои труда'),
    (SystemPrivilege.HERO_WIDOW, 'Федеральная. Вдова героя'),

    # 47 - Ленинградская область
    (SystemPrivilege.LARGE_FAMILY, 'Ленинградская обл. Многодетная семья'),
    (SystemPrivilege.INTELLECTUAL, 'Ленинградская обл. Сельский интеллигент'),
    (SystemPrivilege.LABOUR_VETERAN, 'Ленинградская обл. Ветеран труда'),
    (SystemPrivilege.SOCIAL_WORKER, 'Ленинградская обл. Социальный работник'),

    # 50 - Московская область
    (SystemPrivilege.DISABLED_KID, 'Московская обл. Дети инвалиды'),
    (SystemPrivilege.DISABLED_WITH_PROPERTY,
     'Московская обл. Инвалид (есть собственность)'),
    (SystemPrivilege.EARNER_LOST,
     'Московская обл. Потеря кормильца, дети на попечении'),

    # 77 - Москва
    (
        SystemPrivilege.MSK_LARGE_FAMILY,
        'Москва. Многодетная семья',
    ),
    (
        SystemPrivilege.MSK_ALONE_80,
        'Москва. Одиноко прожив.неработ.собственники, 80 лет. '
        'Статья 169 часть 2.1 ЖК РФ',
    ),
    (
        SystemPrivilege.MSK_ALONE_70,
        'Москва. Одиноко прожив.неработ.собственники, 70 лет. '
        'Статья 169 часть 2.1 ЖК РФ',
    ),
    (
        SystemPrivilege.MSK_LABOUR_VETERAN,
        'Москва. Ветеран труда',
    ),
    (
        SystemPrivilege.MSK_REPRESSION,
        'Москва. Жертвы политических репрессий. ПП РФ №160',
    ),
    (
        SystemPrivilege.MSK_REPRESSION_OLD,
        'Москва. Жертвы политических репрессий (пенсионер). ПП РФ №160',
    ),
    (
        SystemPrivilege.MSK_DONOR,
        'Москва. Донор (ПП Москвы № 1282-ПП)',
    ),
    (
        SystemPrivilege.MSK_ALONE_850,
        'Москва. Одиноко проживающие инвалиды/пенсионеры/семьи. '
        'ППМ от 07.12.2004 №850-ПП',
    ),
    (
        SystemPrivilege.MSK_HERO_850_2_1,
        'Москва. Герои Советского Союза, Герои Российской Федерации, '
        'Полные кавалеры ордена боевой Славы. '
        'ППМ от 07.12.2004 №850-ПП (п.2.1 Порядка)',
    ),
    (
        SystemPrivilege.MSK_HOUSE_ELDER,
        'Москва. Старший по дому, старший по подъезду. '
        'Постановление Правительства Москвы от 13 апреля 1999 г. N 328',
    ),

)


class PrivilegeTypes:
    FEDERAL = 'FederalPrivilege'
    REGION47 = 'Region47Privilege'
    REGION50 = 'Region50Privilege'
    REGION77 = 'Region77Privilege'


PRIVILEGE_TYPE_CHOICES = (
    (PrivilegeTypes.FEDERAL, 'Федеральные льготы'),
    (PrivilegeTypes.REGION47, 'региональные льготы Ленинградской области'),
    (PrivilegeTypes.REGION50, 'региональные льготы Московской области'),
    (PrivilegeTypes.REGION77, 'региональные льготы Москвы'),
)


class AreaPropertyType(object):
    PRIVATE = 'private'
    GOVERNMENT = 'government'
    MUNICIPAL = 'municipal'


PRIVILEGE_TYPES_CHOICES = (
    (AreaPropertyType.PRIVATE, 'Частная собственность'),
    (AreaPropertyType.GOVERNMENT, 'Госсобственность'),
    (AreaPropertyType.MUNICIPAL, 'Муниципальная собственность'),
)


class AreaCommunicationsType(object):
    COLD_WATER = 'cold_water'
    HOT_WATER = 'hot_water'
    ELECTRICITY = 'electricity'
    HEAT = 'heat'
    GAS = 'gas'
    WASTE = 'waste'


AREA_COMMUNICATIONS_CHOICES = (
    (AreaCommunicationsType.COLD_WATER, 'ХВС'),
    (AreaCommunicationsType.HOT_WATER, 'ГВС'),
    (AreaCommunicationsType.ELECTRICITY, 'Электроэнергия'),
    (AreaCommunicationsType.HEAT, 'Отопление'),
    (AreaCommunicationsType.GAS, 'Газ'),
    # (AreaCommunicationsType.WASTE, 'Сточные воды'),
)


class AreaIntercomType(object):
    NONE = 'none'
    UNLOCK = 'unlock'
    INTERCOM = 'intercom'


AREA_INTERCOM_CHOICES = (
    (AreaIntercomType.NONE, 'нет'),
    (AreaIntercomType.UNLOCK, 'только замок'),
    (AreaIntercomType.INTERCOM, 'домофон'),
)


class ServicesGroup(object):
    MAINTENANCE = 0
    COMMUNAL_SERVICES = 1
    OTHER = 2
    CAPITAL_REPAIR = 3
    COMMUNAL_SERVICES_FOR_MAINTENANCE = 4
    PARKING_MAINTENANCE = 10
    UNKNOWN = 12


SERVICES_GROUPS_CHOICES = (
    (ServicesGroup.MAINTENANCE, 'Жилищные услуги'),
    (ServicesGroup.COMMUNAL_SERVICES, 'Коммунальные услуги'),
    (ServicesGroup.OTHER, 'Прочие'),
    (ServicesGroup.CAPITAL_REPAIR, 'Взносы на капитальный ремонт'),
    (ServicesGroup.COMMUNAL_SERVICES_FOR_MAINTENANCE,
     'Коммунальные услуги на СОИ'),
    (ServicesGroup.PARKING_MAINTENANCE, 'Содержание паркинга'),
    (ServicesGroup.UNKNOWN, '')
)
SERVICES_GROUPS_CHOICES_DICT = get_constant_dict(SERVICES_GROUPS_CHOICES)


class FilterCode(object):
    NO_CODE = ''
    HOUSE_ACCOUNTS_ALL = 'house_accounts_all'


FILTER_CODES_CHOICES = (
    (FilterCode.NO_CODE, ''),
    (FilterCode.HOUSE_ACCOUNTS_ALL, 'Все ЛС дома'),
)


class FilterPurpose(object):
    NO_PURPOSE = ''
    ACCRUAL_DOC_VIEW = 'accrual_doc_view'
    ACCRUAL_DOC_CREATE = 'accrual_doc_create'
    CIPCA = 'cipca'


FILTER_PURPOSES_CHOICES = (
    (FilterPurpose.NO_PURPOSE, ''),
    (FilterPurpose.ACCRUAL_DOC_VIEW, 'Документ начислений. Просмотр данных'),
    (FilterPurpose.ACCRUAL_DOC_CREATE, 'Документ начислений. Расчёт'),
    (FilterPurpose.CIPCA, 'Расчёт'),
)


class FilterPreparedDataType(object):
    BALANCE = 'balance'


FILTER_PREPARED_DATA_TYPES = (
    (FilterPreparedDataType.BALANCE, 'Сальдо'),
)


class ReadingsCreator(object):
    SYSTEM = 'system'
    AUTOMATIC = 'automatic'
    WORKER = 'worker'
    TENANT = 'tenant'
    REGISTRY = 'registry'
    MODULE_1C = 'module_1c'
    GIS_TENANT = 'gis_tenant'
    GIS_SYSTEM = 'gis_system'


READINGS_CREATORS_CHOICES = (
    (ReadingsCreator.SYSTEM, 'Система'),
    (ReadingsCreator.AUTOMATIC, 'Автоматизация'),
    (ReadingsCreator.WORKER, 'Сотрудник'),
    (ReadingsCreator.TENANT, 'Житель'),
    (ReadingsCreator.REGISTRY, 'Реестр'),
    (ReadingsCreator.MODULE_1C, 'Модуль 1С'),
    ('import_1c', 'Импорт 1С (УСТАРЕВШЕЕ)'),  # TODO подлежит удалению
    (ReadingsCreator.GIS_TENANT, 'ЛК ГИС ЖКХ'),
    (ReadingsCreator.GIS_SYSTEM, 'ГИС ЖКХ'),
)


class StoveType(object):
    ELECTRIC = 'electric'
    GAS = 'gas'
    NONE = None


STOVE_TYPE_CHOICES = (
    (StoveType.ELECTRIC, 'электрическая'),
    (StoveType.GAS, 'газовая'),
    (StoveType.NONE, 'не установлена'),
)


class GprsOperator(object):
    MEGAFON = 'megafon'
    MTS = 'mts'


GPRS_OPERATORS_CHOICES = (
    (GprsOperator.MEGAFON, 'Мегафон'),
    (GprsOperator.MTS, 'МТС'),
)


class GprsAdapterModel(object):
    ASSV_030 = 'accb-030'
    IRZ_ATM_21 = 'irz_atm_21'


GPRS_ADAPTER_MODELS_CHOICES = (
    (GprsAdapterModel.ASSV_030, 'АССВ-030'),
    (GprsAdapterModel.IRZ_ATM_21, 'IRZ ATM21'),
)


class SystemWorkerPosition(object):
    CH1 = 'ch1'
    CH2 = 'ch2'
    CH3 = 'ch3'
    ACC1 = 'acc1'


SYSTEM_WORKERS_POSITIONS_CHOICES = (
    (SystemWorkerPosition.CH1, 'Председатель правления'),
    (SystemWorkerPosition.CH2, 'Генеральный директор'),
    (SystemWorkerPosition.CH3, 'Директор'),
    (SystemWorkerPosition.ACC1, 'Главный бухгалтер'),
)


class TicketAccessLevelCode(object):
    BASIC = 'basic'
    ALL = 'all'
    BY_DEPT = 'by_dept'


TICKET_ACCESS_LEVEL = (
    (TicketAccessLevelCode.BASIC, 'Базовый'),
    (TicketAccessLevelCode.ALL, 'Полный'),
    (TicketAccessLevelCode.BY_DEPT, 'По отделам'),
)


class TicketSubject(object):
    WORKER = 'worker'
    AREA = 'area'
    TENANT = 'tenant'
    REQUESTS = 'requests'
    METER = 'meter'
    ACCRUAL = 'accrual'
    PENALTY = 'penalty'
    ONLINE_CASH = 'online_cash'
    REGISTRY = 'registry'
    REPORT = 'report'
    QUESTION = 'question'
    OTHER = 'other'


TICKET_SUBJECT_CHOICES = (
    (TicketSubject.WORKER, 'Добавить/убрать сотрудника'),
    (TicketSubject.AREA, 'Добавить/убрать помещение'),
    (TicketSubject.TENANT, 'Изменения по жильцам'),
    (TicketSubject.REQUESTS, 'Журнал заявок/АДС'),
    (TicketSubject.METER, 'Счетчики'),
    (TicketSubject.ACCRUAL, 'Начисления и расчет'),
    (TicketSubject.PENALTY, 'Пени'),
    (TicketSubject.ONLINE_CASH, 'Онлайн-касса/фискализация'),
    (TicketSubject.REGISTRY, 'Реестр/выписки'),
    (TicketSubject.REPORT, 'Отчетность'),
    (TicketSubject.QUESTION, 'Вопросы по работе с системой'),
    (TicketSubject.OTHER, 'Другое'),
)


class TicketStatus(object):
    NEW = 'new'
    CLOSED = 'closed'
    ACCEPTED = 'accepted'
    DELIVERED = 'delivered'


TICKET_STATUS_CHOICES = (
    (TicketStatus.NEW, 'Принято к рассмотрению'),
    (TicketStatus.CLOSED, 'Тикет закрыт'),
    (TicketStatus.ACCEPTED, 'Тикет принят на исполнение работником'),
    (TicketStatus.DELIVERED, 'доставлено'),
)


class SupportTicketStatus(object):
    NEW = 'new'
    AWAITING = 'awaiting'
    PERFORMED = 'performed'
    CLOSED = 'closed'


SUPPORT_TICKET_STATUS_CHOICES = (
    (SupportTicketStatus.NEW, 'Принято к рассмотрению'),
    (SupportTicketStatus.AWAITING, 'Ждет ответа'),
    (SupportTicketStatus.PERFORMED, 'Ответ получен'),
    (SupportTicketStatus.CLOSED, 'Закрыт'),
)
SUPPORT_TICKET_STATUSES_DICT = {
    e[0]: e[1] for e in SUPPORT_TICKET_STATUS_CHOICES
}


class TicketType(object):
    STATEMENT = 'statement'
    NOTIFICATION = 'notification'
    LETTER = 'letter'
    CLAIM = 'claim'
    COMPLAINT = 'complaint'
    INFO = 'info'
    ORDER = 'order'
    MEMORANDUM = 'memorandum'
    OFFER = 'offer'
    GRATITUDE = 'gratitude'

    # SupportTicket
    TECH = 'tech'
    PAYMENT_CENTER = 'paycent'
    COMMON = 'common'
    LEGAL = 'legal'
    CABINET = 'cabinet'
    INTRODUCTION = 'introduction'
    GIS = 'gis'
    BOOKKEEPING = 'bookkeeping'
    BENEFICIARIES = 'beneficiaries'
    RECEIPT_TEMPLATE = 'receipt_template'
    PRINT_CONFIRMATION = 'print_confirmation'


TICKET_TYPE_CHOICES = (
    (TicketType.STATEMENT, 'заявление'),
    (TicketType.NOTIFICATION, 'уведомление'),
    (TicketType.LETTER, 'письмо'),
    (TicketType.CLAIM, 'претензия'),
    (TicketType.COMPLAINT, 'жалоба'),
    (TicketType.INFO, 'информационное сообщение'),
    (TicketType.ORDER, 'поручение'),
    (TicketType.MEMORANDUM, 'докладная записка'),
    (TicketType.OFFER, 'предложение'),
    (TicketType.GRATITUDE, 'благодарность'),

    (TicketType.TECH, 'Техническая поддержка'),
    (TicketType.PAYMENT_CENTER, 'Расчетный центр'),
    (TicketType.COMMON, 'Общие вопросы ЖКХ'),
    (TicketType.LEGAL, 'Юридические вопросы'),
    (TicketType.CABINET, 'Личные кабинеты'),
    (TicketType.INTRODUCTION, 'Внедрение'),
    (TicketType.GIS, 'Вопросы по ГИС'),
    (TicketType.BOOKKEEPING, 'Бухгалтерия'),
    (TicketType.BENEFICIARIES, 'Льготники'),
    (TicketType.RECEIPT_TEMPLATE, 'Шаблон квитанции'),
    (TicketType.PRINT_CONFIRMATION, 'Подтверждение печати'),
)

SUPPORT_TICKET_TYPE_CHOICES = (
    (TicketType.TECH, 'Техническая поддержка'),
    (TicketType.PAYMENT_CENTER, 'Расчетный центр'),
    (TicketType.COMMON, 'Общие вопросы ЖКХ'),
    (TicketType.LEGAL, 'Юридические вопросы'),
    (TicketType.CABINET, 'Личные кабинеты'),
    (TicketType.INTRODUCTION, 'Внедрение'),
    (TicketType.GIS, 'Вопросы по ГИС'),
    (TicketType.BOOKKEEPING, 'Бухгалтерия'),
    (TicketType.BENEFICIARIES, 'Льготники'),
    (TicketType.RECEIPT_TEMPLATE, 'Шаблон квитанции'),
    (TicketType.PRINT_CONFIRMATION, 'Подтверждение печати'),
)
SUPPORT_TICKET_TYPES_DICT = {
    e[0]: e[1] for e in SUPPORT_TICKET_TYPE_CHOICES
}
TENANT_TICKET_TYPE_CHOICES = (
    (TicketType.STATEMENT, 'заявление'),
    (TicketType.NOTIFICATION, 'уведомление'),
    (TicketType.LETTER, 'письмо'),
    (TicketType.CLAIM, 'претензия'),
    (TicketType.COMPLAINT, 'жалоба'),
    (TicketType.OFFER, 'предложение'),
    (TicketType.GRATITUDE, 'благодарность'),
)


class DreamkasTaxMode:
    DEFAULT = 'DEFAULT'
    SIMPLE = 'SIMPLE'
    SIMPLE_WO = 'SIMPLE_WO'
    ENVD = 'ENVD'
    AGRICULT = 'AGRICULT'
    PATENT = 'PATENT'


DREAMKAS_TAX_MODES_CHOICES = (
    (DreamkasTaxMode.DEFAULT, 'Общая'),
    (DreamkasTaxMode.SIMPLE, 'Упрощенная доход'),
    (DreamkasTaxMode.SIMPLE_WO, 'Упрощенная доход минус расход'),
    (DreamkasTaxMode.ENVD, 'Единый налог на вмененный доход'),
    (DreamkasTaxMode.AGRICULT, 'Единый сельскохозяйственный'),
    (DreamkasTaxMode.PATENT, 'Патентная система налогообложения'),
)


class DreamkasTaxNDS:
    NDS_NO_TAX = 'NDS_NO_TAX'
    NDS_0 = 'NDS_0'
    NDS_10 = 'NDS_10'
    NDS_18 = 'NDS_18'
    NDS_20 = 'NDS_20'
    NDS_10_CALCULATED = 'NDS_10_CALCULATED'
    NDS_18_CALCULATED = 'NDS_18_CALCULATED'
    NDS_20_CALCULATED = 'NDS_20_CALCULATED'


DREAMKAS_TAX_NDS_CHOICES = (
    (DreamkasTaxNDS.NDS_NO_TAX, 'Без НДС'),
    (DreamkasTaxNDS.NDS_0, 'НДС 0'),
    (DreamkasTaxNDS.NDS_10, 'НДС 10'),
    (DreamkasTaxNDS.NDS_18, 'НДС 18'),
    (DreamkasTaxNDS.NDS_20, 'НДС 20'),
    (DreamkasTaxNDS.NDS_10_CALCULATED, 'НДС 10/110'),
    (DreamkasTaxNDS.NDS_18_CALCULATED, 'НДС 18/118'),
    (DreamkasTaxNDS.NDS_20_CALCULATED, 'НДС 20/120'),
)


class PaymentDocTypes:
    ManualDoc = 'ManualDoc'
    MemorialOrderDoc = 'MemorialOrderDoc'
    BankOrderDoc = 'BankOrderDoc'
    CollectionOrderDoc = 'CollectionOrderDoc'
    CashReceiptDoc = 'CashReceiptDoc'
    RegistryDoc = 'RegistryDoc'
    StornoDoc = 'StornoDoc'


PAYMENT_DOC_TYPES_CHOICES = (
    (PaymentDocTypes.ManualDoc, 'Платежное поручение'),
    (PaymentDocTypes.MemorialOrderDoc, 'Мемориальный ордер'),
    (PaymentDocTypes.BankOrderDoc, 'Банковский ордер'),
    (PaymentDocTypes.CollectionOrderDoc, 'Инкассовое поручение'),
    (PaymentDocTypes.CashReceiptDoc, 'Приходный кассовый ордер'),
    (PaymentDocTypes.RegistryDoc, 'Реестр'),
    (PaymentDocTypes.StornoDoc, 'Сторно платежа'),
)


class OnlineCashType:
    DREAMKAS = 'dreamkas'


ONLINE_CASH_TYPES_CHOICES = (
    (OnlineCashType.DREAMKAS, 'Дримкас'),
)


class MoscowGCJSExportType:
    DEFAULT = 'default'
    LOSSES = 'losses'


MOSCOW_GCJS_EXPORT_TYPES_CHOICES = (
    (MoscowGCJSExportType.DEFAULT, 'Начисления'),
    (MoscowGCJSExportType.LOSSES, 'Выпадающие доходы'),
)


class GeneralValueType(object):
    MANUAL_OPERATION = 'manual_operation'
    BANK_STATEMENT = 'bank_statement'
    SERVICE_IMPLEMENTATION = 'service_implementation'


GENERAL_VALUE_TYPE_CHOICES = (
    (GeneralValueType.MANUAL_OPERATION, 'Ручная операция'),
    (GeneralValueType.BANK_STATEMENT, 'Выписка банка'),
    (GeneralValueType.SERVICE_IMPLEMENTATION, 'Реализация услуг'),
)


class MonthType(object):
    PREVIOUS = -1
    CURRENT = 0
    NEXT = 1


MONTH_TYPE_CHOICES = (
    (MonthType.PREVIOUS, 'предыдущий'),
    (MonthType.CURRENT, 'текущий'),
    (MonthType.NEXT, 'следующий'),
)


class PublicCommunalServicesRecalcType:
    NONE = 'none'
    BY_MONEY = 'money'
    BY_CONSUMPTION = 'consumption'


PUBLIC_COMMUNAL_SERVICES_RECALC_TYPE_CHOICES = (
    (PublicCommunalServicesRecalcType.NONE, 'автоматически не считать'),
    (PublicCommunalServicesRecalcType.BY_MONEY, 'по сумме начисления'),
    (PublicCommunalServicesRecalcType.BY_CONSUMPTION, 'по расходу ресурса'),
)
PUBLIC_COMMUNAL_SERVICES_RECALC_TYPE_MENU_CHOICES = (
    (PublicCommunalServicesRecalcType.BY_MONEY, 'по сумме начисления'),
    (PublicCommunalServicesRecalcType.BY_CONSUMPTION, 'по расходу ресурса'),
)


class AreaTotalChangeReason(object):
    REPLANNING = 'replanning'
    CORRECTION = 'correction'


AREA_TOTAL_CHANGE_REASON_CHOICES = (
    (AreaTotalChangeReason.REPLANNING, 'перепланировка'),
    (AreaTotalChangeReason.CORRECTION, 'уточнение'),
)


class AreaType(object):
    ALL = 'All'
    LIVING_AREA = 'LivingArea'
    NOT_LIVING_AREA = 'NotLivingArea'
    PARKING_AREA = 'ParkingArea'


AREA_TYPE_CHOICES = (
    (AreaType.ALL, 'Все помещения'),
    (AreaType.LIVING_AREA, 'Жилое помещение'),
    (AreaType.NOT_LIVING_AREA, 'Нежилое помещение'),
    (AreaType.PARKING_AREA, 'Паркинг'),
)

AREA_TYPE_ACCRUAL_SETTINGS = (
    ('LivingArea', 'шаблон квитанции жилых помещений'),
    ('NotLivingArea', 'шаблон квитанции нежилых помещений'),
    ('ParkingArea', 'шаблон квитанции паркингов'),
)


class PaymentDocSource:
    MANUAL = 'Manual'
    MAIL = 'MailRegistry'
    MANUAL_REGISTRY = 'ManualRegistryTask'
    BANK_STATEMENT = 'BankStatement'
    SBER = 'SbolInRegistry'
    EXCHANGE_1C_DEPRECATED = 'Exchange1C'
    EXCHANGE_1C = '1C'


# Места создания PaymentDoc
PAYMENT_DOC_PARENTS_CHOICES = (
    PaymentDocSource.MANUAL,  # в ручную
    PaymentDocSource.MAIL,  # с почты
    PaymentDocSource.MANUAL_REGISTRY,  # с загрузки реестра
    PaymentDocSource.BANK_STATEMENT,  # с загрузки банковской выписки
    PaymentDocSource.SBER,  # с УПШ
    PaymentDocSource.EXCHANGE_1C_DEPRECATED,  # загружено из 1С (устаревшее)
    PaymentDocSource.EXCHANGE_1C,  # загружено из 1С
)


class TenantType:
    PRIVATE_TENANT = 'PrivateTenant'
    LEGAL_TENANT = 'LegalTenant'


TENANT_TYPES_CHOICES = (
    (TenantType.PRIVATE_TENANT, 'Физическое лицо'),
    (TenantType.LEGAL_TENANT, 'Юридическое лицо'),
)


class ProviderTicketRate:
    """Частота обращений от конторы"""

    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'


PROVIDER_TICKET_RATES_CHOICES = (
    (ProviderTicketRate.LOW, 'Мало обращений'),
    (ProviderTicketRate.MEDIUM, 'Средне обращений'),
    (ProviderTicketRate.HIGH, 'Много обращений'),
)


class Terminal(object):
    NOT_EXISTS_BUT_REQUIRED = 'not_exists_but_required'
    NOT_EXISTS_AND_NOT_REQUIRED = 'not_exists_and_not_required'
    TERMINAL_PSKB = 'terminal_PSKB'
    QIWI = 'qiwi'
    COMEPAY = 'comepay'
    MOBILE_CARD = 'mobile_card'
    TERMINAL_BRIS = 'terminal_bris'
    OTHER = 'other'
    SBERBANK = 'sberbank'
    PETRO = 'petro'
    SPRINT = 'sprint'
    PSKB = 'PSKB'
    URALSIB = 'uralsib'
    OTKRITIE = 'otkritie'
    BRIS = 'bris'
    ALEXANDROVSKII = 'alexandrovskii'


TERMINAL = (
    (Terminal.NOT_EXISTS_BUT_REQUIRED, "Не установлен, но нужен"),
    (Terminal.NOT_EXISTS_AND_NOT_REQUIRED, "Не установлен и не нужен"),
    (Terminal.TERMINAL_PSKB, "терминал ПСКБ"),
    (Terminal.QIWI, "Киви"),
    (Terminal.COMEPAY, "Кампей"),
    (Terminal.MOBILE_CARD, "Мобильная карта"),
    (Terminal.TERMINAL_BRIS, "терминал БРИС"),
    (Terminal.OTHER, "Другой"),
    (Terminal.SBERBANK, "Сбербанк"),
    (Terminal.PETRO, "Петроэлектросбыт"),
    (Terminal.SPRINT, "Спринт"),
    (Terminal.PSKB, "ПСКБ"),
    (Terminal.URALSIB, "УралСиб"),
    (Terminal.OTKRITIE, "Открытие"),
    (Terminal.BRIS, "БРИС"),
    (Terminal.ALEXANDROVSKII, "Александровский"),
)


class Mail(object):
    POP3 = "pop3"
    STMP = "smtp"


MAIL = (
    (Mail.POP3, "POP3"),
    (Mail.STMP, "STMP")
)


class Layout(object):
    PORTRAIT = 'portrait'
    LANDSCAPE = 'landscape'


LAYOUT = (
    (Layout.LANDSCAPE, "landscape"),
    (Layout.PORTRAIT, "portrait"),
)


class TabProvider(object):
    SECURED_TAB = 'SecuredTab'
    PUBLIC_TAB = 'PublicTab'
    ADMIN_TAB = 'AdminTab'


TAB_PROVIDER = (
    (TabProvider.ADMIN_TAB, "Административная"),
    (TabProvider.PUBLIC_TAB, "Общедоступная"),
    (TabProvider.SECURED_TAB, "Защищенная"),
)


class Service(object):
    C300_MANAGMENT = 'c300_managment'
    C300_OPERATION = 'c300_operation'
    C300_CONSRACTOR = 'c300_consractor'
    PRINT_RECIEPTS = 'print_reciepts'
    ZHSK_PROF = 'zhsk_prof'
    C300_MANAGMENT_OPERATION = 'c300_managment_operation'
    IP_PHONE = 'ip_phone'
    TERMINAL = 'terminal'
    NO_SERVICES = 'no_services'


SERVICE = (
    (Service.C300_MANAGMENT, "С300-управление"),
    (Service.C300_OPERATION, "С300-эксплуатация"),
    (Service.C300_CONSRACTOR, "С300-подрядчик"),
    (Service.PRINT_RECIEPTS, "Печать квитанций"),
    (Service.ZHSK_PROF, "ЖСК-проф - С300"),
    (Service.C300_MANAGMENT_OPERATION, "С300-эксплуатация - С300-управление"),
    (Service.IP_PHONE, "IP-телефония"),
    (Service.TERMINAL, "Терминал"),
    (Service.NO_SERVICES, "Нет услуг для продажи"),
)


class Sign(object):
    LARGE = 'large'
    WORKS_WITH_SOLARIS = 'works_with_solaris'
    EX_CLIENT = 'ex_client'
    RSO = 'rso'
    RKTS = 'rkts'
    LT100 = 'lt100'
    GT100_LT300 = 'gt100_lt300'
    GT300_LT500 = 'gt300_lt500'
    GT500 = 'gt500'
    AGGRESSIVE = 'aggressive'
    LOYAL = 'loyal'
    INDECISIVE = 'indecisive'
    GOT_LICENCE_NO_HOUSES = 'got_licence_no_houses'
    ONLINE_CASH = 'online_cash'


SIGN = (
    (Sign.LARGE, "Крупный"),
    (Sign.WORKS_WITH_SOLARIS, "Партнер"),
    (Sign.EX_CLIENT, "Бывший клиент"),
    (Sign.RSO, "РСО"),
    (Sign.RKTS, "РКЦ"),
    (Sign.LT100, "Менее 100 ЛС"),
    (Sign.GT100_LT300, "100 - 300 ЛС"),
    (Sign.GT300_LT500, "300 - 500 ЛС"),
    (Sign.GT500, "Более 500 ЛС"),
    (Sign.AGGRESSIVE, "Агрессивный"),
    (Sign.LOYAL, "Лояльный"),
    (Sign.INDECISIVE, "Нерешительный"),
    (Sign.GOT_LICENCE_NO_HOUSES, "Есть лицензия, нет домов"),
    (Sign.ONLINE_CASH, "Онлайн касса"),
)


class Telephone(object):
    CELL = 'cell'
    WORK = 'work'
    DISPATCHER = 'dispatcher'
    HOME = 'home'
    FAX = 'fax'


TELEPHONE = (
    (Telephone.CELL, 'мобильный'),
    (Telephone.DISPATCHER, 'диспетчерский'),
    (Telephone.HOME, 'домашний'),
    (Telephone.WORK, 'рабочий'),
    (Telephone.FAX, 'факс'),
)


class SMSProvider(object):
    NONE = 'none'
    IQSMS = 'iqsms'
    STREAM = 'stream'


SMS_PROVIDER = (
    (SMSProvider.NONE, 'нет'),
    (SMSProvider.IQSMS, 'iqsms'),
    (SMSProvider.STREAM, 'stream-telecom'),
)


class ProcessingSource(object):
    TRMN = 'trmn'
    CBNT = 'cbnt'


PROCESSING_SOURCES_CHOICES = (
    (ProcessingSource.TRMN, "Терминал"),
    (ProcessingSource.CBNT, "Личный кабинет"),
)


class ProcessingType(object):
    PSKB = 'pskb'
    MCARD = 'mcard'
    OTKRITIE = 'otkritie'
    ELECSNET = 'elecsnet'


PROCESSING_TYPE_USERS = {
    'openbank': ProcessingType.OTKRITIE,
    'elecsnet': ProcessingType.ELECSNET,
}

PROCESSING_TYPES_CHOICES = (
    (ProcessingType.MCARD, 'Мобильная карта'),
    (ProcessingType.PSKB, 'ПСКБ'),
    (ProcessingType.OTKRITIE, 'Открытие'),
    (ProcessingType.ELECSNET, 'Элекснет')
)


class SberRegistryNameFormat(object):
    format1 = '1'
    format2 = '2'


SBER_REGISTRY_NAME_CHOICES = (
    (SberRegistryNameFormat.format1, 'По умолчанию (КОД УСЛУГИ_ИНН_Р/С_хххх)'),
    (SberRegistryNameFormat.format2, 'Формат (ИНН_Р/СЧЕТ_КОД УСЛУГИ_хххххх)')
)


class AgreementSettings:
    RULE_354 = 'rule_354'
    ADD_REQUEST = 'add_request'
    ADD_TICKET = 'add_ticket'


Agreement = (
    (AgreementSettings.RULE_354, 'с постановлением №354 ознакомлен'),
    (AgreementSettings.ADD_REQUEST, 'согласен с правилами подачи заявок'),
    (AgreementSettings.ADD_TICKET ,'согласен с правилами подачи обращений')
)


class GisDaySelection:  # TODO gis.models.choices
    DAY_1 = 1
    DAY_2 = 2
    DAY_3 = 3
    DAY_4 = 4
    DAY_5 = 5
    DAY_6 = 6
    DAY_7 = 7
    DAY_8 = 8
    DAY_9 = 9
    DAY_10 = 10
    DAY_11 = 11
    DAY_12 = 12
    DAY_13 = 13
    DAY_14 = 14
    DAY_15 = 15
    DAY_16 = 16
    DAY_17 = 17
    DAY_18 = 18
    DAY_19 = 19
    DAY_20 = 20
    DAY_21 = 21
    DAY_22 = 22
    DAY_23 = 23
    DAY_24 = 24
    DAY_25 = 25
    DAY_26 = 26
    DAY_27 = 27
    DAY_28 = 28
    DAY_29 = 29
    DAY_30 = 30
    DAY_31 = 31
    DAY_LAST = 99

    NEXT_MONTH = 100
    NEXT_1 = NEXT_MONTH + DAY_1
    NEXT_2 = NEXT_MONTH + DAY_2
    NEXT_3 = NEXT_MONTH + DAY_3
    NEXT_4 = NEXT_MONTH + DAY_4
    NEXT_5 = NEXT_MONTH + DAY_5
    NEXT_6 = NEXT_MONTH + DAY_6
    NEXT_7 = NEXT_MONTH + DAY_7
    NEXT_8 = NEXT_MONTH + DAY_8
    NEXT_9 = NEXT_MONTH + DAY_9
    NEXT_10 = NEXT_MONTH + DAY_10
    NEXT_11 = NEXT_MONTH + DAY_11
    NEXT_12 = NEXT_MONTH + DAY_12
    NEXT_13 = NEXT_MONTH + DAY_13
    NEXT_14 = NEXT_MONTH + DAY_14
    NEXT_15 = NEXT_MONTH + DAY_15
    NEXT_16 = NEXT_MONTH + DAY_16
    NEXT_17 = NEXT_MONTH + DAY_17
    NEXT_18 = NEXT_MONTH + DAY_18
    NEXT_19 = NEXT_MONTH + DAY_19
    NEXT_20 = NEXT_MONTH + DAY_20
    NEXT_21 = NEXT_MONTH + DAY_21
    NEXT_22 = NEXT_MONTH + DAY_22
    NEXT_23 = NEXT_MONTH + DAY_23
    NEXT_24 = NEXT_MONTH + DAY_24
    NEXT_25 = NEXT_MONTH + DAY_25
    NEXT_26 = NEXT_MONTH + DAY_26
    NEXT_27 = NEXT_MONTH + DAY_27
    NEXT_28 = NEXT_MONTH + DAY_28
    NEXT_29 = NEXT_MONTH + DAY_29
    NEXT_30 = NEXT_MONTH + DAY_30
    NEXT_31 = NEXT_MONTH + DAY_31
    NEXT_LAST = NEXT_MONTH + DAY_LAST


GIS_DAY_SELECTION = (
    (GisDaySelection.DAY_1, '1 день мес.'),
    (GisDaySelection.DAY_2, '2 день мес.'),
    (GisDaySelection.DAY_3, '3 день мес.'),
    (GisDaySelection.DAY_4, '4 день мес.'),
    (GisDaySelection.DAY_5, '5 день мес.'),
    (GisDaySelection.DAY_6, '6 день мес.'),
    (GisDaySelection.DAY_7, '7 день мес.'),
    (GisDaySelection.DAY_8, '8 день мес.'),
    (GisDaySelection.DAY_9, '9 день мес.'),
    (GisDaySelection.DAY_10, '10 день мес.'),
    (GisDaySelection.DAY_11, '11 день мес.'),
    (GisDaySelection.DAY_12, '12 день мес.'),
    (GisDaySelection.DAY_13, '13 день мес.'),
    (GisDaySelection.DAY_14, '14 день мес.'),
    (GisDaySelection.DAY_15, '15 день мес.'),
    (GisDaySelection.DAY_16, '16 день мес.'),
    (GisDaySelection.DAY_17, '17 день мес.'),
    (GisDaySelection.DAY_18, '18 день мес.'),
    (GisDaySelection.DAY_19, '19 день мес.'),
    (GisDaySelection.DAY_20, '20 день мес.'),
    (GisDaySelection.DAY_21, '21 день мес.'),
    (GisDaySelection.DAY_22, '22 день мес.'),
    (GisDaySelection.DAY_23, '23 день мес.'),
    (GisDaySelection.DAY_24, '24 день мес.'),
    (GisDaySelection.DAY_25, '25 день мес.'),
    (GisDaySelection.DAY_26, '26 день мес.'),
    (GisDaySelection.DAY_27, '27 день мес.'),
    (GisDaySelection.DAY_28, '28 день мес.'),
    (GisDaySelection.DAY_29, '29 день мес.'),
    (GisDaySelection.DAY_30, '30 день мес.'),
    (GisDaySelection.DAY_31, '31 день мес.'),
    (GisDaySelection.DAY_LAST, 'Посл. день мес.'),
    (GisDaySelection.NEXT_1, '1 след. мес.'),
    (GisDaySelection.NEXT_2, '2 след. мес.'),
    (GisDaySelection.NEXT_3, '3 след. мес.'),
    (GisDaySelection.NEXT_4, '4 след. мес.'),
    (GisDaySelection.NEXT_5, '5 след. мес.'),
    (GisDaySelection.NEXT_6, '6 след. мес.'),
    (GisDaySelection.NEXT_7, '7 след. мес.'),
    (GisDaySelection.NEXT_8, '8 след. мес.'),
    (GisDaySelection.NEXT_9, '9 след. мес.'),
    (GisDaySelection.NEXT_10, '10 след. мес.'),
    (GisDaySelection.NEXT_11, '11 след. мес.'),
    (GisDaySelection.NEXT_12, '12 след. мес.'),
    (GisDaySelection.NEXT_13, '13 след. мес.'),
    (GisDaySelection.NEXT_14, '14 след. мес.'),
    (GisDaySelection.NEXT_15, '15 след. мес.'),
    (GisDaySelection.NEXT_16, '16 след. мес.'),
    (GisDaySelection.NEXT_17, '17 след. мес.'),
    (GisDaySelection.NEXT_18, '18 след. мес.'),
    (GisDaySelection.NEXT_19, '19 след. мес.'),
    (GisDaySelection.NEXT_20, '20 след. мес.'),
    (GisDaySelection.NEXT_21, '21 след. мес.'),
    (GisDaySelection.NEXT_22, '22 след. мес.'),
    (GisDaySelection.NEXT_23, '23 след. мес.'),
    (GisDaySelection.NEXT_24, '24 след. мес.'),
    (GisDaySelection.NEXT_25, '25 след. мес.'),
    (GisDaySelection.NEXT_26, '26 след. мес.'),
    (GisDaySelection.NEXT_27, '27 след. мес.'),
    (GisDaySelection.NEXT_28, '28 след. мес.'),
    (GisDaySelection.NEXT_29, '29 след. мес.'),
    (GisDaySelection.NEXT_30, '30 след. мес.'),
    (GisDaySelection.NEXT_31, '31 след. мес.'),
    (GisDaySelection.NEXT_LAST, 'Посл. след. мес.'),
)
