import datetime

from dateutil.relativedelta import relativedelta
from mongoengine_connections import register_mongoengine_connections
from processing.data_producers.balance.base import HousesBalance
from processing.models.billing.payment import Payment
from app.house.models.house import House
from app.accruals.models.accrual_document import AccrualDoc
from processing.models.billing.provider.main import Provider
from utils.crm_utils import get_crm_client_ids


def get_acquiring_stat(month_from, month_till, logger=None, table_print=None):
    if logger:
        logger('Получение исходных данных')
    date_end = month_till + relativedelta(months=1)
    date_now = datetime.datetime.now()
    all_houses = list(
        AccrualDoc.objects(date_from=month_till).as_pymongo().only(
            'house.id', 'provider'
        )
    )
    all_houses = {h['house']['_id']: h['provider'] for h in all_houses}
    # запрос данных отчёта
    agg_pipeline = [
        {'$match': {
            'account.area.house._id': {'$in': list(all_houses.keys())},
            'doc.date': {
                '$gte': month_from,
                '$lt': date_end,
            },
            'by_card': True,
            'is_deleted': {'$ne': True},
        }},
        {'$group': {
            '_id': {
                'house': '$account.area.house._id',
                'provider': '$doc.provider',
            },
            'payments': {'$push': {
                'account': '$account._id',
                'date': '$doc.date',
                'value': '$value',
            }},
        }},
    ]
    data = list(Payment.objects.aggregate(*agg_pipeline))
    if logger:
        logger('Данные получены: {} записей'.format(len(data)))
    # запрос организаций, присутствующих в отчёте
    providers_ids = {p['_id']['provider'] for p in data}
    providers = Provider.objects(
        id__in=list(providers_ids)
    ).only('id', 'str_name', 'inn').as_pymongo()
    providers = {p['_id']: p for p in providers}
    if logger:
        logger('Организаций: {}'.format(len(providers)))
    # запрос адресов, присутствующих в отчёте
    houses_ids = {p['_id']['house'] for p in data}
    houses = House.objects(
        id__in=list(houses_ids)
    ).only('id', 'address').as_pymongo()
    houses = {h['_id']: h for h in houses}
    if logger:
        logger('Организаций: {}'.format(len(houses)))
    # формирование отчёта
    result = [[
        'ИНН',
        'Наименование организации',
        'Адрес дома',
        'Количество платежей',
        'Количество плательщиков',
        'Сумма платежей',
        'Текущая задолженность',
    ]]
    month = month_from
    months = 0
    while month < date_end:
        result[0].append(datetime.date.strftime(month, '%m.%Y'))
        month += relativedelta(months=1)
        months += 1
    if table_print:
        table_print(';'.join(result[0]))
    for ix, house_data in enumerate(data, start=1):
        provider = providers[house_data['_id']['provider']]
        house = houses[house_data['_id']['house']]
        balance = HousesBalance(
            houses=[house['_id']],
            provider_id=provider['_id']
        )
        balance = balance.get_date_balance(date_on=date_now, sectors=['rent'])
        row = [
            provider['inn'],
            provider['str_name'],
            house['address'],
            str(len(house_data['payments'])),
            str(len({p['account'] for p in house_data['payments']})),
            str(round(
                sum(p['value'] for p in house_data['payments']) / 100,
                2
            )),
            str(round(balance[house['_id']]['val'] / 100, 2)),
        ]
        month = month_from
        while month < date_end:
            next_month = month + relativedelta(months=1)
            row.append(str(round(
                sum(
                    p['value']
                    for p in house_data['payments']
                    if month <= p['date'] < next_month
                ) / 100,
                2
            )))
            month += relativedelta(months=1)
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    # добавим дома без оплат
    houses_left = list(set(all_houses.keys()) - set(houses.keys()))
    houses = House.objects(
        id__in=houses_left).only('id', 'address').as_pymongo()
    clients = get_crm_client_ids()
    providers = Provider.objects(id__in=clients).only(
        'id', 'inn', 'str_name').as_pymongo()
    providers = {p['_id']: p for p in providers._iter_results()}
    houses = {h['_id']: h for h in houses}
    for house_id in houses_left:
        house = houses.get(house_id)
        if not house:
            continue
        balance = HousesBalance(
            houses=[house_id],
            provider_id=all_houses[house_id],
        ).get_date_balance(date_on=date_now, sectors=['rent']).get(house_id)
        provider = providers.get(all_houses[house_id])
        row = [
            provider['inn'] if provider else '',
            provider['str_name'] if provider else '',
            house['address'],
            '0.0',
            '0.0',
            '0.0',
            str(round(balance['val'] / 100, 2)) if balance else '0.0',
        ]
        row.extend(['0.0'] * months)
        result.append(row)
        if table_print:
            table_print(';'.join(row))
    return result


if __name__ == '__main__':
    register_mongoengine_connections()

    def logger(message):
        print(datetime.datetime.now(), message)

    get_acquiring_stat(
        datetime.datetime(2018, 1, 1),
        datetime.datetime(2018, 6, 1),
        logger=logger,
        table_print=print
    )

