from app.celery_admin.workers.config import celery_app
from app.messages.core.email.sending import sendmail


@celery_app.task(
    bind=True,
    rate_limit="100/m",
    max_retries=5,
    soft_time_limit=60,
)
def regular_mail(self, email_id, host, port, username, password, ssl=False,
                 address_from=None):
    sendmail(
        parent_task=self,
        email_id=email_id,
        host=host,
        port=port,
        username=username,
        password=password,
        ssl=ssl,
        address_from=address_from,
    )


@celery_app.task(
    bind=True,
    rate_limit="100/m",
    max_retries=5,
    soft_time_limit=60,
)
def access_mail(self, email_id, host, port, username, password, ssl=False,
                address_from=None):
    sendmail(
        parent_task=self,
        email_id=email_id,
        host=host,
        port=port,
        username=username,
        password=password,
        ssl=ssl,
        address_from=address_from,
    )


@celery_app.task(
    bind=True,
    rate_limit="100/m",
    max_retries=5,
    soft_time_limit=60,
)
def ticket_mail(self, email_id, host, port, username, password, ssl=False,
                address_from=None):
    sendmail(
        parent_task=self,
        email_id=email_id,
        host=host,
        port=port,
        username=username,
        password=password,
        ssl=ssl,
        address_from=address_from,
    )


@celery_app.task(
    bind=True,
    rate_limit="100/m",
    max_retries=5,
    soft_time_limit=60,
)
def rare_mail(self, email_id, host, port, username, password, ssl=False,
              address_from=None):
    sendmail(
        parent_task=self,
        email_id=email_id,
        host=host,
        port=port,
        username=username,
        password=password,
        ssl=ssl,
        address_from=address_from,
    )


