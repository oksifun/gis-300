from bson import ObjectId

from app.gis.core.async_operation import AsyncOperation
from app.gis.core.exceptions import UnstatedError, GisWarning, PendingSignal
from app.gis.workers.config import gis_celery_app


@gis_celery_app.task(name='gis.send_request', ignore_result=True,  # БЕЗ bind
    soft_time_limit=60*10,  # максимальная длительность выполнения задачи в сек.
    default_retry_delay=300, max_retries=None)  # без ограничения кол-ва попыток
def send_request(record_id: ObjectId, forced: bool = False):  # БЕЗ self
    """
    Сформировать запрос и отправить в ГИС ЖКХ согласно записи об операции

    Исключения выбрасываются и прекращают выполнение задачи
    """
    from billiard.exceptions import SoftTimeLimitExceeded  # WARN pickle

    # WARN ошибка при загрузке записи об операции не отображается в консоли
    _operation = AsyncOperation.load(record_id, forced)  # экземпляр операции

    try:  # исключения других типов обрабатываются менеджером контекста
        _operation.make_request()  # формируем и отправляем запрос операции

        if _operation.is_acked:  # получена квитанция о приеме сообщения?
            _operation.proceed()  # продолжаем выполнение операции
    except (GisWarning, PendingSignal):  # получено предупреждение или сигнал?
        if not _operation.is_synchronous:  # асинхронное выполнение операции?
            raise  # возбуждаем полученное исключение
        # WARN иначе подавляем
    except SoftTimeLimitExceeded:  # превышен SOFT-лимит выполнения задачи?
        _operation.error("Превышено ограничение по времени"
            " выполнения задачи отправки запроса операции")
        _operation.save()  # WARN сохраняем запись об операции с ошибкой
        raise  # возбуждаем полученное исключение


@gis_celery_app.task(name='gis.fetch_result', ignore_result=True,  # БЕЗ bind
    soft_time_limit=60*20,  # максимальная длительность выполнения задачи в сек.
    default_retry_delay=300, max_retries=None)  # без ограничения кол-ва попыток
def fetch_result(record_id: ObjectId, forced: bool = False):  # БЕЗ self
    """
    Запросить и обработать результат выполнения операции по ид-у записи

    Исключения выбрасываются и прекращают выполнение задачи
    """
    from billiard.exceptions import SoftTimeLimitExceeded  # WARN pickle

    # WARN ошибка при загрузке записи об операции не отображается в консоли
    _operation = AsyncOperation.load(record_id, forced)  # экземпляр операции

    try:  # исключения других типов обрабатываются в менеджере контекста
        _operation.get_result()  # запрашиваем и обрабатываем результат(ы)

        if _operation.is_stated:  # получен(ы) результат(ы) выполнения операции?
            _operation.conclude()  # завершаем выполнение операции
    except GisWarning:  # при извлечении получено предупреждение?
        pass  # WARN подавляем полученное исключение
    except UnstatedError:  # неудовлетворительное состояние обработки?
        # max_retries=_operation.max_state_retries,  # единожды
        # exc=exc.FATAL_ERROR,  # вместо MaxRetriesExceededError
        # счетчика попыток задачи (Celery) не является надежным
        # у выполняемой впервые задачи счетчик self.request.retries = 0
        raise fetch_result.retry(
            eta=_operation.scheduled  # countdown=_operation.get_state_delay
        )
    except SoftTimeLimitExceeded:  # превышен SOFT-лимит выполнения задачи?
        _operation.error("Превышено ограничение по времени"
            " выполнения задачи получения результата операции")
        _operation.save()  # WARN сохраняем запись об операции с ошибкой
        raise  # возбуждаем полученное исключение


if __name__ == '__main__':

    from mongoengine_connections import register_mongoengine_connections
    register_mongoengine_connections()

    r = ObjectId("64e32aa88b65302e816da6dd")

    # send_request.apply(args=(r, True)); exit()
    fetch_result.apply(args=(r, True))  # WARN последующая не запускается
