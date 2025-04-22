from rest_framework import serializers
from rest_framework_mongoengine.serializers import DocumentSerializer, \
    EmbeddedDocumentSerializer

from api.v4.serializers import CustomDocumentSerializer, \
    CustomEmbeddedDocumentSerializer
from app.house.models.house import House
from app.judicial_work.api.v4.serializers import AttachedCourtsSerializer
from processing.models.billing.embeddeds.geo_point import GeoPoint
from app.house.models.house import HouseEmbededServiceBind, Porchart
from app.house.models.house import Porch


class ServiceBindsSerializer(EmbeddedDocumentSerializer):
    class Meta:
        model = HouseEmbededServiceBind
        fields = '__all__'


class PorchesSerializer(CustomEmbeddedDocumentSerializer):

    class Meta:
        model = Porch
        fields = '__all__'


class PorchartSerializer(CustomDocumentSerializer):

    class Meta:
        model = Porchart
        fields = '__all__'


class GeoPointSerializer(CustomEmbeddedDocumentSerializer):

    class Meta:
        model = GeoPoint
        fields = ('coordinates',)


class HouseDetailSerializer(DocumentSerializer):
    porches = PorchesSerializer(many=True, read_only=True)
    attached_courts = AttachedCourtsSerializer(many=True)

    class Meta:
        model = House
        fields = (
            'id',
            'service_binds',
            'porches',
            'attached_courts'
        )

    def update(self, instance, validated_data):
        attached_courts = validated_data.get('attached_courts')
        if attached_courts is not None:
            validated_data.pop('attached_courts')
        super(HouseDetailSerializer, self).update(instance, validated_data)
        updated = AttachedCourtsSerializer.update(
            self,
            instance,
            attached_courts
        )
        return updated


class HouseViewSetSerializer(CustomDocumentSerializer):
    freedom_params = dict(
        allow_blank=True,
        allow_null=True,
        required=False
    )
    zip_code = serializers.CharField(**freedom_params)
    fund_id = serializers.CharField(**freedom_params)
    overhaul_code = serializers.CharField(**freedom_params)
    cadastral_number = serializers.CharField(**freedom_params)
    bulk = serializers.CharField(**freedom_params)
    kladr = serializers.CharField(**freedom_params)
    category = serializers.CharField(**freedom_params)
    structure = serializers.CharField(allow_blank=True)
    floor_count = serializers.CharField(**freedom_params)
    type = serializers.CharField(**freedom_params)
    fias_house_guid = serializers.CharField(allow_blank=True)
    OKTMO = serializers.CharField(allow_blank=True)
    porches = PorchesSerializer(many=True, read_only=True)
    point = GeoPointSerializer(many=False)
    attached_courts = AttachedCourtsSerializer(many=True)
    setl_home_address = serializers.CharField(**freedom_params)

    class Meta:
        model = House
        exclude = (
            'service_binds',
            '_binds',
            'is_deleted',
            'passport'
        )
        read_only_fields = (
            'porches',
        )

    def update(self, instance, validated_data):
        attached_courts = validated_data.get('attached_courts')
        if attached_courts is not None:
            validated_data.pop('attached_courts')
        super(HouseViewSetSerializer, self).update(instance, validated_data)
        updated = AttachedCourtsSerializer.update(
            self,
            instance,
            attached_courts
        )
        return updated


class HouseCreateSerializer(CustomDocumentSerializer):
    fias_street_guid = serializers.CharField(required=True)
    is_allowed_meters = serializers.BooleanField(required=True)
    kladr = serializers.CharField(required=True)
    street = serializers.CharField(required=True)
    street_only = serializers.CharField(allow_blank=True)
    bulk = serializers.CharField(allow_blank=True)
    number = serializers.CharField(required=True)
    structure = serializers.CharField(required=True)
    fias_house_guid = serializers.CharField(
        allow_blank=True,
        allow_null=True,
        required=False,
    )

    class Meta:
        model = House
