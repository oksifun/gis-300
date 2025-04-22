import traceback

from rest_framework.response import Response
from rest_framework.status import HTTP_500_INTERNAL_SERVER_ERROR
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    # Call REST framework's default exception handler first,
    # to get the standard error response.
    response = exception_handler(exc, context)

    try:
        view_log = getattr(context['view'], 'user_activity_log')
        if view_log:
            error_str = traceback.format_exc()
            view_log.traceback = error_str
            view_log.save()
    except Exception:
        pass

    msg = {
        'messages': [{
            'text': 'Ошибка сервера',
            'type': 'validation'
        }]
    }
    # Now add the HTTP status code to the response.
    if response is not None:
        response.data['status_code'] = response.status_code
        response.data.update(msg)
    # Если ошибка не распознана стандартным обработчиком - значит 500
    else:
        response = Response(data=msg, status=HTTP_500_INTERNAL_SERVER_ERROR)

    return response
