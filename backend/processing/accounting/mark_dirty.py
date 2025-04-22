from mongoengine import Q

from processing.celery.tasks.swamp_thing.accounting_exchange import \
    add_account_to_sync, add_accrual_to_sync, add_payment_to_sync
from processing.models.billing.payment import Payment
from processing.models.billing.accrual import Accrual
from processing.models.billing.responsibility import Responsibility


def mark_dirty_accounts(provider_id, acc_from_accruals=None,
                        acc_from_payments=None):
    """ Отмечает все лицевые счета провайдера как несверенные """
    # Получение id жителей отвественных
    responsibility_acc_ids = Responsibility.objects(
        provider=provider_id
    ).as_pymongo().distinct("account._id")
    responsibility_acc_ids = set(responsibility_acc_ids)

    # Добавление жителей документов оплат и начислений
    if acc_from_accruals:
        responsibility_acc_ids.union(set(acc_from_accruals))
    if acc_from_payments:
        responsibility_acc_ids.union(set(acc_from_payments))

    # Добавление всех аккаунтов в синхронизацию AccountingSyncTask через Celery
    add_account_to_sync.delay(provider_id, list(responsibility_acc_ids))


def mark_dirty_accruals(provider_id, date_from=None, date_till=None):
    """ Отмечает все начисления провайдера как несверенные """
    # Получение id всех всех начислений
    if date_from and date_till:
        date_query = Q(doc__date__lte=date_till) & Q(doc__date__gte=date_from)
        all_provider_accruals_ids = Accrual.objects(
            date_query,
            doc__provider=provider_id
        ).only('id', 'account.id').as_pymongo()
    else:
        all_provider_accruals_ids = Accrual.objects(
            doc__provider=provider_id
        ).only('id', 'account.id').as_pymongo()
    # id жителей
    acc_from_accruals = all_provider_accruals_ids.distinct("account._id")
    all_provider_accruals_ids = all_provider_accruals_ids.distinct("_id")
    # Добавление всех документов в синхронизацию AccountingSyncTask через Celery
    add_accrual_to_sync.delay(provider_id, all_provider_accruals_ids)
    return acc_from_accruals


def mark_dirty_payments(provider_id, date_from=None, date_till=None):
    """ Отмечает все платежи провайдера как несверенные """
    # Получение id всех всех платежей
    if date_from and date_till:
        date_query = Q(date__lte=date_till) & Q(date__gte=date_from)
        all_provider_payments_ids = Payment.objects(
            date_query,
            doc__provider=provider_id
        ).only('id', 'account.id').as_pymongo()
    else:
        all_provider_payments_ids = Payment.objects(
            doc__provider=provider_id
        ).only('id', 'account.id').as_pymongo()
    # id жителей
    acc_from_payments = all_provider_payments_ids.distinct("account._id")
    all_provider_payments_ids = all_provider_payments_ids.distinct("_id")
    # Добавление всех документов в синхронизацию AccountingSyncTask через Celery
    add_payment_to_sync.delay(provider_id, all_provider_payments_ids)
    return acc_from_payments


def mark_dirty_all(provider_id, date_from=None, date_till=None):
    """ Отмечает все как несверенное (лицевые счета, платежи, начисления) """
    accruals_ids = mark_dirty_accruals(provider_id, date_from, date_till)
    payments_ids = mark_dirty_payments(provider_id, date_from, date_till)
    mark_dirty_accounts(provider_id, accruals_ids, payments_ids)
