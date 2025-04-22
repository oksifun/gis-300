import datetime

from dateutil.relativedelta import relativedelta


def update_accrual_doc_payers_count(payment):
    from processing.models.billing.accrual import Accrual
    from processing.celery.workers.harley_quinn.tasks import \
        mark_accruals_ready_to_pay

    accrual_key = (
        payment.value,
        payment.sector_code,
        payment.month,
        payment.account.id,
    )
    fields = 'month', 'sector_code', 'account.id', 'doc.id'
    accruals = Accrual.objects(
        bill__exists=True,
        month__gte=payment.month,
        account__id=payment.account.id,
        is_deleted__ne=True,
        doc__status__in=['ready', 'edit'],
        doc__date__gte=datetime.datetime.now() - relativedelta(months=1),
    ).only('bill', *fields).as_pymongo()
    if [a['month'] for a in accruals if a['month'] > payment.month]:
        return
    accruals = {
        (
            x['bill'],
            x['sector_code'],
            x['month'],
            x['account']['_id'],
        ): x['doc']['_id']
        for x in accruals
    }
    doc_id = accruals.get(accrual_key)
    if not doc_id:
        return
    mark_accruals_ready_to_pay.delay(doc_id=doc_id, count_paid=True)
    return True
