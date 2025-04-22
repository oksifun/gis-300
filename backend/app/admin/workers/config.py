from celery.schedules import crontab

ADMIN_TASK_SCHEDULE = {
    'global-tasks-statistics-send': {
        'task': 'app.admin.tasks.statistics.calculate_global_tasks_statistics',
        'schedule': crontab(minute="2", hour="21"),
    },
    'preliminary-global-tasks-statistics-send': {
        'task': 'app.admin.tasks.statistics'
                '.preliminary_global_tasks_statistics',
        'schedule': crontab(minute="2", hour="12"),
    },
}
ADMIN_TASK_ROUTES = {
    'app.admin.tasks.data_restore.restore_data': {
        'queue': 'importer',
    },
    'app.admin.tasks.data_restore.restore_data_by_func': {
        'queue': 'importer',
    },
    'app.admin.tasks.statistics.calculate_global_tasks_statistics': {
        'queue': 'rare_tasks',
    },
    'app.admin.tasks.statistics.preliminary_global_tasks_statistics': {
        'queue': 'rare_tasks',
    },
    'app.admin.tasks.statistics.send_global_tasks_statistics_message': {
        'queue': 'rare_tasks',
    },
}
