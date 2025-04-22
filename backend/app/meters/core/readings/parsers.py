from mongoengine import DoesNotExist, ListField, IntField
from rest_framework import serializers
from rest_framework.fields import CharField, ChoiceField, \
    FloatField as FloatFieldDRF

from app.meters.models.choices import MeterType, ImportReadingsTaskStatus
from app.meters.models.tasks import MeterReadingsImportSettings
from lib.gridfs import get_file_from_gridfs


class CharsetType(object):
    UTF = 'utf-8'
    WIN = 'windows-1251'


class MeterDataType(object):
    values = 'values'
    deltas = 'deltas'


METER_DATA_TYPES_CHOICES = (
    (MeterDataType.values, 'Показания'),
    (MeterDataType.deltas, 'Расходы'),
)
IMPORT_READINGS_METER_TYPES_CHOICES = (
    (MeterType.HEAT_AREA_METER, 'uhb'),
    (MeterType.COLD_WATER_AREA_METER, 'fcw'),
    (MeterType.HOT_WATER_AREA_METER, 'fhw'),
    (MeterType.ELECTRIC_ONE_RATE_AREA_METER, 'fe1'),
    (MeterType.ELECTRIC_TWO_RATE_AREA_METER, 'fe2'),
    (MeterType.ELECTRIC_THREE_RATE_AREA_METER, 'fe3'),
)


class MeterDataCreateSerializer(serializers.Serializer):
    area_number = CharField(required=False)
    meter_type = ChoiceField(IMPORT_READINGS_METER_TYPES_CHOICES)
    serial_number = CharField(required=False, allow_blank=True)
    values = ListField(FloatFieldDRF(default=0))
    points = IntField(default=0)
    house_consumption = FloatFieldDRF(default=0)
    data_type = ChoiceField(METER_DATA_TYPES_CHOICES)


def parse_readings_file(file_id, task):
    data_raw = _get_raw_data(file_id, task)
    data = _get_data(data_raw, task)
    serializer = MeterDataCreateSerializer(many=True)
    serializer.run_validation(data=data)
    return data


def _get_raw_data(file_id, task):
    csv_file = get_file_from_gridfs(file_id, raw=True)
    csv_file_content = csv_file.read()
    try:
        csv_data = csv_file_content.decode(CharsetType.UTF).splitlines()
    except UnicodeDecodeError:
        csv_data = csv_file_content.decode(CharsetType.WIN).splitlines()
    except DoesNotExist:
        task.status = ImportReadingsTaskStatus.FAILED
        task.error = 'Файл не найден.'
        task.save()
        return 'Файл не найден.'
    data = list(
        filter(
            lambda x: x and x[0],
            map(lambda x: x.strip().split(';'), csv_data),
        )
    )
    return data


def _get_parser_func(data_raw):
    for i, row in enumerate(data_raw):
        if len(set(row)) < 3:
            continue
        header = row
        data = data_raw[i+1:]
        for parser in MeterReadingsImportSettings.objects.all().as_pymongo():
            if len(header) != parser['headers_count']:
                continue
            if any([
                header[int(k)].lower() != v.lower()
                for k, v in parser['headers'].items()
            ]):
                continue
            return data, parser['parser_func'], parser['primary_build']
    return data_raw, None, None


def _get_data(data_raw, task):
    data_to_parse, parser_func, primary_build = _get_parser_func(data_raw)
    if not data_to_parse or not parser_func:
        task.status = ImportReadingsTaskStatus.FAILED
        task.error = 'Данные в неправильном формате или отсутствуют.'
        task.save()
        return []
    data = globals()[parser_func](data_to_parse)
    if not data:
        task.status = ImportReadingsTaskStatus.FAILED
        task.error = 'Данные в неправильном формате или отсутствуют.'
        task.save()
        return []
    if primary_build:
        areas = {}
        for d in data:
            areas.setdefault(d['area_number'], [])
            areas[d['area_number']].append(d)
        for a in areas.values():
            for v in a:
                v['values'] /= len(a)
    # проверим номера помещений на лишние символы
    for d in data:
        if d['area_number'].isdigit():
            d['area_number'] = str(int(d['area_number']))
        else:
            num = d['area_number'].replace('-', '')
            ix = len(num)
            while ix > 0:
                if num[0: ix].isdigit():
                    num = '{}{}'.format(int(num[0: ix]), num[ix:])
                    break
                ix -= 1
            d['area_number'] = num
    return data


def _glavstroy(data_to_parse):
    if not data_to_parse:
        return []
    data = []
    for el in data_to_parse:
        if not el:
            continue
        serial_number = el[39]  # AN
        value = el[28]  # AC
        if el[10] == 'площади':
            serial_number = ''
        try:
            data.append({
                'area_number': el[1],  # B
                'meter_type': MeterType.HEAT_AREA_METER,
                'serial_number': serial_number,
                'values': 0 if value == '-' else float(value.replace(',', '.') or 0),
                'house_consumption': float(el[71].replace(',', '.') or 0),  # BT
                'data_type': MeterDataType.deltas,
            })
        except Exception as e:
            return []
    return data


def _glavstroy_short(data_to_parse):
    if not data_to_parse:
        return []
    data = []
    for el in data_to_parse:
        if not el:
            continue
        serial_number = el[2]  # C
        value = el[8]  # G
        try:
            data.append({
                'area_number': el[0],  # B
                'meter_type': MeterType.HEAT_AREA_METER,
                'serial_number': serial_number,
                'values': 0 if value == '-' else float(value.replace(',', '.') or 0),
                'house_consumption': 0,
                'data_type': MeterDataType.deltas,
            })
        except Exception as e:
            return []
    return data


def _kvs(data_to_parse):
    if not data_to_parse:
        return []
    data = []
    for el in data_to_parse:
        if not el or el[10] == 'площади':
            continue
        try:
            values = 0 if el[19] == '-' else float(el[19].replace(',', '.') or 0)
            data.append({
                'area_number': el[0],  # Столбец A
                'meter_type': MeterType.HEAT_AREA_METER,
                'serial_number': el[16],  # Столбец Q
                'values': values,  # T
                'points': 0,
                'house_consumption': float(el[45].replace(',', '.') or 0),  # AT
                'data_type': MeterDataType.deltas,
            })
        except Exception as e:
            return []
    return data


def _default(data_to_parse):
    if not data_to_parse:
        return []
    meter_types_flipped = {
        v: k
        for k, v in dict(IMPORT_READINGS_METER_TYPES_CHOICES).items()
    }
    data_temp = []
    data = []
    for el in data_to_parse:
        try:
            data_temp.append({
                'area_number': el[1],  # B
                'meter_type': meter_types_flipped.get(el[7], ''),  # H
                'serial_number': el[6],  # G
                'values': float(el[9].replace(',', '.') or 0),  # J
                'house_consumption': 0,
                'data_type': MeterDataType.values,
            })
        except Exception as e:
            return []

    electric = {}
    for ix, d in enumerate(data_temp):
        if d['meter_type'] == 'ElectricOneRateAreaMeter':
            electric.setdefault(
                d['serial_number'], [None, None, None])
            electric[d['serial_number']][0] = ix
        elif d['meter_type'] == 'ElectricTwoRateAreaMeter':
            electric.setdefault(
                d['serial_number'], [None, None, None])
            electric[d['serial_number']][1] = ix
        elif d['meter_type'] == 'ElectricThreeRateAreaMeter':
            electric.setdefault(
                d['serial_number'], [None, None, None])
            electric[d['serial_number']][2] = ix
        else:
            data.append(d)

    for el_data in electric.values():
        if el_data[2] is not None:
            data_temp[el_data[2]]['values'] = [
                data_temp[el_data[0]]['values'],
                data_temp[el_data[1]]['values'],
                data_temp[el_data[2]]['values']
            ]
            data.append(data_temp[el_data[2]])
        elif el_data[1] is not None:
            data_temp[el_data[1]]['values'] = [
                data_temp[el_data[0]]['values'],
                data_temp[el_data[1]]['values'],
            ]
            data.append(data_temp[el_data[1]])
        else:
            data_temp[el_data[0]]['values'] = [
                data_temp[el_data[0]]['values'],
            ]
            data.append(data_temp[el_data[0]])
    return data
