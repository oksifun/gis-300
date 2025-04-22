from io import BytesIO
from zipfile import ZipFile


from app.accruals.billing.tools import TenantBill
from app.accruals.models.accrual_document import AccrualDoc
from app.celery_admin.workers.config import celery_app
from app.file_storage.models.clean_task import CleanFilesTask

from bson import ObjectId

from lib.gridfs import put_file_to_gridfs

from processing.models.billing.account import Tenant
from processing.models.billing.accrual import Accrual

from settings import CELERY_SOFT_TIME_MODIFIER


@celery_app.task(
    bind=True,
    max_retries=2,
    soft_time_limit=60 * 50 * CELERY_SOFT_TIME_MODIFIER,
    default_retry_delay=30
)
def create_zip_archive_receipt(self, accrual_doc: ObjectId) -> str:
    """Таска создает архив из квитанций

    Таска получает Id Документа начисления и ищет по нему все Начисления,
    после чего ищет Лицевые счета по начислениям, создает по каждому начислению
    отдельный PDF файл и добавляет его в архив, после окончания цикла,
    сохраняет архив в базу.

    Args:
        self: celery таска
        accrual_doc: Id Документа начисления
    Returns:
        str строковое значение Id записи в Gridfs

    """
    accruals = Accrual.objects(doc__id=accrual_doc).only(
        'account.id',
        'sector_code',
    )
    accounts = Tenant.objects(
        id__in=accruals.distinct('account.id'),
    ).only('number').as_pymongo()
    dict_acc_number = {acc['_id']: acc['number'] for acc in accounts}
    buffer = BytesIO()
    acc_doc = AccrualDoc.objects(id=accrual_doc).first()
    date_acc_doc = f'{acc_doc.date_from.year}-{acc_doc.date_from.month:02d}'
    with ZipFile(buffer, 'a') as zip_archive:
        for acc in accruals:
            tenant_bill = TenantBill(
                accrual_doc,
                acc.account.id,
                binds=None,
            )
            file = tenant_bill.create(
                [acc.sector_code],
                tenants=[acc.account.id],
            )
            zip_archive.writestr(
                f'{dict_acc_number[acc.account.id]}-{date_acc_doc}.pdf',
                data=file,
            )
        zip_archive.close()
        file_id, file_uuid = put_file_to_gridfs(
            resource_name='Accrual',
            resource_id=accrual_doc,
            file_bytes=buffer.getvalue(),
            filename=f'Выгрузка квитанций.zip',
        )
        CleanFilesTask(file=ObjectId(file_id)).save()
    return str(file_id)

