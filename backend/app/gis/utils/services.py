from typing import Optional

from bson import ObjectId

from processing.models.billing.provider.main import Provider, BankProvider
from processing.models.billing.provider.embeddeds import BankAccount, \
    BicEmbedded

from processing.models.billing.settings import Settings

from processing.models.billing.service_type import ServiceType
from processing.models.billing.tariff_plan import TariffPlan


TARIFF_GROUP_NSI_CODE = {  # data_producers/report/splitting_payments.py
    0: 50,  # Жилищные услуги ~ 50.1:
    # Содержание общего имущества, Содержание придомовой территории,
    # Управление МКД, Административно-Управленческие Расходы,
    # Текущий ремонт, Вывоз мусора, Уборка лестничных клеток,
    # Обслуживание лифта / мусоропровода / ПЗУ / систем ГС / ПУ ТЭ
    1: 51,  # Коммунальные услуги:
    # Холодная вода, Горячая вода, Водоотведение, Отопление
    2: 1,  # Дополнительные услуги:
    # Радио, Телевидение (кабельное), Услуги банка / РЦ / ВЦ и т.п.
    3: None,  # взносы на капитальный ремонт
    4: 337,  # Вид комм. ресурса на СОИ (главный комм. ресурс):
    # Электроэнергия день (общедомовые нужды),
    # Электроэнергия ночь (общедомовые нужды)
    10: 50,  # содержание паркинга
    12: 1,  # TODO другое?!
    69: None,  # пени и авансовый платеж
}  # group : nsi

MAINTENANCE_ROOT_CODE = 'maintenance'

COMMUNAL_ROOT_CODE = 'communal_services'

ADDITIONAL_EXCEPTIONS = ['administrative']  # жилищ. услуги без предка (НЕ доп.)

INDIVIDUAL_SERVICE_CODES = {
    'heat_individual', 'heating_water_individual',
    'water_individual', 'waste_water_individual',
    'gas_individual', 'electricity_individual',
    'hot_water_individual',
}

PUBLIC_SERVICE_CODES = {
    'heat_public', 'heating_water_public',
    'water_public', 'waste_water_public',
    'gas_public', 'electricity_public',
    'hot_water_public',
}

MULTI_PARENT_SERVICES = {
    # первый предок приведет к главной услуге, второй к hot_water
    'water_for_hot_public':
        ('water_supply', 'hot_water_public_carrier'),
    'water_for_hot_individual':
        ('water_supply', 'hot_water_individual_carrier'),
    'heated_water_public':
        ('heating_water_public', 'hot_water_public_carrier'),
    'heated_water_individual':
        ('heating_water_individual', 'hot_water_individual_carrier'),
    'heating_water_public':
        ('heat_water', 'hot_water_public'),
    'heating_water_individual':
        ('heat_water', 'hot_water_individual'),
}  # все услуги с двумя предками

OKEI_CODES = {  # processing.models.choice.meter.MeterMeasurementUnits
    'heat_individual': 'A056',  # Гигаджоуль (ГДж)
    'heat_public': 'A056',
    'heat_water_remains': 'A056',
    'heat_water_individual': 'A056',
    'heat_water_public': 'A056',
    'heated_water_individual': '113',  # Кубический метр (м3)
    'heated_water_public': '113',
    'waste_water_individual': '113',
    'waste_hot_water_individual': '113',
    'waste_cold_water_individual': '113',
    'waste_water_public': '113',
    'waste_cold_water_public': '113',
    'waste_hot_water_public': '113',
    'water_public': '113',
    'water_for_hot_individual': '113',
    'water_for_hot_public': '113',
    'gas_individual': '113',
    'gas_public': '113',
    'electricity_regular_individual': '245',  # Киловатт-час (кВт)
    'electricity_day_individual': '245',
    'electricity_night_individual': '245',
    'electricity_semi_peak_individual': '245',
    'electricity_regular_public': '245',
    'electricity_day_public': '245',
    'electricity_night_public': '245',
    'electricity_peak_public': '245',
    'electricity_semi_peak_public': '245',
    'tv': '661',  # Канал
    'radio': 'A030',  # Точка присоединения
    'garbage': 'A023',  # Кубический метр на человека
}

HEAD_CODES = {
    'waste_water_individual': ['hot_water_individual', 'water_individual'],
    'waste_hot_water_individual': ['hot_water_individual'],
    'waste_cold_water_individual': ['water_individual'],
    'waste_cold_water_public': ['water_public'],
    'waste_hot_water_public': ['hot_water_public'],
    'electricity_regular_individual': [
        'electricity_day_individual', 'electricity_night_individual',
        'electricity_peak_individual', 'electricity_semi_peak_individual'
    ],
}

RESOURCE_CODES = {
    'hot_water_individual': 'hot_water',
    'heat_individual': 'heat',
    'water_individual': 'cold_water',
    'gas_individual': 'gas',
    'electricity_regular_individual': 'electricity_regular',
    'electricity_day_individual': 'electricity_day',
    'electricity_night_individual': 'electricity_night',
    'electricity_peak_individual': 'electricity_peak',
    'electricity_semi_peak_individual': 'electricity_semi_peak',
}


def get_services_tree() -> dict:
    """
    Загрузить дерево услуг из БД

    :returns: {'electricity_regular_individual':
        {
            'title': 'Электроэнергия однотар. (индивидуальное потребление)',
            'parent_codes': ['electricity_individual'],
            'resource': 'electricity_regular',
            'calculate_queue': 1,
            'head_codes': [
                'electricity_day_individual',
                'electricity_night_individual',
                'electricity_peak_individual',
                'electricity_semi_peak_individual'
            ],
            'okei': MeterMeasurementUnits.KILOWATT_PER_HOUR,
        }
    } ~ мимикрия под содержимое словаря услуг
    """
    NOT_SYSTEM_WITH_CODE = ['fund_repair_public']  # нужно сделать системными!

    if not hasattr(ServiceType, 'cached_service_tree'):
        services_qs = ServiceType.objects(
            __raw__={
                'is_system': True,
            },
        ).as_pymongo()
        system_services: dict = {
            service['_id']: service
            for service in services_qs
        }

        ServiceType.cached_service_tree = {
            service['code']: dict(
                title=service['title'],
                parent_codes=[system_services[parent_id]['code']  # ДОЛЖЕН быть!
                    for parent_id in service['parents']],
                head_codes=HEAD_CODES.get(service['code'], []),  # или []
                resource=RESOURCE_CODES.get(service['code']),  # или None
                # TODO calculate_queue?
                okei=OKEI_CODES.get(service['code'], '642'),  # или Ед.
            )
            for service in system_services.values()
            if service.get('code')
        }

    return ServiceType.cached_service_tree


def get_parent_codes(service_type_code: str) -> set:
    """
    Коды всех предков услуги (исключая саму услугу)

    Порядок наследования НЕ соблюдается!
    """
    parent_codes = set()
    service_type_tree = get_services_tree()  # дерево услуг с кодами

    while service_type_code:  # получен код услуги?
        if service_type_code in MULTI_PARENT_SERVICES:  # более 1 предка?
            service_type_code, hot_water_code = \
                MULTI_PARENT_SERVICES[service_type_code]
            # главная услуга второго предка - это всегда "Горячая вода"
            parent_codes.add(hot_water_code)  # код 2 предка
            parent_codes.update(
                get_parent_codes(hot_water_code)  # рекурсия
            )  # предки 2-го предка
        else:  # единственный предок!
            tree_service_type = service_type_tree.get(service_type_code)
            assert tree_service_type, f"Услуги «{service_type_code}»" \
                " нет в дереве услуг (SystemServiceTypesTree)"  # Validation

            tree_parent_codes = tree_service_type['parent_codes']
            service_type_code = tree_parent_codes[0] \
                if tree_parent_codes else None  # код первого предка

        if service_type_code:  # получен код предка?
            parent_codes.add(service_type_code)

    return parent_codes


def is_individual_service(service_code: str) -> bool:
    """Индивидуальная услуга?"""
    if not service_code:
        return False

    return service_code in INDIVIDUAL_SERVICE_CODES or \
        bool(get_parent_codes(service_code) & INDIVIDUAL_SERVICE_CODES)


def is_public_service(service_code: str) -> bool:
    """Услуга поставляется на общедомовые нужды (СОИ)?"""
    if not service_code:
        return False

    return service_code in PUBLIC_SERVICE_CODES or \
        bool(get_parent_codes(service_code) & PUBLIC_SERVICE_CODES)


def is_municipal_service(service_code: str) -> bool:
    """Коммунальная услуга?"""
    return COMMUNAL_ROOT_CODE in get_parent_codes(service_code)


def is_housing_service(service_code: str) -> bool:
    """Жилищная услуга?"""
    return MAINTENANCE_ROOT_CODE in get_parent_codes(service_code) \
        or service_code in ADDITIONAL_EXCEPTIONS


def is_additional_service(service_code: str) -> bool:
    """
    Дополнительная услуга?

    У части ДУ нет кода, но у всех нет предка
    """
    return not get_parent_codes(service_code) \
        and service_code not in ADDITIONAL_EXCEPTIONS


def is_heating(service_code: str) -> bool:
    """Отопление?"""
    return service_code == 'heat' \
        or 'heat' in get_parent_codes(service_code)


def is_waste_water(service_code: str) -> bool:
    """Водоотведение?"""
    return 'waste_water' in get_parent_codes(service_code)


def get_tariff_plan_services(tariff_plan_id: ObjectId, *group_s: int) -> list:
    """
    Получить данные услуг (определенной группы) тарифного плана
    """
    plan: dict = TariffPlan.objects.only(
        'tariffs.service_type', 'tariffs.title', 'tariffs.group'
    ).as_pymongo().with_id(tariff_plan_id)  # WARN актуальность не проверяется
    if not plan or not plan.get('tariffs'):  # нет (тарифов) плана?
        return []  # WARN нет (услуг) тарифного плана

    service_tariffs: dict = {tariff['service_type']: (
        # WARN group и title - обязательные поля, group по умолчанию = 0
        tariff['group'],  # группа тарифов услуг (ЖУ, КУ, ДУ ~ "Прочие")
        tariff['title'],  # краткое наименование услуги (для ПД)
    ) for tariff in plan['tariffs']}  # ServiceTypeId: (group, 'title')

    tariff_service_types: dict = {service['_id']: service
        for service in ServiceType.objects(__raw__={
            '_id': {'$in': [*service_tariffs]}
        }).as_pymongo()}

    group_service_types: list = []

    for service_id, (group, title) in service_tariffs.items():
        service_type: dict = tariff_service_types[service_id]
        # среди "Жилищных услуг" находим "Коммунальные ресурсы на ОДН"
        if group == 0 and group not in group_s and \
                is_public_service(service_type.get('code')):  # публичная?
            group = 4  # WARN коммунальный ресурс на ОДН

        service_type['caption'] = title  # WARN отличается от ServiceType.title

        if not group_s or group in group_s:
            group_service_types.append(service_type)

    return group_service_types  # : [ ServiceTypeData,... ]


def get_bank_accounts(provider_id: ObjectId,
        *house_id_s: ObjectId, house_id: ObjectId = None) -> dict:
    """
    Найти банковские реквизиты (БИК и Р/С) всех домов организации

    :returns: HouseId: {'sector_code':('BankProvider.BIC','BankAccount.number')}
    """
    provider: Provider = \
        Provider.objects.only('bank_accounts').get(id=provider_id)
    accounts: dict = {account['number']: account for account
        in provider.bank_accounts or []}

    bank_accounts: dict = {}

    # WARN sectors отсутствуют при house = null
    house_query = {'$in': house_id_s} if house_id_s else \
        ObjectId(house_id) if house_id else {'$ne': None}

    for house_settings in Settings.objects(__raw__={
        'provider': provider_id, 'house': house_query,
        'sectors.0': {'$exists': True},  # может отсутствовать
    }).only('house', 'sectors').as_pymongo():
        for settings in house_settings['sectors']:  # : SectorSettings
            bank_account: BankAccount = accounts.get(settings['bank_account'])
            if bank_account is None:  # реквизиты для направления не найдены?
                continue  # пропускаем без банковских реквизитов

            bank_provider: BankProvider = bank_account.bic  # : ReferenceField
            assert bank_provider.bic_body, "Данные BicNew не загружены"
            last_embedded: BicEmbedded = bank_provider.bic_body[-1]  # : list

            house_accounts: dict = bank_accounts if house_id else \
                bank_accounts.setdefault(house_settings['house'], {})
            house_accounts[settings['sector_code']] = (
                last_embedded.BIC,  # Банковский Идентификационный Код
                bank_account.number  # Расчетный Счет
            )  # : tuple

    return bank_accounts


def get_sector_code(provider_id: ObjectId, house_id: ObjectId,
        bank_account: str = None) -> Optional[str]:
    """
    'rent', 'capital_repair', 'heat_supply', 'waste_water',
    'social_rent', 'communal', 'catv', 'water_supply', 'reg_fee'
    """
    house_settings: dict = Settings.objects(__raw__={
        'provider': provider_id,
        'house': house_id,  # WARN sectors отсутствуют при house = null
        'sectors.0': {'$exists': True},  # может отсутствовать
    }).only('sectors').as_pymongo().first()
    if not house_settings:
        return None  # отсутствуют настройки дома

    sector_settings: list = house_settings.get('sectors') or []

    if not bank_account:  # нет расчетного счета?
        if len(sector_settings) == 1:  # единственный элемент?
            return sector_settings[0]['sector_code']

        return None  # несколько направлений

    bank_account = bank_account.strip()  # удаляем лишние пробелы

    for settings in sector_settings:
        if settings['bank_account'] == bank_account:  # : str
            return settings['sector_code']

    return None  # расчетный счет не найден
