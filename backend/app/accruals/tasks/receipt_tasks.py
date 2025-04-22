from mongoengine import ValidationError

from app.accruals.billing.tools import TenantBill, set_receipt_filename
from app.accruals.models.tasks import HousesCalculateTask
from app.accruals.tasks.pipca.base import CipcaTaskLocked
from app.caching.models.cache_lock import CacheLock
from app.caching.models.filters import FilterCache
from app.celery_admin.workers.config import celery_app
from app.file_storage.models.clean_task import CleanFilesTask
from app.messages.models.messenger import UserTasks
from lib.gridfs import put_file_to_gridfs
from processing.celery.workers.penguin.logic import get_current_and_archive_file
from app.accruals.models.accrual_document import AccrualDoc, ReceiptFiles
from processing.models.house_choices import PrintBillsType
from processing.models.tasks.choices import TaskStateType
from processing.models.tasks.receipt import ReceiptPDFTask
from settings import CELERY_SOFT_TIME_MODIFIER


def _check_lock(task, lock_key, raise_exception=True):
    if not lock_key:
        return True
    task_copy = ReceiptPDFTask.objects(
        pk=task.id,
    ).only(
        'lock_key',
    ).as_pymongo().first()
    if task_copy.get('lock_key') == lock_key:
        return True
    if not task.parent:
        return True
    parent = HousesCalculateTask.objects(
        pk=task.parent,
    ).only(
        'lock_key',
    ).as_pymongo().first()
    if not parent:
        return True
    result = parent.get('lock_key') == lock_key
    if not result and raise_exception:
        raise CipcaTaskLocked()
    return result


@celery_app.task(
    bind=True,
    max_retries=2,
    soft_time_limit=60 * 30 * CELERY_SOFT_TIME_MODIFIER,
    default_retry_delay=30
)
def run_creating_all_receipt(self, task_id, sub_task_ix, lock_key=None):
    task = ReceiptPDFTask.objects(pk=task_id).get()
    if task.state == TaskStateType.FINISHED:
        return 'already finished'
    sub_task = task.tasks[sub_task_ix]
    task_name = 'save_pdf_receipt'
    task.change_sub_task_state(
        task.id,
        sub_task_ix,
        task_name,
        'wip',
        progress=0,
    )
    accrual_doc_id = task.doc or sub_task.kwargs['doc']
    accrual_doc = AccrualDoc.objects(id=accrual_doc_id).first()
    address = accrual_doc.house.address
    try:
        _check_lock(task, lock_key)
        if self and CacheLock.doc_is_locked(AccrualDoc, accrual_doc_id):
            if self.request.retries < self.max_retries:
                raise self.retry()
        locker_name = self.request.id if self else 'run_creating_all_receipt'
        CacheLock.lock_doc(
            AccrualDoc,
            accrual_doc_id,
            secs=60 * 30 * CELERY_SOFT_TIME_MODIFIER,
            locker=locker_name,
        )
        if not accrual_doc.sector_binds:
            raise ValidationError(
                'У документа начислений нет настроек по направлениям'
            )
        sectors = sub_task.kwargs['sectors']
        file_name = sub_task.kwargs['file_name']
        user_id = task.author
        if task.accounts_filter:
            tenants = FilterCache.extract_objs(task.accounts_filter)
        else:
            tenants = None

        print_bills_type = sub_task.kwargs.get('print_bills_type')
        to_render = tuple()
        if print_bills_type != PrintBillsType.ENTIRE:
            from processing.models.billing.account import Tenant

            if tenants:
                query_kwargs = dict(tenant_ids=tenants)
            else:
                query_kwargs = dict(house_id=accrual_doc.house.id)
            recipients = Tenant.recipients_channels(**query_kwargs)

            if print_bills_type == PrintBillsType.ONLY_PAPERS:
                to_render = tuple(
                    tenant['_id'] for tenant in recipients
                    if not tenant['disabled_paper']
                )
                to_render = to_render or 0
            elif print_bills_type == PrintBillsType.NO_CHANNELS:
                to_render = []
                for tenant in recipients:
                    channels = (
                        tenant['telegram'],
                        tenant['mobile_app'],
                        tenant['email'],
                    )
                    if tenant['print_anyway']:
                        to_render.append(tenant['_id'])
                    elif not any(channels):
                        to_render.append(tenant['_id'])
                to_render = to_render or 0

        tenant_bill = TenantBill(
            accrual_doc.id,
            user_id,
            task=task,
            subtask_ix=sub_task_ix,
        )
        file = tenant_bill.create(
            sectors=sectors,
            tenants=tenants,
            settings_params=sub_task.kwargs['settings_params'],
            tenants_to_render=to_render,
        )

        task.reload()

        if task.state == 'canceled':
            return 'canceled'

        file_id, file_uuid = put_file_to_gridfs(
            resource_name='AccrualDoc',
            resource_id=accrual_doc.id,
            file_bytes=file,
            filename=file_name
        )
        sector_code_name = ','.join(sorted(sectors))
        new_file, archive_file, = get_current_and_archive_file(
            file_name, file_id, sector_code_name, accrual_doc
        )

        if accrual_doc.archive:
            accrual_doc.archive.append(archive_file)
        else:
            accrual_doc.archive = [archive_file]
        new_file = ReceiptFiles(
            sector_code=sector_code_name,
            file=new_file
        )
        if accrual_doc.receipt_files:
            accrual_doc.receipt_files.append(new_file)

        else:
            accrual_doc.receipt_files = [new_file]

        accrual_doc.save(print_receipt=True)

        task.change_sub_task_state(
            task.id,
            sub_task_ix,
            task_name,
            'finished'
        )
    except CipcaTaskLocked as e:
        raise e
    except Exception as error:
        task.change_sub_task_state(
            task.id,
            sub_task_ix,
            task_name,
            'failed'
        )
        if not task.parent:
            message = f"Ошибка в формировании квитанций ({address})"
            if isinstance(error, ValidationError):
                message = f'{message}: {str(error)}'
            UserTasks.send_message(
                task.author,
                message,
                url=task.url,
            )
        raise error
    finally:
        locker_name = self.request.id if self else 'run_creating_all_receipt'
        CacheLock.unlock_doc(
            AccrualDoc,
            accrual_doc_id,
            locker=locker_name,
        )
        if task.parent:
            from app.accruals.tasks.pipca.mass_calculation import \
                run_houses_receipt_tasks
            HousesCalculateTask.inc_ready_tasks(task.parent)
            run_houses_receipt_tasks.delay(task.parent)
    return 'success'


@celery_app.task(
    bind=True,
    max_retries=5,
    soft_time_limit=60 * 15 * CELERY_SOFT_TIME_MODIFIER,
    default_retry_delay=30
)
def get_receipt_file(self, accrual, user_id, file_name='', binds=None):
    tenant_bill = TenantBill(
        accrual['doc']['_id'],
        user_id,
        binds=binds,
    )
    try:
        file = tenant_bill.create(
            [accrual['sector_code']],
            tenants=[accrual['account']['_id']],
        )
        if not file_name:
            file_name = set_receipt_filename(
                [accrual['sector_code']],
                area=accrual['account']['area']['str_number']
            )
        file_id, file_uuid = put_file_to_gridfs(
            resource_name='Accrual',
            resource_id=accrual['_id'],
            file_bytes=file,
            filename=file_name,
        )
        CleanFilesTask(file=file_id).save()
    except Exception as error:
        raise error
    file_data = {
        'file_id': str(file_id),
        'author': str(user_id)
    }
    return file_data
