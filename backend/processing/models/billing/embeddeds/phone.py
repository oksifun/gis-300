from bson import ObjectId
from mongoengine import EmbeddedDocument, ObjectIdField, StringField, \
    BooleanField

from processing.models.choices import PHONE_TYPE_CHOICES, PhoneType


def get_str_phone_number(code, number, additional):
    str_number = ''
    if code:
        prefix = "+7 ({}) ".format(code)
    else:
        prefix = ''
    if number:
        str_number = "{}{}".format(prefix, number)
    if additional:
        if str_number != '':
            return "{} доб. {}".format(str_number, additional)
        return 'внутренний {}'.format(additional)
    return str_number


def str_to_phone(phone_number):
    if phone_number.startswith('812'):
        return dict(
            type='home',
            code='812',
            number=phone_number[3:]
        )
    elif (
            phone_number.startswith('+7')
            or phone_number.startswith('7')
    ):
        number = phone_number.lstrip('+')
        return dict(
            type='cell',
            code=number[1:4],
            number=number[4:],
        )
    elif len(phone_number) == 10:
        code = ''.join(phone_number[:3])
        number = ''.join(phone_number[-7:])
        return {'code': code, 'number': number}
    elif len(phone_number) == 11:
        code = ''.join(phone_number[1:4])
        number = ''.join(phone_number[-7:])
        return {'code': code, 'number': number}
    elif len(phone_number) == 8:
        number = ''.join(phone_number[0: 8])
        return {'code': None, 'number': number[-7:]}
    elif len(phone_number) == 7:
        return {'code': None, 'number': phone_number}
    return None


class DenormalizedPhone(EmbeddedDocument):
    id = ObjectIdField(db_field="_id", default=ObjectId, null=True)
    phone_type = StringField(
        required=False,
        choices=PHONE_TYPE_CHOICES,
        db_field='type',
        default=PhoneType.CELL,
    )
    code = StringField(null=True)
    number = StringField(regex='\d{1,10}', null=True)
    add = StringField(regex='\d*', null=True)
    str_number = StringField(regex='\d*', null=True)
    not_actual = BooleanField(
        verbose_name='помечен жителем как неактуальный',
        default=False,
        blank=True,
    )
    added_by_tenant = BooleanField(
        verbose_name='добавлен жителем',
        default=False,
        blank=True,
    )
    telegram = BooleanField(
        verbose_name='Наличие Telegram',
        default=False,
        blank=True,
    )
    whatsapp = BooleanField(
        verbose_name='Наличие WhatsApp',
        default=False,
        blank=True,
    )
    viber = BooleanField(
        verbose_name='Наличие Viber',
        default=False,
        blank=True,
    )

    def __str__(self):
        return get_str_phone_number(self.code, self.number, self.add)

    @classmethod
    def denormalize(cls, phone_number: str):
        """Денормализация телефонного номера."""
        return cls(
            code=phone_number[:3],
            number=phone_number[3:],
            str_number=phone_number,
        )
