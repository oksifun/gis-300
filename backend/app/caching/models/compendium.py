from mongoengine import Document, ObjectIdField

from app.c300.models.tasks import BaseTaskMixin


class CompendiumBindsTask(BaseTaskMixin, Document):
    meta = {
        'db_alias': 'queue-db',
        'collection': 'compendium',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'provider',
        ]
    }

    provider = ObjectIdField(
        required=True,
        verbose_name='Id провайдера, для которого нужно создать новую запись в '
                     'коллекции CompendiumProviderBinds',
    )

    @classmethod
    def create_simple_task(cls, provider_id):
        task = cls(
            provider=provider_id,
        )
        task.save()
        return task

