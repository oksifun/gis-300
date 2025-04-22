from app.accruals.pipca.processing import (
    add_recalculations_values,
    calculate_bank_fee,
    prepare_document_for_calculation
)
from processing.models.choices import SERVICES_GROUPS_CHOICES_DICT


def shortfall_add_func(author_id, doc_id, accounts_ids, **kwargs):
    doc = prepare_document_for_calculation(
        'shortfall_add',
        author_id,
        doc_id,
        accounts_ids,
    )
    sector = kwargs['sector']
    kwargs.pop('doc')
    kwargs.pop('page_url', None)
    add_recalculations_values(
        doc,
        accounts_ids,
        shortfall=True,
        **kwargs
    )
    calculate_bank_fee(doc, accounts_ids, sector=sector)
    return {'doc': doc}


def shortfall_group_add_func(author_id, doc_id, accounts_ids, **kwargs):
    doc = prepare_document_for_calculation(
        'shortfall_group_add',
        author_id,
        doc_id,
        accounts_ids,
    )
    group = kwargs.get('group')
    sector = kwargs['sector']
    if group is not None:
        groups = [group]
    else:
        groups = set(SERVICES_GROUPS_CHOICES_DICT.keys())
    kwargs.pop('doc')
    kwargs.pop('page_url', None)
    add_recalculations_values(
        doc,
        accounts_ids,
        groups=groups,
        shortfall=True,
        **kwargs,
    )
    calculate_bank_fee(doc, accounts_ids, sector=sector)
    return {'doc': doc}


def shortfall_remove_func(author_id, doc_id, accounts_ids, **kwargs):
    doc = prepare_document_for_calculation(
        'tariff_plan_apply',
        author_id,
        doc_id,
        accounts_ids,
    )
    sector = kwargs['sector']
    service_type = kwargs['service_type']
    for account in accounts_ids:
        if not doc.accounts.get(account):
            continue
        debt = doc.accounts[account]['debts'].get(sector)
        if debt and service_type in debt.services_dict:
            debt.services_dict[service_type] = []
    calculate_bank_fee(doc, accounts_ids, sector=sector)
    return {'doc': doc}
