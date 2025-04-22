from app.messages.core.email.base_mail import BaseSendMailRouter
from app.messages.tasks.mail_groups import (
    access_mail,
    rare_mail,
    regular_mail,
    ticket_mail,
)


class RegularMail(BaseSendMailRouter):

    SEND_FUNC = regular_mail


class AccessMail(BaseSendMailRouter):

    SEND_FUNC = access_mail


class TicketMail(BaseSendMailRouter):

    SEND_FUNC = ticket_mail


class RareMail(BaseSendMailRouter):

    SEND_FUNC = rare_mail
