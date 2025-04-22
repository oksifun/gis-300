from datetime import datetime

from app.crm.models.crm import CRM, CRMEvent
from lib.helpfull_tools import DateHelpFulls as Dhf
from processing.models.billing.business_type import BusinessType


def get_crm_statuses(target_provider, submission_providers):
    """
    Получение CRM-статусов одних организаций
    по отношению к другой
    :param target_provider: ObjectId
    :param submission_providers: list: [ObjectId, ...]
    :return: dict: id=статус организации
    """
    statuses = CRM.objects(
        owner=target_provider,
        provider__id__in=submission_providers
    ).only("provider", "status").as_pymongo()
    if not statuses:
        return {}
    return {x['provider']['_id']: x["status"] for x in statuses}


def get_crm_actions(target_provider, submission_providers, sudo):
    """
    Получение последних CRM-действий подконтрольных организаций
    :param target_provider: ObjectId
    :param submission_providers: list: [ObjectId, ...]
    :param sudo: bool: право на получение последних действий
    :return: dict: id= последнии crm действия
    """
    providers_actions = {}
    query = {'provider': {'$in': submission_providers}}
    if not sudo:
        query['account.provider._id'] = target_provider
    last_actions = list(
        CRMEvent.objects(__raw__=query).only(
            'event_type', '_type', 'result', 'status',
            'date', 'created_at', 'provider'
        ).order_by('-created_at').as_pymongo()
    )
    for action in last_actions:
        p_actions = providers_actions.setdefault(
            action['provider'], {'action': None, 'task': None}
        )
        if p_actions['action'] and p_actions['task']:
            continue
        elif not p_actions['action'] and 'Action' in action['_type']:
            del action['provider']
            p_actions['action'] = action
        elif not p_actions['task'] and 'Task' in action['_type']:
            del action['provider']
            p_actions['task'] = action
    return providers_actions


def get_providers_crm(current_provider_id,
                      providers_ids,
                      sudo=False,
                      business_types=None):
    """
    Получение последних crm действий
    :param current_provider_id: id организации из сессии
    :param sudo: bool: право на получение последних действий
    :param business_types: list: business_types
    :param providers_ids: список id организаций
    :return: dict: последнии действия подконтрольных организаций и их статусы
    """
    load_crm = True
    if not sudo and business_types:
        business_types = BusinessType.objects(__raw__={
            '_id': {'$in': business_types}
        }).distinct('slug')
        if 'sales' not in business_types:
            load_crm = False

    # Получение последних действий
    if load_crm:
        providers_actions = get_crm_actions(
            target_provider=current_provider_id,
            submission_providers=providers_ids,
            sudo=sudo
        )
        providers_actions = {
            str(x): providers_actions[x] for x in providers_actions
        }
    else:
        providers_actions = {}

    # Получение CRM-статусов
    crm_statuses = get_crm_statuses(current_provider_id, providers_ids)
    # Приляпаем полученные статусы организаций
    for p_id in providers_ids:
        status = crm_statuses.get(p_id)
        p_a = providers_actions.setdefault(
            str(p_id),
            {'action': None, 'task': None}
        )
        p_a.update({'status': status})

    _add_crm_summary(providers_ids, providers_actions)
    return providers_actions


def get_providers_statistics(provider_id):
    """
    Получение списка статистики для блока статистики
    страницы "Списка организаций". Количество клиентов каждого типа.
    :return: list: ..., {'status': 'client', 'count': 768},..
    """
    pipeline = [
        {'$match': {'owner': provider_id}},
        {'$group': {'_id': '$status', 'count': {'$sum': 1}}}
    ]
    statistic_block = CRM.objects.aggregate(*pipeline)
    return [dict(count=x['count'], status=x['_id']) for x in statistic_block]


def _add_crm_summary(providers_ids, providers_actions):
    crm_summaries = CRMEvent.objects(
        __raw__={
            'is_summary': True,
            'summary_date': {'$gte': Dhf.start_of_day(datetime.now())},
            'provider': {'$in': providers_ids}
        }
    ).only('comment', 'provider', 'summary_date').as_pymongo()
    crm_summary = {}
    for c in crm_summaries:
        c_s = crm_summary.setdefault(str(c['provider']), [])
        c_s.append(c)
    for provider in providers_actions:
        if provider in crm_summary:
            crm_summary[provider].sort(key=lambda i: i['summary_date'])
            providers_actions[provider]['summary_comments'] = [
                s['comment'] for s in reversed(crm_summary[provider])
            ]
