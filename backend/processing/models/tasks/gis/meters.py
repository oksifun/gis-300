import logging
from datetime import datetime, timedelta

from mongoengine import ListField, Q, ReferenceField
from mongoengine.fields import DateTimeField

from app.house.models.house import House
from app.meters.models.meter import HouseMeter, AreaMeter
from constants.common import MONTH_NAMES
from processing.data_importers.gis.meters_info import MetersInfoDataImporter_2
from processing.data_importers.gis.meters_readings import (
    AreaMetersReadingsDataImporter, HouseMetersReadingsDataImporter
)
from processing.data_producers.gis.meters_info import MetersInfoDataProducer
from processing.data_producers.gis.meters_readings import (
    AreaMetersReadingsDataProducer, HouseMetersReadingsDataProducer
)
from processing.models.tasks.gis.base import (
    GisBaseExportRequest, GisBaseExportTask,
    GisBaseImportRequest, GisBaseImportTask,
)
from processing.models.tasks.gis.gis_filename_limiter import limit_xlsx_filename


logger = logging.getLogger('c300')


class MetersInfoExportRequest(GisBaseExportRequest):
    DESCRIPTION = getattr(GisBaseExportRequest, 'DESCRIPTION') + ': ПУ'

    def get_zip_file_name(self):
        return ' '.join([
            self.provider.str_name[0: 80],
            str(self.date.year),
            MONTH_NAMES[self.date.month - 1],
            'ПУ'
        ]) + '.zip'

    def get_tasks(self):
        logger.info(
            'Task %s entered "%s.get_tasks"',
            self.id,
            self.__class__.__name__,
        )
        provider_bind = Q(service_binds__provider=self.provider.id)
        actual_bind = (
                (
                        Q(service_binds__date_start__lt=self.date)
                        | Q(service_binds__date_start=None)
                )
                & (
                        Q(service_binds__date_end=None)
                        | Q(service_binds__date_end__gte=self.date)
                )
        )
        active_bind = Q(service_binds__is_active=True)

        houses = House.objects(provider_bind & actual_bind & active_bind)

        # CRUTCH REFERENCE FIX
        for house in houses:
            house.pk = house.id
        # CRUTCH END

        tasks = []

        for house in houses:

            # TODO OPTIMIZATION (~90 s)
            meters_for_house = Q(house__id=house.id)
            meters_for_areas = Q(area__house__id=house.id)
            meters__date_actual = \
                Q(working_finish_date__gt=self.date) | \
                Q(working_finish_date=None)
            meters_not_deleted = \
                Q(is_deleted__exists=False) | \
                Q(is_deleted=False)
            meters = list(
                HouseMeter.objects(
                    meters_for_house &
                    meters__date_actual &
                    meters_not_deleted
                )
            )
            meters.extend(
                list(
                    AreaMeter.objects(
                        meters_for_areas &
                        meters__date_actual &
                        meters_not_deleted
                    )
                )
            )
            # TODO END

            line_limit = 500  # CRUTCH HARDCODE Нужно решить как разбивать файл со счетчиками на части, сейчас частями по 100 строк

            if len(meters) <= line_limit:
                filename = ' '.join([
                    str(self.date.year),
                    MONTH_NAMES[self.date.month - 1]
                ])

                filename = limit_xlsx_filename(filename=filename,
                                               some_id=str(house.id),
                                               address="{} {}".format(
                                                   house.street_only,
                                                   house.short_address),
                                               doc_type='ПУ')

                tasks.append(self.create_child_task(
                    MetersInfoExportTask,
                    meters=meters,
                    filename=filename,
                    date=self.date
                ))

            else:

                for chunk, chunk_position in [
                    (meters[x:x+line_limit], x) for x in range(
                        0,
                        len(meters),
                        line_limit
                    )
                ]:

                    filename = ' '.join([
                        str(self.date.year),
                        MONTH_NAMES[self.date.month - 1],
                        '{}-{}'.format(
                            chunk_position,
                            chunk_position + len(chunk)),
                    ])

                    filename = limit_xlsx_filename(filename=filename,
                                                   some_id=str(house.id),
                                                   address="{} {}".format(
                                                       house.street_only,
                                                       house.short_address),
                                                   doc_type='ПУ')

                    tasks.append(self.create_child_task(
                        MetersInfoExportTask,
                        meters=chunk,
                        filename=filename,
                        date=self.date
                    ))

        return tasks


class MetersInfoExportTask(GisBaseExportTask):
    DESCRIPTION = getattr(GisBaseExportTask, 'DESCRIPTION') + ': ПУ'

    meters = ListField(ReferenceField(
        'processing.models.billing.meter.Meter',
        verbose_name='Счетчик'
    ))
    date = DateTimeField()

    PRODUCER_CLS = MetersInfoDataProducer

    def get_entries(self):

        entries = {
            meter.id: {
                'meter': meter,
            } for meter in self.meters
        }

        return entries


class HouseMetersReadingsExportRequest(GisBaseExportRequest):
    DESCRIPTION = getattr(
        GisBaseExportRequest,
        'DESCRIPTION'
    ) + ': Показания ОДПУ'

    def get_zip_file_name(self):
        return ' '.join([
            self.provider.str_name[0: 80],
            str(self.date.year),
            MONTH_NAMES[self.date.month - 1],
            'Показания ОДПУ'
        ]) + '.zip'

    def get_tasks(self):
        provider_bind = Q(service_binds__provider=self.provider.id)
        actual_bind = Q(
            service_binds__date_start__lt=self.date
        ) | Q(
            service_binds__date_start=None
        ) & (Q(
            service_binds__date_end=None
        ) | Q(service_binds__date_end__gte=self.date))
        active_bind = Q(service_binds__is_active=True)
        houses = House.objects(provider_bind & actual_bind & active_bind)

        # CRUTCH REFERENCE FIX
        for house in houses:
            house.pk = house.id
        # CRUTCH END

        tasks = []

        for house in houses:
            filename = ' '.join([
                str(self.date.year),
                MONTH_NAMES[self.date.month - 1]
            ])

            filename = limit_xlsx_filename(filename=filename,
                                           some_id=str(house.id),
                                           address="{} {}".format(
                                               house.street_only,
                                               house.short_address
                                           ),
                                           doc_type='Показания ОДПУ')

            tasks.append(
                self.create_child_task(
                    HouseMetersReadingsExportTask,
                    house=house,
                    filename=filename,
                    date=self.date
                )
            )
        return tasks


class HouseMetersReadingsExportTask(GisBaseExportTask):
    DESCRIPTION = getattr(GisBaseExportTask, 'DESCRIPTION') + ': Показания ОДПУ'

    house = ReferenceField(
        'app.house.models.house.House',
        verbose_name="Дом"
    )
    date = DateTimeField()

    PRODUCER_CLS = HouseMetersReadingsDataProducer

    def get_entries(self):

        period = datetime.combine(
            self.date.date().replace(day=1),
            datetime.min.time()
        )

        meters_for_house = Q(house__id=self.house.id)
        meters__date_actual = \
            Q(working_finish_date__gt=datetime.now()) | \
            Q(working_finish_date=None)
        meters_not_deleted = \
            Q(is_deleted__exists=False) | \
            Q(is_deleted=False)
        meter_has_readings_for_period = \
            Q(readings__period__lt=period + timedelta(days=1)) & \
            Q(readings__period__gt=period - timedelta(days=1))
        meters = HouseMeter.objects(
            meters_for_house &
            meters__date_actual &
            meters_not_deleted &
            meter_has_readings_for_period
        )

        entries = {
            meter.id: {
                'meter': meter,
                'period': period,
            } for meter in meters
        }

        return entries


class AreaMetersReadingsExportRequest(GisBaseExportRequest):
    DESCRIPTION = getattr(GisBaseExportRequest, 'DESCRIPTION') + ': Показания ИПУ'

    def get_zip_file_name(self):
        return ' '.join([
            self.provider.str_name[0: 80],
            str(self.date.year),
            MONTH_NAMES[self.date.month - 1],
            'Показания ИПУ'
        ]) + '.zip'

    def get_tasks(self):

        provider_bind = Q(service_binds__provider=self.provider.id)
        actual_bind = (
            Q(service_binds__date_start__lt=self.date) | Q(
                service_binds__date_start=None
            )) & (Q(service_binds__date_end=None) | Q(
            service_binds__date_end__gte=self.date
        ))
        active_bind = Q(service_binds__is_active=True)

        houses = House.objects(provider_bind & actual_bind & active_bind)

        # CRUTCH REFERENCE FIX
        for house in houses:
            house.pk = house.id
        # CRUTCH END

        tasks = []

        for house in houses:
            filename = ' '.join([
                str(self.date.year),
                MONTH_NAMES[self.date.month - 1]
            ])

            filename = limit_xlsx_filename(filename=filename,
                                           some_id=str(house.id),
                                           address="{} {}".format(house.street_only,
                                                                  house.short_address),
                                           doc_type='Показания ИПУ')

            tasks.append(self.create_child_task(AreaMetersReadingsExportTask, house=house, filename=filename, date=self.date))

        return tasks


class AreaMetersReadingsExportTask(GisBaseExportTask):
    DESCRIPTION = getattr(GisBaseExportTask, 'DESCRIPTION') + ': Показания ИПУ'

    house = ReferenceField(
        'app.house.models.house.House',
        verbose_name="Дом"
    )
    date = DateTimeField()

    PRODUCER_CLS = AreaMetersReadingsDataProducer

    def get_entries(self):

        period = datetime.combine(self.date.date().replace(day=1), datetime.min.time())

        # TODO INDEX: [readings.period, area__house__id, working_finish_date, is_deleted]
        meters_for_house = Q(area__house__id=self.house.id)
        meters__date_actual = \
            Q(working_finish_date__gt=datetime.now()) | \
            Q(working_finish_date=None)
        meters_not_deleted = \
            Q(is_deleted__exists=False) | \
            Q(is_deleted=False)
        meters = AreaMeter.objects(
            meters_for_house &
            meters__date_actual &
            meters_not_deleted
        )

        entries = {
            meter.id: {
                'meter': meter,
                'period': period
            } for meter in meters
        }

        return entries


class MetersInfoImportTask(GisBaseImportTask):
    DESCRIPTION = getattr(GisBaseImportTask, 'DESCRIPTION') + ': ПУ'

    IMPORTER_CLS = MetersInfoDataImporter_2
    START_ROW = 2


class AreaMetersReadingsImportTask(GisBaseImportTask):
    DESCRIPTION = getattr(GisBaseImportTask, 'DESCRIPTION') + ': Показания ИПУ'

    IMPORTER_CLS = AreaMetersReadingsDataImporter
    START_ROW = 3


class HouseMetersReadingsImportTask(GisBaseImportTask):
    DESCRIPTION = getattr(GisBaseImportTask, 'DESCRIPTION') + ': Показания ОДПУ'

    IMPORTER_CLS = HouseMetersReadingsDataImporter
    START_ROW = 3


class MetersInfoImportRequest(GisBaseImportRequest):
    DESCRIPTION = getattr(GisBaseImportRequest, 'DESCRIPTION') + ': ПУ'

    IMPORT_TASK_CLS = MetersInfoImportTask


class AreaMetersReadingsImportRequest(GisBaseImportRequest):
    DESCRIPTION = getattr(GisBaseImportRequest, 'DESCRIPTION') + ': Показания ИПУ'

    IMPORT_TASK_CLS = AreaMetersReadingsImportTask


class HouseMetersReadingsImportRequest(GisBaseImportRequest):
    DESCRIPTION = getattr(GisBaseImportRequest, 'DESCRIPTION') + ': Показания ОДПУ'

    IMPORT_TASK_CLS = HouseMetersReadingsImportTask



