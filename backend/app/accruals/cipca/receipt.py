from app.accruals.cipca.source_data.vendors import \
    build_vendors_dict
from processing.data_producers.balance.base import HouseAccountsBalance
from processing.models.billing.accrual import Accrual
from processing.models.billing.provider.main import Provider


def get_balance(doc, accounts_ids, date_on, sector):
    """
    Сальдо на дату документа
    """
    balance = HouseAccountsBalance(
        doc.house.id,
        accounts_ids=accounts_ids,
    )
    result = balance.get_date_balance(
        date_on=date_on,
        sectors=[sector],
        use_bank_date=False,
    )
    return result


def cipca_run(accruals, accounts_ids, provider_id, date_on, sectors):
    """
    Запуск обновления суммы на оплату?
    :param accruals: QuerySet
    :param accounts_ids: list
    :param provider_id: ObjectId
    :param date_on: datetime
    :param sectors: list
    :return: -
    """
    balance = get_balance(accounts_ids, provider_id, date_on, sectors)
    for accrual in accruals:
        accrual.update(bill=max(0, accrual.value + max(0, balance)))


def run_accruals(doc, accounts, sector, debit_include, credit_include,
                 force_all_accounts=False):
    """
    Проводит начисления документа, выписывает счёт. Возвращает словари
    начислений, которые были изменены
    """
    changed_accruals = []
    vendors_dict = build_vendors_dict(
        doc.provider,
        doc.house.id,
        doc.date_from,
    )
    accruals = _get_accruals_queryset(doc.pk, sector, accounts)
    if accounts is None:
        all_accounts = True
    elif accounts and len(accounts) <= 10:
        all_accounts = True
    else:
        all_accounts = False
    balance = get_balance(doc, accounts, doc.date, sector)
    for accrual in accruals:
        if not all_accounts and accrual['account']['_id'] not in accounts:
            continue
        account_balance = balance.get(accrual['account']['_id'])
        account_balance = account_balance['val'] if account_balance else 0
        changed = _run_accrual(
            accrual,
            account_balance,
            debit_include,
            credit_include,
            vendors_dict=vendors_dict,
            force=force_all_accounts,
        )
        if changed:
            changed_accruals.append(accrual)
    return changed_accruals


def _run_accrual(accrual, account_balance, debit_include, credit_include,
                 vendors_dict, force=False):
    # value = get_accrual_total_value(
    #     accrual,
    #     False,
    #     auto_denormalize=False,
    # )
    value = accrual['value']
    if debit_include and account_balance > 0:
        value += account_balance
    elif credit_include and account_balance < 0:
        value += account_balance
    value = max(value, 0)
    changed_services = _get_changed_vendor_services(accrual, vendors_dict)
    update_dict = {}
    if changed_services:
        update_dict.update(services=changed_services)
    if accrual.get('bill') != value or force:
        update_dict.update(bill=value)
    if not update_dict:
        return False
    Accrual.objects(pk=accrual['_id']).update(
        **update_dict
    )
    return True


def _get_providers_by_sectors(doc, sector_or_sectors):
    if isinstance(sector_or_sectors, str):
        sectors = [sector_or_sectors]
    else:
        sectors = sector_or_sectors
    sectors_providers = {
        bind.sector_code: bind.provider
        for bind in doc.sector_binds
        if bind.sector_code in sectors
    }
    providers = Provider.objects(
        id__in=list(sectors_providers.values()),
    ).only(
        'str_name',
        'url',
    ).as_pymongo()
    providers = {p['_id']: p for p in providers}
    return {
        sector: providers[provider]
        for sector, provider in sectors_providers.items()
    }


def _get_accruals_queryset(doc_id, sector_or_sectors, accounts):
    if isinstance(sector_or_sectors, list):
        accruals = Accrual.objects(
            doc__id=doc_id,
            sector_code__in=sector_or_sectors
        ).as_pymongo()
    else:
        accruals = Accrual.objects(
            doc__id=doc_id,
            sector_code=sector_or_sectors
        ).as_pymongo()
    if accounts and len(accounts) <= 10:
        accruals = accruals.filter(account__id__in=accounts)
    return accruals


def _get_changed_vendor_services(accrual, vendors_dict):
    if not vendors_dict:
        return None
    changed_services = None
    for service in accrual['services']:
        vendor = vendors_dict.get(
            (
                service['service_type'],
                accrual['account']['area']['_type'][0],
                accrual['account'].get('is_developer') or False,
            ),
        )
        if vendor != service.get('vendor'):
            service['vendor'] = vendor
            changed_services = accrual['services']
    return changed_services
