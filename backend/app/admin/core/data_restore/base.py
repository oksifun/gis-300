from pymongo import MongoClient

from mongoengine_connections import register_mongoengine_connections


_RESTRICTED_HOSTS = (
    '10.1.1.16',
    '10.1.1.17',
    '10.1.1.12',
    '10.1.1.30',
    '10.1.1.6',
)


class DataRestore:
    _PIPELINE = []

    def __init__(self, target_host, target_port=27017, db_name='c300',
                 batch_size=100, logger=None):
        if target_host in _RESTRICTED_HOSTS:
            raise ValueError('{target_host} is restricted')
        register_mongoengine_connections()
        self.client = MongoClient(target_host, target_port)
        self.db = getattr(self.client, db_name)
        self._batch_size = batch_size or 100
        self._logger = logger or print

    def get_models_list(self):
        return [el[0] for el in self._PIPELINE]

    def restore_data(self, source_id):
        for el in self._PIPELINE:
            self._restore_data_element(el, source_id)

    def restore_by_pipeline_ix(self, ix, source_id):
        el = self._PIPELINE[ix]
        self._restore_data_element(el, source_id)

    def _restore_data_element(self, el, source_id):
        queryset = self._get_queryset_for_restore(el[0], el[1], source_id)
        target_collection = getattr(self.db, el[0]._collection.name)
        target_collection.remove(
            {
                el[1]: source_id,
            },
        )
        self._insert_restore_data(
            queryset,
            target_collection,
        )

    def _insert_restore_data(self, from_queryset, to_db):
        self._logger(f'{from_queryset._document._class_name} insert')
        skip = 0
        data_list = True
        while data_list:
            data_list = list(from_queryset[skip: skip + self._batch_size])
            if data_list:
                to_db.insert(data_list)
            skip += self._batch_size
            if skip % 10000 == 0:
                self._logger(f'обработано {skip}')

    def _get_queryset_for_restore(self, model, field_name, source_id):
        queryset = model.objects(
            __raw__={
                field_name: source_id,
            },
        ).as_pymongo()
        self._logger(f'найдено {model.__name__, queryset.count()}')
        return queryset
