from celery.schedules import crontab

ACCRUALS_CACHING_TASK_SCHEDULE = {
    'run-house-services-cache-tasks': {
        'task': 'app.accruals.tasks.cache.house_service'
                '.run_house_services_cache_tasks',
        'schedule': crontab(hour=22, minute=7),
    },
}

ACCRUALS_CACHING_TASK_ROUTES = {
    'app.accruals.tasks.caching.update_accrual_doc_cache': {
        'queue': 'caching',
    },
    'app.accruals.tasks.cache.house_service.run_house_services_cache_tasks': {
        'queue': 'caching',
    },
    'app.accruals.tasks.cache.house_service.update_house_services_cache': {
        'queue': 'caching',
    },
    'app.accruals.tasks.caching.count_receipts_statistics': {
        'queue': 'caching',
    },
    'app.accruals.tasks.create_split_receipt.create_zip_archive_receipt': {
        'queue': 'caching',
    }
}
