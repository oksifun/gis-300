from processing.celery.workers.great_white_shark.identifications_notify import \
    notice_empty_hcs
from app.hcs_export.api.v4.serializers import ExportHcsSerializer
from api.v4.permissions import SuperUserOnly
from api.v4.universal_crud import BaseCrudViewSet
from rest_framework import status
from django.http.response import JsonResponse


class ExportEmptyHcsViewSet(BaseCrudViewSet):
    permission_classes = (SuperUserOnly,)

    def create(self, request, *args, **kwargs):
        serializer = ExportHcsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data.get('email')
        email_domain = email[email.find('@'):]
        if email_domain != '@eis24.me':
            return JsonResponse(
                data={'error': 'Запрещено указывать личную почту'},
                status=status.HTTP_403_FORBIDDEN
            )
        provider_id = serializer.validated_data.get('provider_id')
        task = notice_empty_hcs.delay(provider_id=provider_id, email=email)
        return JsonResponse(
            data={'task_id': str(task)},
            status=status.HTTP_201_CREATED
        )
