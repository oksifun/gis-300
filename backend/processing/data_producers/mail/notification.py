from app.messages.core.email.extended_mail import RareMail
from processing.models.billing.account import Account
from processing.models.billing.provider.main import Provider
from processing.models.billing.area_bind import AreaBind


def send_mails_about_activation(provider_id, body):
    """
    Рассылка по неактивированным ЛК через Celery
    :param provider_id: id организации, посылающей уведомления
    :param body: str: Тело письма
    """

    mail_settings = Provider.objects(
        id=provider_id
    ).only('email_settings').as_pymongo()

    try:
        settings = mail_settings[0]['email_settings']['smtp']
    except AttributeError:
        raise AttributeError('No mail settings in the document')

    # Квартиры провайдера
    provider_areas = AreaBind.objects(
        provider=provider_id
    ).distinct('area')

    # Поиск неактивированных ЛК
    accounts_emails = Account.objects(
        area__id__in=provider_areas,
        has_access=True,
        activation_code__exists=False,
        activation_step__exists=False
    ).distinct('email')

    if not accounts_emails:
        return

    mail = RareMail(
        _from=settings['user'],
        to='Tenant',
        subject='Активация ЛК',
        body=body,
        addresses=accounts_emails,
        host=settings['host'],
        port=settings['port'],
        username=settings['user'],
        password=settings['password'],
        ssl=settings['ssl']
    )
    mail.send()
