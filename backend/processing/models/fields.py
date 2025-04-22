import datetime
from decimal import Decimal

from mongoengine import DateTimeField, DecimalField


class DateField(DateTimeField):
    def to_mongo(self, value):
        result = super().to_mongo(value)
        if isinstance(result, datetime.datetime):
            return result.replace(hour=0, minute=0, second=0, microsecond=0)
        return result


class MonthField(DateField):
    def to_mongo(self, value):
        if isinstance(value, str) and len(value) == 7:
            value += '-01'
        result = super().to_mongo(value)
        if isinstance(result, datetime.datetime):
            return result.replace(day=1)
        return result


class MoneyField(DecimalField):
    def to_mongo(self, value):
        result = super().to_mongo(value)
        return round(result * 100)

    def from_mongo(self, value):
        if value:
            return Decimal('{:.2f}'.format(value / 100))
        else:
            return value
