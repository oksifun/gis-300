from mongoengine import DictField


class CleanDictField(DictField):

    @classmethod
    def clear(cls, source: dict):

        from datetime import date
        from decimal import Decimal

        for key in [*source]:
            value_s = source[key]  # может быть список!
            for value in value_s if isinstance(value_s, list) else [value_s]:
                if isinstance(value, dict):
                    cls.clear(value)  # рекурсия с аргументом по ссылке
                elif isinstance(value, date):  # bson: Cannot encode: date
                    from datetime import datetime
                    source[key] = datetime(value.year, value.month, value.day)
                elif isinstance(value, Decimal):  # bson: Cannot encode: Decimal
                    from bson.decimal128 import Decimal128  # float -> Double
                    source[key] = Decimal128(value)

    def validate(self, value):

        self.clear(value)  # "подчищаем" данные
        super().validate(value)  # DictField/ComplexBaseField/BaseField.validate

    def __init__(self, *args, **kwargs):

        self.field = None  # переданное значение игнорируется
        self._auto_dereference = False  # был хак

        kwargs.setdefault('default', lambda: None)  # было {}
        super(DictField, self).__init__(*args, **kwargs)  # BaseField.__init__
