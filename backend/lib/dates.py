from datetime import timedelta
from string import Template

from dateutil.relativedelta import relativedelta


def months_between(date1, date2):
    return date2.month - date1.month + (date2.year - date1.year) * 12 + 1


def end_of_month(date):
    """
    Возвращает самый конец месяца переданной даты.
    Например: 2018-03-01 00:00:00 --> 2018-03-31 23:59:59.999999
    :param date: datetime obj
    :return: datetime obj
    """
    return (
            start_of_month(date)
            + relativedelta(months=1)
            - relativedelta(microseconds=1)
    )


def end_day_of_month(date):
    """
    Возвращает последний день месяца переданной даты.
    Например: 2018-03-01 00:00:00 --> 2018-03-31 00:00:00
    :param date: datetime obj
    :return: datetime obj
    """
    return (
            start_of_month(date)
            + relativedelta(months=1)
            - relativedelta(days=1)
    )


def start_of_month(date):
    """
    Возвращает самое начало месяца переданной даты.
    Например: 2018-03-01 04:07:06 --> 2018-01-1 00:00:00
    :param date: datetime obj
    :return: datetime obj
    """
    return date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def start_of_day(date):
    """
    Возвращает самое начало дня переданной даты.
    Например: 2018-03-01 04:07:06 --> 2018-03-01 00:00:00
    :param date: datetime obj
    :return: datetime obj
    """
    return date.replace(hour=0, minute=0, second=0, microsecond=0)


def end_of_day(date):
    return (
        start_of_day(date).replace(
            hour=23, minute=59, second=59, microsecond=999999
        )
    )


def total_seconds(**kwargs):
    return int(timedelta(**kwargs).total_seconds())


class DeltaTemplate(Template):
    delimiter = "%"


def strfdelta(tdelta, fmt):
    """
    Возвращает timedelta (длительность) в нужно формате.
    Например: tdelta(days=1, seconds=32640, "%D дней %H:%M:%S") -> 1 дней 9:4:0
    :param tdelta: datetime.timedelta
    :param fmt: str
    :return: formatted time string
    """
    d = {"D": tdelta.days}
    d["H"], rem = divmod(tdelta.seconds, 3600)
    d["M"], d["S"] = divmod(rem, 60)
    t = DeltaTemplate(fmt)
    return t.substitute(**d)
