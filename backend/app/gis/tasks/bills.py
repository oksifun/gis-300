from datetime import datetime

from bson import ObjectId

from app.gis.services.bills import Bills
from app.gis.workers.config import gis_celery_app


@gis_celery_app.task(name='gis.import_pd')
def import_pd(provider_id: ObjectId, house_id: ObjectId,
        period: datetime = None, **options):
    """
    Загрузка из ГИС ЖКХ платежных документов за (текущий) период
    """
    Bills.exportPaymentDocumentData(
        provider_id, house_id, **options
    ).periodic(period)  # начисления за период


@gis_celery_app.task(name='gis.export_pd')
def export_pd(provider_id: ObjectId, house_id: ObjectId,
        period: datetime = None, **options):
    """
    Выгрузка в ГИС ЖКХ платежных документов за (текущий) период
    """
    Bills.importPaymentDocumentData(
        provider_id, house_id, **options
    ).periodic(period)  # начисления за период


@gis_celery_app.task(name='gis.export_document')
def export_document(provider_id: ObjectId, house_id: ObjectId,
        accrual_doc_id: ObjectId, **options):
    """
    Выгрузка в ГИС ЖКХ начислений определенного документа
    """
    Bills.importPaymentDocumentData(
        provider_id, house_id, **options
    ).document(accrual_doc_id)  # начисления документа


@gis_celery_app.task(name='gis.withdraw_document')
def withdraw_pd(provider_id: ObjectId, house_id: ObjectId,
        period: datetime = None, **options):
    """
    Отзыв из ГИС ЖКХ начислений (ПД) за период
    """
    Bills.withdrawPaymentDocumentData(
        provider_id, house_id, **options
    ).periodic(period)


if __name__ == '__main__':

    from mongoengine_connections import register_mongoengine_connections
    register_mongoengine_connections()

    p = ObjectId('526234b1e0e34c4743821d31')

    h = ObjectId('585a9daf48ba02004c862e76')  # TODO в случае нескольких домов

    from app.gis.utils.houses import get_provider_house
    h = get_provider_house(p, h, abort_failed=True)

    from app.gis.utils.common import get_period
    m = get_period(months=0)

    a = [
        ObjectId("642d63abb9f7ba003312de86"),
        ObjectId("642d63abb9f7ba003312de8c"),
        ObjectId("642d63abb9f7ba003312de8f"),
    ]  # Accrual

    # e = Bills.exportNotificationsOfOrderExecution(p, h)
    # e(*a); exit()

    # i = Bills.importAcknowledgment(p, h)
    # i(*a); exit()  # WARN

    # i = Bills.withdrawPaymentDocumentData(p, h, update_existing=True)
    # i(*a); exit()  # WARN

    # import_pd(p, h, m); exit()
    export_pd(p, h, m, element_limit=200, request_only=False); exit()  # WARN
    # withdraw_pd(p, h, m); exit()  # WARN
