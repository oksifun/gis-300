import datetime

from dateutil.relativedelta import relativedelta
from mongoengine import Document, StringField, ObjectIdField, IntField, \
    DateTimeField


class LockedPermissionError(PermissionError):
    pass


class CacheLock(Document):
    """
    Блокированные данные кэша
    """

    meta = {
        'db_alias': 'cache-db',
        'collection': 'locks',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            ('model', 'obj'),
            'till',
        ],
    }
    model = StringField(verbose_name='Имя модели')
    obj = ObjectIdField(verbose_name='ID блокированного объекта')
    secs = IntField(verbose_name='На сколько секунд')
    till = DateTimeField(verbose_name='Когда истекает')
    locker = StringField(verbose_name='Что блокировало')

    @classmethod
    def do_convert(cls, model):
        return model.__name__ if not isinstance(model, str) else model

    @classmethod
    def lock_doc(cls, model, obj_id, secs=60, locker='default'):
        cls(
            model=cls.do_convert(model),
            obj=obj_id,
            secs=secs,
            till=datetime.datetime.now() + relativedelta(seconds=secs),
            locker=locker,
        ).save()

    @classmethod
    def unlock_doc(cls, model, obj_id, locker='default'):
        cls.objects(
            model=cls.do_convert(model),
            obj=obj_id,
            locker=locker,
        ).delete()

    @classmethod
    def doc_is_locked(cls, model, obj_id):
        cls.objects(till__lt=datetime.datetime.now()).delete()
        locked = cls.objects(
            model=cls.do_convert(model),
            obj=obj_id,
        ).first()
        return locked is not None
