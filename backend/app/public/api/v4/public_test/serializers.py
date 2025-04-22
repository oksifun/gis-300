from mongoengine import ObjectIdField
from rest_framework.fields import SerializerMethodField, CharField

from api.v4.serializers import CustomDocumentSerializer, \
    CustomEmbeddedDocumentSerializer
from app.area.models.area import Area
from app.meters.models.meter import AreaMeter, MeterEmbeddedArea
from processing.models.billing.embeddeds.house import DenormalizedHouseWithFias


class PublicTestEmbeddedHouseSerializer(CustomEmbeddedDocumentSerializer):

    id = ObjectIdField(read_only=False)
    address = SerializerMethodField()

    class Meta:
        model = DenormalizedHouseWithFias
        fields = '__all__'

    def get_address(self, obj):
        return f'г Санкт-Петербург, ул Чудес, д 256'


class PublicTestAreasSerializer(CustomDocumentSerializer):
    house = PublicTestEmbeddedHouseSerializer(many=False)

    class Meta:
        model = Area
        fields = (
            'number',
            'str_number',
            'str_number_full',
            'house',
        )
        read_only_fields = (
            'str_number',
            'str_number_full',
            'house',
        )


class PublicTestAreaEmbeddedSerializer(CustomEmbeddedDocumentSerializer):
    id = ObjectIdField(read_only=False)

    class Meta:
        model = MeterEmbeddedArea
        fields = ('id',)


class PublicTestMeterSerializer(CustomDocumentSerializer):
    area = PublicTestAreaEmbeddedSerializer(many=False)
    serial_number = CharField(allow_blank=True)
    communication = ObjectIdField(required=False)

    class Meta:
        model = AreaMeter
        fields = (
            'id',
            '_type',
            'area',
            'is_automatic',
            'communication',
            'description',
            'serial_number',
            'installation_date',
            'brand_name',
            'model_name',
            'initial_values',
        )

    def recursive_save(self, validated_data, instance=None):
        if validated_data is None:
            return instance
        if instance:
            instance.ignore_meter_validation = True
            instance.safely_readings_added = True
        return super().recursive_save(validated_data, instance)
