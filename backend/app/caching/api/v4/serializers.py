from rest_framework import serializers
from rest_framework.fields import CharField
from rest_framework_mongoengine.fields import ObjectIdField


class AccrualFilterSerializer(serializers.Serializer):
    """
    area_types - Тип квартиры
    areas_str - Номера квартир
    porches_str - Номера подъездов
    account_types - Тип аккаунта
    property_types - Вид собственности
    is_developer - Является ли застройщиком?
    house - ID дома
    only_privileged - Является ли льготником?
    *******_meter - Наличие счетчика
    antenna - Имеется антенна?
    lift - Имеется лифт?
    radio - Имеется радиоточка?
    """

    area_types = serializers.ListField(child=CharField(), required=False)
    areas_str = serializers.CharField(required=False)
    porches_str = serializers.CharField(required=False)
    account_types = serializers.CharField(required=False)
    property_types = serializers.ListField(child=CharField(), required=False)
    is_developer = serializers.NullBooleanField(required=False)
    house = ObjectIdField(required=True)

    only_privileged = serializers.NullBooleanField(required=False)
    cold_water_meter = serializers.NullBooleanField(required=False)
    hot_water_meter = serializers.NullBooleanField(required=False)
    gas_meter = serializers.NullBooleanField(required=False)
    electric_meter = serializers.NullBooleanField(required=False)
    heat_meter = serializers.NullBooleanField(required=False)
    antenna = serializers.NullBooleanField(required=False)
    lift = serializers.NullBooleanField(required=False)
    radio = serializers.NullBooleanField(required=False)
    feat = ObjectIdField(required=False)
    feat_value = serializers.NullBooleanField(required=False)
    coef = ObjectIdField(required=False)
    coef_value = serializers.FloatField(required=False)

    purpose = serializers.CharField(required=False)
    accrual_doc = ObjectIdField(required=False)
    responsible_only = serializers.NullBooleanField(required=False)
    responsible_month = serializers.DateTimeField(required=False)
