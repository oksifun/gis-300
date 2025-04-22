from base64 import b64encode
from datetime import datetime
from urllib.parse import urljoin

from mongoengine import DoesNotExist, ValidationError

from app.acquiring.models.actions import TenantPayAction
from app.acquiring.models.actions_embeddeds import StoredPayDataEmbedded
from app.acquiring.models.choices import TenantPayActionType
from app.cabinet.core.accruals import get_tenant_accruals_data
from processing.models.billing.provider.main import Provider
from processing.models.choices import ACCRUAL_SECTOR_TYPE_CHOICES
from processing.models.exceptions import CustomValidationError
from processing.models.logging.acquiring_error_log import AcquiringErrorLog
from settings import DEFAULT_PAY_RETURN_URL

SECTOR_NAMES = dict(ACCRUAL_SECTOR_TYPE_CHOICES)


def get_pay_by_action(
        action: TenantPayAction,
        debt_as_default=True,
        no_debt=False,
        public_qr_url=None,
        return_url=None,
):
    pay_kwargs = dict(action=action, return_url=return_url)
    if action.for_commercial:
        data = _get_data_for_commercial(**pay_kwargs)
    else:
        accrual_kwargs = dict(
            debt_as_default=debt_as_default,
            no_debt=no_debt,
            public_qr_url=public_qr_url
        )
        pay_kwargs.update(accrual_kwargs)
        data = _get_data_for_accrual(**pay_kwargs)
    return data


def _get_data_for_accrual(
        action: TenantPayAction,
        return_url,
        public_qr_url=None,
        debt_as_default=True,
        no_debt=False,
):
    accruals = action.get_accruals()
    if not accruals:
        raise DoesNotExist('Не найдено начисление')
    try:
        pay_data = action.get_accrual_details(
            accrual=accruals[0],
            return_url=return_url,
            debt_as_default=debt_as_default,
            no_debt=no_debt,
        )
        if public_qr_url:
            pay_data['public_qr_url'] = public_qr_url
        if not action.accrual_id:
            # Пока биллинг полностью не переведен на action, оно будет так
            action.storage.reason.id = pay_data['accrual_id']
        action.save()
        data = _get_result_data(action=action, **pay_data)
    except ValidationError as error:
        AcquiringErrorLog(
            provider=action.provider.id,
            error_message=error.message,
            tenant=action.tenant.id,
            accrual=action.accrual_id,
        ).save()
        raise CustomValidationError(
            'Не удалось получить реквизиты для платежа. '
            'Обратитесь в Управляющую компанию'
        )
    return data


def _get_data_for_commercial(action: TenantPayAction, return_url):
    try:
        pay_data = action.get_commercial_details(return_url)
        action.save()
        data = _get_result_data(action=action, **pay_data)
    except ValidationError as error:
        AcquiringErrorLog(
            provider=action.provider.id,
            error_message=error.message,
            tenant=action.tenant.id,
            accrual=action.accrual_id,
        ).save()
        raise CustomValidationError(
            'Не удалось получить реквизиты для платежа. '
            'Обратитесь в Управляющую компанию'
        )
    return data


def get_public_pay_details(
        tenant, month=None, return_url=None, quiz_url=None, recurrent_pay=None,
        autopay=None, value=None, no_debt=False,
):
    """
    TODO: Этот метод какой-то странный, фронт делает запрос сам со страницы
     к эквайеру, надо договориться, чтобы делали, как везде.
    """
    act_type = TenantPayActionType.ACCRUAL
    action_params = dict(tenant=tenant, source=act_type)
    initial_action = TenantPayAction(**action_params)
    accruals = initial_action.get_accruals(month=month)
    result = {}
    for accrual in accruals:
        accrual_action = TenantPayAction(
            storage=StoredPayDataEmbedded(
                value=value,
                recurrent_pay=recurrent_pay,
                autopay=autopay,
                reason=dict(
                    number=tenant.number,
                    kind=accrual['_id']['sector'],
                ),
            ),
            **action_params,
        )
        # Получаем корректный остаток долга, как в личном кабинете и заменяем
        if not value:
            debt_val = get_tenant_accruals_data(
                month_from=accrual.get('month'),
                month_till=accrual.get('month'),
                sectors=[accrual.get('_id').get('sector')],
                tenant_id=tenant.pk,
            )
            for debt in debt_val.get('accruals'):
                if debt.get('month') == accrual.get('month'):
                    accrual_action.storage.value = debt.get('debt')

        provider_id = accrual['_id']['owner']
        try:
            pay_data = accrual_action.get_accrual_details(
                accrual=accrual,
                return_url=return_url,
                quiz_url=quiz_url,
                debt_as_default=False,
                no_debt=no_debt,
            )
            accrual_action.storage.reason.id = pay_data['accrual_id']
            accrual_action.save()
            # отдать то же, что get_processing_url
            data = _get_result_data(action=accrual_action, **pay_data)
            result[pay_data['sector']] = data
        except ValidationError as error:
            AcquiringErrorLog(
                provider=provider_id,
                error_message=error.message,
                tenant=tenant.id,
                accrual=accrual.get('accrual_id'),
            ).save()
            raise CustomValidationError(
                'Не удалось получить реквизиты для платежа. '
                'Обратитесь в Управляющую компанию'
            )
    return result


def get_bank_attrs(action: TenantPayAction, month=None):
    # TODO: Перенести attr3 полностью на action.id
    attr_3 = '{}{}{}::{}'.format(
        action.provider.id,
        action.accrual_id or action.id,
        action.storage.bank_account,
        1,
    )
    attr_3 = b64encode(attr_3.encode()).decode()

    month_attr = (month or datetime.now()).strftime('%m/%y')

    return [None, month_attr, action.tenant.full_address, attr_3, 'lk_c300']


def _get_bank(bank_bic_id):
    bank = list(
        Provider.objects.aggregate(
            {
                '$match': {
                    '_id': bank_bic_id,
                },
            },
            {
                '$project': {
                    'NameP': '$bic_body.NameP',
                    'BIC': '$bic_body.BIC',
                    'Account': '$bic_body.Account',
                },
            },
        )
    )
    return bank


def _get_result_data(
        action: TenantPayAction, service_code, bank_account, amount,
        processing_url, return_url, month=None, quiz_url=None, service_type=None,
        debt_as_default=True, debt_amount=None, public_qr_url=None, **kwargs
):

    attrs = get_bank_attrs(action=action, month=month)

    if debt_amount is None:
        debt_amount = amount
    if debt_amount <= 0:
        debt_amount = 0
        debt_as_default = False
    if action.storage.recurrent_pay and action.storage.autopay:
        return_url = urljoin(return_url, '/#/main/from/bank_autopay')
    elif public_qr_url:
        return_url = urljoin(return_url, public_qr_url)
    else:
        return_url = urljoin(return_url, DEFAULT_PAY_RETURN_URL)
    data = {
        'params': {
            'service': service_code,
            'account': action.storage.reason.number,
            'amount': '{:.2f}'.format(amount),
            'debt_amount': '{:.2f}'.format(debt_amount),
            'debt_as_default': _bool_to_str(debt_as_default),
            'url_return': quiz_url if quiz_url else return_url,
            'email': action.tenant.email or '',
            'area_name': action.tenant.area.str_number,
        },
        'provider_name': action.provider.str_name,
        'processing_url': processing_url,
        'sector': action.sector_code,
        'inn': action.provider.inn,
        'bank_number': bank_account.number,
        'bic': '',
        'correspondent': '',
        'bank_name': '',
        'service_type': service_type,
    }
    bank = _get_bank(bank_account.bic.id)
    if bank:
        data['bic'] = bank[0]['BIC']
        data['correspondent'] = bank[0]['Account'][0]
        data['bank_name'] = bank[0]['NameP'][0]

    for ix, attr in enumerate(attrs):
        data['params']['attr_{:d}'.format(ix)] = attr
    return data


def _bool_to_str(val):
    if val:
        return 'true'
    return 'false'
