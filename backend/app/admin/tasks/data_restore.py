import datetime

from bson import ObjectId

from app.admin.core.data_restore.area_data import restore_area_data
from app.admin.core.data_restore.houses import restore_house_data, \
    restore_provider_houses_data
from app.admin.core.data_restore.offsets_restore import ProviderFinDataRestore, \
    restore_offsets_by_provider, restore_offsets_by_account
from app.admin.core.data_restore.personnel import \
    restore_provider_personnel_data
from app.admin.core.data_restore.tariffs import restore_tariff_plan, \
    restore_regional_settings
from app.admin.core.data_restore.telephony import restore_telephony
from app.admin.models.choices import LOCAL_BASES_IPS, DataRestoreDataType, \
    DataRestoreTaskState
from app.admin.models.data_restore_task import DataBaseRestoreTask, \
    DataBaseRestoreLog
from app.celery_admin.workers.config import celery_app


def split_restore_offsets_by_provider(task_id, provider_id, batch_size=None,
                                      host='10.1.1.221', logger=None):
    restorer = ProviderFinDataRestore(
        host,
        batch_size=batch_size,
        logger=logger,
    )
    DataBaseRestoreTask.objects(
        pk=task_id,
    ).update(
        parts_left=len(restorer.get_models_list()),
    )
    for ix, model in enumerate(restorer.get_models_list()):
        restore_data_by_func.delay(
            task_id,
            restore_offsets_by_provider,
            params={
                'pipline_ix': ix,
                'provider_id': ObjectId(provider_id),
                'host': host,
                'batch_size': batch_size,
                'logger': logger,
            },
        )


_RESTORE_FUNCS = {
    DataRestoreDataType.HOUSE: (
        restore_house_data,
        'house_id',
        False,
    ),
    DataRestoreDataType.PROVIDER_HOUSES: (
        restore_provider_houses_data,
        'provider_id',
        True,
    ),
    DataRestoreDataType.AREA: (
        restore_area_data,
        'area_id',
        False,
    ),
    DataRestoreDataType.PROVIDER: (
        restore_provider_personnel_data,
        'provider_id',
        False,
    ),
    DataRestoreDataType.OFFSETS_PROVIDER: (
        split_restore_offsets_by_provider,
        'provider_id',
        True,
    ),
    DataRestoreDataType.OFFSETS_ACCOUNT: (
        restore_offsets_by_account,
        'account_id',
        False,
    ),
    DataRestoreDataType.TARIFF_PLAN: (
        restore_tariff_plan,
        'tp_id',
        False,
    ),
    DataRestoreDataType.REGIONAL_SETTINGS: (
        restore_regional_settings,
        'region_code',
        False,
    ),
    DataRestoreDataType.TELEPHONY: (
        restore_telephony,
        'provider_id',
        False,
    ),
}


@celery_app.task(
    soft_time_limit=4 * 60 * 60,
    rate_limit='10/s',
    bind=True
)
def restore_data_by_func(self, task_id, func, params):
    DataBaseRestoreLog(
        message=f'started {str(params)}',
        task=task_id,
    ).save()
    try:
        func(**params)
    except Exception as e:
        DataBaseRestoreTask.objects(
            pk=task_id,
        ).update(
            state=DataRestoreTaskState.ERROR,
            inc__parts_left=-1,
        )
        DataBaseRestoreLog(
            message=f'failed {str(params)}: {str(e)}',
            task=task_id,
        ).save()
        raise e
    DataBaseRestoreLog(
        message=f'finished {str(params)}',
        task=task_id,
    ).save()
    DataBaseRestoreTask.objects(
        pk=task_id,
    ).update(
        inc__parts_left=-1,
    )
    task = DataBaseRestoreTask.objects(
        pk=task_id,
    ).get()
    if task.state == DataRestoreTaskState.WIP and task.parts_left <= 0:
        DataBaseRestoreTask.objects(
            pk=task_id,
        ).update(
            state=DataRestoreTaskState.SUCCESS,
            finished=datetime.datetime.now(),
        )


@celery_app.task(
    soft_time_limit=4 * 60 * 60,
    rate_limit='10/s',
    bind=True
)
def restore_data(self, task_id, data_type, object_id, base_name):
    task = DataBaseRestoreTask.objects(pk=task_id).get()
    if task.state != DataRestoreTaskState.NEW:
        raise ValueError(f'Wrong task state {task.state}')
    DataBaseRestoreTask.objects(
        pk=task_id,
    ).update(
        state=DataRestoreTaskState.WIP,
    )
    func, obj_field, split_tasks = _RESTORE_FUNCS[data_type]
    params = {
        obj_field: object_id,
        'host': LOCAL_BASES_IPS[base_name],
    }
    if split_tasks:
        func(task_id=task_id, **params)
        result = 'Splitted'
    else:
        try:
            result = func(**params)
            DataBaseRestoreTask.objects(
                pk=task_id,
            ).update(
                state=DataRestoreTaskState.SUCCESS,
                finished=datetime.datetime.now(),
            )
        except Exception as e:
            DataBaseRestoreTask.objects(
                pk=task_id,
            ).update(
                state=DataRestoreTaskState.ERROR,
            )
            DataBaseRestoreLog(
                message=f'error {str(e)}',
                task=task_id,
            ).save()
            raise e
    return result
