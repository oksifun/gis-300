from celery.schedules import crontab


_QUEUE = 'rare_tasks'
CLEAN_DB_TASK_SCHEDULE = {
    'clean-db-periodically': {
        'task': 'app.clean_db.tasks.permissions'
                '.find_and_clean_unused_house_group',
        'schedule': crontab(minute=5, hour=16),
    },
}
CLEAN_DB_TASK_ROUTES = {
    'app.clean_db.tasks.permissions.find_and_clean_unused_house_group': {
        'queue': _QUEUE,
    },
}
