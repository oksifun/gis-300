from uuid import UUID
from bson import ObjectId

from typing import Type, Optional, Callable, Iterable  # ~ Collections.abc

from dateutil.relativedelta import relativedelta
from datetime import datetime
from time import sleep

from logging import Logger, getLogger, \
    DEBUG, INFO, WARNING, ERROR

from django.utils.functional import cached_property

from app.house.models.house import House
from processing.models.billing.provider.main import ProviderRelations, Provider
from settings import GIS

from app.gis.core.web_service import WebService
from app.gis.core.exceptions import (
    NoRequestWarning, NoResultWarning,
    GisError, GisWarning, PublicError, InternalError,
    NoGUIDError, NoDataError, UnstatedError, ConsistencyError,
    PendingSignal, RestartSignal, CancelSignal
)

from app.gis.utils.common import reset_logging, sb, json, pct_of, \
    deep_update, as_guid, get_guid, get_time, mongo_time, fmt_period
from app.gis.utils.houses import get_binded_houses, get_house_providers

from app.gis.models.choices import (
    GisObjectType, GisOperationType, GisRecordStatusType, GisManagerContext,
    GIS_RECORD_STATUSES, SUCCESSFUL_STATUSES,
    GIS_MANAGER_CONTEXTS, NO_RECORD_CONTEXTS
)
from app.gis.models.gis_record import GisRecord, DenormalizedHouseInfoEmbedded, \
    DenormalizedProviderInfoEmbedded
from app.gis.models.guid import GUID

from lib.gridfs import put_file_to_gridfs, get_file_from_gridfs


class OperationManager(object):

    @property
    def managed_context(self) -> str:
        """Контекст выполнения операции"""
        return self._managed.context

    @property
    def managed_state(self) -> str:
        """Состояние управляемой операции"""
        return GIS_MANAGER_CONTEXTS.get(self.managed_context,
                f"действия В КОНТЕКСТЕ {sb(self.managed_context)}") \
            if self.managed_context else "действия БЕЗ КОНТЕКСТА"

    @property
    def managed_desc(self) -> str:
        """Описание состояния управляемой операции"""
        return ("попытки" if self._managed.has_error else "успеха") \
            + f" {self.managed_state}"

    def __init__(self, operation: 'AsyncOperation'):
        """
        Создать менеджер контекста операции
        """
        self._managed: AsyncOperation = operation  # управляемая операция

    def __call__(self, context: str) -> 'OperationManager':
        """
        Задать контекст менеджера
        """
        assert context in GIS_MANAGER_CONTEXTS, \
            f"Контекст {sb(context)} операции {self._managed.name} не распознан"

        self._managed._context = context  # задаем контекст выполннения операции

        return self  # возвращаем экземпляр менеджера

    def __enter__(self) -> 'OperationManager':
        """
        Вход в менеджер контекста
        """
        assert self.managed_context, \
            "Контекст (менеджера) операции не определен"

        return self  # экземпляр менеджера возвращается в as

    def __exit__(self, exc_type, exc, tb) -> bool:
        """
        Выход из менеджера контекста

        Допускается возбуждение отличного от exc исключения в рамках метода

        :returns: True - подавить (не возбуждать) полученное исключение
        """
        self.exception = exc  # полученное исключение или None
        suppress_exception: bool = False  # подавить исключение?

        if not exc:  # без исключений?
            pass  # WARN не обнуляем существующую ошибку
        elif isinstance(exc, UnstatedError):  # неудовлетворительное состояние?
            suppress_exception = exc.is_successful  # WARN зависит от состояния
        elif isinstance(exc, GisWarning):  # неблокирующая ошибка?
            self._managed.warning(str(exc))  # изменяем состояние
            suppress_exception = True  # WARN подавляем исключение
        elif isinstance(exc, GisError):  # ошибка ГИС ЖКХ?
            self._managed.error(str(exc),  # записываем код и текст ошибки
                exc.error_details)  # записываем детали ошибки
        elif isinstance(exc, PendingSignal):  # в состоянии ожидания?
            self._managed.warning(str(exc))  # изменяем состояние
            suppress_exception = True  # WARN подавляем исключение
        elif isinstance(exc, RestartSignal):  # сигнал к перезапуску?
            self._managed.error(str(exc.FATAL_ERROR))  # фиксируем нарушение
            raise exc.FATAL_ERROR  # выбрасываем новое исключение
        elif isinstance(exc, CancelSignal):  # отмена операции?
            self._managed.warning(str(exc))  # временное (до cancel) состояние
            self._managed.cancel()  # WARN отменяем операцию и сопутствующие
        elif isinstance(exc, PublicError):  # публичная ошибка?
            self._managed.error(exc.message)  # записываем сообщение об ошибке
            suppress_exception = self._managed.is_scheduled  # WARN плановая?
        elif isinstance(exc, InternalError):  # внутренняя (Системная) ошибка?
            self._managed.error(exc.message or "Сбой в работе Системы!"
                f" Сообщите идентификатор операции в службу ТП ЕИС ЖКХ.",
                exc.details)  # записываем детали ошибки
        elif isinstance(exc, AssertionError):  # нарушено утверждение?
            self._managed.error("Обнаружены некорректные данные!"
                f" Сообщите идентификатор операции в службу ТП ЕИС ЖКХ.",
            str(exc))  # записываем текст утверждения
            suppress_exception = self._managed.is_scheduled  # WARN плановая?
        else:  # неопределенное исключение?
            from traceback import extract_tb
            trace_back: str = f"{exc_type.__name__}: {exc}\n" \
                + '\n'.join(extract_tb(exc.__traceback__).format())
            self._managed.error("Ошибка в процессе выполнения операции!"
                f" Сообщите идентификатор операции в службу ТП ЕИС ЖКХ.",
            trace_back)  # записываем трассировку стека

        if (self.exception or  # исключение или сохраняющий контекст?
                self.managed_context not in NO_RECORD_CONTEXTS):
            self._managed.save()  # сохраняем запись об операции

        self._managed._context = None  # WARN обнуляем контекст операции

        return suppress_exception  # True - подавить исключение


class AsyncOperation(object):

    # region ПАРАМЕТРЫ ОПЕРАЦИИ
    WSDL_NAME: str = None  # name в схеме сервиса, None - название класса

    CONNECTION_ALIAS: str = 'legacy-db'  # подключение к БД  # TODO gis_db?
    DATABASE_NAME: str = 'c300'  # название используемой БД  # TODO list?

    IS_ANONYMOUS: bool = False  # анонимная (без поставщика информации)?
    IS_HOMELESS: bool = IS_ANONYMOUS  # операция без управляемого дома?

    IS_DEBUG_MODE = GIS.get('debug_mode') or False  # глобальный режим отладки?

    VERSION: str = None  # поддерживаемая версия элемента запроса
    ELEMENT_LIMIT: int = 0  # ограничение (ГИС ЖКХ) на кол-во элементов запроса

    FORCED_EXECUTION: bool = False  # выполнять операцию в любом состоянии?

    MAX_RESTART_COUNT: int = 2  # максимальное кол-во ошибок выполнения запроса
    RESTART_DELAY: int = 60  # задержка перед перезапуском запроса, 0 - без

    GET_STATE_DELAY = [5, 10, 30, 60, 120, 300, 900, 1800, 3600,  # по умолчанию
        7200, 14400, 21600, 36000]  # 24 часа - макс. время обработки запроса
    GET_RESULT_DELAY = 30  # задержка перед запросом результата (в обработке)

    REQUIREMENTS: dict = {}  # признаки с процентом требуемых ид-ов операции

    DEFAULT_LOG_LEVEL: int = WARNING  # (минимальный) уровень журнала операции
    # endregion ПАРАМЕТРЫ ОПЕРАЦИИ

    # region ПЕРЕМЕННЫЕ КЛАССА
    _logger: Logger = None  # создаваемый в конструкторе Logger операции
    _service: Type[WebService] = None  # сервис (внешний класс) операции

    _record: GisRecord = None  # используемая запись об операции
    _context: str = None  # текущий контекст выполнения операции

    _house_providers: dict = None  # обслуживаемые дома управляющих организаций
    _mapped_guids: dict = None  # сопоставления идентификаторов операции
    # endregion ПЕРЕМЕННЫЕ КЛАССА

    # region СТАТИЧЕСКИЕ МЕТОДЫ
    @staticmethod
    def get_provider_data(provider_id: ObjectId, *field_s: str):
        """
        Получить данные организации

        :returns: значение одного поля или словарь с (выбранными) данными модели
        """
        assert provider_id, "Требуется идентификатор организации"

        # TODO from utils.crm_utils import provider_can_access
        from processing.models.billing.provider.main import Provider

        query_set = Provider.objects(id=provider_id)  # : QuerySet

        if len(field_s) == 1:  # единственное поле?
            return query_set.scalar(field_s[0]).first()  # ~ only

        return query_set.only(*field_s).as_pymongo().first()

    @staticmethod
    def get_xml_file(file_id: ObjectId, decoded: bool = False) -> bytes or str:
        """Получить содержимое XML-файла"""
        _, file = get_file_from_gridfs(file_id)

        return file if not decoded else file.decode('utf-8')
    # endregion СТАТИЧЕСКИЕ МЕТОДЫ

    # region КЛАССОВЫЕ МЕТОДЫ
    @classmethod
    def _setup_logging(cls, level: int):
        """
        Инициализация журнала клиента и модулей

        :param level: FATAL = CRITICAL = 50, ERROR = 40,
            WARNING = 30, INFO = 20, DEBUG = 10, NOTSET = 0
        """
        # WARN Logger-ы кэшируются и существуют до конца работы интерпретатора
        if cls._logger is None:
            reset_logging()  # сброс параметров базового (root) журнала

            cls._logger = getLogger(cls.__name__)

        cls._logger.setLevel(level)  # (минимальный) уровень журнала операции

    @classmethod
    def _log(cls, debug: str = None,  # по умолчанию
            info: str = None, warn: str = None, error: str = None):
        """
        Журнал (выполнения) операции

        self._client.logger - logger Zeep
        """
        assert cls._logger is not None, "Отсутствует Logger операции"

        if debug:
            cls._logger.debug(debug)
        elif info:
            cls._logger.info(info)
        elif warn:
            cls._logger.warning(warn)
        elif error:  # ~ CRITICAL / FATAL
            cls._logger.error(error)

        return cls._logger

    @classmethod
    def _check_db_connection(cls):
        """Проверить подключение к БД"""
        from pymongo.mongo_client import MongoClient
        from pymongo.database import Database
        from mongoengine.connection import get_connection

        # WARN raise MongoEngineConnectionError
        client: MongoClient = get_connection(cls.CONNECTION_ALIAS)
        # cls._log(f"Базы данных подключения {sb(cls.CONNECTION_ALIAS)}: "
        #     + ', '.join(client.list_database_names()))

        # WARN raise InvalidName
        database: Database = client.get_database(cls.DATABASE_NAME)
        # cls._log(f"Коллекции базы данных {sb(cls.DATABASE_NAME)}: "
        #     + ', '.join(database.list_collection_names()))

        address: str = f"{client.address[0]}:{client.address[1]}"  # : tuple
        cls._log(info=f"Подключение {sb(cls.CONNECTION_ALIAS)}"
            f" к расположенной по адресу mongodb://{address}/"
            f" базе данных {sb(cls.DATABASE_NAME)}")

    @classmethod
    def load(cls, record_id: ObjectId, is_forced: bool = False):
        """
        Получить соответствующий записи экземпляр операции
        """
        assert cls is AsyncOperation, \
            "Некорректный тип операции загружаемой записи"

        gis_record: GisRecord = \
            GisRecord.objects(generated_id=record_id).first()
        if gis_record is None:
            raise NoDataError(f"Запись об операции {record_id} не найдена")

        # получаем тип (класс) операции веб-сервиса ГИС ЖКХ
        service_operation = WebService.operation(gis_record.operation)

        # создаем (БЕЗ инициализации) соответствующий записи экземпляр операции
        async_operation: AsyncOperation = \
            service_operation.__new__(service_operation)  # WARN без __init__
        async_operation.FORCED_EXECUTION = is_forced  # в любом состоянии?

        async_operation._record = gis_record  # связываем операцию с записью

        if async_operation.debug_mode:  # выполняем в режиме отладки?
            async_operation._setup_logging(DEBUG)  # сохраняем журнал операции

        # WARN async_operation['load_requirements'] проверяется перед загрузкой
        async_operation.load_required()  # загружаем данные организации и дома

        async_operation.log(info="Загружены данные (записи об) операции"
            f" с идентификатором {async_operation.record_id}"
            f" в состоянии {sb(async_operation.status)}")

        return async_operation  # : AsyncOperation
    # endregion КЛАССОВЫЕ МЕТОДЫ

    # region СВОЙСТВА ОПЕРАЦИИ
    @property
    def _type(self) -> Type['AsyncOperation']:
        """Получить тип (не экземпляр) операции"""
        return type(self)  # ~ self.__class__

    @property
    def _client(self):  # -> SoapClient
        """SOAP-клиент сервиса для операции"""
        return self._service.soap_client(self.debug_mode)  # WARN кэшируются

    @property
    def _soap_header(self) -> dict:
        """Данные SOAP-заголовка запроса"""
        header_data = dict(  # : HeaderType
            Date=get_time().isoformat(),  # без временной зоны, но с мкс.
            MessageGUID=self.generated_guid if self.is_acked \
            else self.message_guid  # сгенерированный идентификатор сообщения
        )  # ISCreator не используется

        if not self.IS_ANONYMOUS:  # запрос от лица поставщика информации?
            header_data.update(
                orgPPAGUID=self.ppaguid,  # SenderID - упразднен с 10.0.0
                IsOperatorSignature=True,  # используется подпись оператора ИС
            )
            assert header_data['orgPPAGUID'] is not None, \
                "Не загружен идентификатор ГИС ЖКХ поставщика информации"

        return header_data

    @property
    def debug_mode(self) -> bool:
        """Выполнение в режиме отладки?"""
        return self['debug_mode'] is True

    @property
    def test_mode(self) -> bool:
        """Режим тестирования (запроса или выполнения) операции"""
        return self['request_only'] is True or self['result_only'] is True

    @property
    def acquired(self) -> dict:
        """Имеющиеся идентификаторы ГИС ЖКХ операции"""
        if self._record.required is None:  # не определено?
            self._record.required = {}

        return self._record.required

    @property
    def has_requirements(self) -> bool:
        """Требуется загрузка идентификаторов?"""
        return (self['load_requirements'] is True
            and any(req > 0 for req in self.REQUIREMENTS.values())
            and not self.test_mode)

    @property
    def name(self) -> str:
        """Название (класса) операции"""
        return self.__class__.__name__  # ServiceName[Async]

    @property
    def description(self) -> Optional[str]:
        """
        Описание операции

        Сохраняется после распределения аргументов и до формирования запроса
        """
        return self._record.desc  # по умолчанию = None

    @property
    def manager(self) -> OperationManager:
        """Создать новый экземпляр менеджера контекста операции"""
        return OperationManager(self)  # возвращаем экземпляр менеджера

    @property
    def context(self) -> str:
        """Текущий контекст выполнения операции"""
        return self._context

    @property
    def load_context(self) -> OperationManager:
        """
        Создать экземпляр менеджера загрузки данных операции

        Сохранение записи об операции выполняется только в случае ошибки
        """
        context_manager = OperationManager(self)  # __init__

        return context_manager(GisManagerContext.LOAD)  # __call__

    @property
    def record_id(self) -> ObjectId:
        """Идентификатор записи об операции"""
        assert self._record, \
            "Запрошен идентификатор несуществующей записи об операции"
        assert self._record.generated_id is not None, \
            "Запрошен отсутствующий идентификатор записи об операции"

        return self._record.generated_id  # ~ pk

    @property
    def is_forced(self) -> bool:
        """Принудительное выполнение?"""
        assert isinstance(self.FORCED_EXECUTION, bool)
        return self.FORCED_EXECUTION

    @property
    def is_fractured(self) -> bool:
        """Операция разбита на части?"""
        return self._record and self._record.fraction

    @property
    def is_first(self) -> bool:
        """Первая часть разбитой операции?"""
        return self.is_fractured and self._record.fraction[0] == 1

    @property
    def parent_id(self) -> Optional[ObjectId]:
        """Идентификатор порождающей записи об операции"""
        return self._record.parent_id

    @property
    def child_id(self) -> Optional[ObjectId]:
        """Идентификатор порожденной записи об операции"""
        return self._record.child_id

    @property
    def pending_id(self) -> Optional[ObjectId]:
        """Идентификатор упреждающей (предшествующей) записи об операции"""
        return self._record.pending_id

    @property
    def follower_id(self) -> Optional[ObjectId]:
        """Идентификатор последующей записи об операции"""
        return self._record.follower_id

    @property
    def element_limit(self) -> int:
        """Ограничение количества элементов запроса операции"""
        assert isinstance(self.ELEMENT_LIMIT, int), \
            "Некорректное ограничение элементов запроса (0 - без ограничений)"
        return self['element_limit'] or self.ELEMENT_LIMIT

    @property
    def object_type(self) -> Optional[str]:
        """Тип объектов операции"""
        return self._record.object_type

    @property
    def object_ids(self) -> list:
        """Аргументы (идентификаторы объектов) запроса операции"""
        if self._record.object_ids is None:  # отсутствуют аргументы запроса?
            self._record.object_ids = []  # обнуляется при сохранении записи

        return self._record.object_ids

    @property
    def period(self) -> Optional[datetime]:
        """Период данных операции"""
        return self._record.period

    @property
    def request(self) -> dict:
        """Данные запроса операции"""
        return self._record.request or {}  # или пустой словарь

    @property
    def options(self) -> dict:
        """Параметры выполнения операции"""
        return self._record.options or {}

    @property
    def _state(self) -> str:
        """Описание состояния операции"""
        return ('отмененная' if self.is_canceled
            else 'проваленная' if self.has_error
            else 'завершенная' if self.is_stored
            else 'выполненная' if self.is_stated
            else 'невыполненная' if self.is_acked
            else 'незавершенная' if self.is_saved
            else 'несохраненная')

    @property
    def status(self) -> str:
        """Наименование состояния операции"""
        return GIS_RECORD_STATUSES[self._record.status]

    @property
    def has_error(self) -> bool:
        """Ошибка в процессе выполнения операции?"""
        # TODO self._record.error is not None?
        return self._record.status == GisRecordStatusType.ERROR

    @property
    def is_scheduled(self) -> bool:
        """Плановая операция?"""
        return self['is_scheduled'] is True

    @property
    def is_synchronous(self) -> bool:
        """Выполняется в последовательном режиме?"""
        return self['synchronous_mode'] or self.test_mode

    @property
    def is_import(self) -> bool:
        """Операция импорта (выгрузки в) ГИС ЖКХ?"""
        return self._record.is_import

    @property
    def is_house_management(self) -> bool:
        """Операция сервиса HouseManagement?"""
        return self._service.__name__ == 'HouseManagement'

    @property
    def is_canceled(self) -> bool:
        """Выполнение операции отменено?"""
        return self._record.canceled is not None

    @property
    def is_stored(self) -> bool:
        """Полученные данные сохранены?"""
        return self._record.stored is not None

    @property
    def is_stated(self) -> bool:
        """Получено состояние выполнения операции?"""
        return self._record.stated is not None

    @property
    def is_acked(self) -> bool:
        """Запрос операции отправлен (получена квитанция)?"""
        return self._record.acked is not None

    @property
    def is_saved(self) -> bool:
        """Запись об операции сохранена?"""
        return self._record.saved is not None

    @property
    def is_complete(self) -> bool:
        """Операция завершена?"""
        if self._record.status not in SUCCESSFUL_STATUSES:  # не выполнена?
            self.log(warn=f"Текущая операция {self.record_id} находится"
                f" в невыполненном состоянии {sb(self._record.status)}")
            return False

        if not (self.follower_id or self.child_id or self.parent_id):
            self.log(info=f"Текущая операция {self.record_id} без"
                " порожденных и последующих считается выполненной")
            return True

        failed: dict = {record.generated_id: record.status
            for record in self._record.family.filter(__raw__={
                'status': {'$nin': SUCCESSFUL_STATUSES}
            }) if isinstance(record, GisRecord)}
        if failed:  # порождающая или порожденные не выполнены?
            self.log(warn=f"Порожденные {self.parent_id or self.record_id}"
                " невыполненные операции: " + ', '.join(f"{_id}: {sb(status)}"
                    for _id, status in failed.items()))
            return False

        if not self.follower_id:  # без последующей операции?
            self.log(info=f"Все (включая текущую {self.record_id})"
                " порожденные и порождающая операции выполнены")
            return True  # WARN операция (включая порожденные) завершена

        failed: dict = {record.generated_id: record.status
            for record in self._record.crowd.filter(__raw__={
                'status': {'$nin': SUCCESSFUL_STATUSES}
            }) if isinstance(record, GisRecord)}
        if failed:  # упреждающие операции не выполнены?
            self.log(warn=f"Упреждающие {self.follower_id} невыполненные"
                " операции: " + ', '.join(f"{_id}: {sb(status)}"
                    for _id, status in failed.items()))
            return False

        self.log(info=f"Все (включая текущую {self.record_id})"
            f" упреждающие {self.follower_id} операции выполнены")
        return True  # операция (включая порожденные и последующие) завершена

    @property
    def scheduled(self) -> datetime:
        """Планируемое время запуска операции"""
        assert self._record.scheduled, \
            "Планируемое время запуска операции не определено"
        # WARN Дата и время во временной зоне Celery (UTC)!
        # return get_celery_tz().localize(self._record.scheduled)
        return self._record.scheduled - relativedelta(hours=3)

    @property
    def restarts(self) -> int:
        """Попытки выполнения запроса"""
        return self._record.restarts or 0  # по умолчанию = None

    @property
    def retries(self) -> int:
        """Попытки получения состояния обработки сообщения"""
        return self._record.retries or 0  # по умолчанию = None

    @property
    def get_state_delay(self) -> int:
        """Ожидание перед последующим запросом состояния"""
        return (self.GET_STATE_DELAY[self.retries]  # в качестве индекса
            if self.retries < len(self.GET_STATE_DELAY)
            else 300)  # 5 минут

    @property
    def generated_guid(self) -> UUID:
        """Новый (уникальный) идентификатор"""
        return get_guid()

    @property
    def message_guid(self) -> UUID:
        """Идентификатор ГИС ЖКХ сообщения"""
        return self._record.message_guid

    @property
    def ack_guid(self) -> UUID:
        """Идентификатор квитанции о приеме (сообщения) запроса в обработку"""
        return self._record.ack_guid

    @cached_property
    def provider_houses(self) -> dict:
        """
        Управляемые организациями дома

        :returns: ProviderId: [ HouseId,... ]
        """
        assert self._house_providers is not None, \
            "Управляющие домами организации не определены"

        provider_houses: dict = {}

        for hid, pid in self._house_providers.items():
            provider_houses.setdefault(pid, []).append(hid)

        return provider_houses

    @property
    def agent_id(self) -> Optional[ObjectId]:
        """Идентификатор (платежного) агента ~ Р(К)Ц"""
        return self._record.agent_id

    @property
    def provider_id(self) -> ObjectId:
        """Идентификатор поставщика информации"""
        return self._record.provider_id

    @property
    def relation_id(self) -> Optional[ObjectId]:
        """Идентификатор связанной организации, откуда брать данные"""
        return self._record.relation_id

    @cached_property
    def provider_guid(self) -> Optional[GUID]:
        """Данные ГИС ЖКХ (организации) поставщика информации"""
        assert self.provider_id, \
            "Идентификатор поставщика информации не определен"
        return self.owned_guid(GisObjectType.PROVIDER, self.provider_id)

    @property
    def ppaguid(self) -> Optional[UUID]:
        """
        Идентификатор ГИС ЖКХ поставщика информации

        GUID.gis - идентификатор зарегистрированной организации (PPAGUID)
        GUID.root - корневой идентификатор организации
        GUID.version - идентификатор текущей версии
        """
        return self.provider_guid.gis \
            if self.provider_guid else None

    @property
    def provider_name(self) -> str:
        """Название организации (поставщика информации)"""
        if self.provider_guid is not None and self.provider_guid.desc:
            return self.provider_guid.desc  # название организации в ГИС ЖКХ

        return self.get_provider_data(self.provider_id, 'str_name') \
            or 'без названия'

    @property
    def binds_permissions(self) -> dict:
        """
        Привязки организации к группам домов

        Примеры использования:
            Area.objects(**Area.get_binds_query(self.binds_permissions, True))
            Meter.objects(Meter.get_binds_query(self.binds_permissions))  # : Q
        """
        return self.get_provider_data(self.provider_id,  # TODO agent_id?
            '_binds_permissions') or {}  # : dict

    @property
    def house_id(self) -> Optional[ObjectId]:
        """Идентификатор управляемого организацией дома"""
        return self._record.house_id

    @cached_property
    def house_guid(self) -> Optional[GUID]:
        """Данные ГИС ЖКХ дома операции"""
        assert self.house_id, \
            "Идентификатор дома операции не определен"
        return self.owned_guid(GisObjectType.HOUSE, self.house_id)

    @property
    def fias_guid(self) -> Optional[UUID]:
        """
        Идентификатор дома в ФИАС (ГИС ЖКХ)

        GUID.gis - идентификатор дома в ГИС ЖКХ (может не совпадать с ФИАС)
        GUID.root - (отличный от ФИАС) идентификатор дома в ГИС ЖКХ (импорт)
        """
        return self.house_guid.gis if self.house_guid else None

    @property
    def house_address(self) -> str:
        """Адрес дома"""
        if self.house_guid is None:
            return "без загруженных данных"
        elif not self.house_guid.desc:
            return "без (описания) адреса"

        return self.house_guid.desc
    # endregion СВОЙСТВА ОПЕРАЦИИ

    # __slots__: не позволяет создавать новые переменные экземпляра операции!
    # переменные класса становятся константами и не меняются в экземпляре!
    # __del__: деструктор нарушает естественный процесс выбрасывания исключений!

    def __new__(cls, *args, **kwargs):
        """
        Конструктор экземпляра операции
        """
        assert cls._service is not None, \
            "Ссылка на веб-сервис (внешний класс) операции не определена"

        cls._setup_logging(
            DEBUG if cls.IS_DEBUG_MODE else cls.DEFAULT_LOG_LEVEL
        )  # инициализируем журнал операции
        cls._check_db_connection()  # проверим подключение к БД

        return super().__new__(cls)  # возвращаем экземпляр операции

    def __init__(self, provider_id: ObjectId = None, house_id: ObjectId = None,
            agent_id: ObjectId = None, **options):
        """
        Инициализация (записи об) асинхронной операции

        :param provider_id: идентификатор (организации) поставщика информации
        :param house_id: идентификатор участвующего в операции дома
        :param agent_id: идентификатор (организации) агента (РЦ)
        :param options: именованные параметры выполнения операции
        """
        self._record = GisRecord(  # создаем новую запись об операции
            operation=self.name,  # с обязательным наименованием
            status=GisRecordStatusType.CREATED,  # Создана
        )  # WARN сохраняется при ошибке в init или (обязательно) в prepare
        assert self._record.generated_id, \
            "Идентификатор записи о новой операции не сгенерирован"
        assert options is not None, "Некорректные параметры выполнения операции"

        if not self.IS_DEBUG_MODE and options.get('debug_mode'):  # временный?
            self._setup_logging(DEBUG)  # инициализируем подробный журнал

        with self.manager(GisManagerContext.INIT) as context:  # в случае ошибки
            self._setup(options)  # устанавливаем параметры выполнения операции

            self._purge_guids()  # инициализируем сопоставления операции

            if not house_id:  # операция без определенного дома?
                self.log(info=f"Операции {self.record_id} выполняется"
                    " без определенного (идентификатора) дома")
            else:  # операция с определенным домом!
                self._set_house(house_id)  # определяем дом операции

            if not provider_id:  # анонимная операция?
                # WARN анонимная операция может иметь идентификатор организации
                assert self.IS_ANONYMOUS, "Для выполнения операции" \
                    " необходим идентификатор поставщика информации"
                self.log(warn=f"Операция {self.record_id} выполняется без"
                    " (идентификатора организации) поставщика информации")
            else:  # операция поставщика информации!
                self._set_provider(provider_id, house_id, agent_id)

            if self.is_scheduled and not self['export_changes']:
                raise PublicError("Плановая выгрузка изменений не выполняется")

        if context.exception:  # получено предупреждение?
            if self.pending_id:  # операция поставлена в очередь?
                self.execute(self.pending_id)  # выполняем упреждающую операцию

    def __call__(self, *object_id_s: ObjectId, **request_data):
        """
        Инициировать выполнение операции

        Превышение лимита объектов инициирует выполнение подзапросов по очереди
        Повторный вызов инициирует параллельное выполнение идентичной операции

        :param object_id_s: идентификаторы объектов запроса операции,
            формирование запроса выполняется перед отправкой сообщения
        :param request_data: заранее подготовленные данные запроса операции,
            могут изменяться в процессе подготовки данных запроса (в prepare),
            валидация значений выполняется (zeep) при формировании элементов XML
        """
        assert not self.is_forced, \
            "Не допускается вызов операции в принудительном режиме"

        # TODO проверить load_context на exception

        if self.is_saved:  # запись об операции сохранена?
            clone_record: GisRecord = self._record.__copy__()
            self.log(warn="Инициируется (параллельное) выполнение идентичной"
                f" {self.record_id} операции {clone_record.generated_id}")
            self._with(clone_record)  # заменяем идентичной

        if self._agent_ops(*object_id_s, **request_data):
            return self  # WARN завершаем текущую операцию
        elif self._house_ops(*object_id_s, **request_data):
            return self  # WARN завершаем текущую операцию

        self.prepare(*object_id_s, **request_data)  # данные запроса операции

        if self.pending_id:  # последующая операция (в очереди)?
            self.execute(self.pending_id)  # выполняем упреждающую операцию
        else:  # текущая (или порождающая) операция подлежит выполнению!
            self.execute(self.parent_id or self.record_id)  # выполняем операцию

        return self  # возвращаем экземпляр операции

    def __getitem__(self, key: str):
        """
        Получить параметр (выполнения) операции

        ex: self['option']
        """
        if key in {'request_only', 'result_only'}:  # режим тестирования?
            return self.options.get(key) or False
        elif key in self.options:  # переопределенный параметр?
            return self.options[key]
        else:  # WARN параметр по умолчанию или None!
            return GIS.get(key)

    def __setitem__(self, key: str, value):
        """
        Установить параметр (выполнения) операции

        ex: self['option'] = value
        """
        if not self.options:  # параметры не установлены?
            self._record.options = {key: value}  # первый параметр
        else:  # добавляем новый или обновляем параметр выполнения операции!
            self._record.options[key] = value

    def log(self, debug: str = None,  # по умолчанию
            info: str = None, warn: str = None, error: str = None,
            is_spam: bool = False):
        """
        Внести запись в журнал (выполнения) операции
        """
        if is_spam is True:  # None ~ False
            return self._logger

        level: int = ERROR if error else WARNING if warn else \
            INFO if info else DEBUG

        if level >= self._logger.level and self.debug_mode:
            if self._record.log is None:  # журнал пуст?
                self._record.log = [error or warn or info or debug]
            else:  # журнал имеет записи!
                self._record.log.append(error or warn or info or debug)

        return self._log(debug, info, warn, error)

    def _with(self, gis_record: GisRecord):
        """
        Выполнять операцию с иной записью
        """
        assert gis_record.generated_id, \
            "Идентификатор иной записи об операции не сгенерирован"

        self.flush_guids()  # WARN сохраняем сопоставленные идентификаторы
        self.save()  # WARN сохраняем финальное состояние текущей операции

        self.log(warn=f"Запись операции {self.record_id}"
            f" в состоянии {sb(self.status)} подменяется"
            f" на {gis_record.generated_id}")
        self._record = gis_record  # WARN теперь в работе иная запись

    def _setup(self, options: dict):
        """
        Установить параметры выполнения операции
        """
        if self.IS_DEBUG_MODE and 'debug_mode' not in options:  # глобальный?
            options['debug_mode'] = True  # переопределяем параметр операции

        self._record.options = options  # параметры выполнения (по ссылке)

        if self.has_requirements:  # требуется загрузка идентификаторов?
            self.log(info="Операции может потребоваться загрузка данных"
                " (идентификаторов) ГИС ЖКХ " + ', '.join(f"{tag}: {pct}%"
                    for tag, pct in self.REQUIREMENTS.items() if pct > 0))

        for key in [*options]:  # WARN в цикле словарь модифицируется
            if key == 'element_limit':  # ограничение элементов запроса?
                assert isinstance(options[key], int) and options[key] >= 0, \
                    "Установлено некорректное ограничение элементов запроса"
                self.log(warn=f"Установлено ограничение в {options[key]}"
                    f" элементов запроса операции от {self.ELEMENT_LIMIT}"
                    " максимально допустимых")
            elif key not in GIS:
                self.log(info="Специфический параметр выполнения операции"
                    f" {sb(key)} установлен в значение {options[key]}")
            elif options[key] != GIS[key]:  # значение параметра разнится?
                self.log(info="Глобальный параметр выполнения операции"
                    f" {sb(key)} переопределен с {GIS[key]} на {options[key]}")
            else:  # значение параметра совпадает с глобальным!
                del options[key]  # удаляем совпадающий параметр
                self.log(info="Входящий параметр выполнения операции"
                    f" {sb(key)} удален как совпадающий с глобальным")

        assert not self.is_import or self.ELEMENT_LIMIT, \
            "Ограничение элементов запроса операции импорта не установлено"
        if (self.ELEMENT_LIMIT and  # стандартное ограничение операции?
                'element_limit' not in options):  # не переопределено?
            self.log(info=f"Установлено ограничение в {self.ELEMENT_LIMIT}"
                " максимально допустимых элементов запроса операции")

    def _agent_ops(self, *object_id_s: ObjectId, **request_data) -> bool:
        """
        Операция обслуживающей (НЕ управляющей) организации?
        """
        if self.IS_ANONYMOUS:  # анонимная операция?
            return False  # операция выполняется без поставщика информации
        elif not self._house_providers:  # нет управляемых домов?
            return False  # операция выполняется текущей организацией
        elif self.agent_id:  # определена обслуживающая организация?
            return False  # операция выполняется управляющей домом организацией

        if self.IS_HOMELESS:  # операция без дома?
            self.log(warn="Операция без домов подлежит выполнению"
                f" {len(self.provider_houses)} управляющими организациями:\n\t"
                    + ', '.join(str(pid) for pid in self.provider_houses))

            for provider_id in self.provider_houses:  # управляющие организации
                self.log(warn="Инициируется выполнение операции без дома"
                    f" обслуживаемой {self.provider_id} управляющей"
                    f" организации {provider_id}")

                operation = self._type(provider_id,  # экземпляр операции
                    house_id=None,  # WARN без идентификатора управляемого дома
                    agent_id=self.provider_id,  # с идентификатором агента
                   **self.options)  # с идентичными параметрами

                operation(*object_id_s, **request_data)

            return True  # WARN запись о текущей операции не сохраняется

        self.log(warn="Операция подлежит выполнению"
            f" {len(self.provider_houses)} управляющими"
            f" {len(self._house_providers)} домами организациями")

        for house_id, provider_id in self._house_providers.items():
            self.log(warn="Инициируется выполнение операции"
                f" обслуживаемой {self.provider_id} управляющей"
                f" домом {house_id} организации {provider_id}")

            operation = self._type(provider_id,  # экземпляр операции
                house_id=house_id,  # с идентификатором управляемого дома
                agent_id=self.provider_id,  # с идентификатором агента
               **self.options)  # с идентичными параметрами

            operation(*object_id_s, **request_data)

        return True  # WARN запись о текущей операции не сохраняется

    def _house_ops(self, *object_id_s: ObjectId, **request_data) -> bool:
        """
        Операция со всеми обслуживаемыми домами организации?
        """
        if self.IS_HOMELESS:  # операция без дома?
            return False
        elif self.house_id:  # идентификатор дома определен?
            return False
        elif 'FIASHouseGuid' in request_data:  # ФИАС в запросе?
            return False

        # WARN операция может не иметь аргументов запроса
        for house_id, object_ids in self._house_objects(*object_id_s):
            operation = self._type(self.provider_id,  # экземпляр операции
                house_id=house_id,  # с идентификатором управляемого дома
                agent_id=self.agent_id,  # с идентификатором агента
                **self.options)  # с идентичными параметрами

            operation(*object_ids, **request_data)  # выполняем операцию

        return True  # WARN запись о текущей операции не сохраняется

    def _house_objects(self, *object_id_s: ObjectId) -> tuple:
        """
        Распределить аргументы операции по домам
        """
        assert not self.house_id, "Идентификатор дома" \
            " операции не нуждается в определении"

        binded_houses: dict = get_binded_houses(self.provider_id)
        self.log(warn=f"Операция подлежит выполнению с {len(binded_houses)}"
            f" управляемыми {self.provider_name} домами:\n\t"
                + '\n\t'.join(f"{_id} ~ {house['address']}"
                    for _id, house in binded_houses.items()))

        for house_id in binded_houses:  # ~ keys
            yield house_id, object_id_s  # WARN аргументы не делятся

    def _set_provider(self, provider_id: ObjectId, house_id: ObjectId,
            agent_id: ObjectId):
        """
        Определить поставщика информации операции

        В Системе данные (платежного) агента (РЦ), в ГИС ЖКХ - контрагента (УО)
        """
        assert provider_id, "Для выполнения операции" \
            " необходим идентификатор поставщика информации"

        if not agent_id:  # обслуживающая организация не определена?
            # идентификаторы (обслуживаемых) управляющих домами организаций
            self._house_providers: dict = get_house_providers(provider_id)

            if house_id in self._house_providers:  # обслуживаемый дом?
                agent_id = provider_id  # обслуживающая (РЦ)
                provider_id = self._house_providers[house_id]  # управляющая
                self.log(f"Установлена обслуживаемая {agent_id} управляющая"
                    f" домом {house_id} организация {provider_id}")

                self._house_providers = {}  # WARN более не потребуется
            elif self._house_providers:  # дом не обслуживается!
                self.log(f"Найдено {len(self.provider_houses)} обслуживаемых"
                    f" {provider_id} управляющих {len(self._house_providers)}"
                    " домами организаций:\n\t" + '\n\t'.join(f"{pid}: "
                        + ', '.join(str(hid) for hid in houses)
                            for pid, houses in self.provider_houses.items()))

        self._record.provider_id = provider_id  # поставщик информации
        provider = Provider.objects(id=provider_id).first()
        self._record.provider_info = DenormalizedProviderInfoEmbedded.from_ref(
            provider)

        if agent_id:  # операция выполняется агентом?
            self._record.agent_id = agent_id  # идентификатор владельца данных
            message = (f"Операция выполняется обслуживаемой "
                       f"{self.get_provider_data(self.agent_id, 'str_name')} "
                       f"управляющей организацией "
                       f"{self.get_provider_data(self.provider_id, 'str_name')}")
        else:  # операция выполняется контрагентом!
            message = (f"Операция выполняется непосредственно "
                       f"поставщиком информации "
                       f"{self.get_provider_data(self.provider_id, 'str_name')}")
        relation = ProviderRelations.objects(
            slaves__provider=provider_id
        ).first()
        if relation:
            self._record.relation_id = relation.provider  # идентификатор владельца данных
            message += (f" используя данные от привязанной организации "
                        f"{self.get_provider_data(self.relation_id, 'str_name')}")
        self.log(warn=message)

    def _set_house(self, house_id: ObjectId):
        """
        Определить дом операции
        """
        assert house_id, "Для выполнения операции необходим идентификатор дома"

        self._record.house_id = house_id  # записываем идентификатор дома
        house = House.objects(id=house_id).first()
        self._record.house_info = DenormalizedHouseInfoEmbedded.from_ref(house)

    def load_required(self):
        """
        Предварительная загрузка до prepare нарушает выполнение операции
        """
        with self.load_context as context:  # сохраняем только в случае ошибки
            if (not self.IS_ANONYMOUS and  # не анонимная операция?
                    not self.provider_guid):  # идентификатор не загружен?
                if self.agent_id:  # кроме обслуживаемых организаций
                    raise NoGUIDError("Идентификатор ГИС ЖКХ обслуживаемой"
                        " организации не подлежит предварительной загрузке")
                from app.gis.services.org_registry_common import \
                    OrgRegistryCommon
                OrgRegistryCommon.load_org_guid(self)  # данные ГИС ЖКХ

            if (not self.IS_HOMELESS and  # операция с домом?
                    not self.house_guid):  # идентификатор не загружены?
                # raise NoGUIDError("Не загружен идентификатор"
                #     " ГИС ЖКХ (не ФИАС) дома")
                from app.gis.services.house_management import HouseManagement
                HouseManagement.load_house_guid(self)  # данные ГИС ЖКХ дома

        if context.exception:  # получено предупреждение?
            if self.pending_id:  # операция поставлена в очередь?
                self.execute(self.pending_id)  # выполняем упреждающую операцию

    def _filter(self, object_ids: tuple) -> list:
        """
        Получить ненулевые аргументы запроса операции
        """
        if not object_ids:  # аргументы запроса отсутствуют?
            self.log(info="Ограничение отсутствующих аргументов"
                f" запроса операции {self.record_id} не требуется")
            return []  # будет заменен на None перед сохранением записи

        not_null_ids: list = [_id for _id in object_ids if _id is not None]

        self.log(info=f"Получены {len(not_null_ids)} ненулевых из"
            f" {len(object_ids)} аргументов запроса операции {self.record_id}")

        return not_null_ids

    def _validate(self, object_id_s: tuple, request_data: dict) -> bool:
        """
        Проверить корректность данных запроса операции

        Выполняется в процессе (до) подготовки запроса операции

        Переопределенный метод может вносить изменения в данные запроса
        и самостоятельно выбрасывать (обрабатываемые) исключения
        """
        self.log("Корректировка данных запроса операции"
            f" {self.record_id} не требуется")

        return True

    def _prepare(self, object_ids: tuple, request_data: dict) -> None:
        """
        Подготовить данные (к формированию) запроса операции

        Проверку и изменение данных запроса следует выполнять в _validate
        """
        assert not self.is_saved, \
            "Запись о подготавливаемой операции не должна быть сохранена"
        if self._mapped_guids:  # сопоставленные (предшествующей) операции?
            tags = set(sb(guid.tag) for guid in self._mapped_guids.values())
            self.log(warn=f"Подготавливаемая операция {self.record_id}"
                f" получила {len(self._mapped_guids)} сопоставленных"
                f" идентификаторов {', '.join(tags)}")
            self.flush_guids()  # WARN сбрасываем идентификаторы

        self.log(f"Подготовка к формированию {len(object_ids) or 'без'}"
            f" аргументов " + ("с данными" if request_data else "без данных")
                + f" запроса операции {self.record_id}")

        # WARN извлекаем определенные параметры (запроса) операции
        if 'object_type' in request_data:  # определен тип объектов?
            self._record.object_type = request_data.pop('object_type')
        if 'period' in request_data:  # определен период данных?
            self._record.period = request_data.pop('period')

        self._record.request = request_data  # сформированные данные запроса

        if self._record.object_ids:  # аргументы определены до подготовки?
            assert not object_ids, "Полученные аргументы запроса" \
                " определены до подготовки данных операции"
            self.log(warn=f"Определены {len(self.object_ids)} аргументов"
                f" запроса до подготовки данных операции {self.record_id}")
        elif object_ids:  # получены аргументы запроса операции?
            # WARN ListField принимает list, tuple или None
            self._record.object_ids = self._filter(object_ids)

    def prepare(self, *object_id_s: ObjectId, **request_data) -> None:
        """
        Подготовить операцию к выполнению (разрядить запрос)

        Переопределяется для деления на подоперации по признаку

        Повторный вызов поставит операцию в очередь на выполнение
        """
        if self.is_saved:  # запись об операции сохранена?
            child_record: GisRecord = self._record.child()
            # WARN Порожденная выполняется после отправки запроса
            #  (до получения результата) порождающей операции
            self.log(warn="Выполняется подготовка данных запроса порожденной"
                f" от {self.record_id} операции {child_record.generated_id}")
            self._with(child_record)  # запись сохраняется менеджером

        with self.manager(GisManagerContext.PREPARE):  # безусловно
            if not self._validate(object_id_s, request_data):
                raise PublicError("Некорректные данные запроса операции")

            self._prepare(object_id_s, request_data)  # извлекается object_type

            self.set_status(GisRecordStatusType.PREPARED)  # Подготовлена

    def execute(self, record_id: ObjectId = None, is_forced: bool = False):
        """
        Инициировать выполнение (запроса) операции ГИС ЖКХ
        """
        if not record_id:  # запись об операции не определена?
            record_id = self.record_id  # текущая запись об операции

        from app.gis.tasks.async_operation import send_request

        if self.is_synchronous:  # последовательный режим выполнения?
            self.log(warn="Инициировано выполнение (запроса) операции"
                f" {self.record_id} в последовательном режиме")
            return send_request.apply(args=(record_id, is_forced))  # эмуляция

        self.log(info="Инициация выполнения (запроса) операции"
            f" с идентификатором (записи) {record_id}")
        # формирование и отправка запроса выполняются отдельной задачей
        send_request.apply_async(args=(record_id, is_forced))  # вместо delay

    def set_status(self, status: str):
        """
        Установить новое состояние выполнения операции
        """
        assert status in GIS_RECORD_STATUSES, \
            f"Состояние (записи об) операции {sb(status)} не опознано"
        # WARN текущее состояние операции может совпадать с устанавливаемым

        if status == GisRecordStatusType.DONE:  # Завершена?
            if self._record.warnings or self._record.fails:  # не полностью?
                status = GisRecordStatusType.WARNING  # Выполнена
        elif status == GisRecordStatusType.WARNING:  # получено предупреждение?
            if self.pending_id:  # идентификатор предшествующей операции?
                status = GisRecordStatusType.PENDING  # Отложена
            elif self.is_canceled:  # дата и время отмены операции?
                status = GisRecordStatusType.CANCELED  # Отменена
        elif status == GisRecordStatusType.CANCELED:  # Отменена?
            if not self.is_canceled:
                self._record.canceled = get_time()  # дата и время отмены

        if self._record.status != status:  # состояние операции изменилось?
            self.log(f"Состояние (записи об) операции {self.record_id} изменено"
                f" с {sb(self.status)} на {sb(GIS_RECORD_STATUSES[status])}")
            self._record.status = status

    def save(self, record: GisRecord = None) -> None:
        """
        Сохранить состояние (записи об) операции
        """
        if not record:  # запись об операции не указана?
            assert self._record, \
                "Для сохранения состояния необходима запись об операции"
            record = self._record  # используем текущую запись об операции

        # WARN невозможно зафиксировать ошибку при сохранении записи об операции
        record.save()  # сохраняем запись об операции

        self.log("Сохранено состояние (выполнения) операции"
            f" с идентификатором (записи) {record.generated_id}")

    def _produce(self, producer: Callable, subjects: Iterable) -> list:
        """
        Сформировать элементы запроса операции из набора (данных) объектов
        """
        def get_mapped_guid(_object) -> GUID:

            assert self._mapped_guids, \
                "Отсутствуют сопоставленные идентификаторы элементов запроса"

            object_id = _object.get('_id') if isinstance(_object, dict) else \
                _object.id if hasattr(_object, 'id') else None
            assert isinstance(object_id, ObjectId), \
                "Идентификатор объекта запроса не определен"

            object_guid = self._mapped_guids.get(object_id)
            assert isinstance(object_guid, GUID), \
                f"Идентификатор ГИС ЖКХ объекта {object_id} не сопоставлен"

            return object_guid

        assert isinstance(producer, Callable), \
            "Требуется формирующая элементы запроса операции функция"
        assert isinstance(subjects, Iterable), \
            "Требуется составляющий элементы запроса набор (данных) объектов"

        object_count: int = 0  # WARN len (: Sized) делает лишний запрос к БД
        elements: list = []

        for subject in subjects:
            if subject is None:  # нет данных?
                continue  # пропускаем

            object_count += 1  # получены данные объекта

            try:
                element = producer(subject)
            except PublicError as error:  # ~ ObjectError
                self.failure(get_mapped_guid(subject), error.message)
            except AssertionError as error:
                self.failure(get_mapped_guid(subject), str(error))
            else:  # без ошибок!
                if not element:  # элемент не сформирован ~ return None?
                    continue  # ошибка (должна быть) сохранена

                elements.append(element)  # добавляем в запрос

        if not elements:  # элементы запроса не сформированы?
            self.flush_guids()  # WARN сохраняем идентификаторы с ошибками

            raise NoRequestWarning("Отсутствуют подлежащие "
                + ('выгрузке в' if self.is_import else 'загрузке из')
                + " ГИС ЖКХ данные")

        self.log(f"Сформировано содержимое {len(elements)} элементов запроса"
            f" операции в ходе обработки (данных) {object_count} объектов")

        return elements

    def _request(self) -> dict:
        """Данные запроса операции"""
        return {**self.request}  # копия запроса или пустой

    def _compose(self) -> dict:
        """
        Сформировать данные на основе аргументов запроса операции

        Возвращаемые данные будут дописаны к подготовленным перед отправкой
        """
        assert not self.is_import or not self._record.object_ids, \
            "Неиспользованные аргументы запроса операции импорта"

        return {}  # по умолчанию аргументы не используются

    def _parse(self, state_result):
        """
        Извлечь результаты выполнения операции из состояния обработки сообщения

        WARN В полученных данных кроме искомого присутствуют пустые
         (None) элементы всех возможных типов результата операции
        """
        if state_result.ErrorMessage:  # : zeep.objects.ErrorMessageType
            # "Нет объектов для экспорта" тоже является ErrorMessage
            raise GisError.from_result(state_result.ErrorMessage)

        unused_element_names = ('Id', 'Signature', 'version',  # ImportResult=[]
            'MessageGUID', 'RequestState', 'ErrorMessage')  # балласт

        # может быть только один элемент с данными, остальные = None
        result_element_name = next(iter(name for name in state_result
            if name not in unused_element_names and state_result[name]),
        None)  # если "Нет объектов для экспорта", то ВСЕ элементы = None
        assert result_element_name, "В результате обработки сообщения" \
            " данные не обнаружены"

        self.log(f"В полученном по квитанции {self.ack_guid}"
            f" сообщении найден элемент {sb(result_element_name)}")

        return state_result[result_element_name]  # результирующий элемент

    def _store(self, export_result_s):
        """
        Сохранить результат(ы) выполнения операции
        """
        self.warning("Сохранение полученного результата"
            " выполнения операции не поддерживается операцией")

    def _map(self, guid: GUID) -> GUID:
        """
        Сопоставить (транспортный) идентификатор операции

        При повторном выполнении операции идентификатор может быть сопоставлен
        """
        assert guid.object_id, f"Идентификатор ГИС ЖКХ {guid.id} не связан" \
            f" с объектом {guid.tag or 'БЕЗ признака'}"

        guid.record_id = self.record_id  # привязываем к (записи об) операции
        guid.transport = self.generated_guid  # : UUID - новый идентификатор

        if guid.tag not in {GisObjectType.ACCRUAL}:  # ошибка как признак?
            guid.error = None  # TODO игнорируем прежнюю ошибку в данных?

        guid.is_changed = True  # (безальтернативно) подлежит сохранению

        self._mapped_guids[guid.object_id] = guid  # ObjectId: GUID

        return guid  # возвращаем сопоставленный идентификатор

    def _unmap(self, guid: GUID):
        """
        Отменить сопоставление идентификатора с операцией
        """
        assert guid.object_id in self._mapped_guids, \
            f"Среди сопоставленных идентификаторов операции нет {guid}"

        self._mapped_guids.pop(guid.object_id)  # не str
        guid.unmap()  # WARN можно не отвязывать - документ не сохраняется

        self.log(warn=f"Отменено сопоставление {guid.tag}:"
            f" {guid.object_id} с транспортным {guid.transport}")

    def created_guid(self,
            object_tag: str, object_id: ObjectId, **field_values) -> GUID:
        """
        Создать новый идентификатор (с данными) ГИС ЖКХ объекта

        Существование не проверяется и идентификатор не сохраняется
        """
        if 'provider_id' not in field_values:  # WARN допускается None
            field_values['provider_id'] = self.provider_id

        if 'desc' not in field_values:  # без описания?
            if object_tag == GisObjectType.ACCRUAL:  # ПД?
                field_values['desc'] = f"№{object_id}"

        return GUID(tag=object_tag, object_id=object_id,
            **field_values)  # WARN подлежит сохранению

    def owned_guid(self,
            object_tag: str, object_id: ObjectId) -> Optional[GUID]:
        """
        Загрузить (сохраненный) идентификатор ГИС ЖКХ объекта
        """
        assert object_tag not in GUID.DATED_TAGS, \
            f"Признак объекта {sb(object_tag)} больше не используется"

        is_shared: bool = object_tag in GUID.SHARED_TAGS

        guid: GUID = GUID.objects(__raw__={
            'tag': object_tag, 'object_id': object_id,
            'provider_id': None if is_shared else self.provider_id,
        }).first()  # или None

        if guid is not None:  # существующий идентификатор?
            self.log("Загружены данные ГИС ЖКХ"
                f" {guid.tag}: {guid.object_id} ~ {guid}")
        elif is_shared:  # несуществующий общий идентификатор?
            private_guids = GUID.objects(__raw__={
                'tag': object_tag, 'object_id': object_id,
                'provider_id': {'$ne': None},  # частные идентификаторы
            }).order_by('-saved')  # : QuerySet

            if private_guids.count() > 1:  # найдено несколько частных версий?
                self.log(warn=f"Найдено {private_guids.count()} частных версий"
                    f" общего идентификатора ГИС ЖКХ {object_tag}: {object_id}")

            guid: GUID = private_guids.first()  # первый с конца - последний
            if guid is not None:  # частный объект с признаком общего?
                self.log(warn=f"Загружены принадлежащие {guid.provider_id}"
                    f" данные общего {guid.tag}: {guid.object_id} ~ {guid}")

        return guid  # возвращаем загруженный идентификатор или None

    def object_guid(self, object_tag: str, object_id: ObjectId) -> GUID:
        """
        Получить (загрузить или создать) идентификатор ГИС ЖКХ объекта
        """
        guid: GUID = self.owned_guid(object_tag, object_id)

        if guid is None:  # идентификатор не найден?
            # WARN общие данные (provider_id=None) корректируются при валидации
            guid: GUID = self.created_guid(object_tag, object_id)  # не сохранен
            self.log(warn="Подлежит сохранению вновь созданный"
                f" идентификатор ГИС ЖКХ {guid.tag}: {guid.object_id}")

        return guid  # возвращаем полученный идентификатор

    def mapped_guid(self, object_tag: str, object_id: ObjectId) -> GUID:
        """
        Получить сопоставленный (с операцией) идентификатор ГИС ЖКХ объекта

        :param object_tag: признак объекта
        :param object_id: идентификатор объекта
        """
        guid: GUID = self.object_guid(object_tag, object_id)

        return self._map(guid)  # сопоставляем идентификатор с операцией

    def owned_guids(self, tag: str, *object_id_s: ObjectId) -> dict:
        """
        Получить загруженные данные (с идентификаторами) ГИС ЖКХ

        :returns: ObjectId: GUID
        """
        assert isinstance(tag, str), \
            "Для загрузки идентификаторов ГИС ЖКХ необходим признак объекта"
        assert object_id_s, f"Нет подлежащих загрузке идентификаторов {sb(tag)}"

        query: dict = {'object_id': {'$in': object_id_s}}

        if tag == GisObjectType.NOTIFICATION:  # извещения о квитировании?
            query['tag'] = GisObjectType.ACCRUAL  # платежные документы
        else:
            query['tag'] = tag

        if tag not in GUID.SHARED_TAGS:
            query['provider_id'] = self.provider_id
        if tag == GisObjectType.AREA:
            query['premises_id'] = self.house_id

        # только имеющие идентификаторы ГИС ЖКХ (gis, root, version, unique)
        if tag in GUID.UNIQUE_TAGS:  # с уникальным номером?
            query['unique'] = {'$ne': None}  # : str
        elif tag in GUID.VERSION_TAGS:  # с идентификатором версии?
            query['version'] = {'$ne': None}  # : UUID
        else:  # с (корневым) идентификатором ГИС ЖКХ?
            query['$or'] = [
                {'gis': {'$ne': None}}, {'root': {'$ne': None}},  # : UUID
            ]  # TODO определить признаки для поиска по корневому идентификатору

        guids: dict = {guid.object_id: guid
            for guid in GUID.objects(__raw__=query)}

        self.log(f"Загружены данные {len(guids)} имеющих идентификаторы"
            f" ГИС ЖКХ {sb(tag)} из {len(object_id_s)} запрошенных")

        return guids

    def mapped_guids(self, object_tag: str, *object_id_s: ObjectId) -> dict:
        """
        Получить сопоставленные операции идентификаторы ГИС ЖКХ

        WARN Полученные идентификаторы добавляются к уже сопоставленным!
        """
        assert isinstance(object_tag, str), \
            "Для получения ид. ГИС ЖКХ необходим признак объектов"
        assert object_tag not in GUID.DATED_TAGS, \
            f"Признак объекта {sb(object_tag)} больше не используется"

        if self._mapped_guids:  # имеются сопоставленные идентификаторы?
            self.log(warn="Дополнительные идентификаторы"
                f" будут добавлены к {len(self._mapped_guids)}"
                f" сопоставленным операции {self.record_id}")

        provider_id: ObjectId = self.provider_id \
            if object_tag not in GUID.SHARED_TAGS else None  # None - общие

        loaded_guids: dict = {guid.object_id: guid  # WARN не owned_guids
            for guid in GUID.objects(__raw__={'provider_id': provider_id,
                'object_id': {'$in': object_id_s}, 'tag': object_tag})}

        created_guids: dict = {}  # создаваемые идентификаторы

        for object_id in object_id_s:  # для всех объектов
            if not isinstance(object_id, ObjectId):  # str?
                object_id = ObjectId(object_id)

            guid: GUID = loaded_guids.get(object_id)  # идентификатор загружен?

            if guid is None:  # идентификатор не загружен?
                guid = self.created_guid(object_tag, object_id,
                    provider_id=provider_id)  # не сохранен (без _id)
                created_guids[object_id] = guid

            self._map(guid)  # сопоставляем идентификатор операции

        self.log(f"Сопоставлены {len(loaded_guids)} загруженных"
            f" и {len(created_guids)} вновь созданных идентификаторов"
            f" ГИС ЖКХ для {len(object_id_s)} запрошенных {sb(object_tag)}")

        return {**created_guids, **loaded_guids}  # имеющиеся поверх созданных!

    def required_guids(self, tag: str, *object_id_s: ObjectId) -> dict:
        """
        Получить требуемые идентификаторы ГИС ЖКХ
        """
        object_name: str = GUID.object_name(tag)

        if not object_id_s:  # нет требуемых объектов?
            self.acquired[tag] = 100  # требования "выполнены"
            self.log(warn="Нет требуемых для выполнения операции"
                f" идентификаторов ГИС ЖКХ {object_name}")
            return {}  # нечего возвращать

        guids: dict = self.owned_guids(tag, *object_id_s)  # WARN данные ГИС ЖКХ

        if not self.has_requirements:  # загрузка не требуется?
            return guids  # возвращаем загруженные идентификаторы

        assert tag in self.REQUIREMENTS, \
            f"Для выполнения операции идентификаторы {sb(tag)} не требуются"
        required: int = self.REQUIREMENTS[tag]

        acquired: int = pct_of(guids, object_id_s)  # загруженных к запрошенным

        already_acquired: bool = (tag in self.acquired)  # повторный запрос?
        self.acquired[tag] = acquired  # записываем полученный процент

        if acquired >= required:  # требование удовлетворено?
            self.log(info="Загружены достаточные для выполнения операции"
                f" {acquired}% идентификаторов ГИС ЖКХ {object_name}")
            return guids  # возвращаем загруженные идентификаторы

        self.log(warn=f"Загружены {acquired}% из требуемых"
            f" {required}% идентификаторов ГИС ЖКХ {object_name}")

        if already_acquired:  # повторный запрос?
            raise NoGUIDError("Не загружены требуемые для выполнения"
                f" операции идентификаторы ГИС ЖКХ {object_name}")

        return guids  # возвращаем загруженные идентификаторы

    def is_required(self, tag: str) -> bool:
        """Требуется (предварительная) загрузка идентификаторов?"""
        assert tag in self.REQUIREMENTS, \
            f"Для выполнения операции идентификаторы {sb(tag)} не требуются"

        if not self.has_requirements:  # операция без требований (test_mode)?
            return False  # WARN загрузка выполняется в debug_mode
        elif self.is_forced:  # принудительное выполнение?
            self.log(warn=f"Загрузка требуемых идентификаторов {sb(tag)}"
                " не выполняется при принудительном выполнении операции")
            return False

        # TODO не загружаем при отсутствии доли требуемых идентификаторов?
        return self.acquired.get(tag, 100) < self.REQUIREMENTS[tag]

    def _purge_guids(self):
        """
        Очистить сопоставленные идентификаторы операции
        """
        if self._mapped_guids:  # имеются сопоставленные идентификаторы?
            self.log(warn=f"Не подлежат сохранению {len(self._mapped_guids)} "
                f"сопоставленных идентификаторов операции {self.record_id}:\n\t"
                + ', '.join(f"{key} ~ {guid.object_id}"
                    for key, guid in self._mapped_guids.items()))

        self._mapped_guids = {}  # WARN данные ГИС ЖКХ (GUID) не удаляются

    def flush_guids(self):
        """
        Сохранить (измененные) сопоставленные идентификаторы операции
        """
        if not self._mapped_guids:  # нет сопоставленных идентификаторов?
            self.log(info="Отсутствуют (подлежащие сохранению)"
                f" сопоставленные идентификаторы операции {self.record_id}")
            return

        pending_guids: dict = {key: guid
            # ключом сопоставления может быть object_id, transport и др.
            for key, guid in self._mapped_guids.items()
                if key is not None and guid.is_pending}  # подлежащие сохранению
        if not pending_guids:  # нет подлежащих сохранению идентификаторов?
            self.log(info="Отсутствуют подлежащие сохранению"
                f" (измененные) идентификаторы операции {self.record_id}")
            self._purge_guids()  # WARN очищаем сопоставленные идентификаторы
            return

        self.log(f"Выполняется сохранение {len(pending_guids)}"
            f" сопоставленных идентификаторов операции {self.record_id}")

        # необязательный вспомогательный модуль: pip install mongoengine_mate
        from pymongo import InsertOne, ReplaceOne, DeleteOne

        requests: dict = {}  # "запросы" на изменение данных в БД

        for key, guid in pending_guids.items():
            assert isinstance(guid, GUID) and guid.object_id not in requests
            guid.validate()  # валидация и очистка (saved) данных идентификатора

            if guid.is_deleted:  # подлежит удалению?
                requests[guid.object_id] = DeleteOne({'_id': guid.id})
            elif guid.id:  # существующий (сохраненный) идентификатор?
                requests[guid.object_id] = ReplaceOne(  # Update не удаляет поля
                    filter={'_id': guid.id},  # поиск по первичному ключу
                    replacement=guid.to_mongo().to_dict(),  # : dict
                    upsert=False)  # не создавать новые документы
            else:  # вновь созданный идентификатор ~ БЕЗ первичного ключа?
                requests[guid.object_id] = InsertOne(guid.to_mongo().to_dict())

            # WARN mapped_guids нужен для сохранения после извлечения результата
            del self._mapped_guids[key]  # удаляем из сопоставленных

        assert requests, \
            "Список подлежащих сохранению идентификаторов не сформирован"
        # TODO ошибки сохранения ид-ов обрабатываются внешним контекстом
        write_result = GUID.write([*requests.values()])  # записываем данные

        self.log(info=f"В результате записи {len(pending_guids)} GUID"
            f" создано {write_result.inserted_count} новых,"
            f" обновлено {write_result.matched_count} и"
            f" удалено {write_result.deleted_count} существующих")

        self._purge_guids()  # WARN очищаем сопоставленные идентификаторы

    def _is_consistent(self,
            is_not_canceled: bool = True, is_not_stored: bool = True,
            is_not_stated: bool = True, is_not_acked: bool = True):
        """
        Проверить состояние (выполнения) операции
        """
        if self.is_forced:  # выполнять операцию в любом состоянии?
            self.log(warn="Установлен флаг принудительного выполнения операции"
                " вне зависимости от текущего состояния")
        elif is_not_canceled and self.is_canceled:  # операция отменена?
            raise CancelSignal()  # возбуждаем специальное исключение
        elif is_not_stored and self.is_stored:  # результат сохранен?
            raise ConsistencyError("Результат выполнения операции"
                " уже получен и сохранен")  # возбуждаем специальное исключение
        elif is_not_stated and self.is_stated:  # состояние получено?
            raise ConsistencyError("Состояние (с результатом) выполнения"
                " операции уже получено")  # возбуждаем специальное исключение
        elif is_not_acked and self.is_acked:  # квитанция получена?
            raise ConsistencyError("Квитанция о постановке сообщения на"
                " обработку уже получена")  # возбуждаем специальное исключение

    def _ack_request(self, request_data: dict) -> UUID:
        """
        Запросить квитанцию о приеме (в очередь) на обработку сообщения
        """
        assert request_data, \
            "Для выполнения операции требуется сформировать данные запроса"

        self._is_consistent()  # проверяем текущее состояние операции

        try:  # исключения кроме перезапуска обрабатываются менеджером контекста
            ack_result = self._client.send_message(self.WSDL_NAME or self.name,
                self._soap_header,  # с идентификатором сообщения запроса
                request_data)  # : zeep.objects.AckRequest
        except RestartSignal as restart:  # запрошен перезапуск запроса?
            if self.restarts < self.MAX_RESTART_COUNT:  # возможен?
                self._record.restarts = self.restarts + 1  # следующая попытка
                self.log(warn=f"Запланирована {self.restarts} повторная"
                    f" отправка сообщения {self.message_guid}"
                    f" из {self.MAX_RESTART_COUNT} возможных"
                    f" через {self.RESTART_DELAY} сек.")
                sleep(self.RESTART_DELAY)  # ожидание перед повторной отправкой
                ack_result = self._ack_request(request_data)  # отправка запроса
            else:  # лимит попыток отправки запроса исчерпан!
                raise restart.reason  # возбуждаем оригинальное исключение
        # finally:  # выполняется при любых обстоятельствах!
        #     if self.debug_mode:  # в режиме отладки?
        #         self._save_xml_files(response_prefix='ack')

        if 'Ack' not in ack_result:  # ~ hasattr
            raise GisError('GIS',
                "Нарушена структура ответа на запрос квитанции")

        ack = ack_result.Ack  # : { MessageGUID, RequesterMessageGUID }
        assert ack.RequesterMessageGUID == str(self.message_guid), \
            "Возвращенный идентификатор сообщения не совпадает с переданным"

        return UUID(ack.MessageGUID)  # : str - Ид. сообщения ГИС ЖКХ

    def _spread(self) -> GisRecord:
        """
        Распределить аргументы запроса операции
        """
        assert len(self.object_ids) > self.element_limit > 0, \
            "Распределение аргументов запроса не требуется"

        # WARN запись о порождающей операции сохраняется менеджером
        child_record: GisRecord = self._record.heir(self.element_limit)
        assert self.child_id == child_record.generated_id, \
            "Связь порождающей операции с порожденной не установлена"
        assert child_record.object_ids, \
            "Отсутствуют аргументы запроса порожденной записи об операции"

        child_record.save()  # WARN сохраняем порожденную запись об операции

        self.log(info=f"Порожденная от {self.record_id}"
            f" запись об операции {child_record.generated_id} получила"
            f" {len(child_record.object_ids)} аргументов запроса")

        return child_record

    def _preload(self):
        """
        Загрузить требуемые для выполнения операции данные

        Метод выполняется до формирования (распределения аргументов) запроса
        """
        assert not self.REQUIREMENTS, "Метод загрузки требуемых" \
            " для выполнения операции данных не реализован"

        self.log(info="Загрузка необходимых для выполнения"
            f" операции {self.record_id} данных не требуется")

    def make_request(self):
        """
        Сформировать и отправить сообщение (с запросом) в ГИС ЖКХ
        """
        with self.manager(GisManagerContext.SPREAD) as context:  # безусловно
            self._purge_guids()  # инициализируем сопоставления

            self._preload()  # WARN выбрасывает откладывающее исключение
            self._record.pending_id = None  # предшествующей нет или выполнена

            if len(self.object_ids) > self.element_limit > 0:  # по умолчанию 0
                self._spread()  # WARN создается связь порождающей с порожденной
            else:  # ограничения количества аргументов нет или удовлетворено!
                self.log("Ограничение количества аргументов запроса"
                    f" операции {self.record_id} не требуется")

            if self._record.desc is None:  # описание не сформировано?
                self._record.desc = self.description  # формируем описание
            self.set_status(GisRecordStatusType.REQUEST)  # Формируется

        if context.exception:  # получено предупреждение?
            if self.pending_id:  # операция поставлена в очередь?
                self.execute(self.pending_id)  # выполняем упреждающую операцию

            # WARN предупреждение подавляется в задаче send_request
            raise context.exception  # завершаем выполнение текущей операции

        self.log("Формирование данных запроса операции ГИС ЖКХ"
            f" с идентификатором сообщения {self.message_guid}")

        with self.manager(GisManagerContext.REQUEST) as context:  # при ошибке
            if self._mapped_guids:  # предварительно сопоставлены?
                self.log(f"Идентификаторы операции {self.record_id}"
                    " сопоставлены до начала формирования запроса")

            # перед формированием создается (изменяемая) копия данных запроса
            request_data: dict = deep_update(self._request(), self._compose())
            # проверяем наличие (непустых) элементов запроса операции
            if not request_data:  # запрос не сформирован?
                raise NoRequestWarning("Запрос операции не сформирован")
            assert all(v is not None for v in request_data.values()), \
                "Запрос операции не должен содержать пустые элементы"
            if 'version' not in request_data:  # без версии схем сервиса?
                assert self.VERSION, \
                    "Версия (по умолчанию) схем сервиса операции не определена"
                request_data['version'] = self.VERSION  # по умолчанию

            if self['request_only']:  # формирование запроса операции?
                self._log(info=json(request_data))  # WARN не в log записи
                raise CancelSignal("Выполнение операции отменено"
                    " в режиме тестирования (формирования) запроса")

            self.flush_guids()  # WARN сохраняем подготовленные идентификаторы

        if self.child_id and not self.is_forced:  # порожденная операция?
            self.log(info=f"Выполняется следующая за {self.record_id}"
                f" порожденная {self.parent_id or 'текущей'} операция"
                    f" с идентификатором записи {self.child_id}")
            self.execute(self.child_id)  # выполняем порожденную операцию

        # WARN проверка предупреждения ПОСЛЕ запуска порожденной операции
        if context.exception:  # при формировании получено предупреждение?
            # WARN предупреждение подавляется в задаче send_request
            raise context.exception  # завершаем выполнение текущей операции

        self.log("Отправка в ГИС ЖКХ сформированного запроса"
            f" с идентификатором сообщения {self.message_guid}")

        with self.manager(GisManagerContext.ACK):  # безусловно
            # отправляем запрос и получаем идентификатор квитанции
            self._record.ack_guid = self._ack_request(request_data)
            self._record.acked = get_time()  # время получения подтверждения
            self.set_status(GisRecordStatusType.EXECUTING)  # Выполняется

            self._record.stated = None  # обнуляем время получения состояния
            self._record.stored = None  # обнуляем время сохранения результата

            self._record.retries = None  # обнуляем попытки поучения состояния
            # время запроса состояния (с результатом) обработки сообщения
            self._record.scheduled = get_time(ms=0,  # без микросекунд
                seconds=self.get_state_delay)  # зависящая от попытки отсрочка

        self.log(f"Получена квитанция {self.ack_guid} о приеме"
            f" сообщения {self.message_guid} на обработку")

    def proceed(self):
        """
        Инициировать получение состояния (с результатом) выполнения операции
        """
        assert not self.has_error, "Операция с ошибкой не может быть продолжена"

        from app.gis.tasks.async_operation import fetch_result

        self.log(info="Запрос состояния обработки сообщения по квитанции"
            f" {self.ack_guid} через {self.get_state_delay} сек.")

        sleep(self.get_state_delay)  # WARN ETA и COUNTDOWN не(надежно) работают

        if self.is_synchronous:  # последовательный режим выполнения?
            self.log(warn="Инициировано получение состояния"
                f" (с результатом) выполнения операции {self.record_id}"
                " в последовательном режиме")
            return fetch_result.apply(  # завершаем выполнение операции
                args=(self.record_id, self.is_forced),
            )  # немедленно запускаем получение результата

        fetch_result.apply_async(  # асинхронное выполнение задачи
            args=(self.record_id, self.is_forced),
            eta=self.scheduled,  # countdown=self.get_state_delay
        )  # ставим в очередь задачу получения результата

    def _get_state(self):
        """
        Запросить состояние обработки сообщения

        :returns: getStateResult без Id, Signature, MessageGUID, version
        """
        assert self.ack_guid, \
            "Для запроса состояния выполнения операции требуется ид. квитанции"

        self._is_consistent(is_not_acked=False)  # проверяем текущее состояние

        try:  # исключения кроме перезапуска обрабатываются менеджером контекста
            state_result = self._client.send_message(GisOperationType.GET_STATE,
                self._soap_header,  # с новым идентификатором сообщения
                {'MessageGUID': self.ack_guid})  # : getStateResult
        except RestartSignal as restart:  # запрошен перезапуск запроса?
            if self.restarts < self.MAX_RESTART_COUNT:  # возможен?
                self._record.restarts = self.restarts + 1  # следующая попытка
                self.log(warn=f"Запланирован {self.restarts} повторный"
                    f" запрос состояния по квитанции {self.ack_guid}"
                    f" из {self.MAX_RESTART_COUNT} возможных"
                    f" через {self.RESTART_DELAY} сек.")
                sleep(self.RESTART_DELAY)  # ожидание перед повторным запросом
                state_result = self._get_state()  # повторный запрос состояния
            else:  # лимит попыток отправки запроса исчерпан!
                raise restart.reason  # возбуждаем оригинальное исключение
        # finally:  # выполняется при любых обстоятельствах!
        #     if self.debug_mode:  # в режиме отладки?
        #         self._save_xml_files('get', 'state')

        # region УДАЛЯЕМ БАЛЛАСТ
        if 'Id' in state_result:  # WARN может (ошибочно) отсутствовать
            del state_result['Id']  # ~ signed-data-container
        if 'Signature' in state_result:  # Необязательное(?)
            del state_result['Signature']  # подпись сообщения ГИС ЖКХ
        if 'MessageGUID' in state_result:
            del state_result['MessageGUID']  # идентификатор сообщения ГИС ЖКХ
        if 'version' in state_result:
            del state_result['version']  # используемая версию схем сервиса
        # endregion УДАЛЯЕМ БАЛЛАСТ

        return state_result  # ErrorMessage, ImportResult или export[...]Result

    def _suited(self, state_result) -> bool:
        """
        Проверить состояние выполнения операции

        :param state_result: getStateResult
        """
        request_state: int = state_result.RequestState  # : enum
        del state_result['RequestState']  # удаляем состояние обработки

        state = UnstatedError(request_state)  # исключение состояния обработки

        if state.is_successful:  # сообщение обработано?
            return True  # WARN не возбуждаем исключение состояния обработки

        self._record.retries = self.retries + 1  # следующая попытка
        max_retries: int = len(self.GET_STATE_DELAY)  # макс. кол-во попыток

        if state.is_processing:  # сообщение в обработке?
            self.log(f"Сообщение {self.message_guid} в обработке ГИС ЖКХ после"
                f" {self.retries} попытки получения результата")

            task_delay: int = self.GET_RESULT_DELAY  # фиксированная задержка
        else:  # сообщение получено (в очереди на обработку) ГИС ЖКХ!
            self.log(f"Сообщение {self.message_guid} {state.name} ГИС ЖКХ после"
                f" {self.retries} попытки из {max_retries} возможных")

            if self.retries >= max_retries:  # больше нет попыток?
                raise state.FATAL_ERROR  # безрезультатная операция

            task_delay: int = self.get_state_delay  # зависит от кол-ва попыток

        # время следующего запроса состояния обработки (без микросекунд)
        self._record.scheduled = get_time(ms=0, seconds=task_delay)

        if self.is_synchronous:  # последовательный режим выполнения?
            self.log(info="Повторный запрос состояния обработки сообщения"
                f" по квитанции {self.ack_guid} через {task_delay} сек.")
            sleep(task_delay)  # TODO ETA не работает с apply!
        else:  # стандартный режим выполнения операции!
            formatted_time: str = self.scheduled.strftime('%H:%M:%S')  # UTC+3
            self.log(info="Повторный запрос состояния обработки сообщения"
                f" по квитанции {self.ack_guid} в {formatted_time}")

        raise state  # возбуждаем исключение состояния обработки сообщения

    def _restore_mapping(self):
        """
        Восстановить сопоставленные идентификаторы операции
        """
        self._purge_guids()  # инициализируем сопоставления

    def get_result(self):
        """
        Запросить из ГИС ЖКХ и сохранить результат(ы) обработки сообщения
        """
        self.log("Запрос состояния обработки ГИС ЖКХ"
            f" сообщения по квитанции {self.ack_guid}")

        with self.manager(GisManagerContext.STATE):  # безусловно
            self._record.error = None  # обнуляем сообщение об ошибке
            self._record.trace = None  # обнуляем описание ошибки

            # неудовлетворительное состояние обработки пробрасывается в задачу
            state_result = self._get_state()  # запрашиваем состояние обработки

            self._suited(state_result)  # WARN выбрасывает исключение

            self._record.stated = get_time()  # время получения состояния
            self.set_status(GisRecordStatusType.PROCESSING)  # Обработка

            self._record.scheduled = None  # обнуляем время запроса состояния(?)
            self._record.stored = None  # обнуляем время сохранения результата
            self._record.fails = 0  # обнуляем количество ошибок в данных

            if self['result_only']:  # получение результата выполнения операции?
                self._log(info=json(state_result))  # WARN не в log записи
                raise CancelSignal("Сохранение данных отменено в режиме"
                    " получения (состояния) результата выполнения операции")

        self.log("Извлечение результата обработки сообщения"
            f" {self.message_guid} по квитанции {self.ack_guid}")

        with self.manager(GisManagerContext.PARSE) as context:  # при ошибке
            self._restore_mapping()  # загружаем сопоставленные идентификаторы

            parsed_results = self._parse(state_result)  # извлекаем результат(ы)

            if not parsed_results:  # безрезультатная операция?
                raise NoResultWarning()  # сообщение по умолчанию

        if context.exception:  # при извлечении получено предупреждение?
            self.flush_guids()  # сохраняем идентификаторы с ошибками

            # WARN предупреждение подавляется в задаче fetch_result
            raise context.exception  # завершаем выполнение текущей операции

        self.log("Сохранение извлеченных из результата обработки"
            f" полученных по квитанции {self.ack_guid} данных")

        with self.manager(GisManagerContext.STORE):  # безусловно
            # WARN идентификаторы с ошибками удалены из сопоставленных
            self._store(parsed_results)  # вызываем метод сохранения данных

            self.flush_guids()  # сохраняем полученные идентификаторы

            self._record.stored = get_time()  # фиксируем время сохранения
            self.set_status(GisRecordStatusType.DONE)  # Завершена или Выполнена

    def conclude(self):
        """
        Завершить выполнение текущей операции
        """
        assert not self.has_error, "Операция с ошибкой не может быть завершена"

        if not self.follower_id:  # без последующей операции?
            self.log("Отсутствует последующая за завершаемой"
                f" с идентификатором {self.record_id} операция")
        elif self.is_complete and not self.is_forced:  # завершена?
            assert self.follower_id != self.record_id, \
                "Идентификатор записи последующей операции совпадает с текущим"
            self.log(info="Инициируется выполнение последующей"
                f" за {self.record_id} операции {self.follower_id}")

            self.execute(self.follower_id)  # выполняем последующую операцию

    def lead(self, follower: 'AsyncOperation') -> 'AsyncOperation':
        """
        Поставить последующую операцию в очередь за текущей

        export_org().lead(
            export_nsi(p).lead(
                import_nsi(p, update_existing=False).lead(
                    export_area(p, h).lead(
                        export_acc(p, h).lead(
                            import_acc(p, h, update_existing=False).lead(
                                export_dev(p, h).lead(
                                    import_dev(p,h, update_existing=False).lead(
                                        import_pd(p, h)
        )))))))).execution()
        """
        if self.follower_id:  # последующая у текущей?
            follower._record.follower_id = self.follower_id  # в очередь

        self._record.follower_id = follower.record_id  # ид. последующей

        follower._record.pending_id = self.record_id  # ид. упреждающей
        follower.set_status(GisRecordStatusType.PENDING)  # Отложена

        self.log(warn=f"Последующая операция {follower.record_id}"
            f" поставлена в очередь за текущей {self.record_id}")

        # WARN подлежат сохранению обе записи об операциях
        return self  # возвращаем предшествующую операцию

    def follow(self, leader: 'AsyncOperation') -> 'AsyncOperation':
        """
        Поставить текущую операцию в очередь за упреждающей

        import_pd(p, h).follow(
            import_dev(p, h, update_existing=False).follow(
                export_dev(p, h).follow(
                    import_acc(p, h, update_existing=False).follow(
                        export_acc(p, h).follow(
                            export_area(p, h).follow(
                                import_nsi(p, update_existing=False).follow(
                                    export_nsi(p).follow(
                                        export_org().execution()
        ))))))))
        """
        if leader.follower_id:  # последующая у упреждающей?
            self._record.follower_id = leader.follower_id  # в очередь

        leader._record.follower_id = self.record_id  # идентификатор последующей

        self._record.pending_id = leader.record_id  # ид. упреждающей
        self.set_status(GisRecordStatusType.PENDING)  # Отложена

        self.log(warn=f"Операция {self.record_id} поставлена"
            f" в очередь после упреждающей {leader.record_id}")

        # WARN подлежат сохранению обе записи об операциях
        return self  # возвращаем последующую операцию

    def cancel(self):
        """
        Отменить выполнение операции и сопутствующих (порожденных и последующих)
        """
        if not self.has_error:  # не в результате ошибки?
            self.set_status(GisRecordStatusType.CANCELED)  # Отменена

        canceled: list = self._record.cancel()  # WARN только сопутствующие
        if canceled:
            self.log(warn=f"Отменено выполнение {len(canceled)}"
                " сопутствующих текущей (невыполненных) операций: "
                    + ', '.join(str(_id) for _id in canceled))

    def warning(self, message: str):
        """
        Предупреждение в процессе выполнения операции
        """
        self._record.warning(message)  # добавляем в запись об операции
        self._log(warn=message)  # WARN исключено из журнала операции

        self.set_status(GisRecordStatusType.WARNING)  # Выполнена

    def error(self, message: str = None, detail: str = None):
        """
        Ошибка в процессе выполнения операции
        """
        assert message, "Отсутствует текст сообщения об ошибке операции"

        self.set_status(GisRecordStatusType.ERROR)  # Не выполнена

        if not detail:  # только сообщение об ошибке?
            self._record.error = message  # записываем сообщение об ошибке
            self._record.trace = None  # обнуляем описание ошибки

            self._log(error=message)  # WARN исключено из журнала операции
        else:  # сообщение и описание ошибки!
            self._record.error = message  # записываем сообщение об ошибке
            self._record.trace = detail  # записываем описание ошибки

            self._log(error=f"{message}\n{detail}")  # WARN исключено из журнала

        self.cancel()  # WARN отменяем сопутствующие текущей операции

    def _check_mapping(self, guid: GUID) -> bool:
        """Проверить принадлежность идентификатора операции"""
        assert guid.record_id == self.record_id, "Идентификатор ГИС ЖКХ" \
            f" {guid.tag}: {guid.object_id} не сопоставлен с текущей операцией"

        return True

    def success(self, guid: GUID, gis: str or UUID = None,
            root: str or UUID = None, version: str or UUID = None,
            unique: str = None, number: str = None, updated: datetime = None):
        """
        Получены данные сущности ГИС ЖКХ

        :param guid: документ идентификатора ГИС ЖКХ
        :param gis: идентификатор (версии) сущности ГИС ЖКХ
        :param root: идентификатор корневой (изначальной) сущности ГИС ЖКХ
        :param version: идентификатор текущей версии сущности ГИС ЖКХ
        :param unique: уникальный номер ГИС ЖКХ
        :param number: специфичный номер объекта
        :param updated: дата и время последнего обновления
        """
        guid.unmap()  # WARN может быть не привязан к текущей (записи) операции

        guid.deleted = None  # обнуляем (прежнюю) дату аннулирования

        if gis:
            guid.gis = gis  # str будет преобразован в UUID
        if root:
            guid.root = root
        if version:
            guid.version = version
        if unique:
            guid.unique = unique
        if number:
            guid.number = number
        if updated:
            guid.updated = mongo_time(updated)  # без временной зоны

        guid.is_changed = True  # (безальтернативно) подлежит сохранению

        self.log(info="Подлежат сохранению данные ГИС ЖКХ"
            f" {guid.tag}: {guid.object_id} ~ {guid}")

    def failure(self, guid: GUID, error_message: str):
        """
        Ошибка обработки сущности ГИС ЖКХ

        WARN fail() - метод unit-тестирования, считается завершающим код
        """
        self._check_mapping(guid)  # WARN assert

        # WARN не обнуляем идентификаторы (unmap) для локализации ошибки

        guid.error = error_message  # записываем сообщение об ошибке

        guid.is_changed = True  # (безальтернативно) подлежит сохранению

        self._record.fail()  # учитываем ошибку в данных объекта

        self.log(error="Ошибка обработки"
            f" {guid.tag}: {guid.object_id} ~ {error_message}")

    def annulment(self, guid: GUID, updated: datetime = None, gis: str = None):
        """
        Аннулирование сущности ГИС ЖКХ

        Сам идентификатор не удаляется, как и запись в ГИС ЖКХ
        Для удаления идентификатора из БД используется guid.delete()

        :param guid: документ данных ГИС ЖКХ

        :param updated: дата (и время) модификации
        :param gis: идентификатор ГИС ЖКХ сущности
        """
        self._check_mapping(guid)  # WARN assert

        gis_guid: UUID = as_guid(gis)  # или None
        if not gis_guid:  # не получен?
            self.log(warn="Идентификатор ГИС ЖКХ аннулированного"
                f" {guid.tag}: {guid.object_id} не прошел проверку")
        elif not guid.gis:  # не сохранен?
            guid.gis = gis_guid
        elif guid.gis != gis_guid:  # изменен?
            self.log(warn=f"Идентификатор ГИС ЖКХ {guid.gis}"
                f" аннулированного {guid.tag}: {guid.object_id}"
                f" отличается от полученного {gis_guid}")

        if guid.gis:  # получены данные ГИС ЖКХ?
            guid.unmap()  # WARN подлежит сохранению

        if not guid.deleted or updated:  # нет прежней или получена новая?
            guid.deleted = mongo_time(updated)  # или текущие дата и время

        guid.is_changed = True  # (безальтернативно) подлежит сохранению

        self.log(info=f"Данные ГИС ЖКХ {guid.tag}: {guid.object_id}"
            f" ~ {guid} аннулированы {fmt_period(guid.deleted, True)}")

    def deletion(self, guid: GUID):
        """
        Удаление идентификатора ГИС ЖКХ
        """
        self._check_mapping(guid)  # WARN assert

        guid.is_deleted = True  # WARN подлежит удалению (при сохранении)

        self.log(warn="Подлежат удалению данные ГИС ЖКХ"
            f" {guid.tag}: {guid.object_id} ~ {guid}")

    def _schedule(self, guid: GUID):
        """
        Поставить данные объекта в очередь на выгрузку в ГИС ЖКХ
        """
        if not self['export_changes']:  # не выгружать изменения?
            self.failure(guid, "Выгрузка изменений не выполняется")
            return  # не подлежит постановке в очередь на выгрузку

        guid.unmap()  # отвязываем от операции

        guid.is_changed = True  # (безальтернативно) подлежит сохранению

        from app.gis.models.gis_queued import GisQueued
        GisQueued.export(guid.tag, guid.object_id, self.house_id)

        self.log(warn=f"Данные объекта {guid.tag}: {guid.object_id}"
            " подлежат плановой выгрузке в ГИС ЖКХ")

    def _save_xml_files(self,
            request_prefix: str = 'request', response_prefix: str = 'response'):

        sent_envelope: bytes = self._client.debug_plugin.sent_envelope
        if sent_envelope:
            file_name: str = \
                f"{request_prefix}_{self.message_guid}_{self.retries}.xml"
            file_id, file_uuid = put_file_to_gridfs('GisRecord', self.record_id,
                sent_envelope, None,  # uuid будет сгенерирован и возвращен
                file_name, self.provider_id)  # uploader
            self.log(warn=f"Файл запроса {sb(file_name)}"
                f" сохранен с идентификатором {file_id}")

        received_envelope: bytes = self._client.debug_plugin.received_envelope
        if received_envelope:
            file_name: str = \
                f"{response_prefix}_{self.message_guid}_{self.retries}.xml"
            file_id, file_uuid = put_file_to_gridfs('GisRecord', self.record_id,
                received_envelope, None,  # uuid будет сгенерирован и возвращен
                file_name, self.provider_id)  # uploader
            self.log(warn=f"Файл ответа на запрос {sb(file_name)}"
                f" сохранен в идентификатором {file_id}")


if __name__ == '__main__':

    i = ObjectId('644267888b653035714c8960')
    f = AsyncOperation.get_xml_file(i, True)
    print(f)
