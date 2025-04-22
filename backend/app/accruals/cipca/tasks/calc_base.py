from dateutil.relativedelta import relativedelta
from mongoengine import Q

from app.accruals.cipca.caching.doc_sevice_groups import \
    SERVICE_GROUP_CACHE_FUNCS
from app.accruals.pipca.processing import (calculate_bank_fee,
                                           get_sector_binds,
                                           prepare_document_for_calculation)
from app.accruals.pipca.document import (PipcaDocument,
                                         TariffPlanServicesDuplicateError,
                                         CalculatorError)
from app.house.models.house import House
from app.personnel.models.personnel import Worker
from lib.dates import start_of_month, end_of_month, start_of_day
from processing.models.billing.accrual import Accrual
from app.accruals.models.accrual_document import AccrualDoc
from processing.models.billing.responsibility import Responsibility
from processing.models.choices import AccrualDocumentType


_MONTH_DOC_TYPES = (AccrualDocumentType.PER, AccrualDocumentType.ADV)


class EmptyDocIsNotAllowed(CalculatorError):
    pass


def create_accrual_doc_func(doc_id, accounts_ids, user, allow_empty_doc=True,
                            **kwargs):
    if doc_id:
        doc = AccrualDoc.objects(pk=doc_id).get()
        params = {
            'type': doc.document_type,
            'month': start_of_month(doc.date_from),
            'date': doc.date,
            'date_from': doc.date_from,
            'date_till': doc.date_till,
            'house': doc.house.id,
            'provider': doc.provider,
        }
    else:
        params = {}
    for k, v in kwargs.items():
        params[k] = v
    if params['type'] not in _MONTH_DOC_TYPES:
        params['date_from'] = start_of_month(params['month'])
        params['date_till'] = end_of_month(params['month'])
    house = House.objects(id=params['house']).only('address').get()
    accounts = _filter_responsible_tenants(
        house_id=params['house'],
        tenants_ids=accounts_ids,
        date_from=params['date_from'],
        date_till=params['date_till'],
    )
    if params['type'] == AccrualDocumentType.MAIN:
        query = {
            'account._id': {'$in': accounts},
            'month': params['month'],
            'is_deleted': {'$ne': True},
        }
        exist_docs = Accrual.objects(__raw__=query).distinct('doc._id')
        if exist_docs:
            exist_docs_types = AccrualDoc.objects(
                id__in=exist_docs).distinct('type')
            if AccrualDocumentType.MAIN in exist_docs_types:
                msg = f'По указанным лицевым счетам уже создан '\
                      f'документ начислений {house.address}'
                if not allow_empty_doc:
                    raise EmptyDocIsNotAllowed(msg)
                return {
                    'warnings': msg,
                    'status': 'failed'
                }

    # получаем провайдров, привязанных к дому
    sector_binds = get_sector_binds(
        provider_id=params['provider'],
        house_id=params['house'],
        month=params['month'],
        sectors=params.get('sectors') or [],
        document_type=params['type']
    )
    if sector_binds['status'] == 200:
        params['sector_binds'] = sector_binds['result']
    else:
        return {'warnings': sector_binds['result']}
    # считаем начисления
    try:
        user = Worker.objects(pk=user).get()
        for key in ('month', 'sectors', 'filter'):
            params.pop(key, None)
        doc = PipcaDocument.create_new(
            params,
            accounts,
            user,
            updated_doc=doc_id,
        )
    except TariffPlanServicesDuplicateError:
        return {
            'warnings': f'Выбранный тарифный план содержит дубли тарифов, '
                        f'его нельзя использовать в расчёте ({house.address}).'
        }
    if not len(accounts):
        if not allow_empty_doc:
            raise EmptyDocIsNotAllowed('Не найдено ни одного лицевого счёта')
        return {
            'warnings': f'Не найдено ни одного лицевого счёта. Созданный '
                        f'документ начислений пуст ({house.address}).',
        }
    elif doc.offsets_fail_message:
        return {
            'warnings': f'Документ успешно создан, '
                        f'но возникли проблемы ({house.address}): '
                        f'<br>{doc.offsets_fail_message}',
            'doc': doc,
        }
    return {
        'result': 'Документ успешно создан',
        'doc': doc,
    }


def _filter_responsible_tenants(house_id, tenants_ids, date_from, date_till):
    filter_query = (
            (
                    Q(date_till=None)
                    | Q(date_till__gte=date_from)

            )
            & (
                    Q(date_from=None)
                    | Q(
                            date_from__lt=start_of_day(
                                date_till
                                + relativedelta(days=1)
                            )
                    )
            )
    )
    if tenants_ids is None:
        queryset = Responsibility.objects(account__area__house__id=house_id)
    else:
        queryset = Responsibility.objects(account__id__in=tenants_ids)
    queryset = queryset.filter(filter_query).only('account.id').as_pymongo()
    return list({r['account']['_id'] for r in queryset})


def copy_accrual_doc_func(author_id, doc_id, date, month):
    user = Worker.objects(pk=author_id).get()
    new_doc = PipcaDocument.create_by_copying(doc_id, date, month, user)
    new_doc.save(is_copy=True)
    new_doc.add_log_action(new_doc.__class__.__name__,
                           new_doc.get_accounts_list())


def tariff_plan_apply_func(author_id, doc_id, accounts_ids, sector,
                           tariff_plan):
    doc = prepare_document_for_calculation(
        'tariff_plan_apply',
        author_id,
        doc_id,
        accounts_ids,
    )
    c_queue = doc.get_calculate_queue()
    doc.validate_tariff_plans = True
    try:
        tp = doc._add_tariff_plan_by_id(tariff_plan)
    except TariffPlanServicesDuplicateError:
        return {
            'warnings': 'Выбранный тарифный план содержит дубли тарифов, '
                        'его нельзя использовать в расчёте.'
        }
    if not tp.get('tariffs', []):
        Accrual.objects(__raw__={
            'doc._id': doc_id,
            'account._id': {'$in': accounts_ids},
            'sector_code': sector
        }).delete()
        doc.add_offsets_task(accounts_ids)
        return {'doc': None, 'result': 'deleted'}
    debts = []
    for account in accounts_ids:
        if not doc.accounts.get(account):
            continue
        debt = doc.accounts[account]['debts'].get(sector)
        if debt:
            debts.append(debt)
    for debt in debts:
        debt.doc_m['tariff_plan'] = tp['_id']
        debt.find_tariff_plan()
        debt.fill_services_from_tariff_plan(delete_excess=True)
    doc.prepare_debts(debts)
    for debt in debts:
        doc.calculate_debt(debt, calculate_queue=c_queue)
    doc.release_recalculation_tasks()
    calculate_bank_fee(doc, accounts_ids, sector=sector)
    return {'doc': doc, 'result': 'success'}


def add_account_to_accrual_doc_func(author_id, doc_id, account_id, sector):
    doc = prepare_document_for_calculation(
        'add_account_to_accrual_doc',
        author_id,
        doc_id,
        [account_id],
    )
    if sector in [s_b.sector_code for s_b in
                  doc.doc_m.sector_binds]:
        account = doc.accounts[account_id]
        debt = account['debts'].get(sector)
        if not debt:
            debt = doc._add_sector_for_account(account, sector)
            debt.fill_services_from_tariff_plan()
            doc.prepare_debts([debt])
            doc.calculate_debt(debt)
            doc.release_recalculation_tasks()
            calculate_bank_fee(
                doc,
                [account_id],
                True,
                sector,
            )
            return {'doc': doc}
    return {'doc': None}


def calculate_total_func(author_id, doc_id, formula_code):
    doc = prepare_document_for_calculation(
        'calculate_total',
        author_id,
        doc_id,
    )
    # doc.pre_calculate_debts(doc.debts)
    if not formula_code:
        codes = [
            (t.formula_code,
             (t.house_group or 'all') if t.sum_docs else None)
            for t in doc.doc_m.totals
        ]
    else:
        codes = [(formula_code, None)]
    for code in codes:
        tariff_plans = []
        for t_value in doc.doc_m.totals:
            if t_value.formula_code == code:
                tariff_plans.extend(t_value.tariff_plans)
        if tariff_plans:
            for tp in tariff_plans:
                t_plan = doc.find_tariff_plan_by_id(tp)
                doc.recalculate_accrual_value(code, t_plan)
        else:
            doc.recalculate_accrual_value(code[0], None, code[1])
    return {'doc': doc}


def public_communal_recalculation_update_func(author_id, doc_id, months):
    doc = prepare_document_for_calculation(
        'public_communal_recalculation_update',
        author_id,
        doc_id,
    )
    if not doc.public_communal_recalculations:
        for sector in doc.house.settings.keys():
            doc.load_public_communal_recalculation_data(sector, forced=True)
    doc.replace_doc_public_communal_recalculations(
        allowed_month_resource_combinations=months,
    )
    doc.save()
    return {'doc': doc}


def run_accruals_func(author_id, doc_id, accounts_ids, sector):
    # подготовить документ начислений для расчёта
    doc = prepare_document_for_calculation(
        'run_accruals',
        author_id,
        doc_id,
        accounts_ids,
    )
    # посчитать
    doc.load_offsets([sector])
    doc.run_accounts(
        accounts_ids,
        [],
        True,
        sectors=[sector],
        all_accounts=True
    )
    # сохранить
    doc.save()
    # проверим дубли и выделим их в отдельный документ
    doc = PipcaDocument.load_doc(
        doc_id,
        search_errors=True,
    )
    debts = doc.extract_duplicated_debts()
    if debts:
        doc = AccrualDoc({
            'type': doc.doc_m.type,
            'date': doc.doc_m.date,
            'house': doc.doc_m.house._id,
            'provider': doc.doc_m.provider._id,
            'date_from': doc.doc_m.date_from,
            'date_till': doc.doc_m.date_till,
            'tariff_plan': doc.doc_m.tariff_plan._id,
            'description': doc.doc_m.description,
            'sector_binds': doc.doc_m.sector_binds.detach(),
            'pay_till': doc.doc_m.pay_till,
            'status': doc.doc_m.status,
            'totals': doc.doc_m.totals.detach(),
            'lock': None,
            'logs': [],
        })
        doc.save()
        accruals = Accrual.objects(id__in=[d.doc_m['_id'] for d in debts]).all()
        for a in accruals:
            a.doc = doc.id
            a.save()


def recalculate_accrual_func(author_id, doc_id, accounts_ids, sector,
                             service_type=None, services_list=None,
                             services_codes=None, services_cache_codes=None):
    doc = prepare_document_for_calculation(
        'recalculate_accrual',
        author_id,
        doc_id,
        accounts_ids,
    )
    if accounts_ids is None:
        accounts_ids = doc.get_accounts_list()
    s_list = None
    if service_type:
        s_list = [service_type]
    elif services_list:
        s_list = services_list
    elif services_codes:
        s_list = set()
        for code in services_codes:
            s_list |= set(doc.get_services_by_head_type(code))
        s_list = list(s_list)
    elif services_cache_codes:
        s_list = set()
        for code in services_cache_codes:
            func = SERVICE_GROUP_CACHE_FUNCS.get(code)
            if not func:
                continue
            s_list |= set(func(doc))
        s_list = list(s_list)
    c_queue = doc.get_calculate_queue()
    # пересчитать нужные позиции
    debts = []
    for account_id in accounts_ids:
        if not doc.accounts.get(account_id):
            continue
        a = doc.accounts[account_id]['debts'].get(sector)
        if a:
            debts.append(a)
    doc.prepare_debts(debts, s_list)
    for a in debts:
        doc.calculate_debt(a, s_list, calculate_queue=c_queue)
    doc.release_recalculation_tasks(s_list)
    # пересчитать комиссию банка
    calculate_bank_fee(
        doc,
        accounts_ids,
        (
                not services_list
                or doc.system_types['bank_fee']['_id'] in services_list
        ),
        sector
    )
    return {'doc': doc}


def public_communal_recalculation_apply_func(author_id, doc_id, accounts_ids,
                                             calc_type, months):
    doc = prepare_document_for_calculation(
        'public_communal_recalculation_apply',
        author_id,
        doc_id,
        accounts_ids,
        connect_tp_to_services=True,
    )
    if accounts_ids is None:
        accounts_ids = doc.get_accounts_list()
    doc.add_public_communal_recalculations(
        accounts_ids=accounts_ids,
        calc_type=calc_type,
        allowed_month_resource_combinations=months,
    )
    calculate_bank_fee(doc, accounts_ids)
    return {'doc': doc}
