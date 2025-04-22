from app.house.models.house import House
from processing.models.choice.gis_xlsx import MeterRatioGisTypes

from .base import BaseGISDataProducer


class HouseMetersReadingsFields:
    ADDRESS = 'Адрес дома'
    GIS_UID = 'Номер ПУ в ГИС ЖКХ'
    SERVICE_TYPE = 'Коммунальный ресурс'
    PERIOD = 'Период, за который передаются показания'
    VALUE_1 = 'Значение показания (Т1)'
    VALUE_2 = 'Значение показания (Т2), является обязательным для ' \
              'двух- и трехтарифного ПУ'
    VALUE_3 = 'Значение показания (Т3), является обязательным для ' \
              'трехтарифного ПУ'
    READING_DATE = 'Дата снятия показания'
    AUTO_CALC = 'Тех. возможность авто-расчета потребляемого объема'


class AreaMeterReadingsFields:
    ADDRESS = 'Адрес дома'
    GIS_UID = 'Номер ПУ в ГИС ЖКХ'
    SERVICE_TYPE = 'Коммунальный ресурс'
    PERIOD = 'Период, за который передаются показания'
    VALUE_1 = 'Значение показания (Т1)'
    VALUE_2 = 'Значение показания (Т2),  является обязательным для ' \
              'двух- и трехтарифного ПУ'
    VALUE_3 = 'Значение показания (Т3), является обязательным для ' \
              'трехтарифного ПУ'
    READING_DATE = 'Дата снятия показания'
    AUTO_CALC = 'Тех. возможность авто-расчета потребляемого объема'


class HouseMetersReadingsDataProducer(BaseGISDataProducer):

    XLSX_TEMPLATE = 'templates/gis/meters_readings_public_13_1_3_1.xlsx'
    XLSX_WORKSHEETS = {
        'Импорт показаний ОДПУ': {
            'entry_produce_method': 'get_entry_house_meters_readings',
            'title': 'Импорт показаний ОДПУ',
            'start_row': 2,
            'columns': {
                HouseMetersReadingsFields.ADDRESS: 'A',
                HouseMetersReadingsFields.GIS_UID: 'B',
                HouseMetersReadingsFields.SERVICE_TYPE: 'C',
                HouseMetersReadingsFields.PERIOD: 'D',
                HouseMetersReadingsFields.VALUE_1: 'E',
                HouseMetersReadingsFields.VALUE_2: 'F',
                HouseMetersReadingsFields.VALUE_3: 'G',
                HouseMetersReadingsFields.READING_DATE: 'H',
                # HouseMetersReadingsFields.AUTO_CALC: 'I',  # необязательное
            }
        },
    }

    def get_entry_house_meters_readings(self, entry_source, export_task):

        meter = entry_source['meter']
        period = entry_source['period']

        house_id = meter.house.id \
            if getattr(meter, 'house', None) \
            else meter.area.house.id

        house = House.objects(id=house_id).first()

        # TODO Повторяющийся код, вынести в Meter
        meter_class_to_service_type = {
            'ColdWaterAreaMeter': 'Холодная вода',
            'HotWaterAreaMeter': 'Горячая вода',
            'ElectricOneRateAreaMeter': 'Электрическая энергия',
            'ElectricTwoRateAreaMeter': 'Электрическая энергия',
            'ElectricThreeRateAreaMeter': 'Электрическая энергия',
            'HeatAreaMeter': 'Тепловая энергия',
            'HeatDistributorAreaMeter': 'Тепловая энергия',
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
            raise ValueError('Unknown Meter service type for: {}'.format(
                meter._type))

        if set(meter._type) & {
                'ElectricTwoRateAreaMeter', 'ElectricTwoRateHouseMeter'}:
            meter_ratio = MeterRatioGisTypes.TWO
        elif set(meter._type) & {
                'ElectricThreeRateAreaMeter', 'ElectricThreeRateHouseMeter'}:
            meter_ratio = MeterRatioGisTypes.THREE
        else:
            meter_ratio = MeterRatioGisTypes.ONE
        # TODO END

        readings_for_period = [
            reading
            for reading in meter.readings
            if reading.period == period
        ]

        if readings_for_period:
            reading = readings_for_period[-1]
            values = [
                '{:.7f}'.format(reading.values[0]),

                '{:.7f}'.format(reading.values[1])
                if meter_ratio in {
                    MeterRatioGisTypes.TWO, MeterRatioGisTypes.THREE}
                else '',

                '{:.7f}'.format(reading.values[2])
                if meter_ratio in {MeterRatioGisTypes.THREE}
                else '',
            ]
            reading_date = reading.created_at

        else:
            return 'No readings for meter({}) at period {}'.format(
                meter.id, period)

        return {
            HouseMetersReadingsFields.ADDRESS: house.address,
            HouseMetersReadingsFields.GIS_UID: meter.gis_uid,
            HouseMetersReadingsFields.SERVICE_TYPE: service_type,
            HouseMetersReadingsFields.PERIOD: period,
            HouseMetersReadingsFields.VALUE_1: values[0],
            HouseMetersReadingsFields.VALUE_2: values[1],
            HouseMetersReadingsFields.VALUE_3: values[2],
            HouseMetersReadingsFields.READING_DATE: reading_date,
        }


class AreaMetersReadingsDataProducer(BaseGISDataProducer):
    XLSX_TEMPLATE = 'templates/gis/meters_readings_individual_13_1_3_1.xlsx'
    XLSX_WORKSHEETS = {
        'Импорт показаний ИПУ': {
            'entry_produce_method': 'get_entry_area_meters_readings',
            'title': 'Импорт показаний ИПУ',
            'start_row': 2,
            'columns': {
                AreaMeterReadingsFields.ADDRESS: 'A',
                AreaMeterReadingsFields.GIS_UID: 'B',
                AreaMeterReadingsFields.SERVICE_TYPE: 'C',
                AreaMeterReadingsFields.PERIOD: 'D',
                AreaMeterReadingsFields.VALUE_1: 'E',
                AreaMeterReadingsFields.VALUE_2: 'F',
                AreaMeterReadingsFields.VALUE_3: 'G',
                AreaMeterReadingsFields.READING_DATE: 'H',
                # AreaMeterReadingsFields.AUTO_CALC: 'I',  # необязательное
            }
        },
    }

    def get_entry_area_meters_readings(self, entry_source, export_task):
        meter = entry_source['meter']
        period = entry_source['period']

        house_id = meter.house.id \
            if getattr(meter, 'house', None) \
            else meter.area.house.id

        house = House.objects(id=house_id).first()

        # TODO Повторяющийся код, вынести в Meter
        meter_class_to_service_type = {
            'ColdWaterAreaMeter': 'Холодная вода',
            'HotWaterAreaMeter': 'Горячая вода',
            'ElectricOneRateAreaMeter': 'Электрическая энергия',
            'ElectricTwoRateAreaMeter': 'Электрическая энергия',
            'ElectricThreeRateAreaMeter': 'Электрическая энергия',
            'HeatAreaMeter': 'Тепловая энергия',
            'HeatDistributorAreaMeter': 'Тепловая энергия',
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
            raise ValueError('Unknown Meter service type for: {}'.format(
                meter._type))

        if set(meter._type) & {
                'ElectricTwoRateAreaMeter', 'ElectricTwoRateHouseMeter'}:
            meter_ratio = MeterRatioGisTypes.TWO
        elif set(meter._type) & {
                'ElectricThreeRateAreaMeter', 'ElectricThreeRateHouseMeter'}:
            meter_ratio = MeterRatioGisTypes.THREE
        else:
            meter_ratio = MeterRatioGisTypes.ONE
        # TODO END

        readings_for_period = [
            reading
            for reading in meter.readings
            if reading.period <= period
        ]

        if readings_for_period:
            reading = readings_for_period[-1]
            values = [
                '{:.7f}'.format(reading.values[0]),

                '{:.7f}'.format(reading.values[1])
                if meter_ratio in {
                    MeterRatioGisTypes.TWO, MeterRatioGisTypes.THREE}
                else '',

                '{:.7f}'.format(reading.values[2])
                if meter_ratio in {MeterRatioGisTypes.THREE}
                else '',
            ]
            if reading.created_at:
                reading_date = reading.created_at.strftime('%d.%m.%Y')
            else:
                reading_date = ''

        else:
            return 'No readings for meter({}) at period {}'.format(
                meter.id, period)

        return {
            AreaMeterReadingsFields.ADDRESS: house.address,
            AreaMeterReadingsFields.GIS_UID: meter.gis_uid,
            AreaMeterReadingsFields.SERVICE_TYPE: service_type,
            AreaMeterReadingsFields.PERIOD: period,
            AreaMeterReadingsFields.VALUE_1: values[0],
            AreaMeterReadingsFields.VALUE_2: values[1],
            AreaMeterReadingsFields.VALUE_3: values[2],
            AreaMeterReadingsFields.READING_DATE: reading_date,
        }


