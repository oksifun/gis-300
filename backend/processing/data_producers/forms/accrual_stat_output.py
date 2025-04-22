import datetime

from dateutil.relativedelta import relativedelta
from mongoengine import Q

from processing.models.billing.payment import Payment
from processing.models.billing.accrual import Accrual
from app.accruals.models.accrual_document import AccrualDoc


def get_last_accrual_docs(provider_id, house_id):
    result = []
    skip = 0
    current_month = None
    while True:
        accrual_docs = list(AccrualDoc.objects(
            Q(provider=provider_id) | Q(sector_binds__provider=provider_id),
            house__id=house_id,
            document_type='main',
            status__in=['ready', 'edit'],
            is_deleted__ne=True,
        ).exclude('_binds').order_by('-date_from')[skip: skip + 5])
        if not accrual_docs:
            return result
        if not current_month:
            current_month = accrual_docs[0].date_from
        for doc in accrual_docs:
            if doc.date_from == current_month:
                result.append(doc)
            else:
                return result
        skip += 5


def get_accrual_stat_and_process(provider_id, house_id, date_from, date_till, by_sectors):
    """
    В списке документов начислений надо переделать вывод статистики
    Нужная нам "статистика" - это стобцы "Начислено", "Оплачено" и "% собираемости".
    Формировать статистику надо от месяца. Причём суммы отплат (коллекция Payment) надо
    группировать по месяцу, когда она совершена (поле doc.date), а суммы начисленного (коллекция Accrual)
    надо группировать по месяцу квитанции (поле month) и ИД документа (поле doc._id).
    :return dict - строка Итого
    :return list - таблица начислений(словари)
    """

    # Находим все документы провайдера в коллекции AccrualDoc по входящим данным
    accrual_docs = AccrualDoc.objects(Q(provider=provider_id) | Q(sector_binds__provider=provider_id),
                                      house__id=house_id,
                                      date_from__gte=date_from,
                                      date_till__lt=date_till + relativedelta(months=1),
                                      is_deleted__ne=True).as_pymongo()
    # Список id всех найденных документов
    accrual_doc_ids = [x["_id"] for x in accrual_docs]

    # Задолжности
    # Пайплайн для запроса
    pipeline = [
        {'$match':
            {
                'doc._id': {'$in': accrual_doc_ids},
                'sector_code': {'$in': by_sectors}
            }
        },
        {'$group':
            {
                '_id': '$doc._id',
                'total': {'$sum': '$value'},
                'month': {'$first': '$month'}
            }
        },
        {'$group':
            {
                '_id': '$month',
                'docs': {'$push': {
                    'id': '$_id',
                    'value': '$total'}
                }
            }
        },
        {'$sort': {'_id': -1}}
    ]
    # Получение документов за каждый месяц с суммой начислений нему
    accruals = Accrual.objects.aggregate(*pipeline)
    accruals = [(acc['_id'], acc['docs']) for acc in accruals]

    # Оплаты
    pipeline = [
        {'$match':
            {
                'account.area.house._id': house_id,
                'sector_code': {'$in': by_sectors},
                'doc.provider': provider_id,
                'is_deleted': {'$ne': True},
                'doc.date': {
                    '$gte': datetime.datetime(
                        date_from.year, date_from.month, 1
                    ),
                    '$lt': datetime.datetime(
                        date_till.year, date_till.month, 1
                    ) + relativedelta(months=1)
                }
            }
        },
        {'$group':
            {
                '_id': {
                    'year': {'$year': '$doc.date'},
                    'month': {'$month': '$doc.date'},
                },
                'total': {'$sum': '$value'}
            }
        },
        # Сортировка по очереди, так как одновременная не всегда срабатвает правильно
        # {'$sort': {'_id.month': -1, '_id.year': -1}}
        {'$sort': {'_id.month': -1}},
        {'$sort': {'_id.year': -1}}
    ]
    payments = Payment.objects.aggregate(*pipeline)
    payments = [
        (datetime.datetime(p['_id']['year'], p['_id']['month'], 1), p['total'])
        for p in payments
    ]

    # Соединяем ряды данных в соответствии с датой
    table = []
    for acc_raw in accruals:
        # Шаблон строки на случай отсутсвтия оплаты
        pattern = [acc_raw[0], acc_raw[1], 0]
        for pay_raw in payments:
            # Если даты совпали
            if acc_raw[0] == pay_raw[0]:
                pattern[2] = pay_raw[1]
        table.append(pattern)

    # Рассчитываем графу Итого по каждой колонке
    total_accruals = sum([sum([d['value'] for d in x[1]]) for x in table])
    total_payments = sum([x[2] for x in table])
    total = {
        "total_accruals": total_accruals / 100,
        "total_payments": total_payments / 100,
        "total_ratio": round(
            total_payments / total_accruals * 100, 2
        ) if total_accruals > 0 else None,
    }
    # Приведение таблицы к словарю с расчетом процента собираемости
    table = [
        {
            "month": x[0],
            "accruals": [{'id': a['id'], 'value': a['value'] / 100} for a in x[1]],
            "payments": x[2] / 100,
            "ratio": round(
                x[2] / sum([d['value'] for d in x[1]]) * 100, 2
            ) if sum([d['value'] for d in x[1]]) > 0 else None
        }
        for x in table
    ]
    return table, total
