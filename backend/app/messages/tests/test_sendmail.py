from os import path
from unittest import TestCase

from app.messages.core.email.extended_mail import (
    AccessMail,
    RareMail,
    RegularMail,
    TicketMail,
)
from mongoengine_connections import (
    register_testing_mongoengine_connections,
    destroy_testing_mongoengine_connections,
)
from processing.models.billing.mail import Mail


class SendmailTestCase(TestCase):

    email_params = dict(
        addresses='developers@eis24.me',
        subject='Внимание, анекдот!',
        instantly=True,
        remove_after_send=True,
    )
    attachment_path = path.join('app', 'messages', 'tests', 'attachment.jpg')
    body = 'Написал мужик тесты {0}, а они ему как раз.'

    @classmethod
    def setUpClass(cls) -> None:
        register_testing_mongoengine_connections()

    @classmethod
    def tearDownClass(cls) -> None:
        Mail.objects(subject=cls.email_params['subject']).delete()
        destroy_testing_mongoengine_connections()

    def test_base_mail(self):
        # TODO: Написать тест для базового класса отправки
        pass

    def test_access_group(self):
        self.email_params['body'] = self.body.format('доступа')
        mail = AccessMail(**self.email_params)
        mail.send()

    def test_ticket_group(self):
        self.email_params['body'] = self.body.format('обращений')
        mail = TicketMail(**self.email_params)
        mail.send()

    def test_regular_group(self):
        self.email_params['body'] = self.body.format('обычных писем')
        mail = RegularMail(**self.email_params)
        mail.send()

    def test_rare_group(self):
        self.email_params['body'] = self.body.format('редких писем')
        mail = RareMail(**self.email_params)
        mail.send()

    def test_regular_with_attachment(self):
        self.email_params['body'] = self.body.format('писем с вложением')
        with open(self.attachment_path, 'rb+') as file:
            attachment = dict(
                name='test attachment',
                bytes=file.read(),
                type='image',
                subtype='jpg',
            )
            mail = RegularMail(attachments=[attachment], **self.email_params)
            mail.send()
