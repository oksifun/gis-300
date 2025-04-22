import copy
import datetime

from api.v4.serializers import CustomJsonEncoder
from app.reports.core.report import BaseReport
from app.reports.core.utils import update_report_schema_columns

AREA_METER_TYPES = {
    'HeatAreaMeter': 'ТС',
    'ColdWaterAreaMeter': 'ХВС',
    'HotWaterAreaMeter': 'ГВС',
    'ElectricOneRateAreaMeter': 'ЭЛ',
    'ElectricTwoRateAreaMeter': 'ЭЛДТ',
    'ElectricThreeRateAreaMeter': 'ЭЛТТ',
    'GasAreaMeter': 'ГС',
    'HeatHouseMeter': 'ТС',
    'ColdWaterHouseMeter': 'ХВС',
    'HotWaterHouseMeter': 'ГВС',
    'ElectricOneRateHouseMeter': 'ЭЛ',
    'ElectricTwoRateHouseMeter': 'ЭЛДТ',
    'ElectricThreeRateHouseMeter': 'ЭЛТТ',
    'GasHouseMeter': 'ГС',
}


class AreaMetersStatsReport(BaseReport):
    DATA = None
    METER_TYPE = None

    COMMON_COLUMNS = [
        dict(
            data_key='meter_type',
            not_summary=True,
            xlsx=dict(
                caption='Тип',
                width=12,
                align='left',
                text_wrap=True,
            ),
            json=dict(
                name='meter_type',
                caption='Тип',
                width=40,
                align='left',
                format_name='text',
            ),
        ),

        dict(
            data_key='serial_number',
            not_summary=True,
            xlsx=dict(
                caption='№ счётчика',
                width=20,
                align='left',
                text_wrap=True,
            ),
            json=dict(
                name='serial_number',
                caption='№ счётчика',
                width=50,
                align='left',
                format_name='text',
            ),
        ),

        dict(
            data_key='created_at',
            not_summary=True,
            xlsx=dict(
                caption='Дата нач.',
                width=10,
                align='center',
                text_wrap=True,
            ),
            json=dict(
                name='created_at',
                caption='Дата нач.',
                width=50,
                align='center',
                format_name='text',
            ),
        ),

        dict(
            data_key='initial_value',
            not_summary=True,
            format=lambda m: m,
            xlsx=dict(
                caption='Начальное',
                width=8,
                align='right',
                text_wrap=True,
                num_format='0.00;[Red]-0.00;0.00',
            ),
            json=dict(
                name='initial_value',
                caption='Начальное',
                width=240,
                align='right',
                format_name='currency',
            ),
        ),

        dict(
            data_key='current_value',
            not_summary=True,
            format=lambda m: m,
            xlsx=dict(
                caption='Конечное',
                width=8,
                align='right',
                text_wrap=True,
                num_format='0.00;[Red]-0.00;0.00',
            ),
            json=dict(
                name='current_value',
                caption='Конечное',
                width=240,
                align='right',
                format_name='currency',
            ),
        ),

        dict(
            data_key='delta',
            not_summary=True,
            format=lambda m: m,
            xlsx=dict(
                caption='Расход',
                width=8,
                align='right',
                text_wrap=True,
                num_format='0.00;[Red]-0.00;0.00',
            ),
            json=dict(
                name='deltas',
                caption='Расход',
                width=240,
                align='right',
                format_name='currency',
            ),
        ),

        dict(
            data_key='current_date',
            not_summary=True,
            xlsx=dict(
                caption='Дата кон.',
                width=10,
                align='center',
                text_wrap=True,
            ),
            json=dict(
                name='current_date',
                caption='Дата кон.',
                width=240,
                align='center',
                format_name='text',
            ),
        ),

        dict(
            data_key='comment',
            not_summary=True,
            xlsx=dict(
                caption='Примечание',
                width=15,
                align='left',
                text_wrap=True,
            ),
            json=dict(
                name='comment',
                caption='Примечание',
                width=240,
                align='left',
                format_name='text',
            ),
        ),
    ]

    REPORT_SCHEMA = dict(
        caption=dict(
            xlsx=dict(
                rows_num=1
            ),
        ),
        columns=[],
    )

    def get_extended_scheme(self, rows) -> dict:
        """
        Gets extended REPORT_SCHEMA
        :param rows:
        :return:
        """
        #  Возьмём за основу базовую схему отчёта
        extended_scheme = copy.deepcopy(self.REPORT_SCHEMA)

        if self.METER_TYPE == 'AreaMeter':
            extended_scheme['columns'].append(
                dict(
                    data_key='area_number',
                    not_summary=True,
                    xlsx=dict(
                        caption='Квартира',
                        width=7,
                        align='left',
                        text_wrap=True,
                    ),
                    json=dict(
                        name='area',
                        caption='Квартира',
                        width=50,
                        align='left',
                        format_name='text',
                    ),
                ),
            )
        extended_scheme['columns'].extend(self.COMMON_COLUMNS)
        extended_scheme = update_report_schema_columns(extended_scheme,
                                                       start_from='A')
        return extended_scheme

    def get_rows(self, celery_task=None) -> dict:
        result = self.format_data()
        return CustomJsonEncoder.perform_encode(result)

    def get_header(self) -> dict:
        name = 'Показания квартирных счётчиков'
        return {
            'report_name': name,
            'data_description': self.provider.str_name,
            'caption': [
                self.provider.str_name,
                '{} на {}'.format(
                    name,
                    datetime.datetime.now().strftime('%d.%m.%Y'),
                ),
                'Сформирован {}'.format(
                    datetime.datetime.now().strftime('%d.%m.%Y %H:%M'),
                ),
            ]
        }

    def format_data(self) -> list:
        result = []
        for row in self.DATA:
            meter = dict()
            readings = row.get('readings')
            if readings:
                prev_readings = readings['previous_reading']
                mtype = AREA_METER_TYPES.get(row['_type'][0], '')
                prev_date = prev_readings.get('created_at')
                const = {
                    'created_at': prev_date.strftime(
                        '%d.%m.%Y') if prev_date else ''
                }
                if self.METER_TYPE == 'AreaMeter':
                    const.update(
                        {
                            'area_number': row['area']['str_number'],
                            'serial_number': row['serial_number'],
                        }
                    )
                if self.METER_TYPE == 'HouseMeter':
                    serial_number = row['serial_number']
                    if row.get('description'):
                        serial_number += f" ({row['description']})"
                    const.update({'serial_number': serial_number})
                current_readings = readings.get('this_month_reading')
                if current_readings is None:
                    current_readings = {}
                if len(prev_readings['values']) == 3:
                    for name, i_val, c_val, c_delta in zip(
                            ('Пик', 'Ночь', 'Полупик'),
                            prev_readings['values'],
                            current_readings.get('values', ['', '', '']),
                            current_readings.get('deltas', ['', '', ''])
                    ):
                        line = dict()
                        line['meter_type'] = f'{mtype} ({name})'
                        line['comment'] = current_readings.get('comment',
                                                               '')
                        line['initial_value'] = i_val
                        line['current_value'] = c_val
                        line['delta'] = c_delta
                        cur_date = current_readings.get(
                            'created_at')
                        line['current_date'] = cur_date.strftime(
                            '%d.%m.%Y') if cur_date else ''
                        line.update(const)
                        result.append(line)
                elif len(prev_readings['values']) == 2:
                    for name, i_val, c_val, c_delta in zip(
                            ('День', 'Ночь'),
                            prev_readings['values'],
                            current_readings.get('values', ['', '']),
                            current_readings.get('deltas', ['', ''])
                    ):
                        line = dict()
                        line['meter_type'] = f'{mtype} ({name})'
                        line['comment'] = current_readings.get('comment',
                                                               '')
                        line['initial_value'] = i_val
                        line['current_value'] = c_val
                        line['delta'] = c_delta
                        cur_date = current_readings.get(
                            'created_at')
                        line['current_date'] = cur_date.strftime(
                            '%d.%m.%Y') if cur_date else ''
                        line.update(const)
                        result.append(line)
                elif len(prev_readings['values']) == 1:
                    meter['meter_type'] = mtype
                    meter['comment'] = current_readings.get('comment', '')
                    meter['initial_value'] = prev_readings.get('values',
                                                               [0])[0]
                    meter['current_value'] = current_readings.get('values',
                                                                  [''])[0]
                    meter['delta'] = current_readings.get('deltas', [''])[0]
                    cur_date = current_readings.get('created_at')
                    meter['current_date'] = cur_date.strftime(
                        '%d.%m.%Y') if cur_date else ''
                    meter.update(const)
            if meter:
                result.append(meter)
        return result
