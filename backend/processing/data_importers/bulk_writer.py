from bson import ObjectId

from pymongo.operations import InsertOne, UpdateOne
from pymongo.collection import Collection
from pymongo.results import BulkWriteResult
from pymongo.errors import BulkWriteError

from app.gis.utils.common import split_list

from processing.data_importers.logger import Logger, get_debug_logger


DEFAULT_BULK_SIZE: int = 2000  # количество записей в одном блоке


class BulkWriter(object):

    def __init__(self, model, logger: Logger = None):

        self._pk = '_id'

        self._model = model  # : Type
        self._logger: Logger = get_debug_logger() if logger is None else logger

        self._insert_requests: list = []
        self._update_requests: list = []

        self._collection: Collection = self._model._get_collection()  # PyMongo

    @property
    def model_name(self) -> str:

        return self._model.__name__

    @property
    def requests(self) -> list:

        return self._insert_requests + self._update_requests

    def with_pk(self, field_name: str):
        """Изменить ключевое поле для поиска в update_pk"""
        self._pk = field_name

        return self  # для построения цепочек

    def insert(self, document: dict):

        insert_request = InsertOne(document=document)

        self._insert_requests.append(insert_request)

    def update(self, filter_query: dict, upsert: bool = False,
            unset: list = None, **field_values):
        """update({
            'provider': provider_id, 'hidden': True, 'is_total': True,
            'is_deleted': {'$ne': True},
        }, upsert=True,
            title='Все дома', houses=house_ids
        )"""
        assert '$unset' not in field_values, \
            "Удаляемые поля документа передаются списком в unset"
        # WARN update only works with $ operators
        update_query: dict = {'$set': field_values}

        if isinstance(unset, (list, tuple)):
            update_query['$unset'] = {field: True for field in unset}

        self._update_requests.append(
            UpdateOne(filter=filter_query, update=update_query, upsert=upsert)
        )

    def update_pk(self, object_id: ObjectId,
            unset: list = None, **field_values):

        self.update({self._pk: object_id}, unset=unset, **field_values)

    def update_elem(self, object_id: ObjectId, elem_id: ObjectId,
            array_name: str, **field_values):

        # WARN преобразуем названия полей к требуемому виду
        field_values: dict = {f"{array_name}.$.{field_name}"
            if array_name not in field_name else field_name: value
                for field_name, value in field_values.items()}

        self.update({'_id': object_id,
            array_name: {
                '$elemMatch': {'_id': elem_id}
            }
        }, **field_values)

    def append(self, object_id: ObjectId, array_name: str, *values):

        assert values, "Необходимы добавляемые в массив значения"
        field_value = {'$each': values} if len(values) > 1 else values[0]

        update_request = UpdateOne(filter={
            '_id': object_id
        }, update={'$push': {  # добавляем в конец
            array_name: field_value
        }})  # upsert=False
        self._update_requests.append(update_request)

    def write(self, bulk_size: int = DEFAULT_BULK_SIZE):
        """Выполнить запросы на запись в БД"""
        requests: list = self.requests
        total: int = len(requests)

        chunks: list = split_list(requests, bulk_size)  # часть или все
        for i, requests in enumerate(chunks):
            if not requests:
                self._logger.warning("Отсутствуют подлежащие"
                    f" записи данные {self.model_name}")
                continue
            self._logger.debug(f"Выполняется запись {i + 1} части"
                f" из {len(chunks)} с {len(requests)} запросами"
                f" из {total} запланированных... Пожалуйста, ждите!")
            try:
                write_result: BulkWriteResult = self._collection.bulk_write(
                    requests,  # requests must be a list
                    bypass_document_validation=True,  # без валидации
                    ordered=False,  # False-параллельно, True-последовательно
                )
            except BulkWriteError as bulk_write_error:
                """{'writeErrors': [
                    {
                        'index': 0, 'code': 11000,
                        'errmsg': "code message collection index dup key",
                        'op': {'field': 'value',...}
                    },...
                ],
                    'writeConcernErrors': [], 'upserted': [], 'nMatched': 0,
                    'nInserted': 0, 'nUpserted': 0, 'nModified': 0, 'nRemoved': 0,
                }"""
                self._logger.error("В процессе записи получены ошибки:\n"
                    + '\n'.join(error['errmsg'] for error in
                        bulk_write_error.details['writeErrors']))
            else:
                self._logger.info(f"В результате выполнения {len(requests)}"
                    f" запросов на запись в {self.model_name}"
                    f" создано {write_result.inserted_count}"
                    f" и обновлено {write_result.matched_count}")
