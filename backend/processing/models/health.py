from mongoengine import Document, DateTimeField, StringField, ListField, IntField

from processing.models.choices import WORKER_STATUS_CHOICE, WorkerStatus
from datetime import datetime

from processing.models.mixins import EveFix
import settings


class Health(Document, EveFix):
    meta = {
        "db_alias": "queue-db"
    }

    heartbeat = DateTimeField(required=True, default=datetime.now)
    hostname = StringField()
    pid = IntField()
    release = StringField(default=settings.RELEASE)
    status = StringField(
        choices=WORKER_STATUS_CHOICE,
        required=True,
        default=WorkerStatus.OK,
    )
    queues = ListField(
        StringField(),
        required=True,
        default=["request_task", "general"],
    )
