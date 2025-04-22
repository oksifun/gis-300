from app.accruals.pipca.document import CalculatorError
from app.accruals.pipca.penalties import PenisStructure
from app.accruals.pipca.processing import (calculate_bank_fee,
                                           prepare_document_for_calculation)
from processing.models.billing.accrual import Accrual, AccrualDocumentStatus


def recalculate_penalties(author_id, doc_id, accounts_ids, sector, doc=None):
    if not doc:
        doc = prepare_document_for_calculation(
            'recalculate_penalties',
            author_id,
            doc_id,
            accounts_ids,
        )
    if accounts_ids is None:
        accounts_ids = doc.get_accounts_list()
    punishable_accounts = doc.get_only_punishable_accounts(accounts_ids, sector)
    penalties = PenisStructure(
        provider_id=doc.doc_m.provider,
        sector=sector,
        debt_document=doc,
        accounts=punishable_accounts,
    )
    if not doc.check_offsets(penalties):
        raise CalculatorError(doc.offsets_fail_message)
    settings = None
    for s_b in doc.doc_m.sector_binds:
        if s_b.sector_code == sector:
            settings = s_b.settings
    if settings and settings.include_penalty:
        only_paid = False
        for s_s in doc.house.settings[sector].sectors:
            if s_s.sector_code == sector:
                only_paid = s_s.pennies.tracking == 'after_payment'
                break
        if only_paid:
            penalties.set_after_pay_setting()
        penalties.prepare_cutting()
        penalties.prepare_accounts_data()
        for account in accounts_ids:
            if not doc.accounts.get(account):
                continue
            debt = doc.accounts[account]['debts'].get(sector)
            if debt:
                doc.calculate_penalty(debt, penalties, only_paid)
    else:
        for account in accounts_ids:
            debt = doc.accounts[account]['debts'].get(sector)
            if debt:
                debt.changed = True
                debt.doc_m['penalties'] = []
    calculate_bank_fee(doc, accounts_ids, sector=sector)
    return {'doc': doc}


def manual_penalty_set_func(author_id, doc_id, account_id, **kwargs):
    doc = prepare_document_for_calculation(
        'manual_penalty_set',
        author_id,
        doc_id,
        [account_id],
    )
    penalties_table = kwargs['penalties_table']
    sector = kwargs['sector']
    debt = doc.accounts[account_id]['debts'].get(sector)
    if debt:
        debt.doc_m['penalties'] = []
        for value in penalties_table:
            found = None
            for e_value in debt.doc_m['penalties']:
                if e_value['period'] == value['period']:
                    found = e_value
            if not found:
                found = dict(period=value['period'],
                             value=0,
                             value_include=0,
                             value_return=0)
                debt.doc_m['penalties'].append(found)
            for k in ['value', 'value_include', 'value_return']:
                found[k] += round(value[k] * 100)
        debt.changed = True
        calculate_bank_fee(doc, [account_id], sector=sector)
    return {'doc': doc}


def penalty_settings_func(author_id, doc_id, **kwargs):
    doc = prepare_document_for_calculation(
        'penalty_settings',
        author_id,
        doc_id,
    )
    sector = kwargs['sector']
    for s_b in doc.doc_m.sector_binds:
        if s_b.sector_code == sector:
            s_b.settings.debt_penalty_date = kwargs['debt_penalty_date']
            s_b.settings.penalty_till = kwargs['penalty_till']
            s_b.settings.include_penalty = kwargs['include_penalty']
            if 'old_period_penalty_refund' in kwargs:
                s_b.settings.old_period_penalty_refund = \
                    kwargs['old_period_penalty_refund']
            doc.updated = True
    accounts = doc.get_accounts_list()
    return recalculate_penalties(author_id, doc_id, accounts, sector, doc=doc)


def change_penalty_include_settings_func(doc_id, accounts, **kwargs):
    sector = kwargs['sector']
    services_allow_pennies = kwargs['services_allow_pennies']
    use_p = kwargs.get('use_penalty')
    query = {
        'doc._id': doc_id,
        'sector_code': sector
    }
    if len(accounts) < 20:
        query['account._id'] = {'$in': accounts}
    accruals = Accrual.objects(
        __raw__=query,
    ).only(
        'id',
        'account.id',
        'settings',
        'services',
    ).as_pymongo()
    a_p_dict = {
        a_p['service_type']: a_p['value']
        for a_p in services_allow_pennies
        if a_p.get('value', None) is not None
    }
    for accrual in accruals:
        if accrual['account']['_id'] not in accounts:
            continue
        upd_dict = {}
        if use_p is not None:
            if use_p != accrual['settings']['use_penalty']:
                upd_dict['settings.use_penalty'] = use_p
        for ix, service in enumerate(accrual['services']):
            if service['service_type'] in a_p_dict:
                upd_dict[f'services.{ix}.allow_pennies'] = \
                    a_p_dict[service['service_type']]
        if upd_dict:
            Accrual.objects(
                pk=accrual['_id'],
            ).update(
                __raw__={'$set': upd_dict},
            )


def remove_penalty_func(author_id, doc_id, account_id, sector):
    doc = prepare_document_for_calculation(
        'remove_penalty',
        author_id,
        doc_id,
        [account_id],
    )
    debt = doc.accounts[account_id]['debts'].get(sector)
    if debt:
        debt.doc_m['penalties'] = []
        debt.changed = True
        calculate_bank_fee(doc, [account_id], sector=sector)
    return {'doc': doc}
