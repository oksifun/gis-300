import settings

from processing.models.billing.mail import (
    AttachmentEmbedded,
    Mail,
)
from processing.models.billing.provider.main import Provider


class BaseSendMailRouter:
    """
    Класс необходим для того, чтобы можно было выбрать очередь отправки,
    переопределив способ отправки у дочернего класса.
    При наследовании от данного класса достаточно переопределить SEND_FUNC,
    чтобы выбрать celery-функцию для отправки письма, сам класс юзать нельзя.
    """

    # Метод отправки
    SEND_FUNC = None

    def __init__(self, addresses, subject, body, **kwargs):
        """
        :param addresses: адреса электронной почты
        :type addresses: str or list
        :param subject: заголовок письма
        :type subject: str
        :param body: тело письма
        :type body: str

        :param kwargs: Параметры, переопределяющие стандартные настройки класса.
        :keyword _from: адрес отправителя, по умолчанию: "no_reply@eis24.me"
        :keyword to: ...
        :keyword attachments: файлы, прикрепленные к письму.
                              Каждый файл в списке должен иметь структуру:
                                  dict(
                                      name='name',
                                      bytes=filebytes,
                                      type='type',
                                      subtype='subtype',
                                  )
        :keyword host: адрес хоста отправителя
        :keyword port: порт отправителя
        :keyword username: логин от почты отправителя
        :keyword password: пароль от почты отправителя
        :keyword ssl: использовать ли ssl
        :keyword provider_id: _id организации-отправителя
        :keyword delivery: параметр рассылки новости

        :return: 'success', если все пошло по плану
        """

        if self.SEND_FUNC is None:
            raise NotImplementedError('Send method is not defined')

        _used_provider_smtp = False
        self.provider_id = kwargs.get('provider_id')
        if self.provider_id:
            # Если передан ID организации, значит нужно воспользоваться их
            # почтовыми настройками, если они есть
            _used_provider_smtp = self._use_provider_smtp()
        if not _used_provider_smtp:
            # Если не использованы почтовые настройки организации, то используем
            # указанные или дефолтные
            self.host = kwargs.get('host') or settings.MAIL_SRV_HOST
            self.port = kwargs.get('port') or settings.MAIL_SRV_PORT
            self.username = kwargs.get('username') or settings.MAIL_SRV_USER
            self.password = kwargs.get('password') or settings.MAIL_SRV_PASS
            self.ssl = kwargs.get('ssl') or False
            self._from = kwargs.get('_from') or 'no_reply@eis24.me'

        self.remove_after_send = kwargs.get('remove_after_send')
        self.to = kwargs.get('to') or ''

        # Заполняем файлы для их дальнейшего извлечения
        self._generate_attachments(kwargs.get('attachments'))

        self.delivery = kwargs.get('delivery')
        self.instantly = kwargs.get('instantly')
        self.mail_task = kwargs.get('mail_task')

        self.addresses = addresses
        self.subject = subject
        self.body = body

        for kwarg in kwargs:
            setattr(self, kwarg, kwargs[kwarg])

        if isinstance(self.addresses, str):
            # Делаем список из аргумента адресатов
            self.addresses = [self.addresses]

        # Сохраняем письмо в базу
        self.email_id = self._save_email_in_db()

        # Конфигурируем итоговые настройки отправки
        self.email_params = dict(
            email_id=self.email_id,
            host=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            ssl=self.ssl,
            address_from=self._from,
        )

    def _generate_attachments(self, attachments):
        self.attachments = None
        if attachments:
            attachments_embedded = [
                AttachmentEmbedded(**attachment) for attachment in attachments
            ]
            self.attachments = attachments_embedded

    def _use_provider_smtp(self):
        provider_settings = Provider.objects(
            id=self.provider_id
        ).only(
            'email_settings',
        ).as_pymongo().get()
        email_settings = provider_settings.get('email_settings') or {}
        smtp_settings = email_settings.get('smtp')
        if smtp_settings and smtp_settings['host'] and smtp_settings['port']:
            self.host = smtp_settings['host']
            self.port = smtp_settings['port']
            self.username = smtp_settings['user']
            self.password = smtp_settings['password']
            self.ssl = smtp_settings['ssl']
            self._from = smtp_settings.get('address_from')
            return True
        return False

    def _save_email_in_db(self):
        email = Mail(
            _from=self._from or self.username,
            to=self.to,
            subject=self.subject,
            body=self.body,
            addresses=self.addresses,
            attachments=self.attachments,
            remove_after_send=self.remove_after_send,
        )
        if self.mail_task:
            email.task = self.mail_task
        if self.delivery:
            email.delivery = self.delivery
        email.save()
        return email.id

    def send(self):
        if self.instantly:
            self.SEND_FUNC(**self.email_params)
        else:
            self.SEND_FUNC.delay(**self.email_params)
        return 'success'
