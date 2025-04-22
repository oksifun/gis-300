from bson import ObjectId

from app.accruals.models.prepare_data_by_fias import AccrualsByFiasPrepareTask
from app.accruals.models.tasks import HousesCalculateTask
from app.celery_admin.workers.config import celery_app
from app.house.models.house import House
from app.messages.models.messenger import UserTasks
from settings import CELERY_SOFT_TIME_MODIFIER
from app.caching.models.fias_tree import AccountFiasTree, find_branch_by_aoguid, \
    fill_fias_parents_by_aoguid
from app.accruals.models.accrual_document import AccrualDoc, CacheService


@celery_app.task(
    bind=True,
    max_retries=2,
    soft_time_limit=60 * 30 * CELERY_SOFT_TIME_MODIFIER,
    default_retry_delay=30
)
def prepare_accrual_docs_by_fias_data(self, provider_id, month, fias, actor_id):
    try:
        data = get_accrual_docs_cached_data(provider_id, month, fias)
        task = AccrualsByFiasPrepareTask.update_task_state(
            provider_id,
            month,
            fias,
            state='success',
            data=data,
        )
        UserTasks.set_report_state(
            actor_id,
            task.id,
            state='SUCCESS',
        )
    except Exception as error:
        task = AccrualsByFiasPrepareTask.update_task_state(
            provider_id,
            month,
            fias,
            state='error',
            data=None,
        )
        UserTasks.set_report_state(
            actor_id,
            task.id,
            state='FAILURE',
        )
        raise error
    return 'success'


def get_accrual_docs_cached_data(provider_id, month, fias_code=None):
    fias_tree = _get_fias_tree(provider_id)
    fiases, houses = _get_fias_children_and_houses(fias_tree, fias_code)
    result = []
    for fias in fiases:
        _append_fias_data(result, fias, provider_id, month)
    if houses:
        _append_houses_data(result, houses, provider_id, month)
    return result


def _append_fias_data(target_list, fias, provider_id, month):
    data, addrobjs, houses = _get_data_by_fias(fias, provider_id, month)
    if not data:
        return
    data = data[0]
    data['type'] = 'fias'
    data['id'] = fias
    tasks, tasks_progress = _get_calc_tasks_info_by_adrobjs(
        addrobjs,
        month,
    )
    houses_tasks, houses_tasks_progress = \
        _get_calc_tasks_info_by_houses(houses, month)
    tasks.update(houses_tasks)
    tasks_progress.update(houses_tasks_progress)
    task_data, progress = _get_calc_data(tasks, tasks_progress)
    if task_data:
        data['calc_task'] = task_data
        data['progress'] = progress
    target_list.append(data)


def _append_houses_data(target_list, houses, provider_id, month):
    houses_data, addrobjs = _get_data_by_house(houses, provider_id, month)
    fias_tasks, tasks_progress = \
        _get_calc_tasks_info_by_adrobjs(addrobjs, month)
    if not fias_tasks:
        houses_tasks, tasks_progress = \
            _get_calc_tasks_info_by_houses(houses, month)
        task_data, progress = _get_calc_data(houses_tasks, tasks_progress)
    else:
        houses_tasks = None
        task_data, progress = _get_calc_data(fias_tasks, tasks_progress)
    for data in houses_data:
        data['type'] = 'house'
        data['id'] = str(data.pop('_id'))
        if fias_tasks:
            data['calc_task'] = task_data
            data['progress'] = progress
        elif houses_tasks and ObjectId(data['id']) in houses_tasks:
            data['calc_task'] = task_data
            data['progress'] = progress
        target_list.append(data)


def _get_calc_data(fias_or_houses_tasks_dict, tasks_progress_dict):
    tasks = list(set(fias_or_houses_tasks_dict.values()))
    if len(tasks) == 1:
        tasks = tasks[0]
        progress = tasks_progress_dict[tasks]['progress']
    else:
        progress = [tasks_progress_dict[task]['progress'] for task in tasks]
    return tasks, progress


def _get_parent_calc_tasks_info(fias_tree, fias_code, month):
    if not fias_code:
        return []
    fias_addrobjs = []
    fill_fias_parents_by_aoguid(fias_tree['tree'], fias_code, fias_addrobjs)
    return _get_calc_tasks_info_by_adrobjs(fias_addrobjs, month)


def _get_calc_tasks_info_by_adrobjs(fias_addrobjs, month):
    tasks = HousesCalculateTask.objects(
        houses_filter__fias__in=fias_addrobjs,
        state__in=HousesCalculateTask.CIPCA_TODO_STATES,
        month=month,
    ).only(
        'id',
        'houses_filter.fias',
        'total_tasks',
        'ready_tasks',
    ).as_pymongo()
    fiases = {}
    progress = {}
    for task in tasks:
        for fias in task['houses_filter']['fias']:
            fiases[fias] = task['_id']
        _update_task_progress_data(progress, task)
    _calc_progress(progress)
    return fiases, progress


def _get_calc_tasks_info_by_houses(houses_ids, month):
    tasks = HousesCalculateTask.objects(
        houses_filter__houses__in=houses_ids,
        state__in=HousesCalculateTask.CIPCA_TODO_STATES,
        month=month,
    ).only(
        'id',
        'houses_filter.houses',
        'total_tasks',
        'ready_tasks',
    ).as_pymongo()
    houses = {}
    progress = {}
    for task in tasks:
        for house in task['houses_filter']['houses']:
            houses[house] = task['_id']
        _update_task_progress_data(progress, task)
    _calc_progress(progress)
    return houses, progress


def _update_task_progress_data(progress_dict, task):
    task_progress = progress_dict.setdefault(
        task['_id'],
        {
            'total': 0,
            'ready': 0,
        },
    )
    task_progress['total'] += task.get('total_tasks') or 0
    task_progress['ready'] += task.get('ready_tasks') or 0


def _calc_progress(progress_dict):
    for val in progress_dict.values():
        if val['total'] == 0:
            val['progress'] = 0
        else:
            val['progress'] = val['ready'] / val['total'] * 100


def _get_fias_tree(provider_id):
    return AccountFiasTree.objects(
        __raw__={
            'provider': provider_id,
            'account': None,
        },
    ).as_pymongo().get()


def _get_fias_children_and_houses(tree, fias):
    if fias:
        node = find_branch_by_aoguid(tree['tree'], fias)
    else:
        node = {
            'inheritors': tree['tree'],
            'houses': [],
        }
    return (
        list({n['AOGUID'] for n in node.get('inheritors', [])}),
        [n['_id'] for n in node.get('houses', [])],
    )


def _get_data_by_fias(fias, provider_id, month):
    match_dict = {
        'date_from': month,
        'sector_binds.provider': provider_id,
        'house.fias_addrobjs': fias,
    }
    return (
        _get_data_by_filter(match_dict),
        _get_fias_addrobjs_by_filter(match_dict),
        _get_houses_by_filter(match_dict),
    )


def _get_data_by_house(houses_ids, provider_id, month):
    match_dict = {
        'date_from': month,
        'sector_binds.provider': provider_id,
        'house._id': {'$in': houses_ids},
    }
    return (
        _get_data_by_filter(match_dict, '$house._id'),
        _get_fias_addrobjs_by_filter(match_dict),
    )


_SUMMATION_KEYS = {
    'cold_water_total': ('cold_water', 'cold_water_public'),
    'heat_total': ('hot_water', 'hot_water_public', 'heat'),
    'electricity_total': ('electricity', 'electricity_public'),
}


def _get_fias_addrobjs_by_filter(match_dict):
    return AccrualDoc.objects(
        __raw__=match_dict,
    ).distinct(
        'house.fias_addrobjs',
    )


def _get_houses_by_filter(match_dict):
    return AccrualDoc.objects(
        __raw__=match_dict,
    ).distinct(
        'house.id',
    )


def _get_data_by_filter(match_dict, group_id=''):
    fields = list(CacheService._fields)
    fields.remove('id')
    group_dict = {
        f: {'$sum': f'$cache_services.{f}'}
        for f in fields
    }
    group_dict.update(
        _id=group_id,
        wip={'$sum': '$wip'},
        ready={'$sum': '$ready'},
        caching_wip={'$sum': '$caching_wip'},
    )
    result = AccrualDoc.objects(
        __raw__=match_dict,
    ).aggregate(
        {
            '$project': {
                'house._id': 1,
                'cache_services': 1,
                'wip': {
                    '$cond': [
                        {'$eq': ['$status', 'wip']},
                        {'$literal': 1},
                        {'$literal': 0},
                    ],
                },
                'ready': {
                    '$cond': [
                        {'$eq': ['$status', 'wip']},
                        {'$literal': 0},
                        {'$literal': 1},
                    ],
                },
                'caching_wip': {
                    '$cond': [
                        {'$eq': ['$caching_wip', True]},
                        {'$literal': 1},
                        {'$literal': 0},
                    ],
                },
            },
        },
        {
            '$group': group_dict,
        },
    )
    result = list(result)
    for data in result:
        for key, keys in _SUMMATION_KEYS.items():
            data[key] = sum(data.get(k, 0) for k in keys)
    return result
