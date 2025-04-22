from bson import ObjectId
from collections import OrderedDict

# Это денормализованное поле kind,
# где собраны под одним ID все возможные комбинации ID поля kinds
FAST_KINDS = OrderedDict({
    ObjectId('5c174b553968010b26940cc0'): (ObjectId('542582b4a2dc8d604d373db8'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dba')),
    ObjectId('5c174b553968010b26940cc1'): (ObjectId('542582b4a2dc8d604d373db5'),
                                           ObjectId('542582b4a2dc8d604d373dc1'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc5')),
    ObjectId('5c174b553968010b26940cc2'): (ObjectId('542582b4a2dc8d604d373db5'),
                                           ObjectId('542582b4a2dc8d604d373dbf'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc4')),
    ObjectId('5c174b553968010b26940cc3'): (ObjectId('542582b4a2dc8d604d373db6'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dba')),
    ObjectId('5c174b553968010b26940cc4'): (ObjectId('542582b4a2dc8d604d373db5'),
                                           ObjectId('542582b4a2dc8d604d373dba'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc7')),
    ObjectId('5c174b553968010b26940cc5'): (ObjectId('542582b4a2dc8d604d373db5'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dbb')),
    ObjectId('5c174b553968010b26940cc6'): (ObjectId('55116cb8f3b7d41fea3e49df'),
                                           ObjectId(
                                               '55116cb8f3b7d41fea3e49e2')),
    ObjectId('5c174b553968010b26940cc7'): (ObjectId('55116cb8f3b7d41fea3e49df'),
                                           ObjectId(
                                               '55116cb8f3b7d41fea3e49e1')),
    ObjectId('5c174b553968010b26940cc8'): (ObjectId('542582b4a2dc8d604d373db8'),
                                           ObjectId('542582b4a2dc8d604d373dc0'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc4')),
    ObjectId('5c174b553968010b26940cc9'): (ObjectId('542582b4a2dc8d604d373db7'),
                                           ObjectId('542582b4a2dc8d604d373dbd'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc3')),
    ObjectId('5c174b553968010b26940cca'): (ObjectId('542582b4a2dc8d604d373db5'),
                                           ObjectId('542582b4a2dc8d604d373dba'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc6')),
    ObjectId('5c174b553968010b26940ccb'): (ObjectId('542582b4a2dc8d604d373db5'),
                                           ObjectId('542582b4a2dc8d604d373db9'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc6')),
    ObjectId('5c174b553968010b26940ccc'): (ObjectId('542582b4a2dc8d604d373db8'),
                                           ObjectId('542582b4a2dc8d604d373dc2'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc5')),
    ObjectId('5c174b553968010b26940ccd'): (ObjectId('542582b4a2dc8d604d373db5'),
                                           ObjectId('542582b4a2dc8d604d373dba'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc3')),
    ObjectId('5c174b553968010b26940cce'): (ObjectId('542582b4a2dc8d604d373db8'),
                                           ObjectId('542582b4a2dc8d604d373dc2'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc6')),
    ObjectId('5c174b553968010b26940ccf'): (ObjectId('542582b4a2dc8d604d373db7'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373db9')),
    ObjectId('5c174b553968010b26940cd0'): (ObjectId('55116cb8f3b7d41fea3e49df'),
                                           ObjectId(
                                               '572c995d20adff1a8c2f70a6')),
    ObjectId('5c174b553968010b26940cd1'): (ObjectId('542582b4a2dc8d604d373db7'),
                                           ObjectId('542582b4a2dc8d604d373dbd'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc5')),
    ObjectId('5c174b553968010b26940cd2'): (ObjectId('542582b4a2dc8d604d373db5'),
                                           ObjectId('542582b4a2dc8d604d373db9'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc4')),
    ObjectId('5c174b553968010b26940cd3'): (ObjectId('542582b4a2dc8d604d373db5'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dbd')),
    ObjectId('5c174b553968010b26940cd4'): (ObjectId('542582b4a2dc8d604d373db8'),
                                           ObjectId('542582b4a2dc8d604d373dbf'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc4')),
    ObjectId('5c174b553968010b26940cd5'): (ObjectId('542582b4a2dc8d604d373db5'),
                                           ObjectId('542582b4a2dc8d604d373dba'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc4')),
    ObjectId('5c174b553968010b26940cd6'): (ObjectId('542582b4a2dc8d604d373db5'),
                                           ObjectId('542582b4a2dc8d604d373dba'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc5')),
    ObjectId('5c174b553968010b26940cd7'): (ObjectId('542582b4a2dc8d604d373db8'),
                                           ObjectId('542582b4a2dc8d604d373dbf'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc6')),
    ObjectId('5c174b553968010b26940cd8'): (ObjectId('542582b4a2dc8d604d373db8'),
                                           ObjectId('542582b4a2dc8d604d373dc2'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc3')),
    ObjectId('5c174b553968010b26940cd9'): (ObjectId('542582b4a2dc8d604d373db5'),
                                           ObjectId('542582b4a2dc8d604d373db9'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc5')),
    ObjectId('5c174b553968010b26940cda'): (ObjectId('542582b4a2dc8d604d373db8'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dbb')),
    ObjectId('5c174b553968010b26940cdb'): (ObjectId('542582b4a2dc8d604d373db6'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dbc')),
    ObjectId('5c174b553968010b26940cdc'): (ObjectId('542582b4a2dc8d604d373db8'),
                                           ObjectId('542582b4a2dc8d604d373dc2'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc4')),
    ObjectId('5c174b553968010b26940cdd'): (ObjectId('542582b4a2dc8d604d373db8'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dbf')),
    ObjectId('5c174b553968010b26940cde'): (ObjectId('542582b4a2dc8d604d373db8'),
                                           ObjectId('542582b4a2dc8d604d373dbf'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc3')),
    ObjectId('5c174b553968010b26940cdf'): (ObjectId('542582b4a2dc8d604d373db8'),
                                           ObjectId('542582b4a2dc8d604d373dc2'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc7')),
    ObjectId('5c174b553968010b26940ce0'): (ObjectId('542582b4a2dc8d604d373db7'),
                                           ObjectId('542582b4a2dc8d604d373dbd'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc4')),
    ObjectId('5c174b553968010b26940ce1'): (ObjectId('542582b4a2dc8d604d373db8'),
                                           ObjectId('542582b4a2dc8d604d373dc1'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc5')),
    ObjectId('5c174b553968010b26940ce2'): (ObjectId('542582b4a2dc8d604d373db8'),
                                           ObjectId('542582b4a2dc8d604d373dc1'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc6')),
    ObjectId('5c174b553968010b26940ce3'): (ObjectId('542582b4a2dc8d604d373db8'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc1')),
    ObjectId('5c174b553968010b26940ce4'): (ObjectId('542582b4a2dc8d604d373db7'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dbe')),
    ObjectId('5c174b553968010b26940ce5'): (ObjectId('542582b4a2dc8d604d373db5'),
                                           ObjectId('542582b4a2dc8d604d373db9'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc3')),
    ObjectId('5c174b553968010b26940ce6'): (ObjectId('542582b4a2dc8d604d373db8'),
                                           ObjectId('542582b4a2dc8d604d373dc0'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc5')),
    ObjectId('5c174b553968010b26940ce7'): (ObjectId('542582b4a2dc8d604d373db8'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc2')),
    ObjectId('5c174b553968010b26940ce8'): (ObjectId('542582b4a2dc8d604d373db6'),
                                           ObjectId('542582b4a2dc8d604d373dbb'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc4')),
    ObjectId('5c174b553968010b26940ce9'): (ObjectId('542582b4a2dc8d604d373db8'),
                                           ObjectId('542582b4a2dc8d604d373dc0'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc3')),
    ObjectId('5c174b553968010b26940cea'): (ObjectId('542582b4a2dc8d604d373db8'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373db9')),
    ObjectId('5c174b553968010b26940ceb'): (ObjectId('55116cb8f3b7d41fea3e49df'),
                                           ObjectId(
                                               '55116cb8f3b7d41fea3e49e3')),
    ObjectId('5c174b553968010b26940cec'): (ObjectId('542582b4a2dc8d604d373db8'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc0')),
    ObjectId('5c174b553968010b26940ced'): (ObjectId('542582b4a2dc8d604d373db5'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dba')),
    ObjectId('5c174b553968010b26940cee'): (ObjectId('55116cb8f3b7d41fea3e49df'),
                                           ObjectId(
                                               '55116cb8f3b7d41fea3e49e0')),
    ObjectId('5c174b553968010b26940cef'): (ObjectId('542582b4a2dc8d604d373db6'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dbb')),
    ObjectId('5c174b553968010b26940cf0'): (ObjectId('542582b4a2dc8d604d373db5'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373db9')),
    ObjectId('5c174b553968010b26940cf1'): (ObjectId('542582b4a2dc8d604d373db8'),
                                           ObjectId('542582b4a2dc8d604d373dc1'),
                                           ObjectId(
                                               '542582b4a2dc8d604d373dc7')),
    ObjectId('5c174b553968010b26940cf2'): (ObjectId('542582b4a2dc8d604d373db7'),
                                           ObjectId('542582b4a2dc8d604d373dbd')),
    ObjectId('5c174b553968010b26940cf3'): (ObjectId('5f1eaa78276330478206c799'),),
    ObjectId('5c174b553968010b26940cf4'): (ObjectId('5f1eaa78276330478206c79a'),),
    ObjectId('5c174b553968010b26940cf5'): (ObjectId('5f1eaa78276330478206c79b'),),
    ObjectId('5c174b553968010b26940cf6'): (ObjectId('5f1eaa78276330478206c79c'),),
    ObjectId('5c174b553968010b26940cf7'): (ObjectId('5f1eaa78276330478206c79d'),),
    ObjectId('5c174b553968010b26940cf8'): (ObjectId('5f1eaa78276330478206c79e'),),
})
# Отсортируем ID
FAST_KINDS = {k: tuple(sorted(v)) for k, v in FAST_KINDS.items()}

# FAST_KINDS, обращенные своими значениями в ключи, а ключами в значения
FAST_KINDS_REVERSED = {v: k for k, v in FAST_KINDS.items()}

# Это дерево получено с помощью
# from processing.data_producers.forms.requests import make_from_constant
# make_from_constant()
KINDS_TYPES_TREE = {
    '_id': '542582b4a2dc8d604d373db4',
    'default_child': '542582b4a2dc8d604d373db5',
    'inheritors': {
        '542582b4a2dc8d604d373db5': {
            '_id': '542582b4a2dc8d604d373db5',
            'default_child': '542582b4a2dc8d604d373db9',
            'inheritors': {
                '542582b4a2dc8d604d373db9': {
                    '_id': '542582b4a2dc8d604d373db9',
                    'default_child': None,
                    'name': 'Общее '
                            'имущество',
                    'parent': '542582b4a2dc8d604d373db5',
                    'slug': 'common_facilities_repair'},
                '542582b4a2dc8d604d373dba': {
                    '_id': '542582b4a2dc8d604d373dba',
                    'default_child': None,
                    'name': 'Текущий '
                            'ремонт',
                    'parent': '542582b4a2dc8d604d373db5',
                    'slug': 'maintenance'}},
            'name': 'Ремонт строения/дома',
            'parent': '542582b4a2dc8d604d373db4',
            'slug': 'structure'
        },
        '542582b4a2dc8d604d373db6': {
            '_id': '542582b4a2dc8d604d373db6',
            'default_child': '542582b4a2dc8d604d373dbb',
            'inheritors': {
                '542582b4a2dc8d604d373dbb': {
                    '_id': '542582b4a2dc8d604d373dbb',
                    'default_child': None,
                    'name': 'Сан.содержание',
                    'parent': '542582b4a2dc8d604d373db6',
                    'slug': 'sanitary'},
                '542582b4a2dc8d604d373dbc': {
                    '_id': '542582b4a2dc8d604d373dbc',
                    'default_child': None,
                    'name': 'Благоустройство',
                    'parent': '542582b4a2dc8d604d373db6',
                    'slug': 'improvement'}},
            'name': 'Территория',
            'parent': '542582b4a2dc8d604d373db4',
            'slug': 'territory'},
        '542582b4a2dc8d604d373db7': {
            '_id': '542582b4a2dc8d604d373db7',
            'actions': {'542582b4a2dc8d604d373dc8': {
                '_id': '542582b4a2dc8d604d373dc8',
                'default_child': None,
                'name': 'Отключить '
                        'стояк '
                        'ХВС',
                'name_active': 'Стояк '
                               'ХВС '
                               'Отключен',
                'parent': '542582b4a2dc8d604d373db7',
                'slug': 'stop_cw'},
                '542582b4a2dc8d604d373dc9': {
                    '_id': '542582b4a2dc8d604d373dc9',
                    'default_child': None,
                    'name': 'Отключить '
                            'стояк '
                            'ГВС',
                    'name_active': 'Стояк '
                                   'ГВС '
                                   'Отключен',
                    'parent': '542582b4a2dc8d604d373db7',
                    'slug': 'stop_hw'},
                '543f94490bcd96184876660d': {
                    '_id': '543f94490bcd96184876660d',
                    'default_child': None,
                    'name': 'Отключить '
                            'стояк '
                            'ЦО',
                    'name_active': 'Стояк '
                                   'ЦО '
                                   'Отключен',
                    'parent': '542582b4a2dc8d604d373db7',
                    'slug': 'stop_heat'}},
            'default_child': '542582b4a2dc8d604d373dbd',
            'inheritors': {
                '542582b4a2dc8d604d373dbd': {
                    '_id': '542582b4a2dc8d604d373dbd',
                    'default_child': None,
                    'name': 'Платная',
                    'parent': '542582b4a2dc8d604d373db7',
                    'slug': 'paid'},
                '542582b4a2dc8d604d373dbe': {
                    '_id': '542582b4a2dc8d604d373dbe',
                    'default_child': None,
                    'name': 'Гарантийная',
                    'parent': '542582b4a2dc8d604d373db7',
                    'slug': 'warranty'}},
            'name': 'Коммерческая',
            'parent': '542582b4a2dc8d604d373db4',
            'slug': 'commercial'},
        '542582b4a2dc8d604d373db8': {
            '_id': '542582b4a2dc8d604d373db8',
            'default_child': '542582b4a2dc8d604d373dbf',
            'inheritors': {
                '542582b4a2dc8d604d373dbf': {
                    '_id': '542582b4a2dc8d604d373dbf',
                    'actions': {
                        '542582b4a2dc8d604d373dca': {
                            '_id': '542582b4a2dc8d604d373dca',
                            'default_child': None,
                            'name': 'Отключить '
                                    'Лифт',
                            'name_active': 'Лифт '
                                           'отключен',
                            'parent': '542582b4a2dc8d604d373dbf',
                            'slug': 'stop_lift'}},
                    'default_child': '542582b4a2dc8d604d373dc4',
                    'inheritors': {
                        '542582b4a2dc8d604d373dc3': {
                            '_id': '542582b4a2dc8d604d373dc3',
                            'default_child': None,
                            'name': 'В '
                                    'доме',
                            'parent': '542582b4a2dc8d604d373db8',
                            'slug': 'house'},
                        '542582b4a2dc8d604d373dc4': {
                            '_id': '542582b4a2dc8d604d373dc4',
                            'default_child': None,
                            'name': 'В '
                                    'подъезде',
                            'parent': '542582b4a2dc8d604d373db8',
                            'slug': 'porch'}},
                    'name': 'Лифт',
                    'parent': '542582b4a2dc8d604d373db8',
                    'slug': 'lift'},
                '542582b4a2dc8d604d373dc0': {
                    '_id': '542582b4a2dc8d604d373dc0',
                    'actions': {
                        '542582b4a2dc8d604d373dcb': {
                            '_id': '542582b4a2dc8d604d373dcb',
                            'default_child': None,
                            'name': 'Отключить '
                                    'Электроснабжение',
                            'name_active': 'Электроснабжение '
                                           'отключено',
                            'parent': '542582b4a2dc8d604d373dc0',
                            'slug': 'stop_electricity'}},
                    'default_child': '542582b4a2dc8d604d373dc3',
                    'inheritors': {
                        '542582b4a2dc8d604d373dc3': {
                            '_id': '542582b4a2dc8d604d373dc3',
                            'default_child': None,
                            'name': 'В '
                                    'доме',
                            'parent': '542582b4a2dc8d604d373db8',
                            'slug': 'house'},
                        '542582b4a2dc8d604d373dc5': {
                            '_id': '542582b4a2dc8d604d373dc5',
                            'default_child': None,
                            'name': 'В '
                                    'квартире',
                            'parent': '542582b4a2dc8d604d373db8',
                            'slug': 'area'}},
                    'name': 'Электроснабжение',
                    'parent': '542582b4a2dc8d604d373db8',
                    'slug': 'electricity'},
                '542582b4a2dc8d604d373dc1': {
                    '_id': '542582b4a2dc8d604d373dc1',
                    'actions': {
                        '542582b4a2dc8d604d373dc8': {
                            '_id': '542582b4a2dc8d604d373dc8',
                            'default_child': None,
                            'name': 'Отключить '
                                    'стояк '
                                    'ХВС',
                            'name_active': 'Стояк '
                                           'ХВС '
                                           'Отключен',
                            'parent': '542582b4a2dc8d604d373dc1',
                            'slug': 'stop_cw'},
                        '542582b4a2dc8d604d373dc9': {
                            '_id': '542582b4a2dc8d604d373dc9',
                            'default_child': None,
                            'name': 'Отключить '
                                    'стояк '
                                    'ГВС',
                            'name_active': 'Стояк '
                                           'ГВС '
                                           'Отключен',
                            'parent': '542582b4a2dc8d604d373dc1',
                            'slug': 'stop_hw'},
                        '543f94490bcd96184876660d': {
                            '_id': '543f94490bcd96184876660d',
                            'default_child': None,
                            'name': 'Отключить '
                                    'стояк '
                                    'ЦО',
                            'name_active': 'Стояк '
                                           'ЦО '
                                           'Отключен',
                            'parent': '542582b4a2dc8d604d373dc1',
                            'slug': 'stop_heat'}},
                    'default_child': '542582b4a2dc8d604d373dc6',
                    'inheritors': {
                        '542582b4a2dc8d604d373dc5': {
                            '_id': '542582b4a2dc8d604d373dc5',
                            'default_child': None,
                            'name': 'В '
                                    'квартире',
                            'parent': '542582b4a2dc8d604d373db8',
                            'slug': 'area'},
                        '542582b4a2dc8d604d373dc6': {
                            '_id': '542582b4a2dc8d604d373dc6',
                            'default_child': None,
                            'name': 'В '
                                    'подвале',
                            'parent': '542582b4a2dc8d604d373db8',
                            'slug': 'basement'},
                        '542582b4a2dc8d604d373dc7': {
                            '_id': '542582b4a2dc8d604d373dc7',
                            'default_child': None,
                            'name': 'Стояк',
                            'parent': '542582b4a2dc8d604d373db8',
                            'slug': 'standpipe'}},
                    'name': 'Протечка',
                    'parent': '542582b4a2dc8d604d373db8',
                    'slug': 'leak'},
                '542582b4a2dc8d604d373dc2': {
                    '_id': '542582b4a2dc8d604d373dc2',
                    'default_child': None,
                    'name': 'Прочие '
                            'работы',
                    'parent': '542582b4a2dc8d604d373db8',
                    'slug': 'others'}},
            'name': 'Аварийная',
            'parent': '542582b4a2dc8d604d373db4',
            'slug': 'emergency'},
        '55116cb8f3b7d41fea3e49df': {
            '_id': '55116cb8f3b7d41fea3e49df',
            'default_child': '55116cb8f3b7d41fea3e49e0',
            'inheritors': {
                '55116cb8f3b7d41fea3e49e0': {
                    '_id': '55116cb8f3b7d41fea3e49e0',
                    'default_child': None,
                    'name': 'Окна',
                    'parent': '55116cb8f3b7d41fea3e49df',
                    'slug': 'windows'},
                '55116cb8f3b7d41fea3e49e1': {
                    '_id': '55116cb8f3b7d41fea3e49e1',
                    'default_child': None,
                    'name': 'Сантехника',
                    'parent': '55116cb8f3b7d41fea3e49df',
                    'slug': 'sanitary_engineering'},
                '55116cb8f3b7d41fea3e49e2': {
                    '_id': '55116cb8f3b7d41fea3e49e2',
                    'default_child': None,
                    'name': 'Электрика',
                    'parent': '55116cb8f3b7d41fea3e49df',
                    'slug': 'electricity_vandalism'},
                '55116cb8f3b7d41fea3e49e3': {
                    '_id': '55116cb8f3b7d41fea3e49e3',
                    'default_child': None,
                    'name': 'Витражи '
                            'ГО',
                    'parent': '55116cb8f3b7d41fea3e49df',
                    'slug': 'stained_GO'},
                '572c995d20adff1a8c2f70a6': {
                    '_id': '572c995d20adff1a8c2f70a6',
                    'default_child': None,
                    'name': 'Отделка',
                    'parent': '55116cb8f3b7d41fea3e49df',
                    'slug': 'decoration'}},
            'name': 'Вандализм',
            'parent': '542582b4a2dc8d604d373db4',
            'slug': 'vandalism'},
        '5f1eaa78276330478206c799': {
            '_id': '5f1eaa78276330478206c799',
            'default_child': None,
            'name': 'Вентиляция',
            'parent': '542582b4a2dc8d604d373db4',
            'slug': 'ventilation'
        },
        '5f1eaa78276330478206c79a': {
            '_id': '5f1eaa78276330478206c79a',
            'default_child': None,
            'name': 'Водоотведение',
            'parent': '542582b4a2dc8d604d373db4',
            'slug': 'water_disposal'
        },
        '5f1eaa78276330478206c79b': {
            '_id': '5f1eaa78276330478206c79b',
            'default_child': None,
            'name': 'Кровля',
            'parent': '542582b4a2dc8d604d373db4',
            'slug': 'roof'
        },
        '5f1eaa78276330478206c79c': {
            '_id': '5f1eaa78276330478206c79c',
            'default_child': None,
            'name': 'Опломбирование',
            'parent': '542582b4a2dc8d604d373db4',
            'slug': 'sealing'
        },
        '5f1eaa78276330478206c79d': {
            '_id': '5f1eaa78276330478206c79d',
            'default_child': None,
            'name': 'Орг.-правовые вопросы ЖКХ',
            'parent': '542582b4a2dc8d604d373db4',
            'slug': 'procedural_legal_issues'
        },
        '5f1eaa78276330478206c79e': {
            '_id': '5f1eaa78276330478206c79e',
            'default_child': None,
            'name': 'Фасады',
            'parent': '542582b4a2dc8d604d373db4',
            'slug': 'front'
        },
    },
    'name': 'Корневой',
    'slug': '_root'}
