from mongoengine import Q

from app.area.models.area import Area
from app.house.models.house import House
from processing.models.billing.account import Tenant
from processing.models.billing.responsibility import Responsibility
from processing.models.choice.gis_xlsx import METER_GIS_TYPES_CHOICES, \
    MeterGisTypes, METER_RATIO_GIS_TYPES_CHOICES, MeterRatioGisTypes

from .base import BaseGISDataProducer

from processing.models.choice.base import get_choice_str


class MetersInfoFields:
    ADDRESS = 'Адрес дома'
    SERIAL_NUMBER = 'Заводской (серийный) номер ПУ'
    TYPE = 'Вид ПУ'
    BRAND = 'Марка ПУ'
    MODEL = 'Модель ПУ'
    HOUSE_UID = 'Уникальный номер дома. Обязательно для заполнения, если Тип' \
                ' ПУ =  Коллективный (общедомовой) или Индивидуальный ПУ в ЖД'
    AREA_UID = 'Уникальный номер помещения. Обязательно для заполнения, если' \
               ' Тип ПУ = Индивидуальный / Общий (квартирный)'
    ROOM_UID = 'Уникальный номер комнаты. Обязательно для заполнения, если ' \
               'Тип ПУ = Комнатный'
    HCS_UID = 'Номер лицевого счета/Единый лицевой счет/Идентификатор ЖКУ.' \
                 ' Обязательно для всех типов ПУ, кроме типа Коллективный ' \
                 '(Общедомовой)'
    IS_REMOTE = 'Наличие возможности дистанционного снятия показаний'
    REMOTE_TYPE = 'Информация о наличии возможности дистанционного снятия ' \
                  'показаний ПУ указанием наименования установленной системы'
    HAS_MORE_RESOURCE_METERS = 'Объем ресурса(ов) определяется с помощью ' \
                               'нескольких приборов учета'
    PLACING = 'Место установки текущего ПУ (обязательно, если ' \
              '"Объем ресурса(ов) определяется с помощью нескольких ' \
              'приборов учета" = "Да")'
    LINKED_METER_UID = 'Номер ПУ в ГИС ЖКХ, с которым требуется установить ' \
                       'связь текущего ПУ'
    SERVICE_TYPE = 'Вид коммунального ресурса'
    METER_RATE = 'Вид ПУ по количеству тарифов'
    METER_VALUE_1 = 'Базовое показание (Т1)'
    METER_VALUE_2 = 'Базовое показание (Т2) Обязательно для двух- и ' \
                    'трехтарифного ПУ'
    METER_VALUE_3 = 'Базовое показание (Т3) Обязательно для трехтарифных ПУ'
    TRANSFORMATION_RATIO = 'Коэффициент трансформации (заполняется только' \
                           ' для общедомовых ПУ электрической энергии)'
    INSTALL_DATE = 'Дата установки'
    SERVICE_DATE = 'Дата ввода в эксплуатацию'
    INSPECTION_DATE = 'Дата последней поверки'
    FACTORY_SEALING_DATE = 'Дата опломбирования ПУ заводом-изготовителем'
    INSPECTION_INTERVAL = 'Межповерочный интервал'
    HAS_TEMPERATURE_SENSOR = 'Наличие датчиков температуры'
    TEMPERATURE_SENSOR_INFO = 'Информация о наличии датчиков температуры с ' \
                              'указанием их местоположения на узле учета ' \
                              '(обязательно для заполнения, если "Наличие ' \
                              'датчиков температуры" = "Да" и если вид ПУ - ' \
                              'коллективный (общедомовой))'
    HAS_PRESSURE_SENSORS = 'Наличие датчиков давления'
    PRESSURE_SENSORS_INFO = 'Информация о наличии датчиков давления с ' \
                            'указанием их местоположения на узле учета ' \
                            '(обязательно для заполнения, если "Наличие ' \
                            'датчиков давления" = "Да" и если вид ПУ - ' \
                            'коллективный (общедомовой))'
    GIS_UID = 'Номер прибора учета в ГИС ЖКХ'
    GIS_PROCESSING_STATUS = 'Статус обработки'


class MetersInfoExtraServicesFields:
    ADDRESS = 'Адрес дома'
    SERIAL_NUMBER = 'Заводской (серийный) номер ПУ'
    TYPE = 'Вид ПУ'
    BRAND = 'Марка ПУ'
    SERVICE_TYPE = 'Вид коммунального ресурса'
    METER_VALUE = 'Базовое показание'


class MetersInfoExtraAccountsFields:
    ADDRESS = 'Адрес дома'
    SERIAL_NUMBER = 'Заводской (серийный) номер ПУ'
    TYPE = 'Вид ПУ'
    BRAND = 'Марка ПУ'
    ACCOUNT_ID = 'Номер лицевого счета/Единый лицевой счет/Идентификатор ЖКУ'


class MetersInfoExtraRoomsFields:
    ADDRESS = 'Адрес дома'
    SERIAL_NUMBER = 'Заводской (серийный) номер ПУ'
    TYPE = 'Вид ПУ'
    BRAND = 'Марка ПУ'
    ROOM_UID = 'Уникальный номер комнаты'


class MetersInfoDataProducer(BaseGISDataProducer):

    XLSX_TEMPLATE = 'templates/gis/meters_info_11_10_0_3.xlsx'
    XLSX_WORKSHEETS = {
        'Сведения о ПУ': {
            'entry_produce_method': 'get_entry_meters_info',
            'title': 'Сведения о ПУ',
            'start_row': 2,
            'columns': {
                MetersInfoFields.SERIAL_NUMBER: 'A',
                MetersInfoFields.TYPE: 'B',
                MetersInfoFields.BRAND: 'C',
                MetersInfoFields.MODEL: 'D',
                MetersInfoFields.ADDRESS: 'E',
                MetersInfoFields.HOUSE_UID: 'F',
                MetersInfoFields.AREA_UID: 'G',
                MetersInfoFields.ROOM_UID: 'H',
                MetersInfoFields.HCS_UID: 'I',
                MetersInfoFields.IS_REMOTE: 'J',
                MetersInfoFields.REMOTE_TYPE: 'K',
                MetersInfoFields.HAS_MORE_RESOURCE_METERS: 'L',
                MetersInfoFields.PLACING: 'M',
                MetersInfoFields.LINKED_METER_UID: 'N',
                MetersInfoFields.SERVICE_TYPE: 'O',
                MetersInfoFields.METER_RATE: 'P',
                MetersInfoFields.METER_VALUE_1: 'Q',
                MetersInfoFields.METER_VALUE_2: 'R',
                MetersInfoFields.METER_VALUE_3: 'S',
                MetersInfoFields.TRANSFORMATION_RATIO: 'T',
                MetersInfoFields.INSTALL_DATE: 'U',
                MetersInfoFields.SERVICE_DATE: 'V',
                MetersInfoFields.INSPECTION_DATE: 'W',
                MetersInfoFields.FACTORY_SEALING_DATE: 'X',
                MetersInfoFields.INSPECTION_INTERVAL: 'Y',
                MetersInfoFields.HAS_TEMPERATURE_SENSOR: 'Z',
                MetersInfoFields.TEMPERATURE_SENSOR_INFO: 'AA',
                MetersInfoFields.HAS_PRESSURE_SENSORS: 'AB',
                MetersInfoFields.PRESSURE_SENSORS_INFO: 'AC',

                MetersInfoFields.GIS_UID: 'AD',
                MetersInfoFields.GIS_PROCESSING_STATUS: 'AE'
            }
        },
        'Доп. комм. ресурсы': {
            'entry_produce_method': 'get_entry_meters_extra_services',
            'title': 'Доп. комм. ресурсы',
            'start_row': 2,
            'columns': {
                MetersInfoExtraServicesFields.ADDRESS: 'A',
                MetersInfoExtraServicesFields.SERIAL_NUMBER: 'B',
                MetersInfoExtraServicesFields.TYPE: 'C',
                MetersInfoExtraServicesFields.BRAND: 'D',
                MetersInfoExtraServicesFields.SERVICE_TYPE: 'E',
                MetersInfoExtraServicesFields.METER_VALUE: 'F',
            }
        },
        'Доп. лицевые счета ПУ': {
            'entry_produce_method': 'get_entry_meters_extra_accounts',
            'title': 'Доп. лицевые счета ПУ',
            'start_row': 2,
            'columns': {
                MetersInfoExtraAccountsFields.ADDRESS: 'A',
                MetersInfoExtraAccountsFields.SERIAL_NUMBER: 'B',
                MetersInfoExtraAccountsFields.TYPE: 'C',
                MetersInfoExtraAccountsFields.BRAND: 'D',
                MetersInfoExtraAccountsFields.ACCOUNT_ID: 'E',
            }
        },
        'Доп. комнаты ПУ': {
            'entry_produce_method': 'get_entry_meters_extra_rooms',
            'title': 'Доп. комнаты ПУ',
            'start_row': 2,
            'columns': {
                MetersInfoExtraRoomsFields.ADDRESS: 'A',
                MetersInfoExtraRoomsFields.SERIAL_NUMBER: 'B',
                MetersInfoExtraRoomsFields.TYPE: 'C',
                MetersInfoExtraRoomsFields.BRAND: 'D',
                MetersInfoExtraRoomsFields.ROOM_UID: 'E',
            }
        },
    }

    def get_entry_meters_info(self, entry_source, export_task):

        meter = entry_source['meter']

        is_area_meter = bool(set(meter._type) & {'AreaMeter'})
        is_house_meter = bool(set(meter._type) & {'HouseMeter'})

        if is_house_meter:
            house = House.objects(id=meter.house.id).first()
            meter_gis_type = get_choice_str(METER_GIS_TYPES_CHOICES, MeterGisTypes.HOUSE_METER)
        elif is_area_meter:
            house = House.objects(id=meter.area.house.id).first()
            meter_area = Area.objects(id=meter.area.id).first()

            if not meter_area:
                return 'Счетчик({}) прявязан к несуществующему помещению({})'.format(meter.id, meter.area.str_number)
            else:
                meter.area = meter_area

            if meter.area.is_shared:
                meter_gis_type = get_choice_str(METER_GIS_TYPES_CHOICES, MeterGisTypes.AREA_METER)
            else:
                meter_gis_type = get_choice_str(METER_GIS_TYPES_CHOICES, MeterGisTypes.INDIVIDUAL)

        else:
            raise ValueError('Unknown Meter type: {}'.format(meter._type))

        if is_area_meter:
            d = export_task.date
            resp = Responsibility.objects.filter(
                __raw__={
                    'account.area._id': meter.area.id,
                    '$and': [
                        {
                            '$or': [
                                {'date_from': None},
                                {'date_from': {'$lte': d}},
                            ],
                        },
                        {
                            '$or': [
                                {'date_till': None},
                                {'date_till': {'$gte': d}},
                            ],
                        },
                    ],
                }
            ).distinct(
                'account._id',
            )
            accounts = list(
                Tenant.objects(
                    id__in=resp,
                    area__id=meter.area.id,
                ).order_by(
                    'id',
                ),
            )
        else:
            accounts = [None]

        # TODO Повторяющийся код, вынести в Meter
        meter_class_to_service_type = {
            'ColdWaterAreaMeter': 'Холодная вода',
            'HotWaterAreaMeter': 'Горячая вода',
            'ElectricOneRateAreaMeter': 'Электрическая энергия',
            'ElectricTwoRateAreaMeter': 'Электрическая энергия',
            'ElectricThreeRateAreaMeter': 'Электрическая энергия',
            'HeatAreaMeter': 'Тепловая энергия',
            'GasAreaMeter': 'Газ',

            'ColdWaterHouseMeter': 'Холодная вода',
            'HotWaterHouseMeter': 'Горячая вода',
            'ElectricOneRateHouseMeter': 'Электрическая энергия',
            'ElectricTwoRateHouseMeter': 'Электрическая энергия',
            'ElectricThreeRateHouseMeter': 'Электрическая энергия',
            'HeatHouseMeter': 'Тепловая энергия',
            'GasHouseMeter': 'Газ',
        }

        service_type = None
        for meter_type in meter._type:
            if meter_type in meter_class_to_service_type:
                service_type = meter_class_to_service_type[meter_type]
                break

        if not service_type:
            raise ValueError('Unknown Meter service type for: {}'.format(meter._type))

        if set(meter._type) & {'ElectricTwoRateAreaMeter', 'ElectricTwoRateHouseMeter'}:
            meter_ratio = MeterRatioGisTypes.TWO
        elif set(meter._type) & {'ElectricThreeRateAreaMeter', 'ElectricThreeRateHouseMeter'}:
            meter_ratio = MeterRatioGisTypes.THREE
        else:
            meter_ratio = MeterRatioGisTypes.ONE
        # TODO END

        is_electric_meter = service_type == 'Электрическая энергия'

        if meter.expiration_date_check:
            if meter.expiration_date_check == 1:
                inspection_interval_text = '1 год'
            elif 2 <= meter.expiration_date_check <= 4:
                inspection_interval_text = '{} года'.format(meter.expiration_date_check)
            elif 5 <= meter.expiration_date_check <= 25:
                inspection_interval_text = '{} лет'.format(meter.expiration_date_check)
            else:
                raise ValueError('Invalid Meter.expiration_date_check = {} (int 1..25 expected)'.format(meter.expiration_date_check))
        else:
            inspection_interval_text = ''

        hcs_uid = self.get_current_account(
            accounts, meter_area, export_task
        ) if is_area_meter else None

        if is_area_meter and not hcs_uid:
            return f'Счетчик({meter.id}) не прявязан ни к одному аккаунту'

        initial_values = [
            '{:.7f}'.format(initial_value)
            for initial_value in meter.initial_values
        ]

        return {
            MetersInfoFields.ADDRESS: house.address,
            MetersInfoFields.SERIAL_NUMBER: meter.serial_number,
            MetersInfoFields.TYPE: meter_gis_type,
            MetersInfoFields.BRAND: meter.brand_name if getattr(meter, 'brand_name', False) else 'Нет данных',
            MetersInfoFields.MODEL: meter.model_name if getattr(meter, 'model_name', False) else 'Нет данных',
            MetersInfoFields.HOUSE_UID: house.gis_uid if is_house_meter else '',
            MetersInfoFields.AREA_UID: meter.area.gis_uid if is_area_meter else '',
            MetersInfoFields.ROOM_UID: '',  # Комнатных счетчиков в системе нет как класса
            MetersInfoFields.HCS_UID: hcs_uid,
            MetersInfoFields.IS_REMOTE: 'да' if meter.is_automatic else 'нет',  # TODO choices
            MetersInfoFields.REMOTE_TYPE: 'Система С-300' if meter.is_automatic else '',  # TODO choices

            # В текущей версии (11.0.0.1) не понятно как и зачем нужно выгружать
            # "связанные" счетчики, поэтому для всех счетчиков 'нет'
            MetersInfoFields.HAS_MORE_RESOURCE_METERS: 'нет',
            MetersInfoFields.PLACING: '',
            MetersInfoFields.LINKED_METER_UID: '',

            MetersInfoFields.SERVICE_TYPE: service_type,
            MetersInfoFields.METER_RATE: get_choice_str(METER_RATIO_GIS_TYPES_CHOICES, meter_ratio),
            MetersInfoFields.METER_VALUE_1: initial_values[0],
            MetersInfoFields.METER_VALUE_2: initial_values[1] if meter_ratio in {MeterRatioGisTypes.TWO, MeterRatioGisTypes.THREE} else '',
            MetersInfoFields.METER_VALUE_3: initial_values[2] if meter_ratio in {MeterRatioGisTypes.THREE} else '',
            MetersInfoFields.TRANSFORMATION_RATIO: meter.loss_ratio if is_house_meter and is_electric_meter else '',
            MetersInfoFields.INSTALL_DATE: meter.installation_date.date() if meter.installation_date else '',
            MetersInfoFields.SERVICE_DATE: meter.working_start_date.date() if meter.working_start_date else '',
            MetersInfoFields.INSPECTION_DATE: meter.last_check_date.date() if meter.last_check_date else '',
            MetersInfoFields.FACTORY_SEALING_DATE: meter.working_start_date.date() if meter.working_start_date else '',
            MetersInfoFields.INSPECTION_INTERVAL: inspection_interval_text,
            MetersInfoFields.HAS_TEMPERATURE_SENSOR: 'да' if getattr(meter, 'temperature_sensor', False) else 'нет',
            MetersInfoFields.TEMPERATURE_SENSOR_INFO: 'да' if getattr(meter, 'temperature_sensor', False) else 'нет',  # TODO
            MetersInfoFields.HAS_PRESSURE_SENSORS: 'да' if getattr(meter, 'pressure_sensor', False) else 'нет',
            MetersInfoFields.PRESSURE_SENSORS_INFO: 'да' if getattr(meter, 'pressure_sensor', False) else 'нет',  # TODO
            MetersInfoFields.GIS_UID: meter.gis_uid if meter.gis_uid else ''
        }

    def get_entry_meters_extra_services(self, entry_source, export_task):
        return {}

    @staticmethod
    def get_current_account(accounts, meter_area, export_task):
        """
        Определение ответсвенного в переданный период времени, для
        привязки счеткива к не архивному жителю
        """
        date = Q(date_till=None) | Q(date_till__gte=export_task.date)
        responsibility = Responsibility.objects(
            date,
            account__area__id=meter_area.id,
            provider=export_task.provider.id,
        ).distinct("account.id")
        for account in accounts:
            if account and account.id in responsibility:
                return account.hcs_uid
        return None

    def get_entry_meters_extra_accounts(self, entry_source, export_task):
        meter = entry_source['meter']

        if getattr(meter, 'house', None):
            house_id = meter.house.id
        else:
            house_id = meter.area.house.id
        house = House.objects(id=house_id).first()

        is_area_meter = bool(set(meter._type) & {'AreaMeter'})

        if is_area_meter:
            meter_area = Area.objects(id=meter.area.id).first()
            if not meter.area:
                return 'Счетчик прявязан к несуществующему помещению'

            meter.area = meter_area

        multi_entry = []

        if is_area_meter and getattr(meter.area, "is_shared", None):

            accounts = Tenant.objects(
                is_responsible=True,
                area__id=meter.area.id,
            ).order_by(
                'id',
            )

            for account in accounts[1:]:

                multi_entry.append({
                    MetersInfoExtraAccountsFields.ADDRESS: house.address,
                    MetersInfoExtraAccountsFields.SERIAL_NUMBER: meter.serial_number,
                    MetersInfoExtraAccountsFields.TYPE: get_choice_str(METER_GIS_TYPES_CHOICES, MeterGisTypes.AREA_METER),
                    MetersInfoExtraAccountsFields.BRAND: meter.brand_name if getattr(meter, 'brand_name', False) else '',
                    MetersInfoExtraAccountsFields.ACCOUNT_ID: account.number
                })

        return multi_entry

    def get_entry_meters_extra_rooms(self, entry_source, export_task):
        return {}

