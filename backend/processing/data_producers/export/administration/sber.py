from dateutil.relativedelta import relativedelta

from app.bankstatements.models.bankstatement_doc import BankStatementDoc
from processing.data_producers.export.administration.clients_lists import \
    _get_responsibles
from processing.data_producers.export.administration.base import \
    _get_print_services, _has_print_service, _get_gis_services
from app.accruals.models.accrual_document import AccrualDoc
from processing.models.billing.emailcachediddaily import EmailCachedIdDaily
from processing.models.billing.payment import PaymentDoc
from processing.models.billing.provider.main import Provider
from utils.crm_utils import get_crm_client_ids


def get_clients_sber_stats(date, logger=None, table_print=None):
    clients_ids, providers = _get_providers()
    if logger:
        logger(
            '1. те у кого нет начислений (это всякие там те кто находится на '
            'обслуживании РЦ, т. е. платежных агентов) - с ними ничего не '
            'надо делать'
        )
    _get_no_accruals(
        clients_ids,
        providers,
        table_print,
    )
    if logger:
        logger('')
        logger(
            '2. те кто на текущий момент работают через УПШ (есть реестр за '
            '10.03.2021)'
        )
    _get_sber_with_upsh(
        date,
        clients_ids,
        providers,
        table_print,
    )


def _get_no_accruals(clients_ids, providers, table_print):
    title_row = [
        'Наименование',
        'ИНН',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    ids = AccrualDoc.objects(
        provider__in=list(clients_ids),
    ).distinct(
        'provider',
    )
    ids = set(clients_ids) - set(ids)
    providers = providers.filter(
        id__in=list(ids),
    )
    for provider in providers:
        row = [
            provider.get('inn') or '',
            provider['str_name'],
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result


def _get_sber_with_upsh(date, clients_ids, providers, table_print):
    title_row = [
        'Наименование',
        'ИНН',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    ids = PaymentDoc.objects(
        provider__in=clients_ids,
        _type='SberDoc',
        date__gte=date,
        date__lt=date + relativedelta(days=1),
        parent='SbolInRegistry',
    ).distinct(
        'provider',
    )
    ids = [i.id for i in ids]
    providers = providers.filter(
        id__in=ids,
    )
    for provider in providers:
        row = [
            provider.get('inn') or '',
            provider['str_name'],
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result


def get_clients_sber_registry_stats(period, date,
                                    logger=None, table_print=None):
    if logger:
        logger(
            '3. те у кого есть начисления за февраль 2021, нет реестра '
            'УПШ за 10.03.2021'
        )
        logger(
            '3.1. те кто грузит выписку, т. е. есть выписка за 09.03 или 10.03'
        )
    clients_ids, providers = _get_providers()
    if logger:
        logger('')
        logger(
            '3.1.1. те у кого есть реестры Сбербанка, '
            'загруженные вручную за 9.03 или 10.03 - '
            'исключаем их из группы риска, они перестроились'
        )
    ids = _get_sber_with_bank_not_upsh(
        period,
        date,
        clients_ids,
        providers,
        table_print,
    )
    to_exclude = set(ids)
    if logger:
        logger('')
        logger(
            '3.1.2. те у кого нет реестров Сбербанка и есть единичные '
            'платежные поручения - условие то они перешли на единичные платежки'
        )
    ids = _get_sber_with_bank_no_reg_has_pays(
        period,
        date,
        clients_ids,
        providers,
        table_print,
    )
    to_exclude |= set(ids)
    if logger:
        logger('')
        logger('3.1.3. те кто не вошел в 3.1.1. и 3.1.2. - это группа риска')
    _get_sber_exclude(
        period,
        date,
        to_exclude,
        clients_ids,
        providers,
        table_print,
    )


def _get_sber_with_bank_not_upsh(period, date, clients_ids, providers, table_print):
    title_row = [
        'Наименование',
        'ИНН',
        'количество ЛС',
        'грузят ли выписку',
        'на печати квитанций',
    ]
    result = [
        title_row,
    ]
    print_services = _get_print_services()
    if table_print:
        table_print(';'.join(result[0]))
    ids = PaymentDoc.objects(
        provider__in=clients_ids,
        _type='SberDoc',
        date__gte=date,
        parent='SbolInRegistry',
    ).distinct(
        'provider',
    )
    clients_ids = set(clients_ids) - {i.id for i in ids}
    ids = AccrualDoc.objects(
        provider__in=list(clients_ids),
        date_from__gte=period,
    ).distinct(
        'provider',
    )
    ids = BankStatementDoc.objects(
        provider__in=ids,
        date__gte=date,
    ).distinct(
        'provider',
    )
    ids = PaymentDoc.objects(
        provider__in=ids,
        _type='SberDoc',
        date__gte=date,
        parent='ManualRegistryTask',
    ).distinct(
        'provider',
    )
    ids = [i.id for i in ids]
    providers = providers.filter(
        id__in=ids,
    )
    for provider in providers:
        has_print_service = _has_print_service(provider['_id'], print_services)
        responsibles = _get_responsibles(provider['_id'], date)
        row = [
            provider.get('inn') or '',
            provider['str_name'],
            str(len(responsibles)),
            'да',
            'да' if has_print_service else 'нет',
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return ids


def _get_sber_with_bank_no_reg_has_pays(period, date, clients_ids, providers,
                                        table_print):
    title_row = [
        'Наименование',
        'ИНН',
        'количество ЛС',
        'грузят ли выписку',
        'на печати квитанций',
    ]
    result = [
        title_row,
    ]
    print_services = _get_print_services()
    if table_print:
        table_print(';'.join(result[0]))
    ids = PaymentDoc.objects(
        provider__in=clients_ids,
        _type='SberDoc',
        date__gte=date,
        parent='SbolInRegistry',
    ).distinct(
        'provider',
    )
    clients_ids = set(clients_ids) - {i.id for i in ids}
    ids = AccrualDoc.objects(
        provider__in=list(clients_ids),
        date_from__gte=period,
    ).distinct(
        'provider',
    )
    ids = BankStatementDoc.objects(
        provider__in=ids,
        date__gte=date,
    ).distinct(
        'provider',
    )
    ids = PaymentDoc.objects(
        provider__in=ids,
        _type='SberDoc',
        date__gte=date,
    ).distinct(
        'provider',
    )
    clients_ids = set(clients_ids) - {i.id for i in ids}
    ids = PaymentDoc.objects(
        provider__in=clients_ids,
        _type='ManualDoc',
        bank='54cb2543f3b7d455bbabd32c',
        date__gte=date,
    ).distinct(
        'provider',
    )
    providers = providers.filter(
        id__in=[i.id for i in ids],
    )
    for provider in providers:
        has_print_service = _has_print_service(provider['_id'], print_services)
        responsibles = _get_responsibles(provider['_id'], date)
        row = [
            provider.get('inn') or '',
            provider['str_name'],
            str(len(responsibles)),
            'да',
            'да' if has_print_service else 'нет',
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return ids


def _get_sber_exclude(period, date, exclude_ids, clients_ids, providers,
                      table_print):
    title_row = [
        'Наименование',
        'ИНН',
        'количество ЛС',
        'грузят ли выписку',
        'на печати квитанций',
    ]
    result = [
        title_row,
    ]
    print_services = _get_print_services()
    if table_print:
        table_print(';'.join(result[0]))
    ids = PaymentDoc.objects(
        provider__in=clients_ids,
        _type='SberDoc',
        date__gte=date,
        parent='SbolInRegistry',
    ).distinct(
        'provider',
    )
    clients_ids = set(clients_ids) - {i.id for i in ids}
    ids = AccrualDoc.objects(
        provider__in=list(clients_ids),
        date_from__gte=period,
    ).distinct(
        'provider',
    )
    ids = BankStatementDoc.objects(
        provider__in=ids,
        date__gte=date,
    ).distinct(
        'provider',
    )
    ids = set(ids) - set(exclude_ids)
    providers = providers.filter(
        id__in=ids,
    )
    for provider in providers:
        has_print_service = _has_print_service(provider['_id'], print_services)
        responsibles = _get_responsibles(provider['_id'], date)
        row = [
            provider.get('inn') or '',
            provider['str_name'],
            str(len(responsibles)),
            'да',
            'да' if has_print_service else 'нет',
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return ids


def get_clients_sber_no_bank_stats(period, date,
                                   logger=None, table_print=None):
    if logger:
        logger(
            '3. те у кого есть начисления за февраль 2021, нет реестра '
            'УПШ за 10.03.2021'
        )
        logger(
            '3.2. те у кого нет выписки за 09.03 или 10.03'
        )
    clients_ids, providers = _get_providers()
    if logger:
        logger('')
        logger(
            '3.2.1. у кого есть реестры Сбера, загруженные вручную - это не '
            'группа риска'
        )
    _get_sber_no_bank_not_upsh(
        period,
        date,
        clients_ids,
        providers,
        table_print,
    )
    if logger:
        logger('')
        logger(
            '3.2.2. у кого нет реестров сбера совсем - это группа риска'
        )
    _get_sber_no_bank_no_reg(
        period,
        date,
        clients_ids,
        providers,
        table_print,
    )


def _get_sber_no_bank_not_upsh(period, date, clients_ids, providers,
                               table_print):
    title_row = [
        'Наименование',
        'ИНН',
        'количество ЛС',
        'грузят ли выписку',
        'на печати квитанций',
    ]
    result = [
        title_row,
    ]
    print_services = _get_print_services()
    if table_print:
        table_print(';'.join(result[0]))
    ids = PaymentDoc.objects(
        provider__in=clients_ids,
        _type='SberDoc',
        date__gte=date,
        parent='SbolInRegistry',
    ).distinct(
        'provider',
    )
    clients_ids = set(clients_ids) - {i.id for i in ids}
    clients_ids = AccrualDoc.objects(
        provider__in=list(clients_ids),
        date_from__gte=period,
    ).distinct(
        'provider',
    )
    ids = BankStatementDoc.objects(
        provider__in=clients_ids,
        date__gte=date,
    ).distinct(
        'provider',
    )
    clients_ids = set(clients_ids) - set(ids)
    ids = PaymentDoc.objects(
        provider__in=clients_ids,
        _type='SberDoc',
        date__gte=date,
        parent='ManualRegistryTask',
    ).distinct(
        'provider',
    )
    ids = [i.id for i in ids]
    providers = providers.filter(
        id__in=ids,
    )
    for provider in providers:
        has_print_service = _has_print_service(provider['_id'], print_services)
        responsibles = _get_responsibles(provider['_id'], date)
        row = [
            provider.get('inn') or '',
            provider['str_name'],
            str(len(responsibles)),
            'нет',
            'да' if has_print_service else 'нет',
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return ids


def get_sber_total_stats(date, table_print):
    title_row = [
        'ИНН',
        'Наименование',
        'Кол-во ЛС',
        'На печати квитанций (да/нет)',
        'ГИС (да/нет)',
        'Реестры УПШ',
        'Реестры своего СББОЛ',
        'Единичные платежные поручения',
        'Грузят выписку',
        'Автоматическая выписка',
    ]
    result = [
        title_row,
    ]
    print_services = _get_print_services()
    gis_services = _get_gis_services()
    if table_print:
        table_print(';'.join(result[0]))
    _, providers = _get_providers()
    date_lt = date + relativedelta(days=1)
    for provider in providers:
        stats = get_provider_sber_stats(
            provider_id=provider['_id'],
            date_on=date,
            date_gte=date,
            date_lt=date_lt,
            print_services=print_services,
            gis_services=gis_services,
        )
        row = [
            provider.get('inn') or '',
            provider['str_name'],
            str(len(stats['responsibles'])),
            _bool_to_str(stats['has_print_service']),
            _bool_to_str(stats['has_gis_service']),
            _bool_to_str(stats['has_upsh_reg']),
            _bool_to_str(stats['has_own_reg']),
            _bool_to_str(stats['has_sber_pay']),
            _bool_to_str(stats['has_bank_statement']),
            _bool_to_str(stats['has_email_bank_statement']),
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result


def get_provider_sber_stats(provider_id, date_on, date_gte, date_lt,
                             print_services=None, gis_services=None):
    result = {}
    result['has_upsh_reg'] = PaymentDoc.objects(
        provider=provider_id,
        date__gte=date_gte,
        date__lt=date_lt,
        is_deleted__ne=True,
        _type='SberDoc',
        parent='SbolInRegistry',
    ).only('id').as_pymongo().first()
    result['has_own_reg'] = PaymentDoc.objects(
        provider=provider_id,
        date__gte=date_gte,
        date__lt=date_lt,
        is_deleted__ne=True,
        _type='SberDoc',
        parent='ManualRegistryTask',
    ).only('id').as_pymongo().first()
    result['has_sber_pay'] = PaymentDoc.objects(
        provider=provider_id,
        date__gte=date_gte,
        date__lt=date_lt,
        is_deleted__ne=True,
        _type='ManualDoc',
        bank='54cb2543f3b7d455bbabd32c',
    ).only('id').as_pymongo().first()
    result['has_bank_statement'] = BankStatementDoc.objects(
        provider=provider_id,
        date_receipt__gte=date_gte,
        date_receipt__lt=date_lt,
    ).only('id').as_pymongo().first()
    result['has_email_bank_statement'] = EmailCachedIdDaily.objects(
        provider=provider_id,
    ).only('id').as_pymongo().first()
    if print_services:
        result['has_print_service'] = \
            _has_print_service(provider_id, print_services)
    if gis_services:
        result['has_gis_service'] = \
            _has_print_service(provider_id, gis_services)
    result['responsibles'] = _get_responsibles(provider_id, date_on)
    return result


def _bool_to_str(val):
    return 'да' if val else 'нет'


def _get_sber_no_bank_no_reg(period, date, clients_ids, providers,
                             table_print):
    title_row = [
        'Наименование',
        'ИНН',
        'количество ЛС',
        'грузят ли выписку',
        'на печати квитанций',
    ]
    result = [
        title_row,
    ]
    print_services = _get_print_services()
    if table_print:
        table_print(';'.join(result[0]))
    ids = PaymentDoc.objects(
        provider__in=clients_ids,
        _type='SberDoc',
        date__gte=date,
        parent='SbolInRegistry',
    ).distinct(
        'provider',
    )
    clients_ids = set(clients_ids) - {i.id for i in ids}
    clients_ids = AccrualDoc.objects(
        provider__in=list(clients_ids),
        date_from__gte=period,
    ).distinct(
        'provider',
    )
    ids = BankStatementDoc.objects(
        provider__in=clients_ids,
        date__gte=date,
    ).distinct(
        'provider',
    )
    clients_ids = set(clients_ids) - set(ids)
    ids = PaymentDoc.objects(
        provider__in=clients_ids,
        _type='SberDoc',
        date__gte=date,
    ).distinct(
        'provider',
    )
    ids = set(clients_ids) - {i.id for i in ids}
    providers = providers.filter(
        id__in=ids,
    )
    for provider in providers:
        has_print_service = _has_print_service(provider['_id'], print_services)
        responsibles = _get_responsibles(provider['_id'], date)
        row = [
            provider.get('inn') or '',
            provider['str_name'],
            str(len(responsibles)),
            'нет',
            'да' if has_print_service else 'нет',
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return ids


def _get_client_print_stat(date, period, clients_ids, providers, table_print):
    title_row = [
        'Наименование',
        'ИНН',
        'количество ЛС',
        'грузят ли выписку',
        'на печати квитанций',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    print_services = _get_print_services()
    ids = PaymentDoc.objects(
        provider__in=clients_ids,
        _type='SberDoc',
        date__gte=date,
    ).distinct(
        'provider',
    )
    ids = [i.id for i in ids]
    clients_ids = set(clients_ids) - set(ids)
    clients_ids = PaymentDoc.objects(
        provider__in=list(clients_ids),
        _type='SberDoc',
        date__lt=date,
        parent='SbolInRegistry',
    ).distinct(
        'provider',
    )
    clients_ids = [i.id for i in clients_ids]
    providers = providers.filter(
        id__in=list(clients_ids),
    )
    with_bank = BankStatementDoc.objects(
        provider__in=list(clients_ids),
        date__gte=period,
    ).distinct(
        'provider',
    )
    for provider in providers:
        has_print_service = _has_print_service(provider['_id'], print_services)
        responsibles = _get_responsibles(provider['_id'], date)
        has_bank = provider['_id'] in with_bank
        row = [
            provider.get('inn') or '',
            provider['str_name'],
            str(len(responsibles)),
            'да' if has_bank else 'нет',
            'да' if has_print_service else 'нет',
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result


def _get_providers():
    clients_ids = get_crm_client_ids()
    return (
        clients_ids,
        Provider.objects(
            __raw__={
                '_id': {'$in': clients_ids},
            },
        ).only(
            'id',
            'inn',
            'str_name',
        ).order_by(
            '-str_name',
        ).as_pymongo(),
    )


def _get_sber_no_reg_with_bank(period, clients_ids, providers, table_print):
    title_row = [
        'Наименование',
        'ИНН',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    ids = PaymentDoc.objects(
        provider__in=clients_ids,
        _type='SberDoc',
        date__gte=period,
    ).distinct(
        'provider',
    )
    clients_ids = set(clients_ids) - {i.id for i in ids}
    ids = BankStatementDoc.objects(
        provider__in=list(clients_ids),
        date__gte=period,
    ).distinct(
        'provider',
    )
    clients_ids = set(clients_ids) & set(ids)
    ids = AccrualDoc.objects(
        provider__in=list(clients_ids),
        date_from__gte=period,
    ).distinct(
        'provider',
    )
    providers = providers.filter(
        id__in=ids,
    )
    for provider in providers:
        row = [
            provider.get('inn') or '',
            provider['str_name'],
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result


def _get_sber_online_clients(date_from, table_print=None):
    title_row = [
        'Наименование',
        'ИНН',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    providers = PaymentDoc.objects(
        _type='SberDoc',
        parent='SbolInRegistry',
        date__gte=date_from,
    ).distinct(
        'provider',
    )

    for provider in providers:
        row = [provider.str_name, provider.inn or '']
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result

