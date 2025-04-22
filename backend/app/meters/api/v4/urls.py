from api.v4.viewsets import HandyRouter

from .close_meter.viewsets import CloseMeterViewSet
from .events.viewsets import MeterEventsViewSet
from .readings.viewsets import (
    AreaMeterReadingsManipulatorViewSet, HouseMeterReadingsManipulatorViewSet,
    ImportMeterReadingsViewSet,
    AreaMetersAllReadingsViewSet,
)
from .readings_bulk.viewsets import (
    AreaMeterReadingsViewSet,
    AreaMeterReadingsExcelViewSet,
    HouseMeterReadingsViewSet,
    HouseMeterReadingsExcelViewSet,
    MeterReadingsPeriodViewSet,
    ExportMetersDataToCSV,
)
from app.meters.api.v4.area_meter.viewsets import (
    AreaMeterEventsViewSet,
    AreaMeterViewSet,
    AreaMeterFilesViewSet,
)
from app.meters.api.v4.house_meter.viewsets import (
    HouseMeterViewSet,
    HouseMeterFilesViewSet, HouseMeterNoteViewSet,
)

meters_router = HandyRouter()

# Закрытие счетчика
meters_router.register(
    'forms/meter/close',
    CloseMeterViewSet,
    basename='meter_close'
)
meters_router.register(
    'forms/area_meters/all_readings',
    AreaMetersAllReadingsViewSet,
    basename='all_readings'
)
# Добавление показаний по общедомовым счетчикам
meters_router.register(
    'forms/house_meter/add_readings',
    HouseMeterReadingsManipulatorViewSet,
    basename='add_readings'
)
# Добавление примечаний по общедомовым счетчикам
meters_router.register(
    'forms/house_meter/add_notes',
    HouseMeterNoteViewSet,
    basename='add_notes'
)
# Добавление показаний по квартирным счетчикам
meters_router.register(
    'forms/area_meter/add_readings',
    AreaMeterReadingsManipulatorViewSet,
    basename='add_readings'
)
meters_router.register(
    'forms/house_meters/readings',
    HouseMeterReadingsViewSet,
    basename='forms_house_meters_readings'
)
meters_router.register(
    'forms/area_meters/readings',
    AreaMeterReadingsViewSet,
    basename='forms_area_meters_readings'
)
meters_router.register(
    'forms/area/meter_events',
    MeterEventsViewSet,
    basename='meter_events'
)
meters_router.register(
    'forms/meters/readings/current_period',
    MeterReadingsPeriodViewSet,
    basename='forms_readings_period'
)

# CRUD для событий по счетчику
meters_router.register(
    'models/meter_event',
    AreaMeterEventsViewSet,
    basename='meter_event'
)

# CRUD для событий по счетчику
meters_router.register(
    'models/area_meter',
    AreaMeterViewSet,
    basename='area_meter')

# CRUD для событий по счетчику
meters_router.register(
    'models/house_meter',
    HouseMeterViewSet,
    basename='area_meter')

meters_router.register(
    'models/area_meter/files',
    AreaMeterFilesViewSet,
    basename='area_meter_files')

meters_router.register(
    'models/house_meter/files',
    HouseMeterFilesViewSet,
    basename='house_meter_files')

meters_router.register(
    'forms/area_meters/excel',
    AreaMeterReadingsExcelViewSet,
    basename='area_meter_readings_excel'
)
meters_router.register(
    'forms/house_meters/excel',
    HouseMeterReadingsExcelViewSet,
    basename='house_meter_readings_excel'
)
# Импорт показаний счетчиков
meters_router.register(
    'importer/meter_readings',
    ImportMeterReadingsViewSet,
    basename='meter_readings'
)
# Эта вьюха какой-то костыль для выгрузки csv для двух организаций
meters_router.register(
    'forms/export_csv_file',
    ExportMetersDataToCSV,
    basename='export_csv_file'
)
