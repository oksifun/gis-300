from celery.schedules import crontab


_QUEUE = 'vendors'
LEGAL_ENTITY_TASK_SCHEDULE = {}
LEGAL_ENTITY_TASK_ROUTES = {
    'app.legal_entity.tasks.update_vendor.vendor_apply_to_offsets': {
        'queue': _QUEUE,
    },
}
