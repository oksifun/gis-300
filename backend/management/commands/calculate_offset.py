import argparse
from datetime import datetime

from bson import ObjectId
from mongoengine import Q

from mongoengine_connections import register_mongoengine_connections
from app.offsets.core.calculator.offset import payments_to_timeline, \
    accruals_to_timeline, timeline_to_legacy, offsets_to_timeline
from app.offsets.core.calculator.timeline import Timeline
from app.offsets.tasks.calculate_offsets import _payments_query, \
    _accruals_query, _offsets_query
from processing.models.billing.accrual import Accrual
from app.offsets.models.offset import Offset
from processing.models.billing.payment import Payment
from processing.models.billing.account import Account
from processing.models.choices import *

register_mongoengine_connections()


def get_offsets(tenant_id, sector):
    tenant = Q(__raw__={"refer.account._id": tenant_id})
    sector_code = Q(refer__sector_code=sector)
    return tenant & sector_code


def get_accrual_query(tenant_id, sector_code):
    query = (
            Q(doc__status=AccrualDocumentStatus.EDIT)
            | Q(doc__status=AccrualDocumentStatus.READY)
    )
    query &= Q(
        account__id=tenant_id, is_deleted__ne=True, sector_code=sector_code
    )
    return query


def get_payment_query(tenant_id, sector_code):
    query = Q(
        account__id=tenant_id,
        is_deleted__ne=True,
        sector_code=sector_code,
        lock__ne=True
    )
    return query


def valid_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(s)
        raise argparse.ArgumentTypeError(msg)


class Data(object):
    def __init__(self):
        self.tenant = None
        self.sectors = []
        self.on_date = None
        self.provider = None


def main():
    data = Data()

    parser = argparse.ArgumentParser(description='Show tenant timeline')
    parser.add_argument(
        '--tenant', type=str, help='tenant number', required=True
    )

    available_sectors = map(lambda x: x[0], ACCRUAL_SECTOR_TYPE_CHOICES)
    parser.add_argument(
        '--sectors', type=str, nargs='+', required=True,
        help='list of sectors, available types: {a}'
        .format(a=available_sectors)
    )
    parser.add_argument(
        '--on_date', dest='on_date', type=valid_date,
        help='start calculate timeline from date - format \%Y-\%m-\%d'
    )
    parser.add_argument(
        '--provider', type=str, help='provider id', required=True
    )

    args = parser.parse_args(namespace=data)

    tenants = Account.objects(number=data.tenant)
    tenant_id = tenants[0].pk

    for sector in data.sectors:
        timeline = Timeline(provider=ObjectId(data.provider), account=tenant_id)

        payments_query = _payments_query(tenant_id, sector)
        payments = list(Payment.objects.filter(payments_query).as_pymongo())
        if len(payments):
            payments_to_timeline(timeline, payments)

        accrual_query = _accruals_query(tenant_id, sector)
        accruals = list(Accrual.objects.filter(accrual_query).as_pymongo())
        if len(accruals):
            accruals_to_timeline(timeline, accruals)

        # Получаем оффсеты жителя
        old_offsets_query = _offsets_query(tenant_id, sector)
        old_offsets = Offset.objects(old_offsets_query)
        # Отфильтруем заблокированные и добавим к таймлайну
        blocked_offsets = tuple(old_offsets.filter(lock=True).as_pymongo())
        if blocked_offsets:
            offsets_to_timeline(timeline, blocked_offsets)
        # И не заблокированные, которые удалим
        unblocked_offsets = old_offsets.filter(lock__ne=True)
        unblocked_offsets.delete()

        timeline.link_all(show_steps=True)

        new_offsets, old_accruals, old_payments = timeline_to_legacy(timeline)

        if len(new_offsets):
            Offset.objects.insert(new_offsets)
            for accrual in old_accruals:
                updater = dict(
                    repaid_at=accrual['repaid_at'],
                    unpaid_total=accrual['unpaid_total'],
                    unpaid_services=accrual['unpaid_services'],
                )
                Accrual.objects(id=accrual['_id']).update(**updater)
            for payment in old_payments:
                updater = dict(
                    redeemed=payment['redeemed'],
                )
                Payment.objects(id=payment['_id']).update(**updater)


if __name__ == "__main__":
    main()
