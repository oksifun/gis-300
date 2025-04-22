import datetime

from dateutil.relativedelta import relativedelta
from mongoengine import ValidationError

from app.accruals.models.accrual_document import AccrualDoc


def get_current_readings_period(provider_id, house_id, return_is_default=False,
                                readings_stat=False):
    default_period = datetime.datetime.now().replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    try:
        doc, meters_month_get, _ = AccrualDoc.get_period_meters(
            house=house_id,
            provider=provider_id,
            readings_stat=readings_stat
        )
    except ValidationError:
        if return_is_default:
            return default_period, True
        else:
            return default_period

    if doc:
        if return_is_default:
            return (
                doc.date_from - relativedelta(months=meters_month_get - 1),
                False
            )
        else:
            return doc.date_from - relativedelta(months=meters_month_get - 1)

    if return_is_default:
        return default_period, True
    else:
        return default_period
