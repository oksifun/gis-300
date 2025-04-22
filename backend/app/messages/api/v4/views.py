from datetime import timedelta, datetime

from django.http import JsonResponse
from rest_framework import viewsets

from api.v4.authentication import RequestAuth
from api.v4.serializers import json_serializer
from app.messages.models.messenger import MessageEmbedded, UserTasks


class GetUserTaskViewSet(viewsets.ViewSet):
    """
    Принимает сообщения о статусах различных задач,
    касающихся пользователя
    """
    def list(self, request):
        request_auth = RequestAuth(request)
        current_account = request_auth.get_super_account()
        data = self.get_user_messages(current_account.pk)
        return JsonResponse(
            dict(result=data),
            json_dumps_params={'default': json_serializer},
        )

    def get_user_messages(self, account):
        """
        Преобразует данные месенджера в список сообщений
        """
        user_tasks = UserTasks.get_messenger(account)
        result = []
        for field_name in user_tasks:
            field_value = getattr(user_tasks, field_name, None)
            if isinstance(field_value, MessageEmbedded):
                tasks = [field_value]
            elif isinstance(field_value, list):
                tasks = {
                    v.id: v
                    for v in field_value
                    if isinstance(v, MessageEmbedded)
                }
                tasks = list(tasks.values())
            else:
                tasks = []
            for task in tasks:
                message = self._get_message_from_task(task, field_name)
                result.append(message)
        for task in user_tasks.reports:
            message = self._get_message_from_task(task, 'reports')
            result.append(message)
        for task in user_tasks.messages:
            message = self._get_message_from_task(task, 'messages')
            if task.unread and message not in result:
                result.append(message)
        user_tasks.clean_report_tasks()
        user_tasks.clean_field('coefs', account)
        user_tasks.clean_field('accrual_docs', account)
        user_tasks.clean_field('houses_accrual_docs', account)
        if user_tasks.rosreestr:
            rosreestr_timeout_datetime = datetime.now() - timedelta(minutes=20)
            self.check_rosreestr_run_timeout(
                result, rosreestr_timeout_datetime
            )
            user_tasks.clean_rosreestr(timer=rosreestr_timeout_datetime)

        return result

    @staticmethod
    def check_rosreestr_run_timeout(messages, timeout_datetime: datetime):
        rosreestr_timeout = next(
            (e for e in messages if e['obj'] == 'rosreestr'
             and e['created'] < timeout_datetime), False)
        if rosreestr_timeout:
            msg = 'При отправке запроса возникла ошибка, сделайте ' \
                  'запрос повторно или обратитесь в техническую поддержку.'
            messages.append(dict(
                obj='messages',
                text=msg,
            ))
    @staticmethod
    def _get_message_from_task(task, obj_name):
        result = task.to_mongo()
        result['obj'] = obj_name
        if 'extra' in result:
            result.update(result.pop('extra'))
        return result
