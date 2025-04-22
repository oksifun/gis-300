from django.http import JsonResponse
from rest_framework.response import Response

from api.v4.authentication import RequestAuth
from api.v4.forms.base import ConstantsBaseViewSet
from api.v4.permissions import SuperUserOnly
from api.v4.viewsets import BaseLoggedViewSet
from app.admin.api.v4.serializers import RestoreDataSerializer
from app.admin.models.choices import LocalBaseName, \
    DataRestoreDataType, LOCAL_BASES_CHOICES, DATA_RESTORE_DATA_TYPES_CHOICES
from app.admin.models.data_restore_task import DataBaseRestoreTask
from app.admin.tasks.data_restore import restore_data
from processing.models.tasks.sber_autopay import SberAutoPayAccount


class SberAutoPayersView(BaseLoggedViewSet):
    """
    Количество автоплательщиков сбера
    """
    permission_classes = (SuperUserOnly,)
    http_method_names = ['get']

    def retrieve(self, request, pk):
        num = SberAutoPayAccount.objects(
            provider=pk,
        ).count()
        return JsonResponse(
            data={
                'number': num,
            },
        )


class DataRestoreView(BaseLoggedViewSet):
    """
    Восстановление данных в локальную базу.
    """
    permission_classes = (SuperUserOnly,)
    http_method_names = ['get', 'post']

    def retrieve(self, request, pk):
        request_auth = RequestAuth(request)
        account = request_auth.get_super_account()
        tasks = DataBaseRestoreTask.objects(
            author=account.id,
            object_id=pk,
        ).order_by(
            '-created',
        )
        tasks = list(tasks[0: 1])
        if tasks:
            task = tasks[0]
            return JsonResponse(
                data=dict(
                    script_name=task.data_type,
                    date=task.created,
                    status=task.state,
                ),
            )
        return JsonResponse(
            data=dict(
                status='no_tasks',
            ),
        )

    def create(self, request, *args, **kwargs):
        """Согласно переданным параметрам, определяем нужную функцию
        и ее аргументы для запуска через run_migration()."""
        serializer = RestoreDataSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_auth = RequestAuth(self.request)
        account = request_auth.get_super_account()
        task = DataBaseRestoreTask(
            author=account.id,
            data_type=serializer.validated_data['data_type'],
            object_id=serializer.validated_data['object_id'],
            base_name=serializer.validated_data['base_name'],
        )
        task.save()
        restore_data.delay(
            task_id=task.id,
            data_type=serializer.validated_data['data_type'],
            object_id=serializer.validated_data['object_id'],
            base_name=serializer.validated_data['base_name'],
        )
        return Response(data='success')


class DataRestoreConstantsView(ConstantsBaseViewSet):
    CONSTANTS_CHOICES = (
        (LOCAL_BASES_CHOICES, LocalBaseName),
        (DATA_RESTORE_DATA_TYPES_CHOICES, DataRestoreDataType),
    )
