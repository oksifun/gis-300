import copy

from app.meters.models.meter import HouseMeter
from lib.math_eval import math_eval
from processing.models.billing.heat_meter_data import HeatMeterReportTypes, \
    HeatHouseMeterData
from dateutil.parser import parse as dt_parse


class HeatSystemEvalError(Exception):
    pass


class HeatSystemInvalid(HeatSystemEvalError):
    pass


def eval_task_data(task):
    # получим исходные данные
    meter = HouseMeter.objects(pk=task.meter).get()
    # парсим данные задачи
    _parse_new_data(meter, task)
    # меняем статус задачи на успешный
    task.status = 'finished'
    task.save()


# Модели счетчиков, для которых не требуется отдельный запрос тотальных данных
JOINT_TOTALS_METER_MODELS = ['tsrv022', 'tsrv023', 'tsrv030', 'tsrv032']


def _parse_new_data(meter, task):
    """
    Парсинг свежепоступивших данных.
    Отличается от self.parsed_data тем, что для ТСРВ считается разница
    """
    if task.report_type == HeatMeterReportTypes.TOTAL:
        # при парсинге тотальных данных, оставлять только дату
        data = {task.datetime: task.result}
    else:
        data = task.result

    to_parsed = sorted(
        (
            HeatHouseMeterData(
                meter_model=meter.meter_model,
                report_type=task.report_type,
                datetime=dt_parse(date) if isinstance(date, str) else date,
                meter=meter,
                raw=raw,
                task=task.id,
                _type=['HeatHouseMeterData']
            )
            for date, raw in data.items() if raw
        ),
        key=lambda data: data.datetime
    )

    for data in to_parsed:
        if (
            data.meter_model in JOINT_TOTALS_METER_MODELS and
            data.report_type != HeatMeterReportTypes.TOTAL
        ):
            data.current = __calculate_tsrv_diff_raw(
                meter.pk,
                task.report_type,
                data.datetime,
                data.raw
            )
            raw = copy.deepcopy(data.raw)
            raw.update(data.current)
        else:
            raw = data.raw
        _internal_parse_data(data, meter, task, raw=raw)
        _update_meter_data(data)


def _update_meter_data(meter_data):
    """
    обновление документа, перезаписывает повторяющиеся данные
    """

    HeatHouseMeterData.objects(
        meter=meter_data.meter.id,
        report_type=meter_data.report_type,
        datetime=meter_data.datetime,
        lock=False,
    ).update(
        set__raw=meter_data.raw,
        set__parsed=meter_data.parsed,
        set__current=meter_data.current,
        set__correction=meter_data.correction,
        task=meter_data.task,
        _type=meter_data._type,
        # set__type=self.get_polymorphic_types(),
        upsert=True,
    )


def _internal_parse_data(meter_data, meter, task, raw):
    """
    Парсинг сырых данных.
    """
    parsed = []
    season = _get_season(meter, meter_data.datetime)
    if not meter.heat_systems:
        raise HeatSystemInvalid('No heat system meter {}'.format(meter.id))

    for hs in meter.heat_systems:
        season_mapping = hs.mappings[season]
        data = {}
        sensors = season_mapping.sensors.copy()
        sensors = {
            k: sensors[k]
            for k in sensors if k not in ('', None)
        }
        # единицы измерения в lowercase
        unit_table = {
            'гдж': lambda value: value / 4.1868,
            'гкал': lambda value: value,
            None: lambda value: value,
        }

        for sensor_name, sensor_value in sensors.items():
            try:
                value = raw[sensor_value].get('value')
                unit_value = raw[sensor_value].get('unit')
                if unit_value and unit_value.lower() in unit_table:
                    value = unit_table[unit_value.lower()](value)
                data[sensor_name] = value
            except KeyError:
                task.warnings.append(
                    'Отсутствует соответствие датчику! [{}]'.format(sensor_name)
                )
                task.save()
        formulas = season_mapping.formulas.copy()
        formulas = {
            k: formulas[k]
            for k in list(filter(lambda x: formulas[x] != '', formulas))
            if k not in data
        }
        for i in range(len(formulas.keys()) + 1):
            for sensor_name in list(formulas):
                try:
                    data_values = {name: value for name, value in data.items()}
                    data[sensor_name] = \
                        math_eval(formulas[sensor_name], data_values)
                    # Удаляем успешно вычисленные формулы
                    del formulas[sensor_name]
                except KeyError:
                    # raise
                    pass
        # Остались невычисленные формулы
        if formulas:
            task.warnings.append(
                'Невыполненные формулы {formulas} '
                'Данные для формул {data}'.format(
                    formulas=formulas,
                    data=data.keys()
                )
            )
            task.save()
        parsed.append({'name': hs.name, 'data': data})
    meter_data.parsed = parsed


def _get_season(meter, date):
    """
    Получение сезона в зависимости от переданной даты
    """
    if not meter.season_change:
        raise HeatSystemInvalid('No season settings meter {}'.format(meter.id))
    if len(meter.season_change) == 1:
        seasons = meter.season_change
    elif len(meter.season_change) > 1:
        seasons = list(filter(lambda x: x['date'] <= date, meter.season_change))
    else:
        seasons = None
    if not seasons:
        raise HeatSystemInvalid('No season on {}'.format(date))
    seasons = sorted(seasons, key=lambda x: x['date'])
    return seasons[-1].season


TSRV_VARIABLES = [
    'M0', 'V3', 'V5', 'M4', 'V6', 'W1_2', 'W3_3', 'W2_2', 'W3_2',
    'W3_1', 'W1_1', 'M3', 'W1_3', 'M1', 'W2_3', 'V1',
    'M5', 'V2', 'V4', 'W2_1', 'M6', 'V0', 'M2', 'W_сумм',
]


def __calculate_tsrv_diff_raw(meter_id, report_type, date, raw_data):
    """
    ТСРВ возвращает всегда тотальные данные. Поэтому мы ищем разницу с
    предыдущим значением
    """
    prev = HeatHouseMeterData.objects(
        meter=meter_id,
        report_type=report_type,
        datetime__lt=date
    ).order_by('-datetime').as_pymongo().first()
    if not prev:
        return {}
    raw = prev['raw']
    diff_raw = {}
    tsrv_diff = lambda l, r: l.get('value', 0) - r.get('value', 0)
    for k, v in raw.items():
        if k in TSRV_VARIABLES and k in raw_data:
            diff_raw[k] = {
                'value': tsrv_diff(raw_data[k], v),
                'unit': raw_data[k].get('unit')
            }
    return diff_raw

