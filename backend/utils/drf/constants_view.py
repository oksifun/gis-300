from django.http import JsonResponse

from utils.drf.base_serializers import json_serializer
from utils.drf.base_viewsets import PublicViewSet


class ConstantsBaseViewSet(PublicViewSet):
    CONSTANTS_CHOICES = tuple()

    def list(self, request):
        result = {}
        for const in self.CONSTANTS_CHOICES:
            if isinstance(const[1], str):
                key = const[1]
            else:
                key = const[1].__name__
            result[key] = [
                {'value': d[0], 'text': d[1]} for d in const[0]
            ]
        return JsonResponse(
            {'results': result},
            json_dumps_params={'default': json_serializer}
        )
