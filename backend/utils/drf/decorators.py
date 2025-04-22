import json

from django.http import HttpResponseBadRequest
from mongoengine import ValidationError, DoesNotExist
from rest_framework import status
from rest_framework.response import Response

from processing.models.exceptions import CustomValidationError


def custom_400(msg=None, msg_type=None):
    """
    Модификация стандартного BadRequest ответа
    :param msg: str: текстовый овтет
    :param msg_type: str: тип сообщения
    :return: HttpResponseBadRequest object
    """
    response = json.dumps({
        'messages': [{
            'text': msg or 'Неверные параметры запроса',
            'type': msg_type or 'validation'
        }]
    })
    return HttpResponseBadRequest(response)


def permission_validator(func):
    """
    Это декоратор призван оборачивать методы контроллеров
    и возвращать ответ 423 вместо 500 на ручные ошибки.
    """

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except CustomValidationError as restrict_action:
            unwanted_msg_part = 'Original exception was: '
            msg = str(restrict_action)
            if unwanted_msg_part in msg:
                msg = msg.split(unwanted_msg_part)[-1]
            return Response(msg, status=status.HTTP_423_LOCKED)
        except ValidationError as restrict_action:
            unwanted_msg_part = 'Original exception was: '
            msg = str(restrict_action)
            if unwanted_msg_part in msg:
                msg = msg.split(unwanted_msg_part)[-1]
            return Response(msg, status=status.HTTP_400_BAD_REQUEST)
        except DoesNotExist as not_found_error:
            return Response(
                str(not_found_error),
                status=status.HTTP_404_NOT_FOUND
            )
    return wrapper
