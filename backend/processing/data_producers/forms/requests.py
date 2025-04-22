import logging
from collections import defaultdict

from dateutil.relativedelta import relativedelta
from mongoengine import Q

from lib.helpfull_tools import DateHelpFulls as dhf
from processing.data_producers.forms.file_base import FileOperations
from app.personnel.models.personnel import Worker
from app.requests.models.request import Request, RequestKindBase, \
    EmbeddedProvider, TenantEmbedded, HouseEmbedded, AreaEmbedded
# Дерево типов заявок со всеми вложенными подтипами
# ПОЛУЧЕНО ИЗ API V2
from app.requests.models.choices import RequestStatus

logger = logging.getLogger('c300')

KINDS_TYPES_TREE_V2 = {
    "542582b4a2dc8d604d373db4": {
        "_extra": {
            "actions": {},
            "children": {
                "542582b4a2dc8d604d373db5": {
                    "_extra": {
                        "actions": {},
                        "children": {
                            "542582b4a2dc8d604d373db9": {
                                "_extra": {
                                    "actions": {},
                                    "children": {}
                                },
                                "_id": "542582b4a2dc8d604d373db9",
                                "_type": "RequestKind",
                                "default_child": None,
                                "name": "Общее имущество",
                                "parents": [
                                    "542582b4a2dc8d604d373db5"
                                ],
                                "slug": "common_facilities_repair"
                            },
                            "542582b4a2dc8d604d373dba": {
                                "_extra": {
                                    "actions": {},
                                    "children": {}
                                },
                                "_id": "542582b4a2dc8d604d373dba",
                                "_type": "RequestKind",
                                "default_child": None,
                                "name": "Текущий ремонт",
                                "parents": [
                                    "542582b4a2dc8d604d373db5"
                                ],
                                "slug": "maintenance"
                            }
                        }
                    },
                    "_id": "542582b4a2dc8d604d373db5",
                    "_type": "RequestKind",
                    "default_child": "542582b4a2dc8d604d373db9",
                    "name": "Ремонт строения/дома",
                    "parents": [
                        "542582b4a2dc8d604d373db4"
                    ],
                    "slug": "structure"
                },
                "542582b4a2dc8d604d373db6": {
                    "_extra": {
                        "actions": {},
                        "children": {
                            "542582b4a2dc8d604d373dbb": {
                                "_extra": {
                                    "actions": {},
                                    "children": {}
                                },
                                "_id": "542582b4a2dc8d604d373dbb",
                                "_type": "RequestKind",
                                "default_child": None,
                                "name": "Сан.содержание",
                                "parents": [
                                    "542582b4a2dc8d604d373db6"
                                ],
                                "slug": "sanitary"
                            },
                            "542582b4a2dc8d604d373dbc": {
                                "_extra": {
                                    "actions": {},
                                    "children": {}
                                },
                                "_id": "542582b4a2dc8d604d373dbc",
                                "_type": "RequestKind",
                                "default_child": None,
                                "name": "Благоустройство",
                                "parents": [
                                    "542582b4a2dc8d604d373db6"
                                ],
                                "slug": "improvement"
                            }
                        }
                    },
                    "_id": "542582b4a2dc8d604d373db6",
                    "_type": "RequestKind",
                    "default_child": "542582b4a2dc8d604d373dbb",
                    "name": "Территория",
                    "parents": [
                        "542582b4a2dc8d604d373db4"
                    ],
                    "slug": "territory"
                },
                "542582b4a2dc8d604d373db7": {
                    "_extra": {
                        "actions": {
                            "542582b4a2dc8d604d373dc8": {
                                "_extra": {
                                    "actions": {},
                                    "children": {}
                                },
                                "_id": "542582b4a2dc8d604d373dc8",
                                "_type": "RequestAction",
                                "default_child": None,
                                "name": "Отключить стояк ХВС",
                                "name_active": "Стояк ХВС Отключен",
                                "parents": [
                                    "542582b4a2dc8d604d373db7",
                                    "542582b4a2dc8d604d373dc1"
                                ],
                                "slug": "stop_cw"
                            },
                            "542582b4a2dc8d604d373dc9": {
                                "_extra": {
                                    "actions": {},
                                    "children": {}
                                },
                                "_id": "542582b4a2dc8d604d373dc9",
                                "_type": "RequestAction",
                                "default_child": None,
                                "name": "Отключить стояк ГВС",
                                "name_active": "Стояк ГВС Отключен",
                                "parents": [
                                    "542582b4a2dc8d604d373db7",
                                    "542582b4a2dc8d604d373dc1"
                                ],
                                "slug": "stop_hw"
                            },
                            "543f94490bcd96184876660d": {
                                "_extra": {
                                    "actions": {},
                                    "children": {}
                                },
                                "_id": "543f94490bcd96184876660d",
                                "_type": "RequestAction",
                                "default_child": None,
                                "name": "Отключить стояк ЦО",
                                "name_active": "Стояк ЦО Отключен",
                                "parents": [
                                    "542582b4a2dc8d604d373db7",
                                    "542582b4a2dc8d604d373dc1"
                                ],
                                "slug": "stop_heat"
                            }
                        },
                        "children": {
                            "542582b4a2dc8d604d373dbd": {
                                "_extra": {
                                    "actions": {},
                                    "children": {}
                                },
                                "_id": "542582b4a2dc8d604d373dbd",
                                "_type": "RequestKind",
                                "default_child": None,
                                "name": "Платная",
                                "parents": [
                                    "542582b4a2dc8d604d373db7"
                                ],
                                "slug": "paid"
                            },
                            "542582b4a2dc8d604d373dbe": {
                                "_extra": {
                                    "actions": {},
                                    "children": {}
                                },
                                "_id": "542582b4a2dc8d604d373dbe",
                                "_type": "RequestKind",
                                "default_child": None,
                                "name": "Гарантийная",
                                "parents": [
                                    "542582b4a2dc8d604d373db7"
                                ],
                                "slug": "warranty"
                            }
                        }
                    },
                    "_id": "542582b4a2dc8d604d373db7",
                    "_type": "RequestKind",
                    "default_child": "542582b4a2dc8d604d373dbd",
                    "name": "Коммерческая",
                    "parents": [
                        "542582b4a2dc8d604d373db4"
                    ],
                    "slug": "commercial"
                },
                "542582b4a2dc8d604d373db8": {
                    "_extra": {
                        "actions": {},
                        "children": {
                            "542582b4a2dc8d604d373dbf": {
                                "_extra": {
                                    "actions": {
                                        "542582b4a2dc8d604d373dca": {
                                            "_extra": {
                                                "actions": {},
                                                "children": {}
                                            },
                                            "_id": "542582b4a2dc8d604d373dca",
                                            "_type": "RequestAction",
                                            "default_child": None,
                                            "name": "Отключить Лифт",
                                            "name_active": "Лифт отключен",
                                            "parents": [
                                                "542582b4a2dc8d604d373dbf"
                                            ],
                                            "slug": "stop_lift"
                                        }
                                    },
                                    "children": {
                                        "542582b4a2dc8d604d373dc3": {
                                            "_extra": {
                                                "actions": {},
                                                "children": {}
                                            },
                                            "_id": "542582b4a2dc8d604d373dc3",
                                            "_type": "RequestKind",
                                            "default_child": None,
                                            "name": "В доме",
                                            "parents": [
                                                "542582b4a2dc8d604d373dbf",
                                                "542582b4a2dc8d604d373dc0"
                                            ],
                                            "slug": "house"
                                        },
                                        "542582b4a2dc8d604d373dc4": {
                                            "_extra": {
                                                "actions": {},
                                                "children": {}
                                            },
                                            "_id": "542582b4a2dc8d604d373dc4",
                                            "_type": "RequestKind",
                                            "default_child": None,
                                            "name": "В подъезде",
                                            "parents": [
                                                "542582b4a2dc8d604d373dbf"
                                            ],
                                            "slug": "porch"
                                        }
                                    }
                                },
                                "_id": "542582b4a2dc8d604d373dbf",
                                "_type": "RequestKind",
                                "default_child": "542582b4a2dc8d604d373dc4",
                                "name": "Лифт",
                                "parents": [
                                    "542582b4a2dc8d604d373db8"
                                ],
                                "slug": "lift"
                            },
                            "542582b4a2dc8d604d373dc0": {
                                "_extra": {
                                    "actions": {
                                        "542582b4a2dc8d604d373dcb": {
                                            "_extra": {
                                                "actions": {},
                                                "children": {}
                                            },
                                            "_id": "542582b4a2dc8d604d373dcb",
                                            "_type": "RequestAction",
                                            "default_child": None,
                                            "name": "Отключить Электроснабжение",
                                            "name_active": "Электроснабжение отключено",
                                            "parents": [
                                                "542582b4a2dc8d604d373dc0"
                                            ],
                                            "slug": "stop_electricity"
                                        }
                                    },
                                    "children": {
                                        "542582b4a2dc8d604d373dc3": {
                                            "_extra": {
                                                "actions": {},
                                                "children": {}
                                            },
                                            "_id": "542582b4a2dc8d604d373dc3",
                                            "_type": "RequestKind",
                                            "default_child": None,
                                            "name": "В доме",
                                            "parents": [
                                                "542582b4a2dc8d604d373dbf",
                                                "542582b4a2dc8d604d373dc0"
                                            ],
                                            "slug": "house"
                                        },
                                        "542582b4a2dc8d604d373dc5": {
                                            "_extra": {
                                                "actions": {},
                                                "children": {}
                                            },
                                            "_id": "542582b4a2dc8d604d373dc5",
                                            "_type": "RequestKind",
                                            "default_child": None,
                                            "name": "В квартире",
                                            "parents": [
                                                "542582b4a2dc8d604d373dc0",
                                                "542582b4a2dc8d604d373dc1"
                                            ],
                                            "slug": "area"
                                        }
                                    }
                                },
                                "_id": "542582b4a2dc8d604d373dc0",
                                "_type": "RequestKind",
                                "default_child": "542582b4a2dc8d604d373dc3",
                                "name": "Электроснабжение",
                                "parents": [
                                    "542582b4a2dc8d604d373db8"
                                ],
                                "slug": "electricity"
                            },
                            "542582b4a2dc8d604d373dc1": {
                                "_extra": {
                                    "actions": {
                                        "542582b4a2dc8d604d373dc8": {
                                            "_extra": {
                                                "actions": {},
                                                "children": {}
                                            },
                                            "_id": "542582b4a2dc8d604d373dc8",
                                            "_type": "RequestAction",
                                            "default_child": None,
                                            "name": "Отключить стояк ХВС",
                                            "name_active": "Стояк ХВС Отключен",
                                            "parents": [
                                                "542582b4a2dc8d604d373db7",
                                                "542582b4a2dc8d604d373dc1"
                                            ],
                                            "slug": "stop_cw"
                                        },
                                        "542582b4a2dc8d604d373dc9": {
                                            "_extra": {
                                                "actions": {},
                                                "children": {}
                                            },
                                            "_id": "542582b4a2dc8d604d373dc9",
                                            "_type": "RequestAction",
                                            "default_child": None,
                                            "name": "Отключить стояк ГВС",
                                            "name_active": "Стояк ГВС Отключен",
                                            "parents": [
                                                "542582b4a2dc8d604d373db7",
                                                "542582b4a2dc8d604d373dc1"
                                            ],
                                            "slug": "stop_hw"
                                        },
                                        "543f94490bcd96184876660d": {
                                            "_extra": {
                                                "actions": {},
                                                "children": {}
                                            },
                                            "_id": "543f94490bcd96184876660d",
                                            "_type": "RequestAction",
                                            "default_child": None,
                                            "name": "Отключить стояк ЦО",
                                            "name_active": "Стояк ЦО Отключен",
                                            "parents": [
                                                "542582b4a2dc8d604d373db7",
                                                "542582b4a2dc8d604d373dc1"
                                            ],
                                            "slug": "stop_heat"
                                        }
                                    },
                                    "children": {
                                        "542582b4a2dc8d604d373dc5": {
                                            "_extra": {
                                                "actions": {},
                                                "children": {}
                                            },
                                            "_id": "542582b4a2dc8d604d373dc5",
                                            "_type": "RequestKind",
                                            "default_child": None,
                                            "name": "В квартире",
                                            "parents": [
                                                "542582b4a2dc8d604d373dc0",
                                                "542582b4a2dc8d604d373dc1"
                                            ],
                                            "slug": "area"
                                        },
                                        "542582b4a2dc8d604d373dc6": {
                                            "_extra": {
                                                "actions": {},
                                                "children": {}
                                            },
                                            "_id": "542582b4a2dc8d604d373dc6",
                                            "_type": "RequestKind",
                                            "default_child": None,
                                            "name": "В подвале",
                                            "parents": [
                                                "542582b4a2dc8d604d373dc1"
                                            ],
                                            "slug": "basement"
                                        },
                                        "542582b4a2dc8d604d373dc7": {
                                            "_extra": {
                                                "actions": {},
                                                "children": {}
                                            },
                                            "_id": "542582b4a2dc8d604d373dc7",
                                            "_type": "RequestKind",
                                            "default_child": None,
                                            "name": "Стояк",
                                            "parents": [
                                                "542582b4a2dc8d604d373dc1"
                                            ],
                                            "slug": "standpipe"
                                        }
                                    }
                                },
                                "_id": "542582b4a2dc8d604d373dc1",
                                "_type": "RequestKind",
                                "default_child": "542582b4a2dc8d604d373dc6",
                                "name": "Протечка",
                                "parents": [
                                    "542582b4a2dc8d604d373db8"
                                ],
                                "slug": "leak"
                            },
                            "542582b4a2dc8d604d373dc2": {
                                "_extra": {
                                    "actions": {},
                                    "children": {}
                                },
                                "_id": "542582b4a2dc8d604d373dc2",
                                "_type": "RequestKind",
                                "default_child": None,
                                "name": "Прочие работы",
                                "parents": [
                                    "542582b4a2dc8d604d373db8"
                                ],
                                "slug": "others"
                            }
                        }
                    },
                    "_id": "542582b4a2dc8d604d373db8",
                    "_type": "RequestKind",
                    "default_child": "542582b4a2dc8d604d373dbf",
                    "name": "Аварийная",
                    "parents": [
                        "542582b4a2dc8d604d373db4"
                    ],
                    "slug": "emergency"
                },
                "55116cb8f3b7d41fea3e49df": {
                    "_extra": {
                        "actions": {},
                        "children": {
                            "55116cb8f3b7d41fea3e49e0": {
                                "_extra": {
                                    "actions": {},
                                    "children": {}
                                },
                                "_id": "55116cb8f3b7d41fea3e49e0",
                                "_type": "RequestKind",
                                "default_child": None,
                                "name": "Окна",
                                "parents": [
                                    "55116cb8f3b7d41fea3e49df"
                                ],
                                "slug": "windows"
                            },
                            "55116cb8f3b7d41fea3e49e1": {
                                "_extra": {
                                    "actions": {},
                                    "children": {}
                                },
                                "_id": "55116cb8f3b7d41fea3e49e1",
                                "_type": "RequestKind",
                                "default_child": None,
                                "name": "Сантехника",
                                "parents": [
                                    "55116cb8f3b7d41fea3e49df"
                                ],
                                "slug": "sanitary_engineering"
                            },
                            "55116cb8f3b7d41fea3e49e2": {
                                "_extra": {
                                    "actions": {},
                                    "children": {}
                                },
                                "_id": "55116cb8f3b7d41fea3e49e2",
                                "_type": "RequestKind",
                                "default_child": None,
                                "name": "Электрика",
                                "parents": [
                                    "55116cb8f3b7d41fea3e49df"
                                ],
                                "slug": "electricity_vandalism"
                            },
                            "55116cb8f3b7d41fea3e49e3": {
                                "_extra": {
                                    "actions": {},
                                    "children": {}
                                },
                                "_id": "55116cb8f3b7d41fea3e49e3",
                                "_type": "RequestKind",
                                "default_child": None,
                                "name": "Витражи ГО",
                                "parents": [
                                    "55116cb8f3b7d41fea3e49df"
                                ],
                                "slug": "stained_GO"
                            },
                            "572c995d20adff1a8c2f70a6": {
                                "_extra": {
                                    "actions": {},
                                    "children": {}
                                },
                                "_id": "572c995d20adff1a8c2f70a6",
                                "_type": "RequestKind",
                                "default_child": None,
                                "name": "Отделка",
                                "parents": [
                                    "55116cb8f3b7d41fea3e49df"
                                ],
                                "slug": "decoration"
                            }
                        }
                    },
                    "_id": "55116cb8f3b7d41fea3e49df",
                    "_type": "RequestKind",
                    "default_child": "55116cb8f3b7d41fea3e49e0",
                    "name": "Вандализм",
                    "parents": [
                        "542582b4a2dc8d604d373db4"
                    ],
                    "slug": "vandalism"
                }
            }
        },
        "_id": "542582b4a2dc8d604d373db4",
        "_type": "RequestKind",
        "default_child": "542582b4a2dc8d604d373db5",
        "name": "Корневой",
        "parents": [],
        "slug": "_root"
    }
}


def get_executors_workload(date_from, executors, days_to_show=3):
    date_from = dhf.start_of_day(date_from)
    date_till = date_from + relativedelta(days=days_to_show)
    query_new = {
        'executors': {'$in': executors},
        'common_status': 'run',
        'dt_start': {'$gte': date_from, '$lt': date_till},
    }
    query_delay = {
        'executors': {'$in': executors},
        'common_status': 'delayed',
        'delayed_at': {'$gte': date_from, '$lt': date_till}
    }
    requests_new = Request.objects(__raw__=query_new).as_pymongo()
    requests_delay = Request.objects(__raw__=query_delay).as_pymongo()
    requests = defaultdict(int)

    logger.debug(f'executors_workload\n'
                 f'--------\n'
                 f'date_from: {date_from}\n'
                 )
    # заявки попадают в промежутки 9-14 и 14-19 по дате НАЧАЛА их выполнения
    for request in requests_new:
        half_day = (dhf.start_of_day(request['dt_start']) - date_from).days * 2
        if request['dt_start'].hour >= 14:
            half_day += 1
        logger.debug(f'--------\n'
                     f'dt_start: {request["dt_start"]}\n'
                     f'day: {half_day}')
        for executor in request['executors']:
            requests[(executor, half_day)] += 1

    for request in requests_delay:
        half_day = (request['delayed_at'] - date_from).days * 2
        for executor in request['executors']:
            requests[(executor, half_day)] += 1
            requests[(executor, half_day + 1)] += 1
    logger.debug(f'requests: {requests}')

    query = dict(__raw__={'_id': {'$in': executors}})
    fields = '_type', 'department', 'position', 'short_name', 'id'
    executors = Worker.objects(**query).only(*fields).as_pymongo()
    raw_executor = []
    for executor in executors:
        executor = {
            '_id': executor['_id'],
            'short_name': executor['short_name'],
            'position': executor['position'],
            'department': executor['department'],
            'workload': [0] * days_to_show * 2,
        }
        for ix, w_l in enumerate(executor['workload']):
            executor['workload'][ix] = requests.get(
                (executor['_id'], ix), w_l
            )
        raw_executor.append(executor)
    return raw_executor


def disassemble_tree(data=None, split_tree=None):
    """ Разобьем дерево на уровни наследования и сразу состами структуру """

    split_tree = split_tree or []

    next_data = [
        y for x in data
        for y in x['_extra']['children'].values()
        if x.get('_extra')
    ]
    level = []
    for part in data:
        body = dict(
            _id=part['_id'],
            slug=part['slug'],
            name=part['name'],
            parents=sorted(part['parents']),
            default_child=part['default_child']
        )
        name_active = part.get('name_active')
        if name_active:
            body['name_active'] = name_active
        if part['_extra'].get('actions'):
            body.update(
                actions=assemble_new_actions(
                    disassemble_tree(
                        list(part['_extra'].get('actions').values())
                    ),
                    part['_id']
                )
            )
        level.append(body)
    if level:
        split_tree.append(tuple(level))
    if next_data:
        return disassemble_tree(
            data=next_data,
            split_tree=split_tree
        )

    return split_tree


def assemble_new_actions(actions, parent):

    if not actions:
        return []
    formatted_actions = []
    for a in actions[0]:
        del a['parents']
        a['parent'] = parent
        formatted_actions.append(a)
    return {x['_id']: x for x in formatted_actions}


def assemble_new_tree(data, tree=None):
    """ Соберем новое дерево """

    if len(data) == 1:
        del data[0][0]['parents']
        data[0][0]['inheritors'] = {x['_id']: x for x in tree}
        data = data[0][0]
        return data

    if not data:
        return data

    # Делаем первый шкребок снизу, где у листков есть несколько парантев
    if not tree:
        tree = []
        leafs = data[-1]
        for elem in data[-2]:
            inheritors = []
            # Для каждого элемента приляпаем листья
            for leaf in leafs:
                exists = [x['_id'] for x in inheritors]
                condition = (
                        elem['_id'] in leaf['parents']
                        and leaf['_id'] not in exists
                )
                if condition:
                    morphed_leaf = {k: v for k, v in leaf.items()}
                    del morphed_leaf['parents']
                    morphed_leaf['parent'] = elem['parents'][0]
                    inheritors.append(morphed_leaf)
            if inheritors:
                elem['inheritors'] = {x['_id']: x for x in inheritors}
            elem['parent'] = elem.pop('parents')[0]
            tree.append(elem)
        return assemble_new_tree(data[:-2], tree)

    # Соберем для конечного элемента
    branch = []
    for elem in data[-1]:
        elem['parent'] = elem.pop('parents')[0]
        elem['inheritors'] = []
        for child in tree:
            if elem['_id'] == child['parent']:
                elem['inheritors'].append(child)
        elem['inheritors'] = {x['_id']: x for x in elem['inheritors']}
        branch.append(elem)
    return assemble_new_tree(data[:-1], branch)


def make_from_constant():
    """ Очень плохая функция """

    disassembled_tree = disassemble_tree(list(KINDS_TYPES_TREE_V2.values()))
    new_tree = assemble_new_tree(disassembled_tree)
    import pprint
    pprint.pprint(new_tree)
    return new_tree


def get_tenant_requests(account, limit, offset, house_requests=None):
    """
    Житель должен видеть заявки, созданные им,
    а также домовые заявки по его дому, являющиеся публичными.
    Упорядочивать по дате создания по убыванию.
    """

    offset, limit = int(offset), int(limit)
    h_id = account.area.house.id
    fields = (
        'id',
        'number',
        'tenant',
        'area',
        'house',
        'created_at',
        'dt_end',
        'body',
        'photos',
        'comment',
        'common_status',
        '_type',
        'show_all',
        'total_rate',
        'rates'
    )
    query = Q(
        tenant__id=account.id,
        is_deleted__ne=True,
    )
    if house_requests:
        query |= Q(house__id=h_id, show_all=True)
    requests = Request.objects(
        query
    ).only(*fields).as_pymongo().order_by('-created_at')[offset:limit + offset]
    for request in requests:
        if request['common_status'] != RequestStatus.PERFORMED:
            request['can_rate'] = False
            continue
        if (
                (
                        request.get('tenant')
                        and request['tenant'].get('_id')
                        and request['tenant']['_id'] == account.id
                        and 'AreaRequest' in request['_type']
                )
                or 'HouseRequest' in request['_type']
                and request['show_all']
        ):
            request['can_rate'] = True
            continue
        request['can_rate'] = False
    for request in requests:
        request['tenant_rate'] = None
        if 'rates' not in request:
            continue
        for embedded_rate in request.pop('rates'):
            if embedded_rate['account'] == account.id:
                request['tenant_rate'] = embedded_rate['rate']
                request['can_rate'] = False
                break

    return tuple(requests), requests.count()


def create_request(body, tenant, provider_id):
    """ Создание заявки в ЛКЖ """

    slugs = 'structure', 'maintenance'
    kinds = RequestKindBase.objects(slug__in=slugs).distinct('id')

    new_request = Request(
        provider=EmbeddedProvider(id=provider_id),
        tenant=TenantEmbedded(id=tenant.id),
        area=AreaEmbedded(id=tenant.area.id),
        house=HouseEmbedded(id=tenant.area.house.id),
        body=body,
        kinds=kinds,
        _type=['AreaRequest'],
        administrative_supervision=False,
        show_all=False,
        housing_supervision=False,
        common_status='accepted'
    )
    new_request.save()
    return new_request


def add_files_to_request(self, files, request_id, account_id):
    return FileOperations.add_files(
        model=Request,
        obj_id=request_id,
        files=files,
        account_id=account_id,
        file_field_path='photos',
        tenant_path='tenant.id'
    )


def get_request_file(self, request_id, file_id, account_id):
    return FileOperations.get_uuid_by_id(
        model=Request,
        file_id=file_id,
        account_id=account_id,
        obj_id=request_id,
        file_field_path='photos',
        tenant_path='tenant.id'
    )
