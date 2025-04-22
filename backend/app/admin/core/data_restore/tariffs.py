from bson import ObjectId

from processing.models.billing.regional_settings import RegionalSettings
from processing.models.billing.tariff_plan import TariffPlan
from app.admin.core.data_restore.base import DataRestore


class TariffsDataRestore(DataRestore):
    _PIPELINE = [
        (TariffPlan, '_id'),
    ]


class RegionalSettingsDataRestore(DataRestore):
    _PIPELINE = [
        (RegionalSettings, '_id'),
    ]


def restore_tariff_plan(tp_id, batch_size=None, host='10.1.1.221', logger=None):
    restorer = TariffsDataRestore(
        host,
        batch_size=batch_size,
        logger=logger,
    )
    restorer.restore_data(ObjectId(tp_id))


def restore_regional_settings(region_code, batch_size=None,
                              host='10.1.1.221', logger=None):
    r_settings = RegionalSettings.objects(
        region_code=region_code,
    ).get()
    restorer = RegionalSettingsDataRestore(
        host,
        batch_size=batch_size,
        logger=logger,
    )
    restorer.restore_data(r_settings.id)
    restorer = TariffsDataRestore(
        host,
        batch_size=batch_size,
        logger=logger,
    )
    for tariff_plan in r_settings.tariff_plans:
        restorer.restore_data(tariff_plan.id)
