from app.accruals.pipca.accrual import float_to_kopeks
from app.accruals.pipca.processing import (
    calculate_bank_fee,
    normalize_accrual_values,
    prepare_document_for_calculation
)
from app.personnel.models.personnel import Worker
from processing.models.billing.accrual import ConsumptionType
from app.accruals.models.accrual_document import AccrualDocTotalEmbedded, \
    PublicCommunalRecalculationEmbedded


def manual_accrual_set_func(author_id, doc_id, account_id, sector,
                            services_table):
    doc = prepare_document_for_calculation(
        'manual_accrual_set',
        author_id,
        doc_id,
        [account_id],
    )
    # сохраним значения ручного ввода в соответствующее начисление
    debt = doc.accounts[account_id]['debts'].get(sector)
    if not debt:
        return {'doc': doc}
    for s_values in services_table:
        service_id = s_values['service_type']
        normalize_accrual_values(s_values)
        if service_id not in debt.services_dict:
            continue
        service = debt.services_dict[service_id]
        service['value'] = float_to_kopeks(s_values['value'] / 100)
        if abs(service['consumption'] - s_values['consumption']) > 0.00005:
            service['consumption'] = s_values['consumption']
        if service['totals']['recalculations'] != s_values['recalculation']:
            debt.set_recalculation_value(
                service_id,
                float_to_kopeks(s_values['recalculation'] / 100),
            )
        if service['totals']['shortfalls'] != s_values['shortfall']:
            debt.set_shortfall_value(
                service_id,
                float_to_kopeks(s_values['shortfall'] / 100),
            )
        if (
                (
                        service['totals']['privileges']
                        + service['totals']['privileges_info']
                )
                != s_values['privilege']
        ):
            debt.set_privilege_value(
                service_id,
                float_to_kopeks(s_values['privilege'] / 100),
            )
    debt.changed = True
    calculate_bank_fee(doc, [account_id], sector=sector)
    return {'doc': doc}


def manual_service_set_func(author_id, doc_id, **kwargs):
    accounts_table = kwargs['accounts_table']
    sector = kwargs['sector']
    service_type = kwargs['service_type']
    accounts = [a['account'] for a in accounts_table]
    doc = prepare_document_for_calculation(
        'manual_service_set',
        author_id,
        doc_id,
        accounts,
    )
    # сохраним значения ручного ввода в соответствующее начисление
    for a_values in accounts_table:
        debt = doc.accounts[a_values['account']]['debts'].get(sector)
        if not debt:
            continue
        if service_type not in debt.services_dict:
            continue
        debt.services_dict[service_type]['value'] = \
            float_to_kopeks(a_values['value'])
        if (
                debt.services_dict[service_type]['totals']['recalculations']
                != float_to_kopeks(a_values['recalculation'])
        ):
            debt.set_recalculation_value(
                service_type,
                float_to_kopeks(a_values['recalculation']),
            )
        if (
                debt.services_dict[service_type]['totals']['shortfalls']
                != float_to_kopeks(a_values['shortfall'])
        ):
            debt.set_shortfall_value(
                service_type,
                float_to_kopeks(a_values['shortfall']),
            )
        if (
                debt.services_dict[service_type]['totals']['privileges']
                != float_to_kopeks(a_values['privilege'])
        ):
            debt.set_privilege_value(
                service_type,
                float_to_kopeks(a_values['privilege']),
            )
        debt.changed = True
    calculate_bank_fee(doc, accounts, sector=sector)
    return {'doc': doc}


def manual_recalculation_set_func(author_id, doc_id, account_id, **kwargs):
    doc = prepare_document_for_calculation(
        'manual_recalculation_set',
        author_id,
        doc_id,
        [account_id],
    )
    sector = kwargs['sector']
    service_type = kwargs['service_type']
    recalc_table = kwargs['recalculations_table']
    debt = doc.accounts[account_id]['debts'].get(sector)
    if debt:
        debt.set_recalculation_value(service_type, 0)
        for value in recalc_table:
            debt.add_recalculation(
                service_type,
                float_to_kopeks(value['value']),
                value['reason'],
                value.get('date_from', None),
                value.get('date_till', None),
                value.get('consumption_type',
                          ConsumptionType.METER_WO) or ConsumptionType.METER_WO,
            )
        debt.changed = True
        calculate_bank_fee(doc, [account_id], sector=sector)
    return {'doc': doc}


def manual_privilege_set_func(author_id, doc_id, account_id, **kwargs):
    doc = prepare_document_for_calculation(
        'manual_privilege_set',
        author_id,
        doc_id,
        [account_id],
    )
    privileges_table = kwargs['privileges_table']
    sector = kwargs['sector']
    service_type = kwargs['service_type']
    debt = doc.accounts[account_id]['debts'].get(sector)
    if debt:
        debt.set_privilege_value(service_type, 0)
        for value in privileges_table:
            debt.add_privilege(
                service_type,
                float_to_kopeks(value['value']),
                value.get('tenant', None),
                value.get('category', None),
                value['is_info'],
            )
        debt.changed = True
        calculate_bank_fee(doc, [account_id], sector=sector)
    return {'doc': doc}


def manual_totals_set_func(author_id, doc_id, **kwargs):
    doc = prepare_document_for_calculation(
        'manual_totals_set',
        author_id,
        doc_id,
    )
    super_account = kwargs['super_account']
    totals_table = kwargs['totals_table']
    if super_account:
        user = Worker.objects(pk=author_id).get()
        doc.user = user
    else:
        doc.worker = author_id
    doc.add_log_action(doc.__class__.__name__, [])
    doc.doc_m.totals = []
    for value in totals_table:
        doc.doc_m.totals.append(AccrualDocTotalEmbedded(**value))
    doc.updated = True
    return {'doc': doc}


def manual_public_communal_set_func(author_id, doc_id, public_consumptions,
                                    **kwargs):
    doc = prepare_document_for_calculation(
        'manual_public_communal_set',
        author_id,
        doc_id,
    )
    doc.add_log_action(doc.__class__.__name__, [])
    origin_data = {}
    for value in doc.doc_m.public_communal_recalculations:
        if value.consumption == 0:
            continue
        key = (value.month, value.resource)
        origin_data[key] = [
            value.value / value.consumption,
            value.included,
            value.tariffs,
        ]
    doc.doc_m.public_communal_recalculations = []
    for value in public_consumptions:
        key = (value['month'], value['resource'])
        if key in origin_data:
            value['value'] = value['consumption'] * origin_data[key][0]
            value['included'] = origin_data[key][1]
            value['tariffs'] = origin_data[key][2]
        doc.doc_m.public_communal_recalculations.append(
            PublicCommunalRecalculationEmbedded(**value),
        )
    doc.updated = True
    return {'doc': doc}
