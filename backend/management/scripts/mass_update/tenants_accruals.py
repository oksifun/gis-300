from bson import ObjectId
from mongoengine import Q

from app.accruals.cipca.calculator.accrual import get_accrual_total_value
from lib.type_convert import str_to_bool, str_to_bool_or_none
from processing.data_producers.associated.base import get_binded_houses
from processing.data_producers.balance.base import CONDUCTED_STATUSES
from processing.models.billing.account import Tenant
from processing.models.billing.accrual import Accrual
from app.offsets.models.offset import Offset
from processing.models.billing.payment import Payment
from app.offsets.models.reversal import Reversal
from processing.models.logging.custom_scripts import CustomScriptData

NUM = 300


def developer_properties_apply(
        logger, task, provider_id, house_id=None,
        tenant_name=None, search_only_developer=False,
        set_is_developer=None, set_do_not_accrual=None,
):
    """
    Скрипт перепроводит начисления по указанному жителю/дому/провайдеру со
    снятием признака "застройщик".
    :param logger: функция, которая пишет логи
    :param task: задача, запустившая скрипт
    :param provider_id: провайдер
    :param house_id: дом
    :param tenant_name: строка поиска по имени
    :param search_only_developer: обрабатывать только жителей с признаком
                                  "Застройщик"
    :param set_is_developer: установить значение параметру is_developer
                             (None - не менять)
    :param set_do_not_accrual: установить значение параметру do_not_accrual
                               (None - не менять)
    """
    query = {}
    if house_id:
        query['area.house._id'] = ObjectId(house_id)
    else:
        house_ids = get_binded_houses(ObjectId(provider_id))
        query['area.house._id'] = {'$in': house_ids}
    if tenant_name:
        query['str_name'] = {'$regex': tenant_name, '$options': 'i'}
    if str_to_bool(search_only_developer):
        query['is_developer'] = True
    set_is_developer = str_to_bool_or_none(set_is_developer)
    set_do_not_accrual = str_to_bool_or_none(set_do_not_accrual)

    tenants = Tenant.objects(__raw__=query)
    if not tenants:
        logger('По указанным параметрам жителей не найдено')
        return

    tenants_ids = [t['_id'] for t in tenants.only('id').as_pymongo()]
    _update_custom_script_data(task, 'Account', tenants)
    result = _update_developer_properties(
        tenants,
        account_field_path='',
        is_developer=set_is_developer,
        do_not_accrual=set_do_not_accrual,
    )
    logger(f'Изменено собственников {result}')
    result = _update_developer_properties(
        Payment.objects(account__id__in=tenants_ids),
        account_field_path='account',
        is_developer=set_is_developer,
        do_not_accrual=set_do_not_accrual,
    )
    logger(f'Изменено платежей {result}')
    result = _update_developer_properties(
        Reversal.objects(account__id__in=tenants_ids),
        account_field_path='account',
        is_developer=set_is_developer,
        do_not_accrual=set_do_not_accrual,
    )
    logger(f'Изменено возвратов {result}')
    result = _update_developer_properties(
        Offset.objects(refer__account__id__in=tenants_ids),
        account_field_path='refer.account',
        is_developer=set_is_developer,
        do_not_accrual=set_do_not_accrual,
    )
    logger(f'Изменено офсетов {result}')
    accruals = Accrual.objects(account__id__in=tenants_ids)
    result = _update_developer_properties(
        accruals,
        account_field_path='account',
        is_developer=set_is_developer,
        do_not_accrual=set_do_not_accrual,
    )
    logger(f'Изменено начислений {result}')
    if set_do_not_accrual is False:
        _reset_accrual_values(accruals)
    elif set_do_not_accrual is True:
        _remove_accrual_values(accruals)
    logger('Завершено')


def _update_custom_script_data(task, coll, docs_queryset):
    count = docs_queryset.count()
    for i in range(0, count, NUM):
        docs_batch = list(docs_queryset.as_pymongo()[i:i + NUM])
        CustomScriptData(
            task=task.id if task else None,
            coll=coll,
            data=docs_batch,
        ).save()


def _update_developer_properties(queryset, account_field_path,
                                 is_developer, do_not_accrual):
    set_dict = {}
    filter_dict = {'$or': []}
    field_path = f'{account_field_path}.' if account_field_path else ''
    if is_developer is not None:
        set_dict[f'{field_path}is_developer'] = is_developer
        filter_dict['$or'].append(
            {f'{field_path}is_developer': {'$ne': is_developer}},
        )
    if do_not_accrual is not None:
        set_dict[f'{field_path}do_not_accrual'] = do_not_accrual
        filter_dict['$or'].append(
            {f'{field_path}do_not_accrual': {'$ne': do_not_accrual}},
        )
    if set_dict:
        return queryset.filter(
            __raw__=filter_dict,
        ).update(
            __raw__={
                '$set': set_dict,
            },
        )
    return 0


def _reset_accrual_values(accruals_queryset):
    updated = 0
    for accrual in accruals_queryset.as_pymongo():
        if accrual.doc.status not in CONDUCTED_STATUSES:
            continue
        debt = accrual['debt']
        total = get_accrual_total_value(accrual, None)
        if (
                accrual['value'] == total
                and accrual['bill'] == total
                and accrual['debt'] == debt
        ):
            continue
        Accrual.objects(
            pk=accrual['_id'],
        ).update(
            value=total,
            debt=accrual['debt'],
            bill=total,
        )
        updated += 1
    return updated


def _remove_accrual_values(accruals_queryset):
    return accruals_queryset.filter(
        Q(value__ne=0)
        | Q(debt__ne=0)
        | Q(bill__ne=0)
    ).update(
        value=0,
        debt=0,
        bill=1,
    )
