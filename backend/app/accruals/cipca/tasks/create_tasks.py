from app.accruals.cipca.source_data.house import get_house_settings
from app.accruals.models.accrual_document import AccrualDoc
from processing.models.billing.settings import Settings
from app.accruals.models.tasks import SubTask, CipcaTask, ProviderEmbedded
from processing.models.exceptions import CustomValidationError
from processing.models.tasks.choices import TaskStateType


def create_run_task(author_id, doc_id, accounts_filter=None, sectors=None,
                    sectors_for_debit_include=None, credit_include=True,
                    send_registries=False, run_autopay_notify=False):
    doc = AccrualDoc.objects(pk=doc_id).get()
    task = CipcaTask(
        doc=doc_id,
        accounts_filter=accounts_filter,
        author=author_id,
        name='create_run_task',
    )
    task.save()
    sectors_providers = {
        s_b.sector_code: s_b.provider
        for s_b in doc.sector_binds
    }
    if sectors is None:
        sectors = list(sectors_providers.keys())
    if sectors_for_debit_include is None:
        house_settings = get_house_settings(
            doc.house.id,
            list(set(sectors_providers.values())),
        )
        sectors_for_debit_include = []
        for sector in sectors:
            provider_settings = house_settings[sectors_providers[sector]]
            for s_settings in provider_settings['sectors']:
                if (
                        s_settings['sector_code'] == sector
                        and s_settings.get('include_debt')
                ):
                    sectors_for_debit_include.append(sector)
    settings = {}
    for sector in sectors:
        if sectors_providers[sector] not in settings:
            settings[sectors_providers[sector]] = Settings.objects(
                _type='ProviderAccrualSettings',
                provider=sectors_providers[sector],
            ).as_pymongo().first()
        task.tasks.append(
            SubTask(
                name='run_document',
                kwargs={
                    'sector': sector,
                    'debit_include': sector in sectors_for_debit_include,
                    'credit_include': credit_include,
                    'send_registries': send_registries,
                    'run_autopay_notify': run_autopay_notify,
                },
            ),
        )
    task.state = 'new'
    task.save()
    task.run(task.pk)
    return task.pk


def create_calculate_task(author_id, subtask_name, description=None,
                          doc_id=None, mass_operation=False, period=None,
                          provider_name=None, provider_id=None, parent=None,
                          house_id=None, autorun=True, auto_execute=True,
                          **kwargs):
    if kwargs.get('account'):
        account = kwargs.get('account')
    elif kwargs.get('accounts'):
        account = kwargs['accounts'][0]
    else:
        account = None
    if kwargs.get('date'):
        kwargs['date'] = kwargs['date'].replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    task = CipcaTask(
        doc=doc_id,
        accounts_filter=kwargs.get('filter'),
        account_id=account,
        author=author_id,
        name='create_calculate_task',
        description=description,
        url=kwargs.get('page_url'),
        provider=ProviderEmbedded(
            id=provider_id,
            str_name=provider_name
        ),
        period=period,
        parent=parent,
        house=house_id,
    )
    task.save()
    if not mass_operation:
        task.tasks.append(
            SubTask(
                name=subtask_name,
                kwargs=kwargs,
            ),
        )
    else:
        for sub_task_args in kwargs['kwargs']:
            task.tasks.append(
                SubTask(
                    name=subtask_name,
                    kwargs=sub_task_args,
                ),
            )
    task.state = 'new'
    task.save()
    task.reload()
    if not task.pk:
        raise CustomValidationError(
            'Произошла ошибка, пожалуйста, попробуйте еще раз.',
        )
    if autorun:
        celery_tasks = task.run(task.pk, auto_execute=auto_execute)
        if not auto_execute:
            return task.pk, celery_tasks
    return task.pk
