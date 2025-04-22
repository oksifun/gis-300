_QUEUE_SHARED = 'calculate_offsets'
OFFSETS_TASK_ROUTES = {
    'app.offsets.tasks.calculate_offsets.try_calculate': {
        'queue': _QUEUE_SHARED,
    },
    'app.offsets.tasks.calculate_offsets.calculate_offsets_slow': {
        'queue': 'rare_tasks',
    },
    'app.offsets.tasks.calculate_offsets.'
    'calculate_special_offsets_GS': {
        'queue': 'exploitation_gs',
    },
    'app.offsets.tasks.calculate_offsets.'
    'calculate_special_offsets_OhServ': {
        'queue': 'okhta_service',
    },
    'app.offsets.tasks.calculate_offsets.'
    'calculate_special_offsets_ND': {
        'queue': 'nash_dom',
    },
    'app.offsets.tasks.calculate_offsets.'
    'calculate_special_offsets_Sodruj': {
        'queue': 'sodrujestvo',
    },
    'app.offsets.tasks.calculate_offsets.'
    'calculate_special_offsets_Pioneer': {
        'queue': 'pioneer',
    },
}