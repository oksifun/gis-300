from mongoengine import StringField, ObjectIdField, DictField
from mongoengine.document import Document

from app.c300.models.tasks import BaseTaskMixin


class DenormalizationTask(BaseTaskMixin, Document):
    meta = {
        'db_alias': 'queue-db',
        'collection': 'denormalization',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            ('obj_id', '-created'),
        ],
    }
    model_name = StringField(
        required=True,
        verbose_name='Имя модели, объект которой должен быть денормализован',
    )
    field_name = StringField(
        required=True,
        verbose_name='Имя поля, которое должно быть денормализовано',
    )
    obj_id = ObjectIdField(
        required=True,
        verbose_name='ID объекта, поля которого должны быть денормализованы',
    )
    func_name = StringField(
        verbose_name='Имя функции денормализации, если она нестандартная',
    )
    kwargs = DictField(
        verbose_name='Дополнительные параметры для функции',
    )

    @classmethod
    def create_simple_task(cls, model_name, field_name, obj_id):
        task = cls(
            model_name=model_name,
            field_name=field_name,
            obj_id=obj_id,
            func_name=None,
        )
        task.save()
        return task
