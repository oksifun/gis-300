from processing.models.logging.gis_log import GisImportStatus
from processing.models.tasks.base import Task, ZipSiblingsFilesTask

from processing.models.tasks.gis.base import GisBaseExportRequest, \
    GisBaseImportRequest


def get_GIS_task_statuses(provider_id, task_cls):
    if task_cls in GisBaseExportRequest.__subclasses__():
        c_name = 'Task.RequestTask.GisBaseExportRequest.{}'.format(
            task_cls.__name__)
        finish_task_cls = ZipSiblingsFilesTask
    elif task_cls in GisBaseImportRequest.__subclasses__():
        c_name = 'Task.RequestTask.GisBaseImportRequest.{}'.format(
            task_cls.__name__)
        finish_task_cls = None
    else:
        return None
    tasks = Task.objects.as_pymongo().filter(
        provider=provider_id,
        _cls=c_name
    ).only('id', 'created', 'status', '_cls').order_by('-created')[0: 1]
    if not tasks:
        return None
    request_task = tasks[0]
    if request_task['status'] == 'error':
        return {'status': 'fail'}
    elif request_task['status'] != 'done':
        return {'status': 'work_in_progress'}
    tasks = list(Task.objects.as_pymongo().filter(
        parent=request_task['_id']
    ))
    if not tasks:
        return {'status': 'fail'}
    ended_dates = [t['ended'] for t in tasks if t.get('ended')]
    ended_date = max(ended_dates) if ended_dates else None
    statuses = {t['status'] for t in tasks}
    # Проверка записи об ошибке обработки задачи по оплатам
    errors = GisImportStatus.objects(
        task=request_task['_id'],
        is_error=True
    ).as_pymongo().distinct('description')
    if 'error' in statuses:
        return {
            'status': 'error',
            'ended': ended_date,
            'descriptions': errors
        }
    if len(statuses - {'done'}) == 0:
        if not finish_task_cls:
            # завершающей задачи не будет, значит должна быть одна задача
            if len(tasks) == 1:
                return {
                    'status': 'done',
                    'ended': ended_date,
                    'descriptions': errors
                }
            else:
                return {
                    'status': 'error',
                    'ended': ended_date,
                    'descriptions': errors
                }
        f_task = finish_task_cls.objects.as_pymongo().filter(
            parent=request_task['_id']
        ).first()
        if f_task:
            return {
                'status': 'done',
                'ended': ended_date,
                'file': f_task['file_uuid'],
                'descriptions': errors
            }
        return {'status': 'fail', 'ended': ended_date, 'descriptions': errors}
    else:
        return {'status': 'work_in_progress'}

