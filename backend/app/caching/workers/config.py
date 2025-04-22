from celery.schedules import crontab

_QUEUE = 'caching'
CACHING_TASK_SCHEDULE = {
    'denormalization-tasks-restarting': {
        'task': 'app.caching.tasks.periodic.restart_denormalize_tasks',
        'schedule': crontab(minute="*/17"),
    },
}
CACHING_TASK_ROUTES = {
    'app.caching.tasks.cache_update.update_tariffs_cache': {
        'queue': _QUEUE,
    },
    'app.caching.tasks.cache_update.update_house_accruals_cache': {
        'queue': _QUEUE,
    },
    'app.caching.tasks.cache_update.create_fias_tree_cache': {
        'queue': _QUEUE,
    },
    'app.caching.tasks.cache_update.create_provider_fias_tree_cache': {
        'queue': _QUEUE,
    },
    'app.caching.tasks.cache_update.prepare_filter_cache': {
        'queue': _QUEUE,
    },
    'app.caching.tasks.filter_data_prepare.prepare_accrual_doc_data': {
        'queue': _QUEUE,
    },
    'app.caching.tasks.filter_data_prepare.prepare_accounts_balance': {
        'queue': _QUEUE,
    },
    'app.caching.tasks.denormalization.foreign_denormalize_data': {
        'queue': _QUEUE,
    },
    'app.caching.tasks.denormalization'
    '.denormalize_provider_permission_to_cabinets': {
        'queue': _QUEUE,
    },
    'app.caching.tasks.denormalization'
    '.sync_provider_permissions_to_cabinets': {
        'queue': _QUEUE,
    },
    'app.caching.tasks.denormalization'
    '.denormalize_provider_to_cabinets': {
        'queue': _QUEUE,
    },
    'app.caching.tasks.denormalization'
    '.denormalize_house_sectors_to_cabinets': {
        'queue': _QUEUE,
    },
    'app.caching.tasks.periodic.restart_denormalize_tasks': {
        'queue': _QUEUE,
    },
    'app.caching.tasks.news.recalculate_statistics': {
        'queue': _QUEUE,
    },
    'app.caching.tasks.news.update_house_news': {
        'queue': _QUEUE,
    },
    # Бинды провайдера для Каталога
    'app.caching.tasks.compendium_provider_binds'
    '.create_compendium_provider_binds': {
        'queue': _QUEUE,
    }
}


METABASE_QUEUE = 'metabase_task'
METABASE_TASK_SCHEDULE = {
    'run-metebase-stat': {
        'task': 'app.caching.tasks.cache_update.non_sber_registry_stat',
        'schedule': crontab(minute=30, hour='5'),
    },
}
METABASE_TASK_ROUTES = {
    'app.caching.tasks.cache_update.non_sber_registry_stat': {
        'queue': METABASE_QUEUE
    },
}
