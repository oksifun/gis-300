from rest_framework.fields import (
    CharField, DateTimeField, ListField, NullBooleanField
)
from rest_framework_mongoengine.fields import ObjectIdField
from rest_framework_mongoengine.serializers import (
    DocumentSerializer, serializers
)

from api.v4.serializers import (
    CustomDocumentSerializer, CustomEmbeddedDocumentSerializer
)
from app.crm.models.crm import (
    AccountDenormalized, CRM, CRMEvent, IdFieldEmbedded, CRMDenormalized
)


class CRMBasicSerializer(serializers.Serializer):
    status__in = ListField(child=CharField(), required=False)
    managers__in = ListField(child=ObjectIdField(), required=False)
    sbis = NullBooleanField(required=False)
    services__in = ListField(child=CharField(), required=False)
    signs__in = ListField(child=CharField(), required=False)
    ticket_rate__in = ListField(child=CharField(), required=False)
    provider__legal_form__in = ListField(child=CharField(), required=False)
    provider__str_name__in = ListField(child=CharField(), required=False)
    provider__ogrn__in = ListField(child=CharField(), required=False)
    provider__inn__in = ListField(child=CharField(), required=False)
    fias_street_guid = ListField(child=CharField(), required=False)
    fias_house_guid = CharField(required=False)
    email__icontains = CharField(required=False)
    phones__code__icontains = CharField(required=False)
    phones__number__icontains = CharField(required=False)
    provider__business_types__in = ListField(child=ObjectIdField(),
                                             required=False)
    provider__receipt_type__in = ListField(child=CharField(), required=False)
    provider__calc_software__in = ListField(child=CharField(), required=False)
    provider__terminal__in = ListField(child=CharField(), required=False)
    first_name__icontains = CharField(required=False)
    last_name__icontains = CharField(required=False)
    patronymic_name__icontains = CharField(required=False)
    account__id__in = ListField(child=ObjectIdField(), required=False)


class CRMActionsSerializer(CRMBasicSerializer):
    actions__date_from = DateTimeField(required=False)
    actions__date_till = DateTimeField(required=False)
    actions__event_type__in = ListField(child=CharField(), required=False)


class CRMTasksSerializer(CRMBasicSerializer):
    tasks__date_from = DateTimeField(required=False)
    tasks__date_till = DateTimeField(required=False)
    tasks__event_type__in = ListField(child=CharField(), required=False)


class CRMCustomSerializer(CRMBasicSerializer):
    actions__date_from = DateTimeField(required=False)
    actions__date_till = DateTimeField(required=False)
    actions__event_type__in = ListField(child=CharField(), required=False)

    tasks__date_from = DateTimeField(required=False)
    tasks__date_till = DateTimeField(required=False)
    tasks__event_type__in = ListField(child=CharField(), required=False)
    provider__name__icontains = CharField(required=False)
    provider__inn__startswith = CharField(required=False)
    provider__ogrn__startswith = CharField(required=False)


class EmbeddedIdFieldSerializer(CustomEmbeddedDocumentSerializer):
    id = ObjectIdField(read_only=False)

    class Meta:
        model = IdFieldEmbedded
        fields = ('id',)


class _AccountEmbeddedCreateSerializer(CustomEmbeddedDocumentSerializer):
    id = ObjectIdField(read_only=False)

    class Meta:
        model = AccountDenormalized
        fields = ('id',)


class _CRMEmbeddedCreateSerializer(CustomEmbeddedDocumentSerializer):
    id = ObjectIdField(read_only=False)

    class Meta:
        model = CRMDenormalized
        fields = ('id',)


class AccountSerializer(CustomEmbeddedDocumentSerializer):
    department = EmbeddedIdFieldSerializer(many=False)
    provider = EmbeddedIdFieldSerializer(many=False)
    id = ObjectIdField(required=True, read_only=False)

    class Meta:
        model = AccountDenormalized
        fields = '__all__'


class CRMEmbeddedSerializer(CustomEmbeddedDocumentSerializer):
    id = ObjectIdField(required=True, read_only=False)

    class Meta:
        model = CRMDenormalized
        fields = '__all__'


class CRMEventSerializer(CustomDocumentSerializer):

    class Meta:
        model = CRMEvent
        fields = '__all__'
        read_only_fields = ('crm', 'account', '_type', 'status')


class CRMEventCreateSerializer(CustomDocumentSerializer):
    account = _AccountEmbeddedCreateSerializer(many=False)
    crm = _CRMEmbeddedCreateSerializer(many=False)

    class Meta:
        model = CRMEvent
        fields = '__all__'


class CRMEventListSerializer(DocumentSerializer):
    class Meta:
        model = CRMEvent
        fields = '__all__'


class CRMIdSerializer(serializers.Serializer):
    crm_id = ObjectIdField(required=True)


class CRMProviderSerializer(DocumentSerializer):
    class Meta:
        model = CRM
        fields = (
            'id',
            'status',
            'provider',
            'managers',
            'sbis',
            'services',
            'signs',
            'ticket_rate',
            'last_task',
            'last_action',
        )
        read_only_fields = (
            'id',
            'provider',
            'last_task',
            'last_action',
        )



class MonitoringSerializer(DocumentSerializer):
    extra = serializers.DictField()

    class Meta:
        model = CRM
        fields = tuple(CRM._fields.keys()) + ('extra',)
