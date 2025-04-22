import bson
from bson import ObjectId
from mongoengine import DoesNotExist
from rest_framework.exceptions import ValidationError, NotFound

from app.celery_admin.workers.config import celery_app
from app.house.models.house import House
from app.messages.models.messenger import UserTasks
from lib.gridfs import delete_file_in_gridfs, get_file_from_gridfs
from processing.data_producers.associated.base import get_binded_houses
from processing.data_producers.forms.tenant import get_tenant_coefs_on_date
from processing.models.billing.account import Coef, CoefReason, Tenant
from processing.models.billing.responsibility import Responsibility

TENANTS_COEFS_HEADER = [
    'Помещение', 'Собственник', 'Значение', 'Номер договора-основания',
    'Дата договора', 'Комментарий к договору', 'Адрес'
]


class CharsetType(object):
    UTF = 'utf-8'
    WIN = 'windows-1251'


@celery_app.task(
    soft_time_limit=10*60,
    rate_limit='10/s',
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def update_tenants(
        self, file_id, provider, coef_id, coefs, period, account_id, file_name
):
    try:
        data = _get_parsed_data(file_id)
        houses_ids = get_binded_houses(provider)

        # получаем ид-ы актуальных плательщиков всех домов провайдера
        responsible = Responsibility.get_accounts(provider, date_from=period)

        houses = House.objects(id__in=houses_ids).as_pymongo().only('address')
        all_tenants = Tenant.objects(area__house__id__in=houses_ids)
        tenants = []
        error_messages = []
        # Поиск жителей
        for row in data:
            area, name, value, *reason, address = row
            reason = dict(
                zip(['number', 'datetime', 'comment'], reason)
            )
            if not (reason.get('number') or reason.get('datetime')):
                reason = {}
            elif not reason.get('datetime'):
                reason['datetime'] = None
            try:
                address_query = dict(area__house__id=ObjectId(address))
            except bson.errors.InvalidId:
                address_query = dict(area__house__address=address)
                for h in houses:
                    if address in h['address']:
                        address_query = dict(area__house__id=h['_id'])
                        break
            tenant = all_tenants.filter(
                area__str_number=area,
                short_name=name,
                **address_query
            ).as_pymongo().first()
            if not tenant:
                error_messages.append(f'Не найден: {area}, {name}')
                continue
            if tenant['_id'] in responsible:  # плательщик?
                tenants.append(dict(tenant=tenant, value=value, reason=reason))
        # Обновление квартирных коэффициентов жителей
        for tenant in tenants:
            tenant['coefs'] = get_tenant_coefs_on_date(
                tenant['tenant'], coefs, period
            )
            reason = CoefReason(**tenant['reason'])
            tenant_upd = Tenant.objects(id=tenant['tenant']['_id']).get()
            if tenant['coefs']:
                for c in tenant_upd.coefs:
                    if c.coef == coef_id and \
                            c.period == tenant['coefs'][coef_id]['period']:
                        c.value = float(tenant['value'])
                        c.reason = reason
            else:
                tenant_upd.coefs.append(
                    Coef(
                        id=ObjectId(),
                        coef=coef_id,
                        period=period,
                        value=float(tenant['value']),
                        reason=reason
                    )
                )
            tenant_upd.save()
        if error_messages:
            msg = error_messages[0]
            if len(error_messages) > 1:
                msg += ' и др.'
            UserTasks.send_notices(
                [account_id],
                'coefs',
                message=f'{{"status": "error", "text": "Файл {file_name} '
                        f'импортирован с ошибками: {msg}"}}',
            )
        else:
            UserTasks.send_notices(
                [account_id],
                'coefs',
                message=f'{{"status": "success", "text": "Файл {file_name} '
                        f'успешно импортирован."}}',
            )
    except Exception as error:
        msg = error.args[0] if len(error.args) else str(error)
        UserTasks.send_notices(
            [account_id],
            'coefs',
            message=f'{{"status": "error", "text": "Ошибка импорта: {msg}."}}',
        )
        raise error


def _get_parsed_data(file_id):
    csv_file = get_file_from_gridfs(file_id, raw=True)
    csv_file_content = csv_file.read()
    try:
        csv_data = csv_file_content.decode(CharsetType.UTF).splitlines()
    except UnicodeDecodeError:
        csv_data = csv_file_content.decode(CharsetType.WIN).splitlines()
    except DoesNotExist:
        raise NotFound('Файл не найден.')
    try:
        data = list(map(lambda x: x.strip().split(';'), csv_data[1:]))
        if any([len(d) != len(TENANTS_COEFS_HEADER) for d in data]):
            raise ValidationError('Неправильный формат данных')
        data_parsed = []
        for d in data:
            d[2] = float(d[2].replace(',', '.') or 0)
            data_parsed.append(d)
    except ValueError as err:
        raise ValidationError(f'Неправильный формат значений: {err}')
    finally:
        delete_file_in_gridfs(file_id)
    if not data_parsed:
        raise ValidationError('В файле нет ненулевых данных.')
    return data_parsed
