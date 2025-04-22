from celery.schedules import crontab

_QUEUE = 'calculate_accruals'
CALCULATE_ACCRUALS_SCHEDULE = {
    'resurrect-accrual-doc-tasks': {
        'task': 'app.accruals.tasks.pipca.tasks_control.'
                'resurrect_cipca_tasks',
        'schedule': crontab(minute='*/4'),
    },
}
CALCULATE_ACCRUALS_TASK_ROUTES = {
    'app.accruals.tasks.pipca.tasks_control.resurrect_cipca_tasks': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.accrual_doc.run_document': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.accrual_doc.create_accrual_doc': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.accrual_doc.copy_accrual_doc': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.accrual_doc.tariff_plan_apply': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.accrual_doc.add_account_to_accrual_doc': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.accrual_doc.calculate_total': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.accrual_doc'
    '.public_communal_recalculation_apply': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.accrual_doc'
    '.public_communal_recalculation_update': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.accrual_doc.run_accruals': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.consumption.set_consumption_methods': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.manual.manual_accrual_set': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.manual.manual_service_set': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.manual.manual_recalculation_set': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.manual.manual_privilege_set': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.manual.manual_totals_set': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.manual.manual_public_communal_set': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.mass_calculation.run_houses_calculate_tasks': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.mass_calculation.run_houses_receipt_tasks': {
        'queue': 'big_receipts',
    },
    'app.accruals.tasks.pipca.mass_calculation.zip_houses_receipts': {
        'queue': 'big_receipts',
    },
    'app.accruals.tasks.pipca.mass_calculation.mass_calculate_service_group': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.mass_calculation.mass_calculate_penalties': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.mass_calculation.mass_create_accrual_doc': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.penalty.penalty_calculate': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.penalty.manual_penalty_set': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.penalty.penalty_settings': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.penalty.change_penalty': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.penalty.remove_penalty': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.accrual_doc.recalculate_accrual': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.recalculation.recalculation_add': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.recalculation.recalculation_group_add': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.recalculation.recalculation_remove': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.shortfalls.shortfall_add': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.shortfalls.shortfall_group_add': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.pipca.shortfalls.shortfall_remove': {
        'queue': _QUEUE
    },
}
