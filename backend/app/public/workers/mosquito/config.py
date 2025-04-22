_QUEUE = 'qr_calls'
MOSQUITO_SCHEDULE = {}
QR_CALLS = {
    'app.public.tasks.qr_call.qr_verification_call': {
        'queue': _QUEUE
    },
}
