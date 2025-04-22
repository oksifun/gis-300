from bson import ObjectId

from processing.models.billing.tariff_plan import TariffPlan
from processing.models.billing.service_type import ServiceType
from processing.models.billing.regional_settings import RegionalSettings

SERVICE_SYSTEM_TYPES = (
    {'code': 'administrative', 'parents': [], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c474382232c'), 'provider': None,
     'title': 'Административно-хозяйственные расходы'},
    {'code': 'capital_repair', 'parents': [], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c4743822325'), 'provider': None,
     'title': 'Взнос на капитальный ремонт'},
    {'parents': [ObjectId('5936af7ccd3024006a086e65')], 'code': 'waste_water',
     'is_system': True, 'title': 'Водоотведение',
     '_id': ObjectId('5936af7ccd3024006a086e64')},
    {'code': 'waste_water_individual',
     'parents': [ObjectId('5936af7ccd3024006a086e64')], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c4743822333'), 'provider': None,
     'title': 'Водоотведение (индивидуальное потребление)'},
    {'code': 'waste_water_public',
     'parents': [ObjectId('5936af7ccd3024006a086e64')], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c4743822328'), 'provider': None,
     'title': 'Водоотведение (общедомовые нужды)'},
    {'code': 'waste_hot_water_individual',
     'parents': [ObjectId('526234c0e0e34c4743822333')], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c4743822334'), 'provider': None,
     'title': 'Водоотведение горячей воды (индивидуальное потребление)'},
    {'code': 'waste_hot_water_public',
     'parents': [ObjectId('526234c0e0e34c4743822328')], 'is_system': True,
     '_id': ObjectId('53030283b6e69753712ae68c'), 'provider': None,
     'title': 'Водоотведение горячей воды (общедомовые нужды)'},
    {'code': 'waste_cold_water_individual',
     'parents': [ObjectId('526234c0e0e34c4743822333')], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c4743822335'), 'provider': None,
     'title': 'Водоотведение холодной воды (индивидуальное потребление)'},
    {'code': 'waste_cold_water_public',
     'parents': [ObjectId('526234c0e0e34c4743822328')], 'is_system': True,
     '_id': ObjectId('53030282b6e69753712ae68b'), 'provider': None,
     'title': 'Водоотведение холодной воды (общедомовые нужды)'},
    {'code': 'garbage', 'parents': [], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c474382232e'), 'provider': None,
     'title': 'Вывоз мусора'}, {'code': 'gas_individual', 'parents': [
        ObjectId('5936af7ccd3024006a086e63')], 'is_system': True,
                                '_id': ObjectId('526234c0e0e34c4743822330'),
                                'provider': None,
                                'title': 'Газ (индивидуальное потребление)'},
    {'parents': [ObjectId('5936af7ccd3024006a086e63')], 'code': 'gas_public',
     'is_system': True, 'title': 'Газ (общедомовые нужды)',
     '_id': ObjectId('5936af7ccd3024006a086e62')},
    {'parents': [ObjectId('5936af7ccd3024006a086e5b')], 'code': 'gas_supply',
     'is_system': True, 'title': 'Газоснабжение',
     '_id': ObjectId('5936af7ccd3024006a086e63')},
    {'code': 'SГК', 'parents': [], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c4743822331'), 'provider': None,
     'title': 'ГВ+канализ.(ГВ)'},
    {'parents': [], 'code': 'hot_water', 'is_system': True,
     'title': 'Горячая вода', '_id': ObjectId('5936af7ccd3024006a086e60')},
    {'parents': [ObjectId('5936af7ccd3024006a086e60')],
     'code': 'hot_water_individual', 'is_system': True,
     'title': 'Горячая вода (индивидуальное потребление)',
     '_id': ObjectId('5936af7dcd3024006a086e69')},
    {'parents': [ObjectId('5936af7ccd3024006a086e60')],
     'code': 'hot_water_public', 'is_system': True,
     'title': 'Горячая вода (общедомовые нужды)',
     '_id': ObjectId('5936af7ccd3024006a086e5f')},
    {'code': 'heated_water_individual',
     'parents': [ObjectId('5936af7dcd3024006a086e6a'),
                 ObjectId('5936af7ccd3024006a086e68')], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c474382232f'), 'provider': None,
     'title': 'Горячая вода подогретая (индивидуальное потребление)'},
    {'code': 'heated_water_public',
     'parents': [ObjectId('5936af7ccd3024006a086e5d'),
                 ObjectId('5936af7dcd3024006a086e6b')], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c4743822329'), 'provider': None,
     'title': 'Горячая вода подогретая (общедомовые нужды)'}, {
        'parents': [ObjectId('5936af7ccd3024006a086e5e'),
                    ObjectId('5936af7dcd3024006a086e69')],
        'code': 'heating_water_individual', 'is_system': True,
        'title': 'Горячая вода тепловая энергия (индивидуальное потребление)',
        '_id': ObjectId('5936af7dcd3024006a086e6a')}, {
        'parents': [ObjectId('5936af7ccd3024006a086e5e'),
                    ObjectId('5936af7ccd3024006a086e5f')],
        'code': 'heating_water_public', 'is_system': True,
        'title': 'Горячая вода тепловая энергия (общедомовые нужды)',
        '_id': ObjectId('5936af7ccd3024006a086e5d')},
    {'parents': [ObjectId('5936af7dcd3024006a086e69')],
     'code': 'hot_water_individual_carrier', 'is_system': True,
     'title': 'Горячая вода теплоноситель (индивидуальное потребление)',
     '_id': ObjectId('5936af7ccd3024006a086e68')},
    {'parents': [ObjectId('5936af7ccd3024006a086e5f')],
     'code': 'hot_water_public_carrier', 'is_system': True,
     'title': 'Горячая вода теплоноситель (общедомовые нужды)',
     '_id': ObjectId('5936af7dcd3024006a086e6b')},
    {'code': 'bank_fee', 'parents': [], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c474382232d'), 'provider': None,
     'title': 'Комиссия банка'},
    {'parents': [], 'code': 'communal_services', 'is_system': True,
     'title': 'Коммунальные услуги',
     '_id': ObjectId('5936af7ccd3024006a086e5b')},
    {'parents': [ObjectId('5936af7ccd3024006a086e5a')], 'code': 'heat',
     'is_system': True, 'title': 'Отопление',
     '_id': ObjectId('5936af7ccd3024006a086e59')},
    {'code': 'heat_individual',
        'parents': [ObjectId(
            '5936af7ccd3024006a086e59')],
        'is_system': True,
        '_id': ObjectId(
            '526234c0e0e34c4743822338'),
        'provider': None,
        'title': 'Отопление (индивидуальное потребление)'},
    {'code': 'heat_public', 'parents': [ObjectId('5936af7ccd3024006a086e59')],
     'is_system': True, '_id': ObjectId('526234c0e0e34c4743822326'),
     'provider': None, 'title': 'Отопление (общедомовые нужды)'},
    {'code': 'penalty', 'parents': [], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c4743822339'), 'provider': None,
     'title': 'Пени'}, {'code': 'ПКГ', 'parents': [], 'is_system': True,
                        '_id': ObjectId('591b19c92964ab385f93d131'),
                        'provider': None,
                        'title': 'Повышающий коэффициент ГВС'},
    {'code': 'ПКХ', 'parents': [], 'is_system': True,
     '_id': ObjectId('591b19c92964ab385f93d130'), 'provider': None,
     'title': 'Повышающий коэффициент ХВС'},
    {'code': 'ПКЭ', 'parents': [], 'is_system': True,
     '_id': ObjectId('591b19cb2964ab385f93d132'), 'provider': None,
     'title': 'Повышающий коэффициент ЭС'},
    {'parents': [ObjectId('5936af7ccd3024006a086e5a')], 'code': 'heat_water',
     'is_system': True, 'title': 'Подогрев воды для ГВС',
     '_id': ObjectId('5936af7ccd3024006a086e5e')},
    {'code': 'heat_water_individual',
     'parents': [ObjectId('5936af7dcd3024006a086e6a')], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c474382234d'), 'provider': None,
     'title': 'Подогрев воды для ГВС (индивидуальное потребление)'},
    {'code': 'heat_water_public',
     'parents': [ObjectId('5936af7ccd3024006a086e5d')], 'is_system': True,
     '_id': ObjectId('52b813a0b6e6976491231c09'), 'provider': None,
     'title': 'Подогрев воды для ГВС (общедомовые нужды)'},
    {'code': 'radio', 'parents': [], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c474382233b'), 'provider': None,
     'title': 'Радиоточка'},
    {'code': 'manual', 'parents': [], 'is_system': True,
     '_id': ObjectId('53a936bad9f4038d5780e76a'), 'provider': None,
     'title': 'Ручное начисление/Корректировки'},
    {'code': 'fire_protection',
     'parents': [ObjectId(
         '5936af7ccd3024006a086e61')],
     'is_system': True,
     '_id': ObjectId(
         '526234c0e0e34c474382232a'),
     'provider': None,
     'title': 'Содержание и тех.обслуживание АППЗ'},
    {'code': 'gas_systems', 'parents': [ObjectId('5936af7ccd3024006a086e61')],
     'is_system': True, '_id': ObjectId('526234c0e0e34c4743822332'),
     'provider': None, 'title': 'Содержание и тех.обслуживание газовых систем'},
    {'code': 'elevator', 'parents': [ObjectId('5936af7ccd3024006a086e61')],
     'is_system': True, '_id': ObjectId('526234c0e0e34c4743822336'),
     'provider': None, 'title': 'Содержание и тех.обслуживание лифта'},
    {'code': 'chute', 'parents': [ObjectId('5936af7ccd3024006a086e61')],
     'is_system': True, '_id': ObjectId('526234c0e0e34c4743822337'),
     'provider': None, 'title': 'Содержание и тех.обслуживание мусоропровода'},
    {'code': 'house_meters', 'parents': [ObjectId('5936af7ccd3024006a086e61')],
     'is_system': True, '_id': ObjectId('526234c0e0e34c474382234a'),
     'provider': None, 'title': 'Содержание и тех.обслуживание ОДПУ'},
    {'code': 'house_meters_gas',
     'parents': [ObjectId('526234c0e0e34c474382234a')], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c4743822324'), 'provider': None,
     'title': 'Содержание и тех.обслуживание ОДПУ газа'},
    {'code': 'house_meters_heat',
     'parents': [ObjectId('526234c0e0e34c474382234a')], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c4743822323'), 'provider': None,
     'title': 'Содержание и тех.обслуживание ОДПУ тепла и горячей воды'},
    {'code': 'house_meters_water',
     'parents': [ObjectId('526234c0e0e34c474382234a')], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c4743822321'), 'provider': None,
     'title': 'Содержание и тех.обслуживание ОДПУ холодной воды'},
    {'code': 'house_meters_electricity',
     'parents': [ObjectId('526234c0e0e34c474382234a')], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c4743822322'), 'provider': None,
     'title': 'Содержание и тех.обслуживание ОДПУ электроэнергии'},
    {'code': 'intercom', 'parents': [ObjectId('5936af7ccd3024006a086e61')],
     'is_system': True, '_id': ObjectId('526234c0e0e34c474382233a'),
     'provider': None, 'title': 'Содержание и тех.обслуживание ПЗУ'},
    {'code': 'garbage_area', 'parents': [ObjectId('5936af7ccd3024006a086e61')],
     'is_system': True, '_id': ObjectId('53e376e6f3b7d436ce95b4c6'),
     'provider': None, 'title': 'Содержание контейнерной площадки'},
    {'code': 'housing', 'parents': [ObjectId('5936af7ccd3024006a086e61')],
     'is_system': True, '_id': ObjectId('526234c0e0e34c474382233d'),
     'provider': None, 'title': 'Содержание общего имущества'},
    {'parents': [], 'code': 'maintenance', 'is_system': True,
     'title': 'Содержание общего имущества и тех.обслуживание',
     '_id': ObjectId('5936af7ccd3024006a086e61')},
    {'code': 'territory', 'parents': [ObjectId('5936af7ccd3024006a086e61')],
     'is_system': True, '_id': ObjectId('526234c0e0e34c474382233c'),
     'provider': None, 'title': 'Содержание придомовой территории'},
    {'code': 'repair', 'parents': [ObjectId('5936af7ccd3024006a086e61')],
     'is_system': True, '_id': ObjectId('526234c0e0e34c474382233f'),
     'provider': None, 'title': 'Текущий ремонт'},
    {'code': 'tv', 'parents': [], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c474382232b'), 'provider': None,
     'title': 'Телевидение'}, {'code': 'SТП', 'parents': [], 'is_system': True,
                               '_id': ObjectId('526234c0e0e34c474382233e'),
                               'provider': None, 'title': 'Тепловой счетчик'},
    {'parents': [ObjectId('5936af7ccd3024006a086e5b')], 'code': 'heat_supply',
     'is_system': True, 'title': 'Теплоснабжение',
     '_id': ObjectId('5936af7ccd3024006a086e5a')},
    {'code': 'heat_water_remains', 'parents': [], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c4743822464'), 'provider': None,
     'title': 'ТЭ на подогрев воды в целях ГВС'},
    {'code': 'stairs_cleaning',
     'parents': [ObjectId(
         '5936af7ccd3024006a086e61')],
     'is_system': True,
     '_id': ObjectId(
         '526234c0e0e34c4743822340'),
     'provider': None,
     'title': 'Уборка лестничных клеток'},
    {'code': 'management', 'parents': [ObjectId('5936af7ccd3024006a086e61')],
     'is_system': True, '_id': ObjectId('526234c0e0e34c4743822348'),
     'provider': None, 'title': 'Управление многоквартирными домами'},
    {'code': 'SХК', 'parents': [], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c4743822342'), 'provider': None,
     'title': 'ХВ+канализ.(сумм.)'},
    {'code': 'SХХ', 'parents': [], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c4743822343'), 'provider': None,
     'title': 'ХВ+канализ.(ХВ)'}, {
        'parents': [ObjectId('5936af7ccd3024006a086e67'),
                    ObjectId('5936af7ccd3024006a086e68')],
        'code': 'water_for_hot_individual', 'is_system': True,
        'title': 'Холодная вода для ГВС (индивидуальное потребление)',
        '_id': ObjectId('5936af7ccd3024006a086e66')}, {
        'parents': [ObjectId('5936af7ccd3024006a086e67'),
                    ObjectId('5936af7dcd3024006a086e6b')],
        'code': 'water_for_hot_public', 'is_system': True,
        'title': 'Холодная вода для ГВС (общедомовые нужды)',
        '_id': ObjectId('5936af7dcd3024006a086e6c')},
    {'parents': [ObjectId('5936af7ccd3024006a086e65')], 'code': 'water_supply',
     'is_system': True, 'title': 'Холодное водоснабжение',
     '_id': ObjectId('5936af7ccd3024006a086e67')},
    {'code': 'water_individual',
     'parents': [ObjectId(
         '5936af7ccd3024006a086e67')],
     'is_system': True,
     '_id': ObjectId(
         '526234c0e0e34c4743822341'),
     'provider': None,
     'title': 'Холодное водоснабжение (индивидуальное потребление)'},
    {'code': 'water_public', 'parents': [ObjectId('5936af7ccd3024006a086e67')],
     'is_system': True, '_id': ObjectId('526234c0e0e34c4743822327'),
     'provider': None, 'title': 'Холодное водоснабжение (общедомовые нужды)'},
    {'parents': [ObjectId('5936af7ccd3024006a086e5b')], 'code': 'water_cycle',
     'is_system': True, 'title': 'Холодное водоснабжение и водоотведение',
     '_id': ObjectId('5936af7ccd3024006a086e65')},
    {'parents': [ObjectId('5936af7ccd3024006a086e5b')],
     'code': 'electricity_supply', 'is_system': True,
     'title': 'Электроснабжение', '_id': ObjectId('5936af7ccd3024006a086e5c')},
    {'code': 'electricity_individual',
     'parents': [ObjectId('5936af7ccd3024006a086e5c')], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c4743822347'), 'provider': None,
     'title': 'Электроэнергия (индивидуальное потребление)'},
    {'code': 'electricity_public',
     'parents': [ObjectId('5936af7ccd3024006a086e5c')], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c4743822349'), 'provider': None,
     'title': 'Электроэнергия (общедомовые нужды)'},
    {'code': 'electricity_day_individual',
     'parents': [ObjectId('526234c0e0e34c4743822347')], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c4743822344'), 'provider': None,
     'title': 'Электроэнергия день (индивидуальное потребление)'},
    {'code': 'electricity_day_public',
     'parents': [ObjectId('526234c0e0e34c4743822349')], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c474382231f'), 'provider': None,
     'title': 'Электроэнергия день (общедомовые нужды)'},
    {'code': 'electricity_night_individual',
     'parents': [ObjectId('526234c0e0e34c4743822347')], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c4743822346'), 'provider': None,
     'title': 'Электроэнергия ночь (индивидуальное потребление)'},
    {'code': 'electricity_night_public',
     'parents': [ObjectId('526234c0e0e34c4743822349')], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c4743822320'), 'provider': None,
     'title': 'Электроэнергия ночь (общедомовые нужды)'},
    {'code': 'electricity_regular_individual',
     'parents': [ObjectId('526234c0e0e34c4743822347')], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c4743822345'), 'provider': None,
     'title': 'Электроэнергия однотар. (индивидуальное потребление)'},
    {'code': 'electricity_regular_public',
     'parents': [ObjectId('526234c0e0e34c4743822349')], 'is_system': True,
     '_id': ObjectId('526234c0e0e34c474382234b'), 'provider': None,
     'title': 'Электроэнергия однотар. (общедомовые нужды)'},
    {'code': 'electricity_peak_individual',
     'parents': [ObjectId('526234c0e0e34c4743822347')], 'is_system': True,
     '_id': ObjectId('56fa5c01401aac2a8a522e95'), 'provider': None,
     'title': 'Электроэнергия пиковая (индивидуальное потребление)'},
    {'code': 'electricity_peak_public',
     'parents': [ObjectId('526234c0e0e34c4743822349')], 'is_system': True,
     '_id': ObjectId('56fd228183c9e2ad42d11a42'), 'provider': None,
     'title': 'Электроэнергия пиковая (общедомовые нужды)'},
    {'code': 'electricity_semi_peak_individual',
     'parents': [ObjectId('526234c0e0e34c4743822347')], 'is_system': True,
     '_id': ObjectId('56fa5c0c401aac2a8a522e96'), 'provider': None,
     'title': 'Электроэнергия полупиковая (индивидуальное потребление)'},
    {'code': 'electricity_semi_peak_public',
     'parents': [ObjectId('526234c0e0e34c4743822349')], 'is_system': True,
     '_id': ObjectId('56fd228a83c9e2ad42d11a43'), 'provider': None,
     'title': 'Электроэнергия полупиковая (общедомовые нужды)'})


def get_system_services():
    return [
        {'id': x['_id'], 'title': x['title'], 'code': x['code']}
        for x in SERVICE_SYSTEM_TYPES
    ]


def get_all_services(tariff_plan_id):
    """
    Получение всех услуг
    :param tariff_plan_id: ObjectId: id тарифного плана TariffPlan
    :return:
    """
    result = {}

    # Системные
    system = {x['_id']: x['title'] for x in SERVICE_SYSTEM_TYPES}

    tp = TariffPlan.objects(id=tariff_plan_id).as_pymongo().get()

    # Параметры необходимые для определения городских
    region_code = tp['region_code']
    date_from = tp['date_from']

    # Пользовательские
    if tp.get('provider'):
        user = [
            {'_id': x['_id'], 'title': x['title']}
            for x in list(ServiceType.objects(
                provider=tp['provider']
            ).as_pymongo())
        ]
    else:
        user = []

    # Городские
    city_plans = RegionalSettings.objects(
        region_code=region_code
    ).only('tariff_plans').as_pymongo()
    if city_plans:
        # Если запрос не пустой
        city_plans = city_plans.get()
        city_tariff_plans = []  # Список городских тарифов
        for t_p in city_plans['tariff_plans']:
            # Берем первый, который удовлетворяет временному условию,
            # т.к. они в БД отсортированы по дате
            if t_p['date_from'] <= date_from:
                # Проходим по группам и собираем все услуги
                for group_tariff in t_p['tariffs']:
                    city_tariff_plans.extend([
                        {
                            '_id': x['service_type'],
                            'title': system[x['service_type']],
                        }
                        for x in group_tariff['tariffs']
                        if system.get(x['service_type'])
                    ])
                city_tariff_plans.sort(key=lambda x: x['title'].upper())
                result['urban'] = city_tariff_plans
                break
    else:
        result['urban'] = []

    system = [{'_id': k, 'title': v} for k, v in system.items()]

    # Объединяем пользовательские и системные в один список
    result['all'] = sorted(user + system, key=lambda x: x['title'].upper())

    return result
