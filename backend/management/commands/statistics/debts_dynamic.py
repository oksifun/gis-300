import datetime

from bson import ObjectId
from dateutil.relativedelta import relativedelta

from app.area.models.area import Area
from app.messages.core.email.extended_mail import RareMail
from app.offsets.models.offset import Offset
from processing.data_producers.associated.base import get_provider_services_tree
from processing.models.billing.accrual import Accrual
from processing.models.billing.account import Tenant


def debts_dynamic(logger, month, email=None):
    # группы услуг
    system_services_tree = get_provider_services_tree(None)
    communal_services = system_services_tree['communal_services']
    maintenance_services = system_services_tree['maintenance']
    logger(message='services ready')
    # начислено за месяц
    accruals = _get_accruals(month, communal_services, maintenance_services)
    logger(message='saccruals ready')
    # данные домов
    houses = {
        (h['_id']['p'], h['_id']['h']): h
        for h in _get_houses_data(month)
    }
    for h in houses.values():
        h['tt_tot'] = len(h['tt'])
        tt = Tenant.objects(__raw__={
            '_id': {'$in': h['tt']},
            'has_access': True,
            'activation_code': {'$exists': False},
            'activation_step': {'$exists': False},
        }).count()
        h['tt_acc'] = tt
        areas = Area.objects(__raw__={
            '_id': {'$in': h['aa']}
        }).as_pymongo().only('area_total')
        h['area'] = sum(a['area_total'] for a in list(areas))
    logger(message='houses ready')
    # оплаты
    date = month + relativedelta(months=1)
    date_e = datetime.datetime.now().replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    header = 'ИНН;Адрес;Площадь;Кол. ЛС;Кол. ЛКЖ;' \
             'Нач.КУ;Нач.ЖУ;Нач.ПР;Нач.пени;Оплачено'
    logger(message='offsets starting')
    while date <= date_e:
        header += ';{0} КУ;{0} ЖУ;{0} ПР;{0} пени'.format(
            date.strftime('%d.%m.%Y')
        )
        offsets = _get_offsets(
            month,
            date,
            communal_services,
            maintenance_services,
        )
        for key, accrual in accruals.items():
            offset = offsets.get(key)
            if offset:
                for k in ('c', 'm', 'o', 'p'):
                    accrual[k]['pay'] = offset[k]['val']
                    accrual[k]['debts'].append(
                        accrual[k]['debt'] - offset[k]['val']
                    )
        date += relativedelta(months=1)
        logger(message='offsets {} ready'.format(date.strftime('%d.%m.%Y')))
    result = [header]
    for key, accrual in accruals.items():
        pay = sum(accrual[k]['pay'] for k in ('c', 'm', 'o', 'p'))
        row = '{};{};{:.2f};{};{};{:.2f};{:.2f};{:.2f};{:.2f};{:.2f}'.format(
            houses[key]['inn'],
            houses[key]['addr'],
            houses[key]['area'],
            houses[key]['tt_tot'],
            houses[key]['tt_acc'],
            accrual['c']['val'] / 100,
            accrual['m']['val'] / 100,
            accrual['o']['val'] / 100,
            accrual['p']['val'] / 100,
            pay / 100,
        )
        for ix in range(len(accrual['c']['debts'])):
            row += ';{}'.format(
                ';'.join([
                    '{:.2f}'.format(accrual[k]['debts'][ix] / 100)
                    for k in ('c', 'm', 'o', 'p')
                ])
            )
        result.append(row)
    logger(message='table ready')
    if email:
        _send(result, email)
    return result


def _send(data, email):
    reg_str = '\n'.join(data)
    file = reg_str.encode()
    filename = 'debts_stat_{}.csv'.format(datetime.datetime.now().isoformat())
    attachment = dict(
        name=filename,
        bytes=file,
        type='text',
        subtype='plain'
    )
    mail = RareMail(
        _from='dr.hugo.strange@s-c300.com',
        to=email,
        subject='Report {}'.format(filename),
        body='',
        attachments=[attachment],
        addresses=[email]
    )
    mail.send()


def _get_accruals(month, communal_services, maintenance_services):
    accruals_pipeline = [
        {'$match': {
            'month': month,
            'doc.status': {'$in': ['ready', 'edit']},
            'is_deleted': {'$ne': True},
            'doc.date': {
                '$gte': month - relativedelta(months=1),
                '$lt': month + relativedelta(months=2),
            },
        }},
        {'$project': {
            'owner': 1,
            'account.area.house._id': 1,
            'services.service_type': 1,
            'services.value': 1,
            'services.totals': 1,
        }},
        {'$unwind': '$services'},
        {'$project': {
            'owner': 1,
            'house': '$account.area.house._id',
            'service': '$services.service_type',
            'value': {'$add': [
                '$services.value',
                '$services.totals.privileges',
                '$services.totals.recalculations',
                '$services.totals.shortfalls',
            ]},
        }},
        {'$project': {
            'owner': 1,
            'house': 1,
            'service': 1,
            'value': 1,
            'debt': {'$cond': [
                {'$gt': ['$value', 0]},
                '$value',
                {'$literal': 0},
            ]},
        }},
        {'$group': {
            '_id': {
                'h': '$house',
                's': '$service',
                'p': '$owner',
            },
            'val': {'$sum': '$value'},
            'debt': {'$sum': '$debt'},
        }},
    ]
    accruals = list(Accrual.objects.aggregate(*accruals_pipeline))
    accruals = _group_services(
        accruals,
        communal_services,
        maintenance_services,
    )
    accruals_pipeline = [
        {'$match': {
            'month': month,
            'doc.status': {'$in': ['ready', 'edit']},
            'is_deleted': {'$ne': True},
            'doc.date': {
                '$gte': month - relativedelta(months=1),
                '$lt': month + relativedelta(months=2),
            },
        }},
        {'$project': {
            'owner': 1,
            'house': '$account.area.house._id',
            'value': '$totals.penalties',
        }},
        {'$project': {
            'owner': 1,
            'house': 1,
            'value': 1,
            'debt': {'$cond': [
                {'$gt': ['$value', 0]},
                '$value',
                {'$literal': 0},
            ]},
        }},
        {'$group': {
            '_id': {
                'h': '$house',
                'p': '$owner',
            },
            'val': {'$sum': '$value'},
            'debt': {'$sum': '$debt'},
        }},
    ]
    penalties = {
        (p['_id']['p'], p['_id']['h']): p
        for p in list(Accrual.objects.aggregate(*accruals_pipeline))
    }
    for key, accrual in accruals.items():
        penalty = penalties.get(key)
        if penalty:
            accrual['p']['val'] += penalty['val']
            accrual['p']['debt'] += penalty['debt']
    return accruals


def _get_offsets(month, date, communal_services, maintenance_services):
    offsets_pipeline = [
        {'$match': {
            'accrual.month': month,
            'refer.doc.date': {'$lt': date},
        }},
        {'$project': {
            'refer.doc.provider': 1,
            'refer.account.area.house._id': 1,
            'services.service_type': 1,
            'services.value': 1,
        }},
        {'$unwind': '$services'},
        {'$project': {
            'owner': '$refer.doc.provider',
            'house': '$refer.account.area.house._id',
            'service': '$services.service_type',
            'value': '$services.value',
        }},
        {'$group': {
            '_id': {
                'h': '$house',
                's': '$service',
                'p': '$owner',
            },
            'val': {'$sum': '$value'},
        }},
    ]
    offsets = list(Offset.objects.aggregate(*offsets_pipeline))
    return _group_services(offsets, communal_services, maintenance_services)


_OLD_PENALTY_SERVICE_TYPE = ObjectId('0' * 24)


def _group_services(data_list, communal_services, maintenance_services):
    def def_dict():
        return {'val': 0, 'debt': 0, 'pay': 0, 'debts': []}

    result = {}
    for data in data_list:
        house_data = result.setdefault(
            (data['_id']['p'], data['_id']['h']),
            {
                'c': def_dict(),
                'm': def_dict(),
                'o': def_dict(),
                'p': def_dict()
            },
        )
        if data['_id']['s'] in communal_services:
            key = 'c'
        elif data['_id']['s'] in maintenance_services:
            key = 'm'
        elif data['_id']['s'] == _OLD_PENALTY_SERVICE_TYPE:
            key = 'p'
        else:
            key = 'o'
        house_data[key]['val'] += data['val']
        if 'debt' in data:
            house_data[key]['debt'] += data['debt']
    return result


def _get_houses_data(month):
    aa_p = [
        {'$match': {
            'month': month,
            'doc.status': {'$in': ['ready', 'edit']},
            'is_deleted': {'$ne': True},
            'doc.date': {
                '$gte': month - relativedelta(months=1),
                '$lt': month + relativedelta(months=2),
            },
        }},
        {'$project': {
            'owner': 1,
            'account._id': 1,
            'account.area._id': 1,
            'account.area.house._id': 1,
        }},
        {'$group': {
            '_id': {
                'h': '$account.area.house._id',
                'p': '$owner',
            },
            'tt': {'$addToSet': '$account._id'},
            'aa': {'$addToSet': '$account.area._id'},
        }},
        {'$lookup': {
            'from': 'House',
            'localField': '_id.h',
            'foreignField': '_id',
            'as': 'house',
        }},
        {'$unwind': '$house'},
        {'$project': {
            'tt': 1,
            'aa': 1,
            'addr': '$house.address',
            'area': '$house.area_total',
        }},
        {'$lookup': {
            'from': 'Provider',
            'localField': '_id.p',
            'foreignField': '_id',
            'as': 'provider',
        }},
        {'$unwind': '$provider'},
        {'$project': {
            'tt': 1,
            'aa': 1,
            'addr': 1,
            'area': 1,
            'inn': '$provider.inn',
        }},
    ]
    return list(Accrual.objects.aggregate(*aa_p))
