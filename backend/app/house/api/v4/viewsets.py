from django.http import HttpResponseForbidden, JsonResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import action

from api.v4.authentication import RequestAuth
from api.v4.forms.base import ConstantsBaseViewSet
from api.v4.permissions import READONLY_ACTIONS, SuperUserOnly
from api.v4.universal_crud import BaseCrudViewSet, ModelFilesViewSet, \
    CustomPagination
from app.house.api.v4.serializers import HouseViewSetSerializer, \
    PorchartSerializer, HouseDetailSerializer, ServiceBindsSerializer, \
    PorchesSerializer, HouseCreateSerializer
from app.house.models.house import House, Porchart
from processing.models.choices import ACCRUAL_SECTOR_TYPE_CHOICES, \
    AccrualsSectorType, GIS_DAY_SELECTION, GisDaySelection
from processing.models.house_choices import ALL_COMMUNITY_SYSTEMS_CHOICES, \
    CommunitySystem, BUILDING_DESIGN_TYPES_CHOICES, BuildingDesignType, \
    WELL_TYPES_CHOICES, WellType, RESOURCE_TYPES_CHOICES, ResourceType, \
    HEATING_TYPES_CHOICES, HeatingType, HOT_WATER_SUPPLY_TYPES_CHOICES, \
    HotWaterSupplyType, COLD_WATER_SUPPLY_TYPES_CHOICES, ColdWaterSupplyType, \
    SEWERAGE_TYPES_CHOICES, SewerageType, POWER_SUPPLY_TYPES_CHOICES, \
    PowerSupplyType, GAS_SUPPLY_TYPES_CHOICES, GasSupplyType, \
    VENTILATION_TYPES_CHOICES, VentilationType, STORM_SEWAGE_TYPES_CHOICES, \
    StormSewageType, BOOT_RECEIVE_VALVE_PLACEMENTS_CHOICES, \
    BootReceiveValvePlacement, ENERGY_EFFICIENCY_CLASS_CHOICES, \
    EnergyEfficiencyClass, AREA_LOCATIONS_CHOICES, AreaLocation, \
    WATER_SUPPLY_ZONES_CHOICES, WaterSupplyZone, HOUSE_PORCH_INTERCOM_CHOICES, \
    HousePorchIntercomType, PROTOCOL_CATEGORIES_CHOICES, ProtocolCategory, \
    PROTOCOL_RESULTS_CHOICES, ProtocolResult, HOUSE_ENGINEERING_STATUS_CHOICES, \
    HouseEngineeringStatusTypes, HOUSE_CATEGORIES_CHOICES, HouseCategory, \
    HOUSE_TYPES_CHOICES, HouseType, STRUCTURE_ELEMENTS_CHOICES, \
    StructureElement, EQUIPMENT_ELEMENTS_CHOICES, EquipmentElement


class HouseQuerySetMixin:
    def get_queryset(self):
        # Документы только для данной организации
        request_auth = RequestAuth(getattr(self, 'request'))
        binds = request_auth.get_binds()
        return House.objects(House.get_binds_query(binds), is_deleted__ne=True)


class HouseViewSet(HouseQuerySetMixin, BaseCrudViewSet):
    """Работа с домом (подъезды только для чтения)"""

    http_method_names = ['get', 'patch']
    serializer_class = HouseViewSetSerializer
    slug = (
        'houses',
        'house_squares',
        {
            'name': 'request_log',
            'actions': READONLY_ACTIONS,
        },
    )
    paginator = CustomPagination()


class HouseFilesViewSet(ModelFilesViewSet):
    """Работа с файлами дома"""

    model = House
    slug = 'houses'


class PorchartViewSet(BaseCrudViewSet):
    """Квартирограмма"""

    serializer_class = PorchartSerializer
    slug = 'houses'

    def get_queryset(self):
        return Porchart.objects.all()


class HouseDetailViewSet(HouseQuerySetMixin, BaseCrudViewSet):
    """Работа со списками вложенных документов модели"""

    serializer_class = HouseDetailSerializer
    slug = 'houses', 'house_squares'

    @action(detail=True, methods=['patch'], permission_classes=(SuperUserOnly,))
    def build_fias_tree(self, request, *args, **kwargs):
        """Формирование дерева ФИАС дома"""
        request_auth = RequestAuth(request)
        if not request_auth.is_super():
            return HttpResponseForbidden()
        house: House = self.get_object()  # получаем объект дома
        provider_ids: list = house.build_fias_tree()  # запускаем задачи

        return Response(status=status.HTTP_202_ACCEPTED,
            data={'providers': ', '.join(str(_id) for _id in provider_ids)})

    @action(detail=True, methods=['get', 'post'])
    def service_binds(self, request, *args, **kwargs):
        """ Получение списка привязок или создание новой """
        request_auth = RequestAuth(request)
        if not request_auth.is_super():
            return HttpResponseForbidden()
        return self.operate_list_objects(
            request=request,
            object_name='service_binds',
            object_serializer=ServiceBindsSerializer
        )

    @action(
        detail=True,
        methods=['get', 'patch', 'delete'],
        url_path=r'service_binds/(?P<bind_id>\w+)'
    )
    def service_bind(self, request, bind_id, *args, **kwargs):
        """ Работа с одной привязкой (удаление/редактирование/получение) """
        request_auth = RequestAuth(request)
        if not request_auth.is_super():
            return HttpResponseForbidden()
        return self.operate_one_object(
            request=request,
            object_id=bind_id,
            object_name='service_binds',
            object_serializer=ServiceBindsSerializer
        )

    @action(detail=True, methods=['get', 'post'])
    def porches(self, request, *args, **kwargs):
        """ Получение списка подездов или создание новой """
        return self.operate_list_objects(
            request=request,
            object_name='porches',
            object_serializer=PorchesSerializer,
        )

    @action(
        detail=True,
        methods=['get', 'patch', 'delete'],
        url_path=r'porches/(?P<porch_id>\w+)'
    )
    def porch(self, request, porch_id, *args, **kwargs):
        """ Работа с одним подъездом (удаление/редактирование/получение) """
        return self.operate_one_object(
            request=request,
            object_id=porch_id,
            object_name='porches',
            object_serializer=PorchesSerializer,
        )


class CreateHouseViewSet(BaseCrudViewSet):
    http_method_names = ['post']
    permission_classes = (SuperUserOnly, )
    serializer_class = HouseCreateSerializer

    def create(self, request, *args, **kwargs):
        fias_street_guid = request.data['fias_street_guid']
        street = request.data['street']
        street_only = request.data['street_only']
        kladr = request.data['kladr']
        number = request.data['number']
        bulk = request.data['bulk']
        structure = request.data['structure']
        is_allowed_meters = request.data['is_allowed_meters']
        new_house = House(
            fias_street_guid=fias_street_guid,
            street=street,
            street_only=street_only,
            kladr=kladr,
            number=number,
            bulk=bulk,
            structure=structure,
            is_allowed_meters=is_allowed_meters
        )
        new_house.save()
        return JsonResponse({'id': str(new_house.id)})


class HouseConstantsViewSet(ConstantsBaseViewSet):
    CONSTANTS_CHOICES = (
        (ACCRUAL_SECTOR_TYPE_CHOICES, AccrualsSectorType),
        (ALL_COMMUNITY_SYSTEMS_CHOICES, CommunitySystem),
        (BUILDING_DESIGN_TYPES_CHOICES, BuildingDesignType),
        (WELL_TYPES_CHOICES, WellType),
        (RESOURCE_TYPES_CHOICES, ResourceType),
        (HEATING_TYPES_CHOICES, HeatingType),
        (HOT_WATER_SUPPLY_TYPES_CHOICES, HotWaterSupplyType),
        (COLD_WATER_SUPPLY_TYPES_CHOICES, ColdWaterSupplyType),
        (SEWERAGE_TYPES_CHOICES, SewerageType),
        (POWER_SUPPLY_TYPES_CHOICES, PowerSupplyType),
        (GAS_SUPPLY_TYPES_CHOICES, GasSupplyType),
        (VENTILATION_TYPES_CHOICES, VentilationType),
        (STORM_SEWAGE_TYPES_CHOICES, StormSewageType),
        (BOOT_RECEIVE_VALVE_PLACEMENTS_CHOICES, BootReceiveValvePlacement),
        (ENERGY_EFFICIENCY_CLASS_CHOICES, EnergyEfficiencyClass),
        (AREA_LOCATIONS_CHOICES, AreaLocation),
        (WATER_SUPPLY_ZONES_CHOICES, WaterSupplyZone),
        (HOUSE_PORCH_INTERCOM_CHOICES, HousePorchIntercomType),
        (PROTOCOL_CATEGORIES_CHOICES, ProtocolCategory),
        (PROTOCOL_RESULTS_CHOICES, ProtocolResult),
        (HOUSE_ENGINEERING_STATUS_CHOICES, HouseEngineeringStatusTypes),
        (HOUSE_CATEGORIES_CHOICES, HouseCategory),
        (HOUSE_TYPES_CHOICES, HouseType),
        (STRUCTURE_ELEMENTS_CHOICES, StructureElement),
        (EQUIPMENT_ELEMENTS_CHOICES, EquipmentElement),
        (GIS_DAY_SELECTION, GisDaySelection),
    )
