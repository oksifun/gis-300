import logging
import settings
import smtplib
import ssl as ssl_module

from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from lib.gridfs import get_file_from_gridfs

from processing.models.billing.mail import Mail

logger = logging.getLogger(__name__)


def sendmail(email_id, host, port, username, password, ssl=False,
             address_from=None, parent_task=None):
    """
    Отправка письма.
    Настраивает соединение с smtp сервером и отсылает единственное письмо.
    Raises:
        ValueError - если не передано ни msg ни msg_str.
        smtplib.SMTPSenderRefused - Sender address refused.
        smtplib.SMTPRecipientsRefused - All recipient addresses refused.
        smtplib.SMTPServerDisconnected - Not connected to any SMTP server.
        smtplib.SMTPResponseException - Smtp server responds with error code.
    """
    email = Mail.objects(id=email_id).first()
    if not email or (not email.body and not email.task):
        raise ValueError("Nothing to send!")

    # Если есть ссылка на задачу, значит это массовая отправка писем
    # и нужно подтягивать данные оттуда
    if email.task:
        subject, body, attachments = _get_data_from_task(email.task)
    else:
        subject = email.subject
        body = email.body
        attachments = [dict(x.to_mongo()) for x in email.attachments or []]

    # Возьмем адреса из документа
    if settings.DEVELOPMENT:
        to_addrs = settings.TEST_MAIL
        subject = '"{}" для {}'.format(subject, ','.join(email.addresses))
    else:
        to_addrs = email.addresses
    # Подготовка письма
    msg = make_message(
        _from=email._from,
        to=email.to,
        subject=subject,
        body=body,
        attachments=attachments
    )
    if not address_from:
        address_from = username

    if any((
            # running on local machine
            settings.DEVELOPMENT,
            # running on stage
            settings.URL == 'http://stage.s-c300.com',
    )):
        with smtplib.SMTP(host=settings.MAIL_SRV_HOST,
                          port=settings.MAIL_SRV_PORT) as smtp:
            smtp.send_message(msg, from_addr=address_from, to_addrs=to_addrs)
        return

    smtp = {
        True: smtplib.SMTP_SSL,
        False: smtplib.SMTP,
    }[ssl](host=host, port=port)

    try:
        if not ssl:
            try:
                smtp.starttls()
            except smtplib.SMTPNotSupportedError:
                pass
            except ssl_module.SSLError:
                smtp.connect(host=host, port=port)
            try:
                smtp.ehlo()
            except smtplib.SMTPNotSupportedError:
                pass
        try:
            smtp.login(user=username, password=password)
        except smtplib.SMTPNotSupportedError:
            pass
        try:
            smtp.send_message(msg, from_addr=address_from, to_addrs=to_addrs)
            email.status = 'sent'
            if email.task:
                _task_increment(email.task)
        except smtplib.SMTPDataError as exc:
            email.status = 'error'
            if email.task:
                _task_set_log(email.task, next((x for x in to_addrs), ''), exc)
            if parent_task:
                raise parent_task.retry(exc=exc, countdown=120)
            raise exc
    finally:
        email.save()
        smtp.quit()


def make_message(_from, to, subject, body, attachments=[], text_attachments=[]):
    msg = MIMEMultipart()

    msg['From'] = _from
    msg['To'] = to
    msg['Subject'] = subject

    for k, v in settings.get('MAIL_HEADERS', {}).items():
        msg[k] = v

    msg.attach(MIMEText(body, 'html'))

    for attachment in attachments:
        attachment_name = attachment.get('name')
        attachment_path = attachment.get('path')
        attachment_bytes = attachment.get('bytes')
        attachment_type = attachment.get('type')
        attachment_subtype = attachment.get('subtype')

        conditions = [attachment_name, attachment_path or attachment_bytes,
                      attachment_type, attachment_subtype]

        if all(conditions):
            if not attachment_bytes:
                with open(attachment_path, 'rb') as f:
                    attachment_bytes = f.read()
            base = MIMEBase(attachment_type, attachment_subtype)
            try:
                base.set_payload(attachment_bytes)
            except IOError as e:
                e_msg = 'Error during attach the file. Message could not' \
                        ' be sent. {0}'.format(e)
                logger.error(e_msg)
            else:
                encoders.encode_base64(base)
                base.add_header(
                    'Content-Disposition', 'attachment',
                    filename=attachment_name)
                msg.attach(base)

    for attachment in text_attachments:
        base = MIMEText(attachment['body'], 'plain', 'utf-8')
        base.add_header('Content-Disposition', 'attachment',
                        filename=attachment['name'])
        msg.attach(base)

    return msg


def _get_data_from_task(task_id):
    """
    Получение тела, темы и вложений письма
    из задачи по массовой рассылке
    """
    from processing.models.tasks.accounting_sync import MailNotifications

    task = MailNotifications.objects(id=task_id).first()
    if not task:
        raise ValueError('Задача не найдена!')

    return (
        task.subject,
        task.body,
        _get_attachments(task.attachments) if task.attachments else []
    )


def _get_attachments(attachments_ids):
    """ Достанем все имеющиеся вложения из задачи """

    files = [get_file_from_gridfs(x) for x in attachments_ids]
    attachments = [
        dict(
            name=file_[0],
            bytes=file_[1],
            type='application',
            subtype=file_[0].split('.')[-1]
        )
        for file_ in files
    ]
    return attachments


def _task_increment(task_id):
    """ Увеличим счетчик отправленных писем """

    from processing.models.tasks.accounting_sync import MailNotifications
    MailNotifications.objects(id=task_id).update(inc__sent=1)


def _task_set_log(task_id, address, exc):
    """ Вставим лог в таску об ошибке """

    from processing.models.tasks.accounting_sync import MailNotifications
    MailNotifications.objects(id=task_id).update(push__log=f'{address}: {exc}')
