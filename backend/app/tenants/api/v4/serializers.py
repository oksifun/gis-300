from rest_framework_mongoengine.serializers import drf_fields, drfm_fields

from api.v4.serializers import BaseCustomSerializer
from lib.helpfull_tools import DateHelpFulls as dhf


_IMPORT_READINGS_FILE_EXTENSIONS = ['csv']


class TenantCoefficientImportSerializer(BaseCustomSerializer):
    coef = drfm_fields.ObjectIdField(required=True)
    period = drf_fields.DateTimeField(required=True)
    file = drf_fields.FileField(required=True)


class ResonEmbeddedSerializer(BaseCustomSerializer):
    number = drf_fields.CharField(required=False, allow_blank=True)
    comment = drf_fields.CharField(required=False, allow_blank=True)
    datetime = drf_fields.DateTimeField(required=False, allow_null=True)


class TenantCoefficientSerializer(BaseCustomSerializer):
    coef = drfm_fields.ObjectIdField(required=True)
    period = drf_fields.DateTimeField(required=True)
    value = drf_fields.FloatField(required=True)
    reason = drf_fields.DictField(required=False, default={})

    def validate_period(self, value):
        period = dhf.begin_of_month(value)
        return period

    def validate_reason(self, values):
        serializer = ResonEmbeddedSerializer(data=values)
        return serializer.validated_data


class TenantListCoefficientSerializer(BaseCustomSerializer):
    coef = drfm_fields.ObjectIdField(required=True)
    house = drfm_fields.ObjectIdField(required=True)
    date = drf_fields.DateTimeField(required=True)
    show_null = drf_fields.BooleanField(required=True)

    def validate_date(self, value):
        period = dhf.begin_of_month(value)
        return period


class TenantCoefficientsSerializer(BaseCustomSerializer):
    tenant = drfm_fields.ObjectIdField(required=True)
    month = drf_fields.DateTimeField(required=True)

    def validate_date(self, value):
        period = dhf.begin_of_month(value)
        return period
