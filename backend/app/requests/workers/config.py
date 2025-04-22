from celery.schedules import crontab


_QUEUE = 'rare_tasks'
TASK = 'app.requests.tasks.checking_new_applications.excel_report_requests'
REQUEST_TASK_SCHEDULE = {
    'send-exel-report-to-support-every-24-hours': {
        'task': TASK,
        'schedule': crontab(day_of_week='mon-fri', hour='4', minute='0')
    }
}
REQUEST_TASK_ROUTES = {
    'app.requests.tasks.checking_new_applications.excel_report_requests': {
        'queue': _QUEUE
    },

    # Денормализации.
    # Связывание заявок со звонками.
    'app.requests.tasks.linking_request_to_call'
    '.bind_related_calls_after_request_save_task': {
        'queue': _QUEUE
    },
}
