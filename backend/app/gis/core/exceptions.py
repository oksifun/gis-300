from re import search


class GisWarning(Exception):
    """Предупреждение не вызывающее (аварийного) завершения операции"""

    def __init__(self, notification: str):

        super().__init__(notification)


class GisError(Exception):
    """Общий предок связанных с ГИС ЖКХ исключений"""

    CUSTOM_DETAILS = {
        'AUT011002': "Возможно, изменен сервер (ППАК ~ СИТ) ГИС ЖКХ",
        'AUT011003': "Дом (в данный момент) не обслуживается организацией",
        'AUT011009': "Не предоставлен доступ или необходимые права ИС",
        'INT002000': "Дом не найден по ФИАС или не указан в ДУ (Уставе)",
        'INT002012': "По запросу в ГИС ЖКХ ничего не найдено",
        'INT002031': "Идентификатор ГИС ЖКХ дома изменился или устарел",
        'SRV007079': "Загружены элементы справочника другого сервера",
    }

    WARNING_CODES = {'INT002012', }  # пропускаемые исключения

    @staticmethod
    def _parse_details(error_details: str) -> str:
        """Извлечь детальное описание ошибки"""
        pattern = r'.*Message:[^:]*: (.+?)\n: ru.lanit.*'  # НЕ для ошибок INT
        regex_match = search(pattern, error_details)

        error_details = regex_match.group(1) if regex_match else \
            error_details.split('\n')[0]  # первая строка трассировки стека

        return error_details

    @staticmethod
    def message_of(*error_s) -> str:
        """
        Сформировать общее сообщение полученных ошибок ГИС ЖКХ
        """
        descriptions: list = []

        for error in error_s:  # : ErrorMessageType
            if error.StackTrace:  # получено детальное описание ошибки?
                error_details = GisError._parse_details(error.StackTrace)
                descriptions.append(f"{error.Description} ~ {error_details}")
            else:  # без ErrorCode и StackTrace
                descriptions.append(error.Description)

        return '\n'.join(descriptions)

    @classmethod
    def from_result(cls, error_message) -> 'GisError' or 'GisWarning':
        """
        Составить исключение из ошибки ГИС ЖКХ

        :param error_message: zeep.objects.ErrorMessageType

        :returns: GisException или GisWarning
        """
        error_code: str = getattr(error_message, 'ErrorCode', None)
        description: str = getattr(error_message, 'Description', None)
        stack_trace: str = getattr(error_message, 'StackTrace', None)

        if error_code in cls.WARNING_CODES:  # является предупреждением?
            return GisWarning(f"{error_code}: {description}")

        return cls(error_code, description, stack_trace)

    def __init__(self, code: str, message: str, details: str = None):

        self.error_code: str = code
        self.error_message: str = message
        self.error_details: str = details

        super().__init__(code, message, details)  # для pickle-сериализации

    def __str__(self):
        """Строковое представление ошибки с детализацией"""
        if not self.error_code:  # None?
            return self.error_message  # только сообщение

        if any(self.error_code.startswith(ext)
                for ext in ['INT', 'SRV', 'EXP']):  # коды ошибок ГИС ЖКХ
            description = f"{self.error_code}: {self.error_message}"
        else:  # ошибка со внутренним кодом!
            description = self.error_message  # без кода

        if self.error_code in self.CUSTOM_DETAILS:  # своя детализация?
            return f"{description} ~ {self.CUSTOM_DETAILS[self.error_code]}"
        else:  # детализацию ошибки не показываем пользователю!
            return description

    def __repr__(self):
        """Строковое представление ошибки с трассировкой стека"""
        result: str = f"{self.error_code or 'БЕЗ КОДА'}: {self.error_message}"

        if self.error_details:
            result += f"\n{self.error_details}"

        return result


class GisTransferError(GisError):
    """Ошибка передачи данных ~ RequestException"""

    def __init__(self, status_code: int, error_reason: str):

        super().__init__(str(status_code), error_reason)


class GisProcessError(GisError):
    """Ошибка обработки данных ~ Fault"""

    def __init__(self, error_code: str, error_message: str = None,
            stack_trace: str = None):

        super().__init__(error_code, error_message, stack_trace)

    @classmethod
    def from_fault(cls, fault_detail: str) -> 'GisProcessError':
        """
        Ошибка в процессе выполнения из детализации Fault без кода
        """
        xml = search(r'<ns\d*:ErrorCode>(.*)</ns\d*:ErrorCode>\s*'
            r'<ns\d*:Description>(.*)</ns\d*:Description>', fault_detail)
        if xml:  # найден фрагмент в формате XML?
            return cls(xml.group(1), xml.group(2))

        html = search(r'<title>(.*)</title>', fault_detail)
        if html:  # найден фрагмент в формате HTML?
            return cls('FAULT', html.group(1), fault_detail)

        return cls('FAULT', cls._parse_details(fault_detail), fault_detail)


class PublicError(Exception):
    """Публичное (отображаемое пользователю) исключение"""

    def __init__(self, message: str):

        self.message: str = message

        super().__init__(message)  # для pickle-сериализации


class NoGUIDError(PublicError):
    """Не загружен идентификатор ГИС ЖКХ"""

    def __init__(self, message: str = None):

        super().__init__(message
            or "Не загружен требуемый идентификатор сущности ГИС ЖКХ")


class NoDataError(PublicError):
    """Отсутствует необходимые для выполнения операции данные"""

    def __init__(self, message: str = None):

        super().__init__(message
            or "Отсутствуют необходимые для выполнения операции данные")


class ObjectError(PublicError):
    """Ошибка обработки объекта"""

    def __init__(self, message: str = None):

        super().__init__(message or
            "Получена ошибка в процессе обработки (данных) объекта")


class NoRequestWarning(GisWarning):
    """Отсутствуют данные запроса операции"""

    def __init__(self, notification: str = None):

        super().__init__(notification or
            "Отсутствуют данные запроса операции")


class NoResultWarning(GisWarning):
    """Отсутствует результат выполнения операции"""

    def __init__(self, notification: str = None):

        super().__init__(notification or
            "Отсутствуют подлежащие сохранению результаты выполнения операции")


class CancelSignal(Exception):
    """Сигнал к отмене выполнения операции"""

    def __init__(self, reason: str = None):

        super().__init__(reason
            or "Выполнение операции было принудительно отменено")


class PendingSignal(CancelSignal):
    """Сигнал к отложенному выполнению операции"""

    def __init__(self, reason: str = None):

        super().__init__(reason
            or "Выполнение операции отложено до завершения предшествующей")


class ConsistencyError(CancelSignal):  # НЕ GisError
    """Нарушена последовательность выполнения операции"""

    def __init__(self, reason: str):

        super().__init__(reason)


class RestartSignal(Exception):
    """Сигнал к перезапуску операции"""

    FATAL_ERROR = ConsistencyError("Сигнал к перезапуску"
        " операции не должен возвращаться в виде ошибки")

    def __init__(self, reason: BaseException):

        self.reason = reason  # сохраняем первоначальную ошибку

        super().__init__(f"Запрос был перезапущен после ошибки {reason}")


class UnstatedError(Exception):
    """(Не)удовлетворительное состояние обработки сообщения"""

    RECEIVED_STATE = 1  # код состояния полученного сообщения
    PROCESSING_STATE = 2  # код состояния обрабатываемого сообщения
    SUCCESSFUL_STATE = 3  # код состояния обработанного сообщения

    ASYNC_OPERATION_STATES = {
        RECEIVED_STATE: 'получено',
        PROCESSING_STATE: 'в обработке',
        SUCCESSFUL_STATE: 'обработано',
    }  # варианты статуса обработки

    FATAL_ERROR = GisTransferError(0,  # фатальная ошибка
        "Исчерпан лимит получения результата обработки сообщения")

    @classmethod
    def get_state_name(cls, request_state: int) -> str:

        return cls.ASYNC_OPERATION_STATES.get(request_state,
            f"в состоянии №{request_state}")

    @property
    def name(self) -> str:

        return self.get_state_name(self.request_state)

    @property
    def is_successful(self) -> bool:

        return self.request_state == self.SUCCESSFUL_STATE

    @property
    def is_processing(self) -> bool:

        return self.request_state == self.PROCESSING_STATE

    # WARN сообщение задается в init и переопределять str не требуется

    def __init__(self, request_state: int):

        self.request_state = request_state

        super().__init__(f"Сообщение запроса {self.name} ГИС ЖКХ")


class InternalError(Exception):
    """Внутренняя (Системная) ошибка"""

    def __init__(self, message: str = None, details: str = None):

        super().__init__()  # НЕ записываем сообщение об ошибке в Exception

        self.message = message
        self.details = details

    def __str__(self):  # -> str

        raise RuntimeError("Для формирования строкового представления"
            " внутренних ошибок следует использовать параметры класса")
