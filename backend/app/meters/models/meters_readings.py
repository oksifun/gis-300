from bson import ObjectId
from dateutil.relativedelta import relativedelta

from app.area.models.area import Area
from app.meters.models.meter import Meter
from processing.data_producers.associated.meters import \
    get_current_readings_period
from lib.helpfull_tools import DateHelpFulls as dhf
from processing.models.permissions import Permissions, ClientTab


class BaseMetersReadings:
    METER_TYPE = None

    def __init__(self, house, period, provider, account, binds,
                 meter_types=None):
        self.house = house
        self.period = period
        self.provider = provider
        self.account = account
        self.binds = binds
        self.meter_types = meter_types

    def get_readings(self):
        """
        Получение показаний за переданную дату по переданному дому
        по всем счетчикам типа
        """
        # Получение всех активных счетчиков дома
        meters = self._get_meters()
        # Получаем показания счетчиков на переданный месяц, предудыщее,
        # и если ничего нет - начальные
        readings = self._get_readings(meters)
        read_only = self.is_read_only()
        return readings, read_only

    def _get_meters(self):
        fields = (
            'id',
            '_type',
            'area.id',
            'order',
            'area.str_number',
            'readings',
            'serial_number',
            'description',
            'serial_number',
            'initial_values',
            'working_start_date',
            'ratio',
            'loss_ratio',
            'reference'
        )
        date_sub_query = {
            '$and': [
                {
                    '$or': [
                        {'working_finish_date': None},
                        {'working_finish_date': {
                            '$gt': dhf.begin_of_month(self.period)
                        }},
                    ],
                },
                {
                    '$or': [
                        {'working_start_date': None},
                        {'working_start_date': {
                            '$lte': dhf.end_of_month(self.period)
                        }},
                    ]
                },
            ]
        }
        query = (
            {'area.house._id': self.house, **date_sub_query}
            if self.METER_TYPE == 'AreaMeter'
            else {'house._id': self.house, **date_sub_query}
        )
        if self.meter_types:
            query.update({'_type': {'$in': self.meter_types}})
        query.update(Meter.get_binds_query(self.binds, raw=True))
        query['is_deleted'] = {'$ne': True}
        if self.provider==ObjectId('553e5c6aeb049b001b652020'):
            query = self.check_query_for_ses2(query)
        return tuple(Meter.objects(__raw__=query).only(*fields).as_pymongo())

    def check_query_for_ses2(self, query):
        """
        Ужасный костыль для ограничения видимости счетчиков ГВС
        для двух домов в организации СЭС
        Удалить при первой же возможности
        """
        house_ids = [
            ObjectId('534cefc9f3b7d47f1d69a7d9'),
            ObjectId('52e8eb7fb6e6974167de599d'),
        ]
        if self.METER_TYPE == 'AreaMeter' and self.house in house_ids:
            query.update({'_type': {'$ne': 'HotWaterAreaMeter'}})
        return query

    def _get_readings(self, meters):
        new_meters_list = sorted(
            (self._get_data_from_meter(x) for x in meters),
            key=lambda meter: (meter['order'], meter.get('serial_number'))
        )
        return new_meters_list

    def _get_data_from_meter(self, meter):
        # Найдем показание за переданный месяц и предыдущий
        search_period = dhf.begin_of_month(self.period)
        # Заменим показания необходимыми данными
        this_month_reading = None
        # На случай отсутствия показаний устанавливаем предыдущее из начального
        previous_month_reading = dict(
            created_at=meter['working_start_date'],
            values=meter['initial_values']
        )
        for reading in reversed(meter['readings']):
            if not reading.get('period'):
                continue
            if reading['period'] == search_period:
                this_month_reading = reading

            elif reading['period'] < search_period:
                # Если найдено показание переданного месяца -
                # значит мы нашли предыдущее
                previous_month_reading = reading
                break

        meter['readings'] = dict(
            this_month_reading=this_month_reading,
            previous_reading=previous_month_reading
        )
        return meter

    def is_read_only(self):
        # if self.account.is_super:
        #     return False
        period, is_default = get_current_readings_period(
            self.provider,
            self.house,
            return_is_default=True,
        )

        read_only = False  # Блокировка таблицы BE-326
        if not is_default:
            period = period - relativedelta(months=1)
            months = (
                    self.period.month
                    - period.month
                    + (self.period.year - period.year) * 12
            )
            # если документ начислений перекрывает текущией период
            # и статус документа в работе - блокируем для всех кроме тех,
            # у кого есть право на удаление slug(apartment_meters)
            if months == 0:
                read_only = True
            elif months < 0:
                read_only = True
            elif months > 2:
                read_only = not self._can_green_table()

        return read_only

    def _can_green_table(self):
        permissions = self._get_user_permissions()
        tabs = self.get_tabs_dict()

        if self.METER_TYPE == 'HouseMeter':
            return self._check_allowance(permissions, tabs, 'house_green_table')
        else:
            slug = 'all_apartments_meters_data'
            return self._check_allowance(permissions, tabs, slug)

    def _get_user_permissions(self):
        permissions = Permissions.objects(
            actor_id=self.account.id
        ).as_pymongo().first()
        if permissions:
            return (
                permissions['granular']['Tab']
                if permissions.get('granular')
                else None
            )
        return

    def get_tabs_dict(self):
        slugs = 'house_green_table', 'all_apartments_meters_data'
        return dict(ClientTab.objects(slug__in=slugs).scalar('slug', 'id'))

    def _check_allowance(self, permissions, tabs, slug):
        if not permissions:
            return False
        slug_p = permissions.get(str(tabs[slug]))
        return (
            slug_p[0]['permissions'].get('d')
            if slug_p
            else False
        )


class AreaMetersReadings(BaseMetersReadings):
    METER_TYPE = 'AreaMeter'


class HouseMetersReadings(BaseMetersReadings):
    METER_TYPE = 'HouseMeter'
