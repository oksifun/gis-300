from rest_framework_mongoengine import serializers
import rest_framework_mongoengine.fields as fields

from api.v4.serializers import CustomDocumentSerializer, \
    CustomEmbeddedDocumentSerializer
from api.v4.universal_crud import ModelFilesViewSet
from app.meters.models.meter import AreaMeter, MeterEmbeddedArea
from app.meters.models.meter_event import MeterReadingEvent


class AreaEmbeddedSerializer(CustomEmbeddedDocumentSerializer):
    id = fields.ObjectIdField(read_only=False)

    class Meta:
        model = MeterEmbeddedArea
        fields = ('id',)


class AreaMeterUpdateSerializer(CustomDocumentSerializer):
    serial_number = serializers.drf_fields.CharField(allow_blank=True)

    class Meta:
        model = AreaMeter
        exclude = (
            'first_check_date',
            'last_check_date',
            'next_check_date',
            'working_start_date',
            'expiration_date_check',
            'order',
            'readings',
            'area',
            'is_deleted',
            'average_deltas',
            'created_by',
            '_binds',
        )


class AreaMeterCreateSerializer(CustomDocumentSerializer):
    area = AreaEmbeddedSerializer(many=False)
    serial_number = serializers.drf_fields.CharField(allow_blank=True)
    communication = fields.ObjectIdField(required=True)

    class Meta:
        model = AreaMeter
        fields = (
            'id',
            'area',
            'mounting',
            'digit_capacity',
            'is_automatic',
            'reverse',
            'communication',
            '_type',
            'readings',
            'attached_passport',
            'attached_seal_act',
            'description',
            # 'expiration_date_check',
            'serial_number',
            # 'working_start_date',
            'working_finish_date',
            'check_history',
            'closed_by',
            # 'first_check_date',
            # 'last_check_date',
            # 'next_check_date',
            'installation_date',
            'initial_values',
            'average_deltas',
            'ratio',
            'loss_ratio',
            'order',
            'model_name',
            'brand_name',
            'gis_uid',
            'unit_of_measurement_okei'
        )


class AreaMeterListSerializer(CustomDocumentSerializer):
    class Meta:
        model = AreaMeter
        fields = (
            'id',
            'area',
            'mounting',
            'digit_capacity',
            'is_automatic',
            'reverse',
            'communication',
            '_type',
            'is_deleted',
            'readings',
            'attached_passport',
            'attached_seal_act',
            'description',
            'expiration_date_check',
            'serial_number',
            'working_start_date',
            'working_finish_date',
            'check_history',
            'closed_by',
            'first_check_date',
            'last_check_date',
            'next_check_date',
            'installation_date',
            'initial_values',
            'average_deltas',
            'ratio',
            'loss_ratio',
            'order',
            'created_by',
            'model_name',
            'brand_name',
            'gis_uid',
            'unit_of_measurement_okei'
        )


class AreaMeterRetrieveSerializer(CustomDocumentSerializer):
    class Meta(AreaMeterListSerializer.Meta):
        pass


class MeterReadingEventSerializer(CustomDocumentSerializer):
    class Meta:
        model = MeterReadingEvent
        fields = "__all__"


class AreaMeterFilesViewSet(ModelFilesViewSet):
    model = AreaMeter
    slug = 'apartment_meters'
