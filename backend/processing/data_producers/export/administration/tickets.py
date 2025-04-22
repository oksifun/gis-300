from dateutil.relativedelta import relativedelta

from app.tickets.models.support import SupportTicket
from processing.models.choices import SUPPORT_TICKET_TYPES_DICT


def support_tickets_statistics(date_from, date_till,
                               logger=None, table_print=None):
    return support_tickets_statistics_by_types(
        [
            'tech',
            'legal',
            'common',
            'cabinet',
        ],
        date_from,
        date_till,
        logger=logger,
        table_print=table_print,
    )


def calc_center_tickets_statistics(date_from, date_till,
                                   logger=None, table_print=None):
    return support_tickets_statistics_by_types(
        [
            'paycent',
            'print_confirmation',
        ],
        date_from,
        date_till,
        logger=logger,
        table_print=table_print,
    )


def support_tickets_statistics_by_types(types, date_from, date_till,
                                        logger=None, table_print=None):
    statistics = SupportTicket.objects(
        __raw__={
            'type': {'$in': types},
            'initial.created_at': {
                '$gte': date_from,
                '$lt': date_till + relativedelta(days=1),
            },
        },
    ).aggregate(
        {
            '$group': {
                '_id': {
                    'provider': '$author.department.provider',
                    'year': {'$year': "$initial.created_at"},
                    'month': {'$month': "$initial.created_at"},
                },
                'count': {'$sum': 1},
            },
        },
        {
            '$group': {
                '_id': '$_id.provider',
                'months': {
                    '$push': {
                        'month': '$_id.month',
                        'year': '$_id.year',
                        'count': '$count',
                    },
                },
                'count': {'$sum': '$count'},
            },
        },
        {
            '$lookup': {
                'from': 'Provider',
                'localField': '_id',
                'foreignField': '_id',
                'as': 'provider',
            },
        },
        {
            '$unwind': '$provider',
        },
        {
            '$project': {
                'provider': '$provider.str_name',
                'inn': '$provider.inn',
                'months': 1,
                'count': 1,
            },
        },
    )
    row = [
        'Организация',
        'ИНН',
        'Всего',
        'Среднее',
    ]
    for i in range(1, 13):
        row.append(f'{str(i).zfill(2)}.20')
    if table_print:
        table_print(';'.join(row))
    rows = [row]
    for data in statistics:
        row = [
            data['provider'],
            data['inn'],
            str(data['count']),
            str(data['count'] / 12),
        ]
        for i in range(1, 13):
            count = 0
            for month_data in data['months']:
                if month_data['month'] == i:
                    count = month_data['count']
                    break
            row.append(str(count))
        if table_print:
            table_print(';'.join(row))
        rows.append(row)
    return rows


def support_statistics_by_author(date_from, date_till, summary=False,
                                 logger=None, table_print=None):
    months = 1
    types = ('tech', 'paycent', 'common', 'legal', 'cabinet')
    if summary:
        queries = [
            {'$in': types},
        ]
    else:
        queries = types
    for query in queries:
        tt = SupportTicket.objects.aggregate(
            {
                '$match': {
                    'type': query,
                    'initial.created_at': {
                        '$gte': date_from,
                        '$lt': date_till + relativedelta(days=1),
                    },
                },
            },
            {
                '$lookup': {
                    'from': 'Account',
                    'localField': 'author._id',
                    'foreignField': '_id',
                    'as': 'worker',
                },
            },
            {
                '$unwind': {
                    'path': '$worker',
                    'preserveNullAndEmptyArrays': True,
                },
            },
            {
                '$project': {
                    'provider': '$owner.provider._id',
                    'ch1': {
                        '$cond': [
                            {'$eq': ['$worker.position.code', 'ch1']},
                            {'$literal': 1},
                            {'$literal': 0},
                        ],
                    },
                    'ch2': {
                        '$cond': [
                            {'$eq': ['$worker.position.code', 'ch2']},
                            {'$literal': 1},
                            {'$literal': 0},
                        ],
                    },
                    'ch3': {
                        '$cond': [
                            {'$eq': ['$worker.position.code', 'ch3']},
                            {'$literal': 1},
                            {'$literal': 0},
                        ],
                    },
                    'name': {
                        'name': '$worker.position.name',
                        'code': '$worker.position.code',
                    },
            }},
            {
                '$group': {
                    '_id': '$provider',
                    'ch1': {'$sum': '$ch1'},
                    'ch2': {'$sum': '$ch2'},
                    'ch3': {'$sum': '$ch3'},
                    'tot': {'$sum': 1},
                    'names': {'$push': '$name'},
                },
            },
            {
                '$lookup': {
                    'from': 'Provider',
                    'localField': '_id',
                    'foreignField': '_id',
                    'as': 'provider',
                },
            },
            {
                '$unwind': {
                    'path': '$provider',
                    'preserveNullAndEmptyArrays': True,
                },
            },
            {
                '$project': {
                    'provider': '$provider.str_name',
                    'chief': {'$add': ['$ch1', '$ch2', '$ch3']},
                    'tot': 1,
                    'names': 1,
                },
            },
        )
        if isinstance(query, str):
            logger()
            logger(SUPPORT_TICKET_TYPES_DICT[query])
        logger('орг;дир;бух;др')
        for ttt in tt:
            buh = sum(
                1 for n in ttt['names']
                if (
                        'бух' in n.get('name', '').lower()
                        and n.get('code') not in ['ch1', 'ch2', 'ch3']
                )
            )
            table_print(
                '{};{};{};{}'.format(
                    ttt.get('provider', 'НЕ ЗАДАНО'),
                    ttt['chief'] / months,
                    buh / months,
                    (ttt['tot'] - ttt['chief'] - buh) / months,
                ),
            )
