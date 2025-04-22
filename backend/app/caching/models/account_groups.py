from mongoengine.base.fields import ObjectIdField
from mongoengine.document import Document
from mongoengine.fields import ListField, StringField


# TODO Сделать общий абстрактный класс групп


class SimilarWorkerGroup(Document):
    get_group = 'get_similar_workers'

    meta = {
        'db_alias': 'cache-db',
        'collection': 'similar_workers_group_cache',
    }

    workers = ListField(ObjectIdField())
    group_code = StringField()  # Код группы, например "ch1,ch2,ch3"

    @staticmethod
    def get_group_code(worker_position_codes):
        return ','.join(sorted(worker_position_codes))


class WorkersFIOGroup(Document):
    get_group = 'get_worker_fio_group'

    meta = {
        'db_alias': 'cache-db',
        'collection': 'workers_fio_group_cache',
    }

    workers = ListField(ObjectIdField())
    group_code = StringField()  # Код группы, например "ch1,ch2,ch3"

    @staticmethod
    def get_group_code(worker_position_codes):
        return ','.join(sorted(worker_position_codes))
