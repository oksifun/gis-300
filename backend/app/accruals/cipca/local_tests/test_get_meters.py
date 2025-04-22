"""Скромные тесты для Cipca"""
from datetime import datetime
from unittest import TestCase
import warnings

from bson import ObjectId

from app.area.models.area import Area
from mongoengine_connections import register_mongoengine_connections
from app.accruals.cipca.source_data.meters import get_meters

register_mongoengine_connections()

class TestCipca(TestCase):
    MIGRATION = False

    def area_migration(self, str_id):
        """
        Метод для миграции коммуникаций и счетчиков
        В данный момент НЕ ТРЕБУЕТСЯ, так как коммуникации не используются
        """
        from scripts.migrations.areas_communication import \
            add_areas_communications
        from scripts.migrations.areas_communication import recreate_communications

        str_id = str(str_id)

        ar = Area.objects(id=ObjectId(str_id))
        add_areas_communications(ar)
        ar = Area.objects(id=ObjectId(str_id))
        recreate_communications(ar)

    def get_meters_from_area(self, str_id, date, postponement=3, mig=False):
        """
        Метод расчета параметров со счетчиков квартиры
        :param str_id: id квартиры
        :param date: период расчета
        :param postponement: какое-то смещение для увеличения
                             периода определения активных счетчиков
        :param mig: bool: True запускает миграцию квартиры перед рассчетом
        """
        str_id = str(str_id)
        if mig:
            self.area_migration(str_id)

        areas = Area.objects(id=ObjectId(str_id)).only('id'
                                                       ).as_pymongo()
        return get_meters(list(areas), date, postponement)

    def test_areas_period(self):
        """
        Проверка периодов - month_from_last_reading.
        """
        warnings.simplefilter("ignore")
        month = datetime(2018, 4, 1)
        test_list = (
            ['573f2c04f3d0a400013cf1ec', 13, 'cold_water', month],
            ['56b0b60889849c00018b270e', 1, 'cold_water', month],
            ['526237d0e0e34c524382c013', 25, 'cold_water', month],
            ['52623760e0e34c523e829fd1', 1, 'cold_water', month],
            ['52e95d3ab6e69766c1564949', 15, 'cold_water', month],
            ['56b0b60889849c00018b26cd', 3, 'cold_water', month],
            ['52623761e0e34c523e82a007', 1, 'cold_water', month],
            ['526237bae0e34c524382b7a5', 1, 'cold_water', month],
            ['5692c054a3741a000111f207', 2, 'cold_water', month],
            ['5852b60625d35500010585fe', 20, 'hot_water', month],
            ['568d3d0fb8e3140001f5992c', 3, 'hot_water', month],
            ['52b476f52560d07129a7497d', 38, 'cold_water', month],
            ['526237c7e0e34c524382bbf7', 54, 'cold_water',
             datetime(2018, 4, 1)],
            ['5328a2dfb6e6976965819aeb', 3, 'cold_water',
             datetime(2017, 10, 1)],
        )
        # print('Квартир в тесте: ', len(test_list))
        for id_, res, res_name, date in test_list:
            with self.subTest(id_=id_, res=res, res_name=res_name):
                obj = self.get_meters_from_area(
                    id_, date, mig=self.MIGRATION
                )[ObjectId(id_)][res_name]['month_from_last_reading']
                self.assertEqual(obj, res)

    def test_areas_rift(self):
        """
        Проверка разрывов - rift.
        """
        warnings.simplefilter("ignore")
        month = datetime(2018, 4, 1)
        test_list = (
            ['526237ece0e34c523982d17b', False, 'cold_water', month],
            ['52d27ec9b6e6976062a68ca4', False, 'hot_water', month],
            ['58ef7d5728bad40001d53990', False, 'hot_water', month],
            ['52b421d32560d06b0641381f', True, 'hot_water',
             datetime(2018, 6, 21)],
            ['568e30a604eeb90001dd7d3c', True, 'hot_water',
             datetime(2018, 5, 1)],
            ['551292d2f3b7d4681123ee69', False, 'hot_water',
             datetime(2018, 5, 1)],
        )
        # print('rift - Квартир в тесте: ', len(test_list))
        for id_, res, res_name, date in test_list:
            with self.subTest(id_=id_, res=res, res_name=res_name):
                obj = self.get_meters_from_area(
                    id_, date, mig=self.MIGRATION
                )[ObjectId(id_)][res_name]['rift']
                self.assertEqual(obj, res)

    def test_areas_vals(self):
        """
        Проверка средних объемов - average_volume.
        """
        warnings.simplefilter("ignore")
        test_list = (
            ['561a9c8acd584c001d61a268', 15.0, 'cold_water',
             datetime(2018, 7, 13)],
            ['58e219c4cec9ce0001b16a0f', 3.25, 'cold_water',
             datetime(2018, 5, 1)],
            ['59940e2f6489e0000196642f', 60.81375, 'cold_water',
             datetime(2018, 5, 1)],
            ['551292d2f3b7d4681123eea8', 9.416666666666666, 'cold_water',
             datetime(2018, 5, 1)],
        )

        for id_, res, res_name, date in test_list:
            with self.subTest(id_=id_, res=res, res_name=res_name):
                obj = self.get_meters_from_area(
                    id_, date, mig=self.MIGRATION
                )[ObjectId(id_)][res_name]['average_volume']
                self.assertEqual(obj, res)

    def test_areas_last_finish(self):
        """
        Проверка дат окончания счетчиков - last_finish_date.
        """
        warnings.simplefilter("ignore")
        test_list = (
            ['597f3f142deee700012c08d8', None, 'electricity_regular',
             datetime(2018, 5, 13), 3],
            ['59940e2f6489e0000196642f', datetime(2018, 2, 15, 0, 0),
             'cold_water', datetime(2018, 4, 1), 3],
        )
        for id_, res, res_name, date, pp in test_list:
            with self.subTest(id_=id_, res=res, res_name=res_name):
                obj = self.get_meters_from_area(
                    id_, date, pp, mig=self.MIGRATION
                )[ObjectId(id_)][res_name]['last_finish_date']
                self.assertEqual(obj, res)
