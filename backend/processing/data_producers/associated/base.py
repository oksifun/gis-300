import datetime

from bson import ObjectId
from dateutil.relativedelta import relativedelta

from app.crm.models.crm import CRM
from app.personnel.models.department import Department
from processing.models.billing.provider.main import Provider
from app.house.models.house import House
from processing.models.billing.accrual import Accrual
from processing.models.billing.service_type import ServiceType
from app.accruals.models.accrual_document import AccrualDoc
from processing.models.billing.account import Tenant
from processing.models.billing.settings import Settings
from processing.models.billing.tariff_plan import TariffPlan
from processing.references.service_types import SystemServiceTypesTree
from settings import ZAO_OTDEL_PROVIDER_OBJECT_ID


def get_phones_of_tenants(ids):
    aggregation_pipeline = [
        {
            '$match': {'_id': {'$in': ids}},
        },
        {
            '$unwind': '$phones',
        },
        {
            '$project': {
                'code': '$phones.code',
                'number': '$phones.number',
                'add': '$phones.add',
                'area': '$area.str_number',
                'name': '$short_name',
            },
        },
    ]
    phones = Tenant.objects.aggregate(*aggregation_pipeline)
    return [
        {
            '_id': p['_id'],
            'area': p['area'],
            'name': p['name'],
            'number': '+7{}{}{}'.format(
                p['code'],
                p['number'],
                ' доб {}'.format(p['add']) if p.get('add') else ''
            )
        }
        for p in phones
    ]


def filter_otdel_clients(providers_ids):
    data = CRM.objects.filter(
        owner=ZAO_OTDEL_PROVIDER_OBJECT_ID,
        status='client',
        provider__id__in=providers_ids,
    ).distinct('provider._id')
    return list(data)


def get_providers_ids_by_bank_accounts(account_numbers):
    providers = list(Provider.objects.as_pymongo().filter(
        bank_accounts__number__in=account_numbers
    ).only('id', 'bank_accounts.number'))
    clients = filter_otdel_clients([p['_id'] for p in providers])
    result = {}
    for p in providers:
        for b_account in p['bank_accounts']:
            if b_account['number'] not in account_numbers:
                continue
            if b_account['number'] not in result or p['_id'] in clients:
                result[b_account['number']] = p['_id']
    return result


def get_house_services(house_id, provider_id):

    tariff_plans = Settings.objects(
        house=house_id,
        provider=provider_id,
        _type="AccrualSettings"
    ).distinct("sectors.tariff_plan")
    services = TariffPlan.objects(
        id__in=tariff_plans
    ).distinct('tariffs.service_type')
    return services


def get_binded_houses(provider_id, date_on=None, return_binds=False,
                      business_type=None):
    """
    Для организации находит дома с действующими привязками. Отдаёт список id
    или сами привязки
    """
    all_houses = House.objects(
        service_binds__provider=provider_id
    ).as_pymongo().only(
        'id',
        'service_binds.provider',
        'service_binds.is_active',
        'service_binds.business_type',
        'service_binds.date_start',
        'service_binds.date_end',
        'service_binds.sectors.sector_code',
        'service_binds.sectors.permissions',
    )
    houses = []
    if not date_on:
        date_on = datetime.datetime.now()
    for house in all_houses._iter_results():
        for bind in house['service_binds']:
            if (
                bind['provider'] == provider_id
                and bind['is_active']
                and (bind.get('date_start') or date_on) <= date_on
                and (bind.get('date_end') or date_on) >= date_on
                and (business_type or bind['business_type'])
                == bind['business_type']
            ):
                if return_binds:
                    houses.append(house)
                else:
                    houses.append(house['_id'])
                break
    return houses


def get_binded_houses_ext(provider_id, date_on=None, return_binds=False,
                          business_type=None, only_active=True):
    """
    Для организации находит дома с действующими привязками. Отдаёт список id
    или сами привязки
    """
    all_houses = House.objects(
        service_binds__provider=provider_id,
    ).as_pymongo().only(
        'id',
        'service_binds.provider',
        'service_binds.is_active',
        'service_binds.business_type',
        'service_binds.date_start',
        'service_binds.date_end',
        'service_binds.sectors.sector_code',
        'service_binds.sectors.permissions',
    )
    houses = []
    if not date_on:
        date_on = datetime.datetime.now()
    for house in all_houses:
        for bind in house['service_binds']:
            if bind['provider'] != provider_id:
                continue
            if (
                    (business_type or bind['business_type'])
                    != bind['business_type']
            ):
                continue
            if only_active:
                if (
                    not bind['is_active']
                    or (bind.get('date_start') or date_on) > date_on
                    or (bind.get('date_end') or date_on) < date_on
                ):
                    continue
            if return_binds:
                houses.append(house)
            else:
                houses.append(house['_id'])
            break
    return houses


def get_allowed_sectors(provider_id, house_id, date_on=None):
    house = House.objects(pk=house_id).as_pymongo().only(
        'id',
        'service_binds.provider',
        'service_binds.is_active',
        'service_binds.date_start',
        'service_binds.date_end',
        'service_binds.sectors.sector_code',
        'service_binds.sectors.permissions',
    ).get()
    if not date_on:
        date_on = datetime.datetime.now()
    sectors = set()
    for bind in house['service_binds']:
        if (
            bind['provider'] == provider_id and
            bind['is_active'] and
            (bind.get('date_start') or date_on) <= date_on and
            (bind.get('date_end') or date_on) >= date_on
        ):
            for sector in bind['sectors']:
                if sector['permissions'].get('r'):
                    sectors.add(sector['sector_code'])
    return list(sectors)


def cut_binded_houses(houses, provider_id, date_on=None):
    """
    Из переданного списка домов в виде объёктов моделей оставляет список только
    домов привязанных к переданной организации. Возвращает новый список.
    """
    result = []
    if not date_on:
        date_on = datetime.datetime.now()
    for house in houses:
        for bind in house.service_binds:
            if (
                bind.provider == provider_id and
                bind.is_active and
                (bind.date_start or date_on) <= date_on and
                (bind.date_end or date_on) >= date_on
            ):
                result.append(house)
                break
    return result


def get_provider_services_tree(provider_id,
                               system_types=None, provider_types=None,
                               resources=None):
    """
    Получает услуги, сгруппированные по системным кодам, в виде словаря.
    Можно передать список системных услуг и услуг провайдера, чтобы не
    делать запрос в базу. Если передать параметр resources, то будут отданы
    услуги, только соответствующие нужным ресурсам. Если передать
    provider_id=None, пользовательские услуги не будут обрабатываться
    """
    # системные услуги из базы
    s_types = {
        s.code: s.id
        for s in (system_types or
                  ServiceType.objects.filter(is_system=True).only('code'))
    }
    # свои услуги из базы
    if provider_id:
        p_types = provider_types or \
                  ServiceType.objects.filter(
                      provider=provider_id).only('parents')
    else:
        p_types = []

    def get_p_children(p_type_id):
        """
        Рекурсивно составляет список всех потомков пользовательской услуги
        """
        children = []
        for p_p_type in p_types:
            if p_p_type.parents and p_type_id in p_p_type.parents:
                children.append(p_p_type.id)
                children.extend(get_p_children(p_p_type.id))
        return children

    # для каждой пользовательской услуги составим список потомков
    for p_type in p_types:
        p_type.children = get_p_children(p_type.id)
    # системное дерево настроек услуг
    s_types_tree = SystemServiceTypesTree[0]['services']

    def get_children(main_code):
        """
        Рекурсивно составляет список всех потоков услуги по системному коду
        """
        children = []
        for s_code, s_data in s_types_tree.items():
            if s_data.get('parent_codes') and main_code in s_data['parent_codes']:
                children.append(s_types[s_code])
                children.extend(get_children(s_code))
        return children

    # составим словарь системных кодов и добавим им всех потомков
    result = {}
    for code, data in s_types_tree.items():
        if resources is not None and data.get('resource') not in resources:
            continue
        result[code] = [s_types[code]]
        result[code].extend(get_children(code))
        for p_type in p_types:
            if p_type.parents:
                if set(p_type.parents) & set(result[code]):
                    result[code].append(p_type.id)
                    result[code].extend(p_type.children)
    return result


def get_resource_accruals_by_area(area_id, resources, month_from, month_till):
    services_tree = get_provider_services_tree(None, resources=resources)
    services = []
    for s in services_tree.values():
        services.extend(s)
    if not services:
        return []
    accruals = Accrual.objects(__raw__={
        'account.area._id': area_id,
        'services.service_type': {'$in': services},
        'month': {'$gte': month_from, '$lte': month_till},
        'doc.status': {'$in': ['ready', 'edit']},
        'is_deleted': {'$ne': True},
    }).as_pymongo().only(
        'owner', 'month', 'services.value', 'services.service_type'
    )
    result = []
    for a in accruals:
        a_services = a.pop('services')
        a['value'] = 0
        for s in a_services:
            if s['service_type'] in services:
                a['value'] += s['value']
        result.append(a)
    return result


def get_houses_meters_periods(provider_id, accrual_settings=None, house=None):
    """
    Возвращает словарь, где для каждого дома указан текущий месяц, куда класть
    показания по счётчикам. Можно передать настройки начислений
    (accrual_settings), чтобы не делать лишний запрос в базу. Параметр
    accrual_settings должен быть в виде словарей
    """
    query = dict(
        _type='ProviderAccrualSettings',
        provider=provider_id,
    )
    if house:
        query.update(dict(house=house))
    if not accrual_settings:
        accrual_settings = Settings.objects(**query).as_pymongo()
    houses = [a['house'] for a in accrual_settings]
    aggregation_pipeline = [
        {'$match': {
            'sector_binds.provider': provider_id,
            'house._id': {'$in': houses},
            'is_deleted': {'$ne': True},
        }},
        {'$sort': {'date_from': -1}},
        {'$group': {
            '_id': '$house._id',
            'month': {'$first': '$date_from'},
        }},
    ]
    houses_months = list(AccrualDoc.objects.aggregate(*aggregation_pipeline))
    houses_months = {h['_id']: h['month'] for h in houses_months}
    current_month = datetime.datetime.now().replace(
        day=1, hour=0, minute=0, second=0, microsecond=0)
    for a_setting in accrual_settings:
        if houses_months.get(a_setting['house']):
            houses_months[a_setting['house']] += relativedelta(months=1)
        else:
            houses_months[a_setting['house']] = current_month
        if not a_setting['area_meters_month_get_usage']:
            # houses_months[a_setting['house']] = max(
            #     houses_months[a_setting['house']],
            #     current_month
            # )
            houses_months[a_setting['house']] = current_month
        elif a_setting['area_meters_month_get']:
            houses_months[a_setting['house']] -= \
                relativedelta(months=a_setting['area_meters_month_get'])
    return houses_months


def get_cc_clients(cc_provider_id):
    houses = get_binded_houses(cc_provider_id, return_binds=True)
    result = set()
    for house in houses:
        for bind in house['service_binds']:
            if bind['provider'] != cc_provider_id:
                result.add(bind['provider'])
    return list(result)


def get_spectator_department(provider_id):
    query = dict(
        provider=provider_id,
        settings__tenant_tickets=True,
        is_deleted__ne=True
    )
    dept = Department.objects(**query).only('id').as_pymongo().first()
    return dept['_id'] if dept else None
