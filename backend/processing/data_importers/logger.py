from logging import Logger, getLogger, basicConfig, \
    NOTSET, DEBUG, INFO, WARNING, ERROR, FATAL

from processing.models.logging.gis_log import GisImportStatus
from processing.models.tasks.gis.base import GisBaseExportTask


class GisImportLogger(Logger):

    def __init__(self, import_task: GisBaseExportTask, level=INFO):

        self._import_task = import_task

        self._debug_logger = get_debug_logger()

        super().__init__(__name__, level)

    def _log(self, level, msg, args, **kwargs):  # msg % args

        self._debug_logger.log(level, msg, *args, **kwargs)  # TODO всегда?

        if level not in {NOTSET, DEBUG}:
            is_error: bool = level in {FATAL, ERROR}

            GisImportStatus(  # date = datetime.now по умолчанию
                status='ошибка' if is_error
                    else 'неудача' if level == WARNING
                    else 'успешно' if level == INFO
                    else 'OK',
                task=self._import_task.parent.id,
                is_error=is_error,
                description=msg,
            ).save()


def get_debug_logger(min_level: int = DEBUG) -> Logger:

    from sys import stdout
    basicConfig(level=NOTSET, stream=stdout)  # сброс глобального уровня журнала

    logger = getLogger(__name__)  # журнал имени модуля
    logger.setLevel(min_level)

    return logger
