from app.accruals.pipca.processing import (add_recalculations_values,
                                           calculate_bank_fee,
                                           prepare_document_for_calculation)
from processing.models.choices import (RecalculationReasonType,
                                       SERVICES_GROUPS_CHOICES_DICT)


def recalculation_add_func(author_id, doc_id, accounts_ids, **kwargs):
    doc = prepare_document_for_calculation(
        'recalculation_add',
        author_id,
        doc_id,
        accounts_ids,
    )
    kwargs.pop('doc')
    kwargs.pop('page_url', None)
    add_recalculations_values(
        doc,
        accounts_ids,
        **kwargs
    )
    sector = kwargs['sector']
    calculate_bank_fee(doc, accounts_ids, sector=sector)
    return {'doc': doc}


def recalculation_group_add_func(author_id, doc_id, accounts_ids, **kwargs):
    doc = prepare_document_for_calculation(
        'recalculation_add',
        author_id,
        doc_id,
        accounts_ids,
    )
    group = kwargs.get('group')
    sector = kwargs['sector']
    kwargs.pop('doc')
    kwargs.pop('page_url', None)
    if group is not None:
        groups = [group]
    else:
        groups = set(SERVICES_GROUPS_CHOICES_DICT.keys())
    add_recalculations_values(
        doc,
        accounts_ids,
        groups=groups,
        **kwargs,
    )
    calculate_bank_fee(doc, accounts_ids, sector=sector)
    return {'doc': doc}


def recalculation_remove_func(author_id, doc_id, accounts_ids, **kwargs):
    doc = prepare_document_for_calculation(
        'recalculation_remove',
        author_id,
        doc_id,
        accounts_ids,
    )
    sector = kwargs['sector']
    service_type = kwargs['service_type']
    r_c = 0
    for account in accounts_ids:
        debt = doc.accounts[account]['debts'].get(sector)
        if debt:
            r_c += debt.remove_recalculations(
                service_type, RecalculationReasonType.MANUAL)
    if r_c == 0:
        for account in accounts_ids:
            if not doc.accounts.get(account):
                continue
            debt = doc.accounts[account]['debts'].get(sector)
            if debt:
                r_c += debt.remove_recalculations(service_type, None)
    calculate_bank_fee(doc, accounts_ids, sector=sector)
    return {'doc': doc}
