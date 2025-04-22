from rest_framework.fields import ListField
from rest_framework_mongoengine import fields as fields
from rest_framework_mongoengine.serializers import DocumentSerializer
from rest_framework import serializers

from api.v4.serializers import (
    CustomEmbeddedDocumentSerializer,
    FileFieldSerializer,
    CustomDocumentSerializer,
)
from app.requests.models.request import (
    EmbeddedProvider,
    HouseEmbedded,
    AreaEmbedded,
    TenantEmbedded,
    OtherPersonEmbedded,
    RequestDispatcherDenormalized,
    PhotoEmbedded,
    Request,
    RequestSample,
    EmbeddedCommercialData,
    RequestAutoSelectExecutorBinds
)

REQUEST_FIELDS = (
    'id',
    '_type',
    'area',
    'actions',
    'attachments',
    'house',
    'body',
    'comment',
    'comment_materials',
    'comment_works',
    'comment_sample',
    'common_status',
    'common_status_changes',
    'created_at',
    'dt_desired_start',
    'dt_desired_end',
    'dt_start',
    'dt_end',
    'executors',
    'intercom_status',
    'kinds',
    'manually_added_services',
    'manually_added_materials',
    'number',
    'provider',
    'tenant',
    'photos',
    'housing_supervision',
    'completion_act_file',
    'service_doc',
    'storage_docs',
    'other_person',
    'show_all',
    'administrative_supervision',
    'ticket',
    'total_rate',
    'cost_works',
    'cost_materials',
    'body_sample',
    'delayed_at',
    'rates',
    'tags',
    'free',
    'related_call_ids',
)
SOMETIMES_REQUEST_FIELDS = (
    'dispatcher',
    'control_info',
    'monitoring',
    )

COMMERCIAL_FIELDS = ('commercial_data',)


class ProviderEmbeddedSerializer(CustomEmbeddedDocumentSerializer):
    id = fields.ObjectIdField(read_only=False)

    class Meta:
        model = EmbeddedProvider
        fields = '__all__'


class HouseEmbeddedSerializer(CustomEmbeddedDocumentSerializer):
    id = fields.ObjectIdField(read_only=False)

    class Meta:
        model = HouseEmbedded
        fields = '__all__'


class AreaEmbeddedSerializer(CustomEmbeddedDocumentSerializer):
    id = fields.ObjectIdField(allow_null=True, read_only=False)

    class Meta:
        model = AreaEmbedded
        fields = '__all__'


class AreaIdEmbeddedSerializer(CustomEmbeddedDocumentSerializer):
    id = fields.ObjectIdField(allow_null=True, read_only=False)

    class Meta:
        model = AreaEmbedded
        fields = ('id',)


class TenantEmbeddedSerializer(CustomEmbeddedDocumentSerializer):
    id = fields.ObjectIdField(allow_null=True, read_only=False, required=False)

    class Meta:
        model = TenantEmbedded
        fields = '__all__'


class OtherTenantEmbeddedSerializer(CustomEmbeddedDocumentSerializer):
    id = fields.ObjectIdField(allow_null=True, read_only=False, required=False)

    class Meta:
        model = OtherPersonEmbedded
        fields = '__all__'


class CommercialDataEmbeddedSerializer(CustomEmbeddedDocumentSerializer):
    class Meta:
        model = EmbeddedCommercialData
        fields = '__all__'
        read_only_fields = (
            'pay_status',
        )


class DispatcherEmbeddedSerializer(CustomEmbeddedDocumentSerializer):
    id = fields.ObjectIdField(read_only=False)

    class Meta:
        model = RequestDispatcherDenormalized
        fields = '__all__'
        read_only_fields = (
            'str_name',
            '_type',
            'short_name',
            'provider',
            'phones',
            'position',
        )


class PhotoEmbeddedSerializer(CustomEmbeddedDocumentSerializer):
    file = FileFieldSerializer(many=False, required=False, allow_null=True)

    class Meta:
        model = PhotoEmbedded
        fields = '__all__'


class RequestUpdateSerializer(CustomDocumentSerializer):
    provider = ProviderEmbeddedSerializer(many=False)
    house = HouseEmbeddedSerializer(many=False)
    tenant = TenantEmbeddedSerializer(many=False, read_only=True)
    other_person = OtherTenantEmbeddedSerializer(many=False, required=False)
    photos = ListField(child=PhotoEmbeddedSerializer(many=False))
    commercial_data = CommercialDataEmbeddedSerializer(
        many=False,
        required=False,
    )

    class Meta:
        model = Request
        fields = REQUEST_FIELDS + COMMERCIAL_FIELDS
        read_only_fields = (
            'total_rate',
            'tenant',
            'number',
            'area',
            'free',
            'tags',
            'common_status_changes',
        )

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        self.restore_read_only_embedded_fields(value)
        return value


class RequestSerializer(CustomDocumentSerializer):
    provider = ProviderEmbeddedSerializer(many=False)
    house = HouseEmbeddedSerializer(many=False)
    area = AreaEmbeddedSerializer(many=False)
    tenant = TenantEmbeddedSerializer(many=False)
    dispatcher = DispatcherEmbeddedSerializer(many=False)
    other_person = OtherTenantEmbeddedSerializer(many=False, required=False)

    class Meta:
        model = Request
        fields = REQUEST_FIELDS + SOMETIMES_REQUEST_FIELDS + COMMERCIAL_FIELDS


class RequestCreateSerializer(CustomDocumentSerializer):
    provider = ProviderEmbeddedSerializer(many=False)
    house = HouseEmbeddedSerializer(many=False)
    area = AreaIdEmbeddedSerializer(many=False)
    tenant = TenantEmbeddedSerializer(many=False)
    dispatcher = DispatcherEmbeddedSerializer(many=False)
    other_person = OtherTenantEmbeddedSerializer(many=False, required=False)

    class Meta:
        model = Request
        fields = REQUEST_FIELDS + SOMETIMES_REQUEST_FIELDS
        read_only_fields = (
            'total_rate',
            'common_status_changes',
        )


class RequestSampleSerializer(DocumentSerializer):
    class Meta:
        model = RequestSample
        fields = '__all__'


class MLTranscriptPhraseSerializer(serializers.Serializer):

    speaker = serializers.CharField()
    message = serializers.CharField()


class MLTranscriptionResultSerializer(serializers.Serializer):

    summary = serializers.CharField()
    transcript = MLTranscriptPhraseSerializer(many=True)


class RequestBoundCallSerializer(serializers.Serializer):

    id = serializers.CharField()
    record_url = serializers.URLField()
    calldate = serializers.DateTimeField()
    direction = serializers.CharField()
    ml_transcription_result = MLTranscriptionResultSerializer()


class RequestAutoSelectSerializer(DocumentSerializer):
    class Meta:
        model = RequestAutoSelectExecutorBinds
        fields = '__all__'

