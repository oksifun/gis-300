from datetime import datetime
from fractions import Fraction

from mongoengine import DoesNotExist
from rest_framework import exceptions

from api.v4.authentication import RequestAuth
from api.v4.forms.base import ConstantsBaseViewSet
from api.v4.permissions import READONLY_ACTIONS
from api.v4.serializers import PrimaryKeySerializer
from api.v4.universal_crud import BaseCrudViewSet
from api.v4.viewsets import BaseLoggedViewSet
from app.area.models.area import Area
from app.meters.models.choices import (
    METER_CLOSER_TYPES_CHOICES, METER_EXPIRATIONS_DATE_CHOISES_DICT,
    METER_MEASUREMENT_UNITS_CHOICES_DICT, METER_TYPE_NAMES_SHORT,
    METER_TYPE_NAMES, METER_TYPE_UNIT_NAMES,
    MeterCloserType, MeterTypeNames, MeterTypeNamesShort, MeterTypeUnitNames,
)
from processing.data_producers.forms.tenant import (
    get_family, tenant_is_archive, mate_serializer
)
from processing.models.billing.account import Tenant
from processing.models.choices import (
    ACCRUAL_SECTOR_TYPE_CHOICES, AREA_COMMUNICATIONS_CHOICES,
    AREA_INTERCOM_CHOICES, AREA_TOTAL_CHANGE_REASON_CHOICES, AREA_TYPE_CHOICES,
    STOVE_TYPE_CHOICES,
    AccrualsSectorType, AreaCommunicationsType, AreaIntercomType,
    AreaLocations, AreaTotalChangeReason, AreaType, StoveType,
    READINGS_CREATORS_CHOICES, ReadingsCreator
)
from processing.models.choice.area_passport import (
    KITCHEN_LIGHTING_CHOICES, KITCHEN_LOCATION_CHOICES, ROOM_BALCONY_CHOICES,
    ROOM_DEFECTS_CHOICES, ROOM_ENGINEERING_STATUS_CHOICES, ROOM_ENTRY_CHOICES,
    ROOM_FLOOR_CHOICES, ROOM_FORM_CHOICES, ROOM_PLAN_CHOICES,
    ROOM_REPAIR_CHOICES, ROOM_TYPE_CHOICES, WC_TYPE_CHOICES,
    KitchenLighting, KitchenLocation, RoomBalcony, RoomDefects,
    RoomEngineeringStatus, RoomEntry, RoomFloor, RoomForm, RoomPlan,
    RoomRepair, RoomType, WCType,
)
from .serializers import AreasSerializer, FamilySerializer, RequestSerializer


class AreasViewSet(BaseCrudViewSet):
    # Передаем сериализатор модели, на основе которого будет проинспектирована
    # модель и drf узнает все о ее полях
    serializer_class = AreasSerializer
    slug = (
        'apartment',
        {
            'name': 'apartments',
            'actions': READONLY_ACTIONS,
        },
        {
            'name': 'request_log',
            'actions': READONLY_ACTIONS,
        },
    )

    def get_queryset(self):
        # Документы только для данной организации
        request_auth = RequestAuth(self.request)
        binds = request_auth.get_binds()
        try:
            binds_q = Area.get_binds_query(binds)
        except DoesNotExist as e:
            raise exceptions.AuthenticationFailed(
                e.args[0] if e.args else 'No required binds permissions',
            )
        return Area.objects(
            binds_q,
            is_deleted__ne=True,
        ).order_by('order')


class FamilyViewSet(BaseLoggedViewSet):
    """
    Получение данных о семьях
    """
    protect_personal_data = False
    slug = ('apartment', 'request_log', 'payments')

    def list(self, request):
        serializer = RequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        request_auth = RequestAuth(request)
        binds = request_auth.get_binds()
        provider_id = request_auth.get_provider_id()
        area_ids = serializer.validated_data['account__area__id']
        others = serializer.validated_data.get('other_tenants_include')
        serializer = FamilySerializer(
            self._get_families(
                area_ids,
                binds,
                provider_id,
                other_tenants_include=others,
            ),
            many=True,
        )
        return self.json_response(data={'results': serializer.data})

    def _get_families(self, area_ids, binds, provider_id,
                      other_tenants_include=False):
        tenants = self._get_areas_tenants(
            area_ids,
            binds,
            other_tenants_include=other_tenants_include,
        )
        families = []
        now = datetime.now()
        for tenant in self._get_responsible_iter(tenants):
            ownership = (tenant.get('statuses') or {}).get('ownership')
            family = {
                'id': tenant['_id'],
                'name': tenant['str_name'],
                'email': tenant.get('email', ''),
                'phones': [
                    dict(
                        code=x.get('code', ''),
                        number=x.get('number', ''),
                        add=x.get('add', ''),
                        phone_type=x.get('type', ''),
                        not_actual=x.get('not_actual', ''),
                    )
                    for x in tenant.get('phones', [])
                ],
                'is_archive': tenant_is_archive(tenant, now),
                'members': get_family(
                    tenant,
                    binds,
                    include_self=True,
                    include_archive=True,
                    provider_id=provider_id
                ),
                'registered_count': 0,
                'living_count': 0,
                'property_share': Fraction(0, 1),
                'ownership': ownership,
                'has_responsibles': False,
                'rooms': tenant.get('rooms'),
            }
            self._family_stats_calculate(family)
            families.append(family)
        families = sorted(
            families,
            key=lambda i: (
                i['is_archive'],
                not i['has_responsibles'],
                i['name'],
            ),
        )
        not_family = self._get_not_family_men(tenants, families)
        if not_family:
            families.append(not_family)
        return families

    @staticmethod
    def _family_stats_calculate(family):
        for member in family['members']:
            family['registered_count'] += 1 if member['registered'] else 0
            family['living_count'] += 1 if member['living'] else 0
            if member.get('property_share'):
                family['property_share'] += \
                    Fraction(*member['property_share'])
            if member['is_responsible']:
                family['has_responsibles'] = True
        family['property_share'] = [
            family['property_share'].numerator,
            family['property_share'].denominator,
        ]

    def _get_areas_tenants(self, area_ids, binds, other_tenants_include=False):
        tenant_types = ['PrivateTenant', 'LegalTenant']
        if other_tenants_include:
            tenant_types.append('OtherTenant')
        return list(
            Tenant.objects(
                Tenant.get_binds_query(binds),
                area__id__in=area_ids,
                _type__in=tenant_types,
                is_deleted__ne=True,
            ).only(
                'id',
                '_type',
                'str_name',
                'family',
                'area',
                'statuses',
                'phones',
                'email',
                'rooms',
            ).as_pymongo(),
        )

    def _get_responsible_iter(self, tenants):
        return (
            t
            for t in tenants
            if (
                t.get('family')
                and t['family'].get('householder')
                and t['_id'] == t['family']['householder']
            )
        )

    def _get_not_family_men(self, tenants, families):
        tenants_ids = {x['_id'] for x in tenants}
        members = [
            t
            for t in tenants
            if (
                    not t.get('family')
                    or not t['family'].get('householder')
                    or t['family']['householder'] not in tenants_ids
            )
        ]
        if not members:
            for f in families:
                for m in f['members']:
                    for ten in tenants:
                        if ten['_id'] == m['id']:
                            tenants.remove(ten)
        if not members and not tenants:
            return None
        not_family = {
            'id': None,
            'name': 'Другие жители',
            'email': '',
            'phones': [],
            'is_archive': False,
            'registered_count': 0,
            'living_count': 0,
            'property_share': Fraction(0, 1),
            'has_responsibles': False,
        }
        if members:
            not_family.update(
                {'members': [mate_serializer(t) for t in members]}
            )
            for member in not_family['members']:
                member['is_archive'] = True
        else:
            not_family.update(
                {'members': [mate_serializer(t) for t in tenants]}
            )
        self._family_stats_calculate(not_family)
        return not_family


class AreasOfHouseViewSet(BaseLoggedViewSet):
    slug = ('apartment', 'request_log')

    def retrieve(self, request, pk):
        """
        Получение списка всех квартир дома
        """
        house = PrimaryKeySerializer.get_validated_pk(pk)
        request_auth = RequestAuth(request)
        binds = request_auth.get_binds()
        areas = self._get_house_areas(house, binds)
        return self.json_response(data={'results': areas})

    def _get_house_areas(self, house_id, binds):
        areas = Area.objects(
            Area.get_binds_query(binds),
            house__id=house_id,
            is_deleted__ne=True
        ).scalar(
            'id',
            'str_number_full',
            '_type'
        ).order_by('order')
        return [dict(
            id=x[0], str_number_full=x[1], _type=x[2][0]
        ) for x in areas]


def filter_meter_by_type(const, meter_type: str):
    if meter_type not in ['AreaMeter', 'HouseMeter']:
        raise ValueError("meter_type not in ['AreaMeter', 'HouseMeter'].")

    return tuple(x for x in const if meter_type in x[0])


class AreaConstantsViewSet(ConstantsBaseViewSet):
    CONSTANTS_CHOICES = (
        (ACCRUAL_SECTOR_TYPE_CHOICES, AccrualsSectorType),
        (AreaLocations.CHOICES, AreaLocations),
        (METER_CLOSER_TYPES_CHOICES, MeterCloserType),
        (METER_TYPE_NAMES_SHORT, MeterTypeNamesShort),
        (METER_TYPE_UNIT_NAMES, MeterTypeUnitNames),
        (METER_TYPE_NAMES, MeterTypeNames),
        (AREA_TYPE_CHOICES, AreaType),
        (AREA_TOTAL_CHANGE_REASON_CHOICES, AreaTotalChangeReason),
        (STOVE_TYPE_CHOICES, StoveType),
        (AREA_INTERCOM_CHOICES, AreaIntercomType),
        (READINGS_CREATORS_CHOICES, ReadingsCreator),
        (ROOM_TYPE_CHOICES, RoomType),
        (ROOM_PLAN_CHOICES, RoomPlan),
        (ROOM_FORM_CHOICES, RoomForm),
        (ROOM_ENTRY_CHOICES, RoomEntry),
        (ROOM_BALCONY_CHOICES, RoomBalcony),
        (ROOM_FLOOR_CHOICES, RoomFloor),
        (ROOM_REPAIR_CHOICES, RoomRepair),
        (ROOM_ENGINEERING_STATUS_CHOICES, RoomEngineeringStatus),
        (KITCHEN_LOCATION_CHOICES, KitchenLocation),
        (KITCHEN_LIGHTING_CHOICES, KitchenLighting),
        (WC_TYPE_CHOICES, WCType),
        (ROOM_DEFECTS_CHOICES, RoomDefects),
        (AREA_COMMUNICATIONS_CHOICES, AreaCommunicationsType),
        (
            filter_meter_by_type(METER_TYPE_NAMES_SHORT, 'AreaMeter'),
            type('AreaMeterTypeNamesShort', (), {})
        ),
        (
            filter_meter_by_type(METER_TYPE_UNIT_NAMES, 'AreaMeter'),
            type('AreaMeterTypeUnitNames', (), {})
        ),
        (
            filter_meter_by_type(METER_TYPE_NAMES, 'AreaMeter'),
            type('AreaMeterTypeNames', (), {})
        ),
        # Домовые
        (
            filter_meter_by_type(METER_TYPE_NAMES_SHORT, 'HouseMeter'),
            type('HouseMeterTypeNamesShort', (), {})
        ),
        (
            filter_meter_by_type(METER_TYPE_UNIT_NAMES, 'HouseMeter'),
            type('HouseMeterTypeUnitNames', (), {})
        ),
        (
            filter_meter_by_type(METER_TYPE_NAMES, 'HouseMeter'),
            type('HouseMeterTypeNames', (), {})
        ),
        *[
            (values, type + 'OKEI')
            for type, values in METER_MEASUREMENT_UNITS_CHOICES_DICT.items()
        ]
    )


class MetersUnitsConstantsViewSet(ConstantsBaseViewSet):
    CONSTANTS_CHOICES = tuple(
        (values, type)
        for type, values in METER_MEASUREMENT_UNITS_CHOICES_DICT.items()
    )


class MeterExpirationConstantsViewSet(ConstantsBaseViewSet):
    CONSTANTS_CHOICES = tuple(
        (values, type)
        for type, values in METER_EXPIRATIONS_DATE_CHOISES_DICT.items()
    )
