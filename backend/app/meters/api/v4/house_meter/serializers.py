import rest_framework_mongoengine.fields as fields
from rest_framework_mongoengine.serializers import serializers
from rest_framework.serializers import Serializer
from rest_framework.fields import DateTimeField
from rest_framework.fields import CharField

from api.v4.serializers import CustomDocumentSerializer, \
    CustomEmbeddedDocumentSerializer
from app.meters.models.meter import AdapterEmbedded, HouseMeter, \
    MeterEmbeddedHouse

READ_WRITE_FIELDS = (
    'id',
    'adapter',
    'mounting',
    'loss_ratio',
    'digit_capacity',
    'install_at',
    'started_at',
    'checked_at',
    'temperature_sensor',
    'pressure_sensor',
    'description_control',
    'serial_number_control',
    'meter_model',
    'flowmeter_type',
    'sphere_application',
    'connection_schema',
    'temperature_chart',
    'pressure_transformer',
    'winter_calc_formula',
    'summer_calc_formula',
    'code_uute',
    'heat_systems',
    'season_change',
    'equip_info',
    'address',
    'expances',
    'tolerance_dt',
    'allowable_unbalance_mass',
    '_type',
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
    'installation_date',
    'ratio',
    'model_name',
    'brand_name',
    'gis_uid',
    'unit_of_measurement_okei',
    'initial_values',
    'description',
    'reference',
)

READ_ONLY_FIELDS = (
    'next_check_date',
    'order',
    'readings',
    'house',
    'is_deleted',
    'average_deltas',
    'created_by'
)


class AdapterEmbeddedSerializer(CustomEmbeddedDocumentSerializer):
    sim_number = serializers.CharField(allow_blank=True, allow_null=True)
    app_number = serializers.CharField(allow_blank=True, allow_null=True)
    account_number = serializers.CharField(allow_blank=True, allow_null=True)

    class Meta:
        model = AdapterEmbedded
        fields = '__all__'


class HouseMeterGetSerializer(CustomDocumentSerializer):
    class Meta:
        model = HouseMeter
        fields = READ_WRITE_FIELDS + READ_ONLY_FIELDS


class BasePatchAndCreateSerializer(CustomDocumentSerializer):
    freedom_params = dict(
        allow_blank=True,
        allow_null=True,
        required=False
    )

    adapter = AdapterEmbeddedSerializer(
        many=False,
        allow_null=True,
        required=False,
    )
    winter_calc_formula = serializers.CharField(**freedom_params)
    summer_calc_formula = serializers.CharField(**freedom_params)
    mounting = serializers.CharField(**freedom_params)
    description_control = serializers.CharField(**freedom_params)
    serial_number_control = serializers.CharField(**freedom_params)


class HouseMeterPartialUpdateSerializer(BasePatchAndCreateSerializer):

    class Meta:
        model = HouseMeter
        fields = READ_WRITE_FIELDS
        read_only_fields = READ_ONLY_FIELDS


class HouseEmbeddedSerializer(CustomEmbeddedDocumentSerializer):
    id = fields.ObjectIdField()

    class Meta:
        model = MeterEmbeddedHouse
        fields = ('id',)


class HouseMeterCreateSerializer(BasePatchAndCreateSerializer):
    house = HouseEmbeddedSerializer(many=False)

    class Meta:
        model = HouseMeter
        fields = READ_WRITE_FIELDS + ('house', )
        read_only_fields = READ_ONLY_FIELDS


class HouseMeterNotePartialUpdateSerializer(Serializer):
    """Сериализатор для примечания ОДПУ"""
    period = DateTimeField()
    comment = CharField(
        max_length=60,
        allow_blank=True,
        required=False,
        help_text="Текст примечания")
