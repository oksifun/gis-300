from rest_framework.fields import ListField
from rest_framework_mongoengine import serializers

from api.v4.serializers import BaseCustomSerializer


class ProvidersSearchSerializer(BaseCustomSerializer):
    name = serializers.drf_fields.CharField(required=False, allow_blank=True)
    ogrn = serializers.drf_fields.CharField(required=False, allow_blank=True)
    inn = serializers.drf_fields.CharField(required=False, allow_blank=True)
    legal_form = ListField(
        child=serializers.drf_fields.CharField(
            required=False,
            allow_blank=True,
        ),
        required=False,
    )
    offset = serializers.drf_fields.CharField(required=False, allow_blank=True)
    limit = serializers.drf_fields.CharField(required=False, allow_blank=True)
