_QUEUE = 'big_receipts'
DOLLMAKER_SCHEDULE = {}
DOLLMAKER_TASK_ROUTES = {
    'app.accruals.tasks.receipt_tasks.run_creating_all_receipt': {
        'queue': _QUEUE
    },
}
