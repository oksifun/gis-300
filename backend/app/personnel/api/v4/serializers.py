from rest_framework import serializers
from rest_framework.fields import (
    ListField,
    BooleanField,
    CharField,
    DateTimeField,
)
from rest_framework.serializers import Serializer
from rest_framework_mongoengine.fields import ObjectIdField

from api.v4.serializers import (
    CustomDocumentSerializer,
    CustomEmbeddedDocumentSerializer,
)
from app.personnel.models.denormalization.worker import SystemDepartmentEmbedded
from app.personnel.models.department import (
    DepartmentEmbeddedPosition,
    Department,
)
from app.personnel.models.personnel import (
    AccountEmbeddedProvider,
    MessengerTemplate,
    Worker,
)
from app.personnel.models.denormalization.caller import (
    AccountEmbeddedPosition,
    AccountEmbeddedDepartment,
)
from app.personnel.models.system_department import SystemDepartment

REQUIRED_FIELDS = (
    'id',
    'str_name',
    'position',
    'department',
    'email',
    'phones',
)


class PositionWorkerSerializer(CustomEmbeddedDocumentSerializer):
    class Meta:
        model = AccountEmbeddedPosition
        fields = (
            'name',
            'id'
        )


class DepartmentWorkerSerializer(CustomEmbeddedDocumentSerializer):
    class Meta:
        model = AccountEmbeddedDepartment
        fields = (
            'name',
            'id'
        )


class ProviderSerializer(CustomEmbeddedDocumentSerializer):
    class Meta:
        model = AccountEmbeddedProvider
        fields = 'id',


class WorkerListSerializer(Serializer):
    provider__id = ObjectIdField(required=False)


class WorkerSerializer(CustomDocumentSerializer):
    position = PositionWorkerSerializer(many=False)
    department = DepartmentWorkerSerializer(many=False)

    class Meta:
        model = Worker
        fields = REQUIRED_FIELDS
        read_only_fields = REQUIRED_FIELDS


class WorkerBaseInfoSerializer(CustomDocumentSerializer):
    class Meta:
        model = Worker
        fields = ('id', 'str_name')


class SupportTicketUpdateSerializer(CustomDocumentSerializer):
    class Meta:
        model = Worker
        fields = ('settings',)


class SystemDepartmentEmbeddedSerializer(CustomEmbeddedDocumentSerializer):
    id = ObjectIdField(allow_null=True, read_only=False)

    class Meta:
        model = SystemDepartmentEmbedded
        fields = '__all__'


class WorkerEmbeddedSerializer(CustomDocumentSerializer):
    class Meta:
        model = Worker
        fields = (
            'id',
            'str_name',
            'has_access',
            'is_dismiss',
            'dismiss_date',
            'phones',
            'email',
            'settings',
        )


class PositionEmbeddedSerializer(CustomEmbeddedDocumentSerializer):
    workers = ListField(
        child=WorkerEmbeddedSerializer(many=False),
    )

    class Meta:
        model = DepartmentEmbeddedPosition
        fields = '__all__'


class PositionUpdateEmbeddedSerializer(CustomEmbeddedDocumentSerializer):
    id = ObjectIdField(allow_null=True, read_only=False)

    class Meta:
        model = DepartmentEmbeddedPosition
        fields = '__all__'


class DepartmentsSerializer(CustomDocumentSerializer):
    inherit_parent_rights = BooleanField(required=False)
    system_department = SystemDepartmentEmbeddedSerializer(
        many=False,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Department
        exclude = ('_binds', 'is_deleted')


class DepartmentUpdateSerializer(CustomDocumentSerializer):
    positions = ListField(
        child=PositionUpdateEmbeddedSerializer(many=False),
        required=False,
        allow_null=True,
    )
    inherit_parent_rights = BooleanField(required=False)
    system_department = SystemDepartmentEmbeddedSerializer(
        many=False,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Department
        exclude = ('_binds', 'is_deleted')


class DepartmentsTreeSerializer(CustomDocumentSerializer):
    inherit_parent_rights = BooleanField(required=False)
    system_department = SystemDepartmentEmbeddedSerializer(
        many=False,
        required=False,
        allow_null=True,
    )
    positions = ListField(
        child=PositionEmbeddedSerializer(many=False),
    )

    class Meta:
        model = Department
        exclude = ('_binds', 'is_deleted')


class DepartmentPublicUpdateSerializer(CustomDocumentSerializer):
    class Meta:
        model = Department
        fields = ('settings',)


class SystemDepartmentsSerializer(CustomDocumentSerializer):
    class Meta:
        model = SystemDepartment
        fields = '__all__'


class ResendActivationMailSerializer(serializers.Serializer):
    worker_id = ObjectIdField(required=True)


class WorkerProviderSerializer(CustomEmbeddedDocumentSerializer):
    id = ObjectIdField(required=True)

    class Meta:
        model = AccountEmbeddedProvider
        fields = '__all__'


class DepartmentProviderSerializer(CustomEmbeddedDocumentSerializer):
    id = ObjectIdField(required=True)

    class Meta:
        model = AccountEmbeddedDepartment
        fields = ('id', 'name')


class PositionProviderSerializer(CustomEmbeddedDocumentSerializer):
    id = ObjectIdField(required=True)

    class Meta:
        model = AccountEmbeddedPosition
        fields = ('id', 'name', 'code')


class WorkerDocSerializer(CustomDocumentSerializer):
    number = CharField(allow_blank=True, allow_null=True, required=False)
    provider = WorkerProviderSerializer(required=False)
    department = DepartmentProviderSerializer()
    position = PositionProviderSerializer()

    class Meta:
        model = Worker
        fields = (
            'id',
            'inn',
            'email',
            'number',
            'is_dismiss',
            'dismiss_date',
            'comment',
            'str_name',
            'provider',
            'has_access',
            'snils',
            'timer',
            'settings',
            'position',
            'department',
            'employee_id',
            'doc_copies',
            'tenants',
            'election_history',
            'sex',
            'photo',
            'short_name',
            'birth_date',
            'first_name',
            'last_name',
            'patronymic_name',
            'phones',
        )
        read_only = (
            'has_access',
            'provider',
        )


class ServicedHousesSerializer(serializers.Serializer):
    id = ObjectIdField(required=True)
    fias_street_guid = CharField(required=False, allow_blank=True)
    street = CharField(required=False)
    short_address = CharField(required=False, allow_blank=True)
    worker_serviced = serializers.BooleanField(required=False)


class WorkerSearchSerializer(serializers.Serializer):
    provider__str_name__icontains = CharField()
    provider___id__in = ListField(child=ObjectIdField())
    last_name__in = ListField(child=CharField())
    first_name__in = ListField(child=CharField())
    patronymic_name__in = ListField(child=CharField())
    email__in = ListField(child=CharField())
    phones__str_number = CharField()


class CopyWorkerPermissionsSerializer(serializers.Serializer):
    parent_worker = ObjectIdField()
    child_worker = ObjectIdField()


class ModelWorkerSearchSerializer(CustomDocumentSerializer):
    class Meta:
        model = Worker
        fields = (
            'id',
            'str_name',
            'provider'
        )


class AccessWorkerSerializer(serializers.Serializer):
    has_access = BooleanField(required=True)
    password = CharField(required=False)


class DismissWorkerSerializer(serializers.Serializer):
    is_dismiss = BooleanField(required=True)
    dismiss_date = DateTimeField(required=False)


class VCardSerializer(serializers.Serializer):
    provider = ObjectIdField(allow_null=True, required=False)


class WorkerManagementSerializer(serializers.Serializer):
    is_super = BooleanField(required=True)
    has_access = BooleanField(required=True)
    is_activated = serializers.SerializerMethodField()

    class Meta:
        model = Worker
        fields = ('id', 'is_super', 'has_access', 'is_activated')

    @staticmethod
    def get_is_activated(obj):
        return obj.is_activated


class MessengerTemplateSerializer(CustomDocumentSerializer):

    class Meta:
        model = MessengerTemplate
        fields = 'message',
