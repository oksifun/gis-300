_QUEUE = 'little_receipts'
TOYMAN_SCHEDULE = {}
TOYMAN_TASK_ROUTES = {
    'app.accruals.tasks.receipt_tasks.get_receipt_file': {
        'queue': _QUEUE
    },
    'app.accruals.tasks.reports.prepare_accrual_docs_by_fias_data': {
        'queue': 'reports'
    },
}
