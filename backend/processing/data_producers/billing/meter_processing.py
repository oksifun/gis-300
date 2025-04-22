from mongoengine import Q, ValidationError

from app.meters.models.meter import AreaMeter, HouseMeter


class MeterNotFoundError(ValidationError):
    pass


def close_meter(meter, values, date,
        provider_id, account_id, binds, change_meter_date=None):
    """Метод для закрытия счетчика"""
    amb = AreaMeter.get_binds_query(binds)
    hmb = HouseMeter.get_binds_query(binds)
    meter = (
            AreaMeter.objects(Q(id=meter) & amb).first()
            or HouseMeter.objects(Q(id=meter) & hmb).first()
    )
    if not meter:
        raise MeterNotFoundError("Счетчик не найден!")
    if values:
        meter.add_closing_values(
            provider_id=provider_id,
            account_id=account_id,
            default_period=date,
            values=values,
            change_meter_date=change_meter_date,
        )
    meter.closed_by = 'worker'
    meter.working_finish_date = date
    meter.save()
