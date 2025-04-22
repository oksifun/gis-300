import datetime

from bson import ObjectId
from mongoengine import Q, DoesNotExist

from processing.data_producers.balance.base import AccountBalance, \
    AccountsListBalance
from processing.models.billing.accrual import Accrual
from processing.models.billing.tariff_plan import TariffPlan
from app.accruals.models.accrual_document import AccrualDoc
from processing.models.billing.service_type import ServiceType
from processing.models.billing.provider.main import BankProvider, Provider
from processing.models.billing.settings import Settings
from app.caching.models.filters import FilterCache, FilterPreparedData
from processing.models.choices import ACCRUAL_SECTOR_TYPE_CHOICES

GROUP_NAMES = (
    (0, 'Жилищные услуги'),
    (1, 'Коммунальные услуги'),
    (2, 'Прочие'),
    (3, 'Взносы на капитальный ремонт'),
    (4, 'Коммунальные услуги на СОИ'),
    (10, 'Содержание паркинга'),
    (12, ''),
)
SERVICE_WARNINGS = {
    'nothing_to_refund': 'Нет источника для возврата',
}
SYSTEM_NAMES = {
    'electricity_individual': 'Электроэнергия (индивидуальное потребление)',
    'waste_water_individual': 'Водоотведение (индивидуальное потребление)',
}


def get_accruals_with_grouped_tariffs(doc_id, account_id=None, accounts=None,
                                      sectors=None, binds=None):
    """
    Взять цельный акруал, добавить недостающие данные, сгруппировать тарифы и
    вывести в виде:
    - sector
    -- group (tariff_plan)
    --- group (service_type)
    ---- service: id, title, value, privileges, recalculations, shortfalls,
                  total
    """
    # получаем из базы акруалы
    if accounts is not None:
        aa = _get_accruals_of_list(doc_id, accounts, sectors, binds)
        tp_ids = set()
        for a in aa:
            a['tariff_plans'] = set()
            for s in a['services']:
                a['tariff_plans'] |= set(s['tariff_plans'])
            tp_ids |= a['tariff_plans']
    else:
        aa = _get_accruals_of_one(doc_id, account_id, sectors, binds)
        tp_ids = {a['tariff_plan'] for a in aa}
        for a in aa:
            a['tariff_plans'] = {a['tariff_plan']}

    # получаем из базы тарифы
    tariffs, tp_names = _get_tariffs_data(list(tp_ids))

    # получаем из базы услуги
    pp = {a['owner'] for a in aa}
    s_types = {}
    system_types = ServiceType.objects.filter(is_system=True)
    service_titles = {'sys': {str(s.pk): s.title for s in system_types}}
    for p in pp:
        provider_types = ServiceType.objects.filter(provider=p)
        s_types[p] = ServiceType.get_provider_tree(
            p, system_types=system_types, provider_types=provider_types)
        service_titles[p] = {str(s.pk): s.title for s in provider_types}

    # собираем всё в отчёт
    sectors_data = {}
    for a in aa:
        s_title = ''
        for s_c in ACCRUAL_SECTOR_TYPE_CHOICES:
            if a['sector_code'] == s_c[0]:
                s_title = s_c[1]
                break
        sector_data = sectors_data.setdefault(a['sector_code'], {
            'sector': a['sector_code'],
            'title': s_title,
            'data': [],
            'use_penalty': a['use_penalty'],
            'accrual_value': 0,
            'tariff_plan': None,
            'tariff_plan_title': '',
            'id': str(a['_id']) if a.get('_id') else None,
            'total': {
                'value': 0,
                'privileges': 0,
                'recalculations': 0,
                'shortfalls': 0,
                'total': 0,
            },
            'penalties': {
                'total': a['totals']['penalties'],
                'table': a.get('penalties', []),
            }
        })
        accrual = sector_data['data']
        if a.get('value'):
            sector_data['accrual_value'] += a['value']
        if a.get('tariff_plan') and a['tariff_plan'] in tp_names:
            sector_data['tariff_plan'] = str(a['tariff_plan'])
            sector_data['tariff_plan_title'] = tp_names[a['tariff_plan']]
        if sector_data['penalties'].get('table'):
            for penalty in sector_data['penalties']['table']:
                if '_id' in penalty:
                    penalty.pop('_id')
        tp = {}
        for t in a['tariff_plans']:
            if t in tariffs:
                tp.update(tariffs[t])
        s_tree = s_types[a['owner']]

        # формируем список услуг
        services = _get_services_list(a, tp, service_titles)
        for service in services:
            for key in sector_data['total']:
                sector_data['total'][key] += service[key]

        # группируем по номеру группы в тарифах
        groups = _group_services_by_tariff_groups(services, tp)

        # добавляем в результаты
        for g in GROUP_NAMES:
            if g[0] in groups:
                group = groups[g[0]]
                data = _group_services_by_system_services(group, s_tree)
                data['title'] = g[1]
                accrual.append(data)

    # возвращаем в виде списка
    return list(sectors_data.values())


def get_balance_by_accrual_doc(provider_id, doc, account_id=None,
                               accounts=None, sectors=None, binds=None):
    if accounts is not None:
        balance = AccountsListBalance(accounts, provider_id, binds)
    else:
        balance = AccountBalance(account_id, provider_id, binds)
    if isinstance(doc, ObjectId):
        doc = AccrualDoc.objects(pk=doc).get()
    if not sectors:
        sectors = [s.sector_code for s in doc.sector_binds]
    balance = balance.get_date_balance(
        doc.date,
        sectors,
        use_bank_date=False,
        group_by_sector=True,
    )
    return balance


def get_balance_by_accrual_doc_filter(provider_id, doc, filter_id,
                                      sectors=None, binds=None):
    """
    Принимает фильтр, проверяет готовы ли данные по нему.
    Отдаёт статус и данные
    """
    data = None
    status = 'wip'
    filt = FilterCache.objects(
        pk=filter_id,
    ).as_pymongo().only('readiness').get()
    if 'balance' in filt['readiness']:
        try:
            data = FilterPreparedData.objects(
                filter_id=filter_id,
                code='balance',
            ).as_pymongo().get()
            FilterPreparedData.objects(
                pk=data['_id'],
            ).update(
                set__used=datetime.datetime.now(),
            )
            if isinstance(doc, ObjectId):
                doc = AccrualDoc.objects.get(id=doc)
            if not sectors:
                sectors = [s.sector_code for s in doc.sector_binds]
            data = {
                d['sector']: d['data']
                for d in data['data'] if d['sector'] in sectors
            }
        except DoesNotExist:
            # Отмечено, что данные готовы, но их нет
            filt = FilterCache.objects(
                pk=filter_id,
            ).as_pymongo().only('objs').get()
            data = get_balance_by_accrual_doc(
                provider_id,
                doc,
                accounts=filt['objs'],
                sectors=sectors,
                binds=binds,
            )
        status = 'done'
    FilterCache.objects(pk=filter_id).update(set__used=datetime.datetime.now())
    return data, status


def get_pay_details_for_accrual_doc(doc, sectors):
    """
    Определяет реквизиты получателей каждого из направлений переданного
    документа начислений
    :param doc: документ начислений
    :param sectors: направления
    :return:
    """
    provider_sectors = {
        s_b.sector_code: s_b.provider
        for s_b in doc.sector_binds if s_b.sector_code in sectors
    }
    a_settings = Settings.objects(
        _type='ProviderAccrualSettings',
        house=doc.house.id,
        provider__in=set(provider_sectors.values()),
    ).as_pymongo().only(
        'provider',
        'sectors.sector_code',
        'sectors.bank_account',
        'sectors.area_types.bank_account',
    )
    a_settings = {s['provider']: s for s in a_settings._iter_results()}
    result = {}
    providers = Provider.objects(
        pk__in=set(provider_sectors.values())
    ).as_pymongo().only(
        'id',
        'str_name',
        'bank_accounts.number',
        'bank_accounts.bic',
    )
    providers = {
        p['_id']: p
        for p in providers._iter_results()
    }
    banks = set()
    for sector, provider_id in provider_sectors.items():
        settings = a_settings.get(provider_id)
        if not settings:
            continue
        provider = providers[provider_id]
        result[sector] = {
            'sector': sector,
            'str_name': provider['str_name'],
            'bank_accounts': [],
        }
        bank_accounts = set()
        for sector_s in settings['sectors']:
            if sector_s['sector_code'] == sector:
                bank_accounts.add(sector_s['bank_account'])
                if not sector_s.get('area_types'):
                    continue
                for area_s in sector_s['area_types']:
                    if area_s.get('bank_account'):
                        bank_accounts.add(area_s['bank_account'])
        for b_account in bank_accounts:
            bank = None
            for p_account in provider['bank_accounts']:
                if p_account['number'] == b_account:
                    bank = p_account['bic']
                    banks.add(bank)
                    break
            result[sector]['bank_accounts'].append({
                'number': b_account,
                'bank': bank,
            })
    banks = BankProvider.objects(pk__in=list(banks)).as_pymongo().only(
        'id',
        'NAMEP',
        'NEWNUM',
        'KSNP',
    )
    banks = {b['_id']: b for b in banks._iter_results()}
    for bank in banks.values():
        bank.pop('_id')
    for data in result.values():
        for bank_account in data['bank_accounts']:
            if bank_account['bank']:
                bank_account['bank'] = banks.get(bank_account['bank'])
    return list(result.values())


def _get_tariffs_data(ids):
    """
    Возвращает настройки тарифов, сгруппированные по видам услуг, а также
    наименования тарифных планов
    """
    tps = TariffPlan.objects.filter(
        id__in=ids,
    ).fields(
        tariffs__service_type=1,
        tariffs__title=1,
        tariffs__group=1,
        id=1,
        title=1,
    ).as_pymongo()
    tariffs = {}
    names = {}
    for tp in tps:
        names[tp['_id']] = tp['title']
        tp_data = tariffs.setdefault(tp['_id'], {})
        for t in tp['tariffs']:
            tp_data[str(t['service_type'])] = t
    return tariffs, names


def _get_accruals_of_one(doc_id, account_id, sectors, binds):
    q = Q(doc__id=doc_id, account__id=account_id, is_deleted__ne=True)
    if sectors is not None:
        q &= Q(sector_code__in=sectors)
    if binds:
        q &= Accrual.get_binds_query(binds)
    aa = Accrual.objects.as_pymongo().filter(q)
    for a in aa:
        a['use_penalty'] = [a['settings']['use_penalty']]
        for s in a['services']:
            s['allow_pennies'] = [s.get('allow_pennies', True)]
    return aa


def _get_accruals_of_list(doc_id, accounts, sectors, binds):
    m_query = {
        'account._id': {'$in': accounts},
        'doc._id': doc_id,
        'is_deleted': {'$ne': True},
    }
    if binds:
        m_query.update(Accrual.get_binds_query(binds, raw=True))
    if sectors is not None:
        m_query['sector_code'] = {'$in': sectors}
    a_pipeline = [
        {'$match': m_query},
        {'$project': {
            'services': 1,
            'sector_code': 1,
            'tariff_plan': 1,
            'owner': 1,
        }},
        {'$unwind': '$services'},
        {'$group': {
            '_id': {
                'sector_code': '$sector_code',
                'service_type': '$services.service_type'
            },
            'value': {'$sum': '$services.value'},
            'privileges': {'$sum': '$services.totals.privileges'},
            'recalculations': {'$sum': '$services.totals.recalculations'},
            'shortfalls': {'$sum': '$services.totals.shortfalls'},
            'consumption': {'$sum': '$services.consumption'},
            'tariff': {'$addToSet': '$services.tariff'},
            'tariff_plans': {'$addToSet': '$tariff_plan'},
            'allow_pennies': {'$addToSet': '$services.allow_pennies'},
            'warnings': {'$addToSet': '$services.warnings'},
            'owner': {'$first': '$owner'},
        }},
        {'$group': {
            '_id': '$_id.sector_code',
            'services': {'$push': {
                'service_type': '$_id.service_type',
                'tariff': '$tariff',
                'allow_pennies': '$allow_pennies',
                'consumption': '$consumption',
                'value': '$value',
                'totals': {
                    'privileges': '$privileges',
                    'recalculations': '$recalculations',
                    'shortfalls': '$shortfalls',
                },
                'tariff_plans': '$tariff_plans',
                'warnings': '$warnings',
            }},
            'owner': {'$first': '$owner'},
        }}
    ]
    aa = {a['_id']: a for a in Accrual.objects.aggregate(*a_pipeline)}
    a_pipeline = [
        {'$match': m_query},
        {'$project': {
            'totals': 1,
            'sector_code': 1,
            'settings.use_penalty': 1,
            'owner': 1,
        }},
        {'$group': {
            '_id': '$sector_code',
            'value': {'$sum': '$totals.penalties'},
            'use_penalty': {'$addToSet': '$settings.use_penalty'},
            'owner': {'$first': '$owner'},
        }},
    ]
    pp = list(Accrual.objects.aggregate(*a_pipeline))
    pp = {p['_id']: p for p in pp}
    sectors = set(aa) | set(pp)
    for sector in sectors:
        accrual = aa.get(sector)
        penalty_data = pp.get(sector)
        if not accrual:
            accrual = {
                '_id': sector,
                'services': [],
                'owner': penalty_data['owner'],
            }
            aa[sector] = accrual
        accrual['sector_code'] = sector
        for service in accrual['services']:
            if service.get('warnings'):
                warnings = set()
                for warning in service['warnings']:
                    warnings |= set(warning)
                service['warnings'] = warnings
        penalty_data = pp.get(sector)
        if penalty_data:
            accrual['use_penalty'] = penalty_data['use_penalty']
            accrual['totals'] = {'penalties': penalty_data['value']}
        else:
            accrual['use_penalty'] = False
            accrual['totals'] = {'penalties': 0}
    return list(aa.values())


def _get_services_list(accrual, tariffs, service_titles):
    services = []
    for s in accrual['services']:
        s_id = str(s['service_type'])
        if s_id in tariffs:
            title = tariffs[s_id]['title']
        elif s_id in service_titles[accrual['owner']]:
            title = service_titles[accrual['owner']][s_id]
        elif s_id in service_titles['sys']:
            title = service_titles['sys'][s_id]
        else:
            title = 'неизвестно'
        if isinstance(s['tariff'], list):
            service_tariffs = s['tariff']
        else:
            service_tariffs = s['tariff']
        service = {
            'service_type': s_id,
            'title': title,
            'value': s['value'],
            'privileges': s['totals']['privileges'],
            'recalculations': s['totals']['recalculations'],
            'shortfalls': s['totals']['shortfalls'],
            'tariff': service_tariffs,
            'consumption': s['consumption'],
            'norma': s.get('norma'),
            'allow_pennies': s.get('allow_pennies', True),
            'warnings': [],
        }
        service['total'] = (
                service['value']
                + service['privileges']
                + service['recalculations']
                + service['shortfalls']
        )
        if s.get('warnings'):
            service['warnings'].extend(
                [
                    SERVICE_WARNINGS.get(w)
                    for w in s['warnings']
                ]
            )
        services.append(service)
    return services


def _group_services_by_tariff_groups(services, tariffs):
    groups = {}
    for s in services:
        s_id = str(s['service_type'])
        if s_id in tariffs:
            g_ix = tariffs[s_id]['group']
        else:
            g_ix = 2
        group = groups.setdefault(g_ix, [])
        group.append(s)
    return groups


def _group_services_by_system_services(services, services_tree):
    no_group = []
    sub_groups = {}
    for s_name in SYSTEM_NAMES.keys():
        sub_groups[s_name] = []
    for s in services:
        found = False
        for key in sub_groups:
            if ObjectId(s['service_type']) in services_tree[key]:
                sub_groups[key].append(s)
                found = True
        if not found:
            no_group.append(s)
    grouped_groups = []
    for name, sub_group in sub_groups.items():
        if not sub_group:
            continue
        if len(sub_group) == 1:
            no_group.append(sub_group[0])
        else:
            grouped_groups.append({
                'title': SYSTEM_NAMES[name],
                'service_types': [
                    s['service_type'] for s in sub_group
                ],
                'data': sub_group,
                'total': {
                    'value': sum(s['value'] for s in sub_group),
                    'privileges': sum(
                        s['privileges'] for s in sub_group
                    ),
                    'recalculations': sum(
                        s['recalculations'] for s in sub_group
                    ),
                    'shortfalls': sum(
                        s['shortfalls'] for s in sub_group
                    ),
                    'total': sum(s['total'] for s in sub_group),
                },
            })
    grouped_groups = sorted(
        grouped_groups, key=lambda i: i['title'])
    return {
        'grouped_data': grouped_groups,
        'not_grouped_data': no_group,
        'service_types': [s['service_type'] for s in services]
    }