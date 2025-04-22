import datetime

from dateutil.relativedelta import relativedelta

from app.area.models.area import Area
from app.house.models.house import House
from app.requests.models.request import Request
from app.requests.models.tenant_rate import TenantRate
from app.tickets.models.tenants import Ticket
from processing.data_producers.balance.base import AccountsListBalance
from processing.models.billing.account import Tenant
from processing.models.billing.log import History


def get_tenant_requests_statistic(tenant_id, worker_id, binds):
    """Получение статистики жителя по заявкам"""
    return _get_tenant_statistic(tenant_id, worker_id, Request, binds)


def get_tenant_tickets_statistic(tenant_id, worker_id, binds):
    """Получение статистики жителя по обращениям"""
    return _get_tenant_statistic(tenant_id, worker_id, Ticket, binds)


def _get_tenant_statistic(tenant_id, worker_id, model, binds):
    """
    Получение информации о жильце вместе со статистикой для переданной модели
    """
    # Получим данные о жителе и ID его сожителей
    tenant, mates_ids = _get_tenant_with_mates(tenant_id)
    # Сальдо всех сожителей на текущую дату, сгруппированную по секторам
    mates_balance = _get_mates_balance_by_sectors(mates_ids)
    # Получение статистики по модели
    objects = _get_object_stats(tenant, model)
    can_vote = _is_permit_vote(tenant, worker_id, binds)
    tenant.update(dict(
        sectors=mates_balance,
        can_vote=can_vote,
        **(
            dict(requests=objects)
            if model.__name__ == 'Request'
            else dict(tickets=objects)
        )
    ))
    return tenant


def _get_tenant_with_mates(tenant_id):
    fields = '_binds', 'password'
    tenant = Tenant.objects(id=tenant_id).exclude(*fields).as_pymongo().get()
    mates_ids = Tenant.objects(area__id=tenant['area']['_id']).distinct('id')
    _mix_porch_and_floor(tenant)
    return tenant, mates_ids


def _mix_porch_and_floor(tenant):
    query = dict(id=tenant['area']['_id'])
    floor, porch_id = Area.objects(**query).scalar('floor', 'porch').get()
    query = dict(id=tenant['area']['house']['_id'])
    house_porches = House.objects(**query).only('porches').as_pymongo().get()
    porch_number = (
        x.get('number') or ''
        for x in house_porches['porches']
        if x['_id'] == porch_id
    )
    tenant['porch_number'] = next(porch_number, '')
    tenant['area_floor'] = floor or ''


def _get_mates_balance_by_sectors(mates_ids):
    balance = AccountsListBalance(accounts=mates_ids)
    balance_in = balance.get_date_balance(
        date_on=datetime.datetime.now(),
        group_by_sector=True
    )
    return [dict(code=k, value=v) for k, v in balance_in.items()]


def _get_object_stats(tenant, model):
    # TODO Переработать без запросов ???
    query_map = dict(
        house_objects=(
            dict(area__house__id=tenant['area']['house']['_id'])
            if model.__name__ == 'Ticket'
            else dict(house__id=tenant['area']['house']['_id'])
        ),
        tenant_count=(
            dict(initial__author=tenant['_id'])
            if model.__name__ == 'Ticket'
            else dict(tenant__id=tenant['_id'])
        ),
        area_count=dict(area__id=tenant['area']['_id']),
        all_areas_count=dict(area__id__exists=True),

    )
    objects = model.objects(**query_map['house_objects']).as_pymongo()
    # Посчитаем количество поданных обращений:
    # Со всего дома
    objects_house_count = objects.count()
    # Этим пациентом
    objects_tenants_count = objects.filter(**query_map['tenant_count']).count()
    # Из его квартиры
    objects_areas_count = objects.filter(**query_map['area_count']).count()
    # Из всех квартир его дома
    areas_with_objects_count = len(
        objects.filter(**query_map['all_areas_count']).distinct('area.id')
    )
    result = dict(
        house_count=objects_house_count,
        tenant_count=objects_tenants_count,
        area_count=objects_areas_count,
        areas_from_house_count=areas_with_objects_count,
    )
    return result


def _is_permit_vote(tenant, worker_id, binds):
    return TenantRate.worker_can_rate_tenant(worker_id, tenant['_id'], binds)
