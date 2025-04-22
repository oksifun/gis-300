class CustomScriptError(Exception):
    NOTICE_MESSAGE = 'Ошибка проведения скрипта'


class ParameterNotFoundError(CustomScriptError):
    NOTICE_MESSAGE = 'Отсутствует обязательный параметр'


class ProviderNotFoundError(CustomScriptError):
    NOTICE_MESSAGE = 'Организация не найдена'


class HouseNotFoundError(CustomScriptError):
    NOTICE_MESSAGE = 'Дом не найден'
