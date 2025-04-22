from app.personnel.models.personnel import Worker
from processing.models.permissions import ClientTab, Permissions
from utils.crm_utils import get_crm_client_ids


def get_admin_workers(logger=None, table_print=None):
    tab = ClientTab.objects(slug='worker_rules').as_pymongo().get()
    users = Permissions.objects(
        __raw__={
            f'granular.Tab.{tab["_id"]}.0.permissions.u': True,
            'actor_type': 'Account',
        },
    ).distinct(
        'actor_id',
    )
    if logger:
        logger(f'Пользователей с правами всего {len(users)}')
    clients_ids = get_crm_client_ids()
    workers = Worker.objects(
        provider__id__in=clients_ids,
        pk__in=users,
        has_access=True,
        is_deleted__ne=True,
    ).only(
        'id',
        'str_name',
        'provider.str_name',
        'position.name',
    ).as_pymongo()
    if logger:
        logger(f'Текущих пользователей {workers.count()}')
    title_row = [
        'Организация',
        'Должность',
        'ФИО',
        'id',
    ]
    result = [
        title_row,
    ]
    if table_print:
        table_print(';'.join(result[0]))
    for worker in workers:
        row = [
            worker['provider']['str_name'],
            worker['position']['name'],
            worker['str_name'],
            str(worker['_id']),
        ]
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result


def get_workers_transfer(logger=None, table_print=None):
    workers = Worker.objects(
        _type='Worker',
        last_name__nin=['', None],
    ).aggregate(
        {
            '$project': {
                'is_deleted': 1,
                'short_name': 1,
                'str_name': 1,
                'provider_id': '$provider._id',
                'provider_name': '$provider.str_name',
                'position': '$position.name',
            },
        },
        {
            '$lookup': {
                'from': 'Provider',
                'localField': 'provider_id',
                'foreignField': '_id',
                'as': 'provider',
            },
        },
        {
            '$unwind': '$provider',
        },
        {
            '$match': {
                'provider.inn': {'$regex': '^78'},
            },
        },
        {
            '$group': {
                '_id': '$short_name',
                'providers': {
                    '$push': {
                        'name': '$provider_name',
                        'inn': '$provider.inn',
                        'position': '$position',
                        'is_deleted': '$is_deleted',
                    },
                },
                'is_deleted': {'$addToSet': '$is_deleted'},
            },
        },
        {
            '$project': {
                '_id': 1,
                'providers': 1,
                'is_deleted': {
                    '$cond': [
                        {'$in': [True, '$is_deleted']},
                        {'$literal': 1},
                        {'$literal': 0},
                    ],
                },
            },
        },
        {
            '$match': {
                'is_deleted': 1,
            },
        },
    )
    max_len = 0
    result = []
    for worker in workers:
        row = [
            worker['_id'],
        ]
        for provider in worker['providers']:
            row.append('Уволен' if provider.get('is_deleted') else '')
            row.append(provider.get('inn') or '')
            row.append(provider['name'])
            row.append(provider['position'])
        max_len = max(max_len, len(row))
        result.append(row)
    if table_print:
        for row in result:
            while len(row) < max_len:
                row.append('')
            table_print(';'.join(row))
    return result


def get_workers_responsibility(logger=None, table_print=None):

    if logger:
        logger('Получение исходных данных')
    clients_ids = get_crm_client_ids()
    tabs = ClientTab.objects().as_pymongo().only('slug', 'title')
    tabs = {
        tab['slug']: {
            'title': tab['title'],
            '_id': tab['_id'],
        }
        for tab in tabs
    }

    initial_table_head = ['Организация', 'ФИО', 'Должность']
    initial_keys = ['provider', 'worker_name', 'position']
    for tab in tabs:
        initial_table_head.append(tabs[tab]['title'])
        initial_keys.append(tab)
    aggregation_pipeline = [
        {"$match": {
            'provider._id': {'$in': clients_ids},
            'is_deleted': {'$ne': True},
        }},
        {'$project': {
            'provider': {"$ifNull": ['$provider.str_name', '']},
            'worker_name': {"$ifNull": ['$str_name', '']},
            'position': {"$ifNull": ['$position.name', '']},
        }},
    ]
    if logger:
        logger('Агрегация данных')

    result = list(Worker.objects.aggregate(*aggregation_pipeline))

    workers_ids = [row['_id'] for row in result]
    permissions = Permissions.objects(
        actor_id__in=workers_ids
    ).as_pymongo().only('granular.Tab', 'actor_id')

    perms = {
        permission['actor_id']: permission['granular'].get('Tab')
        for permission in permissions
    }
    for row in result:
        for key in initial_keys[3:]:
            row[key] = 'Да'if __get_perm(perms, row, tabs[key]['_id']) else'Нет'

    report = [initial_table_head, initial_keys]

    for row in result:
        row_list = []
        for key in initial_keys:
            key = key.strip().lower()
            row_list.append(row.get(key, 'Нет'))
        report.append(row_list)

    if table_print:
        table_print(''.join([';'.join(i) + '\n' for i in report]))

    return report


def __get_perm(permissions, row, tab_id):
    worker_tabs = permissions.get(row['_id'])
    if not worker_tabs:
        return None
    tab = worker_tabs.get(str(tab_id))
    if not tab:
        return None
    permissions = [tab_property.get('permissions') for tab_property in tab]
    if not permissions:
        return None
    return permissions[0].get('r')