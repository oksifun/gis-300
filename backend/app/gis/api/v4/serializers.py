from re import findall

from rest_framework.serializers import Serializer
from rest_framework.fields import ListField, \
    IntegerField, CharField, DateTimeField, BooleanField

from rest_framework_mongoengine.fields import ObjectIdField

from app.gis.models.gis_queued import GisQueued
from app.gis.models.gis_record import GisRecord
from app.gis.models.guid import GUID
from app.gis.tasks.gis_task import GisTask

from processing.models.billing.account import Tenant
from processing.models.billing.base import BindsPermissions
from utils.drf.base_serializers import CustomDocumentSerializer, \
    BaseCustomSerializer


class GisSendRequestSerializer(Serializer):
    record_id = ObjectIdField(required=True)
    forced = BooleanField(default=False)


class GisQueuedSerializer(CustomDocumentSerializer):
    class Meta:
        model = GisQueued
        fields = '__all__'


class GisTaskSerializer(CustomDocumentSerializer):
    class Meta:
        model = GisTask
        fields = '__all__'


class GisRecordSerializer(CustomDocumentSerializer):
    class Meta:
        model = GisRecord
        fields = (
            'generated_id',  # Object of type ObjectId is not JSON serializable
            'operation', 'desc', 'message_guid',
            'provider_id', 'house_id',
            'parent_id', 'child_id', 'follower_id',
            'canceled', 'saved', 'acked', 'stated', 'stored',
            'fraction', 'restarts', 'retries', 'scheduled',
            'status', 'warnings', 'error', 'trace',
        )


class FullRecordSerializer(CustomDocumentSerializer):
    class Meta:
        model = GisRecord
        fields = '__all__'


class AllRecordSerializer(CustomDocumentSerializer):
    class Meta:
        model = GisRecord
        fields = (
            'generated_id',  # Object of type ObjectId is not JSON serializable
            'operation', 'desc', 'message_guid',
            'provider_id', 'house_id', 'relation_id',
            'provider_info', 'house_info',
            'parent_id', 'child_id', 'follower_id',
            'canceled', 'saved', 'acked', 'stated', 'stored',
            'fraction', 'restarts', 'retries', 'scheduled',
            'status', 'warnings', 'error', 'trace',
            'task_state', 'task_owner'
        )


class GisGuidSerializer(CustomDocumentSerializer):
    class Meta:
        model = GUID
        fields = (
            'id', 'provider_id', 'premises_id',
            'object_id', 'tag', 'desc',
            'gis', 'root', 'version',
            'unique', 'number',
            'updated', 'deleted', 'saved',
            'record_id', 'transport',
            'status', 'error',
        )


class GisOperationSerializer(Serializer):

    task = CharField(required=True)


class EntityPropsSerializer(Serializer):

    ogrn = CharField(required=False)

    def validate(self, attrs: dict) -> dict:

        self.ogrn = findall(r'(\d{13,15})', attrs.pop('ogrn', ''))  # list

        return attrs

    def entity_props(self, binds_permissions: BindsPermissions) -> dict:

        assert self.ogrn, "Отсутствуют реквизиты (организаций) ЮЛ"

        props: dict = {}
        for tenant in Tenant.objects(__raw__={
            '_type': 'LegalTenant', 'has_access': False,  # индекс
            'ogrn': {'$in': self.ogrn}, 'entity': {'$ne': None},
            'is_deleted': {'$ne': True},
            **Tenant.get_binds_query(binds_permissions, raw=True),
        }).only('entity', 'ogrn', 'kpp').as_pymongo():
            assert isinstance(tenant, dict)
            existing = props.get(tenant['entity'])  # по условию запроса
            if existing is None:
                props[tenant['entity']] = \
                    {'ogrn': tenant['ogrn'], 'kpp': tenant.get('kpp')}
            elif not existing['ogrn']:
                existing['ogrn'] = tenant['ogrn']  # по условию запроса
                if existing['kpp'] != tenant.get('kpp'):
                    existing['kpp'] = None  # все филиалы организации
            elif existing['kpp'] != tenant.get('kpp'):
                existing['kpp'] = None  # все филиалы организации

        return props


class MeteringsSerializer(BaseCustomSerializer):

    period = DateTimeField(required=False)
    is_collective = BooleanField(required=False)


class PeriodSerializer(BaseCustomSerializer):

    period = DateTimeField(required=False)  # по умолчанию = empty


class OptionalDateIntervalSerializer(BaseCustomSerializer):

    date_from = DateTimeField(required=False)
    date_till = DateTimeField(required=False)


class RegistryNumbersSerializer(BaseCustomSerializer):

    registry_numbers = ListField(allow_empty=False,
        child=IntegerField(min_value=1, max_value=999))


class AccountNumbersSerializer(Serializer):

    accounts = CharField(required=False)  # номера (НЕ идентификаторы) ЛС

    def validate(self, attrs):

        self.accounts = findall(r'(\d{13})', attrs.pop('accounts', ''))  # list

        return attrs

    def house_tenants(self, binds_permissions: BindsPermissions) -> dict:

        house_tenants: dict = {}

        if not self.accounts:  # номера лицевых счетов не распознаны?
            return house_tenants  # WARN пустой словарь

        for tenant in Tenant.objects(__raw__={
            'number': {'$in': self.accounts},  # по номерам
            **Tenant.get_binds_query(binds_permissions, raw=True),
        }).only('area').as_pymongo():
            house_id = tenant['area']['house']['_id']
            house_tenants.setdefault(house_id, []).append(tenant['_id'])

        return house_tenants  # HouseId: [ TenantId,... ]


class ForceUpdateSerializer(Serializer):

    force_update = BooleanField(required=False)


class RecordIdSerializer(BaseCustomSerializer):

    record_id = ObjectIdField(required=True)


class ExportClosedSerializer(BaseCustomSerializer):

    export_closed = BooleanField(required=False)


class PreviousMonthSerializer(BaseCustomSerializer):

    previous_month = BooleanField(required=False)


class ExportAsPrivateSerializer(BaseCustomSerializer):

    as_private = BooleanField(required=False)