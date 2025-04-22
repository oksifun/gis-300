from datetime import datetime

from bson import ObjectId

from app.gis.services.device_metering import DeviceMetering
from app.gis.workers.config import gis_celery_app


@gis_celery_app.task(name='gis.import_readings')
def import_readings(provider_id: ObjectId, house_id: ObjectId,
        period: datetime = None, **options):
    """
    Загрузка из ГИС ЖКХ показаний ПУ (помещений) дома

    У каждого дома индивидуальный период внесения текущих показаний
    Интервал рассчитывается на основе сроков передачи показаний дома
    """
    DeviceMetering.exportMeteringDeviceHistory(
        provider_id, house_id, **options
    ).house_meterings(period)  # всех видов ПУ дома за период


@gis_celery_app.task(name='gis.export_readings')
def export_readings(provider_id: ObjectId, house_id: ObjectId,
        period: datetime, is_collective: bool = False, **options):
    """
    Выгрузка в ГИС ЖКХ показаний ПУ (помещений) дома
    """
    _export = DeviceMetering.importMeteringDeviceValues(
        provider_id, house_id, **options
    )
    if is_collective:
        _export.house_meterings(period)
    else:
        _export.area_meterings(period)


if __name__ == '__main__':

    from mongoengine_connections import register_mongoengine_connections
    register_mongoengine_connections()

    p = ObjectId('540047c0f3b7d41966c4d5eb')

    h = ObjectId("5f312bd4c14d7a00137dcd8b")  # TODO в случае нескольких домов

    from app.gis.utils.houses import get_provider_house
    h = get_provider_house(p, h, abort_failed=True)

    from app.gis.utils.common import get_period
    m = get_period(months=0)  # TODO период показаний

    # import_readings(p, h, m, update_existing=True); exit()
    export_readings(p, h, m, is_collective=False, request_only=False)  # WARN
