from app.celery_admin.workers.config import celery_app
from app.messages.core.email.sending import sendmail as sendmail_new


@celery_app.task(
    bind=True,
    rate_limit="100/m",
    max_retries=5,
    soft_time_limit=60,
)
def sendmail(self, email_id, host, port, username, password,
             ssl=False, address_from=None):
    return sendmail_new(
        email_id,
        host,
        port,
        username,
        password,
        ssl=ssl,
        address_from=address_from,
        parent_task=self,
    )
