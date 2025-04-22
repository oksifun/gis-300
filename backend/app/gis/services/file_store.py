from uuid import UUID
from bson import ObjectId

from datetime import datetime, timezone
from pathlib import Path

from logging import Logger, getLogger

from http import HTTPStatus

from requests import RequestException, Response
from requests.structures import CaseInsensitiveDict

from email.header import Header, decode_header

from app.gis.core.exceptions import GisTransferError
from app.gis.core.gost import bin_to_b64
from app.gis.core.soap_client import SoapClient, GisSession, GisServerAddress

from app.gis.models.guid import GUID
from app.gis.models.choices import GisObjectType

from app.gis.utils.common import reset_logging, is_latin1, as_guid, sb, jn


class UploadContext:

    AGREEMENTS = 'agreements'
    HOME_MANAGEMENT = 'homemanagement'
    CONTENT_MANAGEMENT = 'contentmanagement'
    VOTING = 'voting'
    INDICES = 'indices'
    INFORMING = 'informing'
    RKI = 'rki'
    INSPECTION = 'inspection'
    BILLS = 'bills'
    LICENSES = 'licenses'
    PROGRAMS = 'programs'  # WARN одна m
    CR_PROGRAMS = 'capitalrepairprograms'
    NSI = 'nsi'
    DISCLOSURE = 'disclosure'
    APPEALS = 'appeals'
    MSP = 'msp'
    FUND_DECISIONS = 'funddecisions'
    HOA_MEMBERS = 'hoamembers'
    RPG = 'rpg'
    VQT = 'vqt'
    ESC = 'esc'
    HOA_REPORTS = 'hoareports'
    TKO = 'tko'
    RQR = 'rqr'
    PAYMENTS_STATE = 'payments-state'
    TKO_REG_OP = 'tkoregop'
    RATE_CONSUMPTION = 'rate-consumption'


UPLOAD_CONTEXTS = {
    UploadContext.AGREEMENTS: "Договора (ДУ, уставы, ДПОИ)",
    UploadContext.HOME_MANAGEMENT: "Управление домами и лицевыми счетами",
    UploadContext.CONTENT_MANAGEMENT: "Управление контентом",
    UploadContext.VOTING: "Голосования",
    UploadContext.INDICES: "Индексы",
    UploadContext.INFORMING: "Оповещения",
    UploadContext.RKI: "Реестр коммунальной инфраструктуры",
    UploadContext.INSPECTION: "Инспектирование жилищного фонда",
    UploadContext.BILLS: "Электронные счета",
    UploadContext.LICENSES: "Лицензии",
    UploadContext.PROGRAMS: "Реестр программ",
    UploadContext.CR_PROGRAMS: "Реестр программ капитального ремонта",
    UploadContext.NSI: "Нормативно-справочная информации",
    UploadContext.DISCLOSURE: "Раскрытие деятельности управляющей организации",
    UploadContext.APPEALS: "Управление обращениями",
    UploadContext.MSP: "Меры социальной поддержки",
    UploadContext.FUND_DECISIONS: "Решения фонда капитального ремонта",
    UploadContext.HOA_MEMBERS: "Реестр членов ТСЖ",
    UploadContext.RPG: "Ведение информации о готовности к отопительному сезону",
    UploadContext.VQT: "Качество коммунальных ресурсов и услуг",
    UploadContext.ESC: "Энергосервисные контракты",
    UploadContext.HOA_REPORTS: "Отчеты товарищества и кооператива",
    UploadContext.TKO: "Места сбора ТКО",
    UploadContext.RQR: "Решения о качестве предоставляемых услуг",
    UploadContext.PAYMENTS_STATE: "Информация о состоянии расчетов",
    UploadContext.TKO_REG_OP: "Региональные операторы по обращению с ТКО",
    UploadContext.RATE_CONSUMPTION: "Объемы потребления",
}


class UploadHeaders:
    PREFIX = 'X-Upload-'

    ORG_PPA_GUID = f'{PREFIX}OrgPPAGUID'
    UPLOAD_ID = f'{PREFIX}UploadID'
    FILE_NAME = f'{PREFIX}Filename'
    LENGTH = f'{PREFIX}Length'
    ERROR = f'{PREFIX}Error'
    PART_NUMBER = f'{PREFIX}Partnumber'
    PART_COUNT = f'{PREFIX}Part-Count'
    COMPLETED_PARTS = f'{PREFIX}Completed-Parts'
    COMPLETED = f'{PREFIX}Completed'

    LOCATION = 'Location'
    DATE = 'Date'
    SERVER = 'Server'  # всегда ""?


class FileStore(object):  # Service

    # region ПАРАМЕТРЫ ОБМЕНА
    CHUNK_SIZE = 5242880  # максимальный размер (части) файла
    HEADER_CHARSET = 'utf-8'  # кодировка значений атрибутов заголовка

    UPLOAD_ERRORS = {
        'DataProviderValidationException':
            "Поставщик информации не найден, заблокирован или неактивен",
        'CertificateValidationException':
            "ИС не найдена по отпечатку или заблокирована",
        'FilePermissionException':
            "Нет требуемых полномочий или нарушена сессия",
        'HashConflictException':
            "Неверно подсчитана контрольная сумма (хэш) файла",
        'FileNotFoundException': "Файл не найден",
        'FieldValidationException': "Некорректно заполнены поля запроса",
        'InvalidStatusException':
            "Некорректный статус файла (сессия финализирована?)",
        'InvalidSizeException': "Некорректный размер (сформированного) файла",
        'FileVirusInfectionException': "Содержимое файла инфицировано",
        'FileVirusNotCheckedException':
            "Требуется проверка на вредоносное содержимое",
        'InvalidPartNumberException':
            "Количество загруженных частей не совпадает",
        'ExtensionException': "Недопустимое расширение файла",
        'DetectionException': "Не удалось определить тип загружаемого файла"
    }

    MIME_TYPE = {  # WARN проверяется расширение с точкой в начале
        '.pdf': 'application/pdf',
        '.xls': 'application/excel',
        # vnd - вендорные файлы, x - нестандартные файлы:
        # 'application/[vnd.ms-excel/x-excel/x-msexcel]'
        '.xlsx': 'application/vnd.openxmlformats-officedocument'
                 '.spreadsheetml.sheet',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument'
                 '.wordprocessingml.document',
        '.rtf': 'application/rtf',  # 'application/x-rtf'  # 'text/richtext'
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',  # 'image/pjpeg'
        '.tif': 'image/tiff',
        '.tiff': 'image/tiff',  # 'image/x-tiff'
        '.zip': 'application/zip',
        '.xml': 'application/xml',
        # '.rptdesign': '?',
        '.crt': 'application/x-x509-user-cert',  # 'application/x-x509-ca-cert'
        '.cer': 'application/pkix-cert',
        # добавленные
        '.txt': 'text/plain',
        '.bmp': 'image/x-windows-bmp',
        '.gif': 'image/gif',
        '.rar': 'application/x-rar-compressed',
        '.csv': 'text/csv',
        '.odp': 'application/vnd.oasis.opendocument.presentation',
        '.odf': 'application/vnd.oasis.opendocument.formula',
        '.ods': 'application/vnd.oasis.opendocument.spreadsheet',
        '.odt': 'application/vnd.oasis.opendocument.text',
        '.sxc': 'application/vnd.sun.xml.calc',
        '.sxw': 'application/vnd.sun.xml.writer',
    }

    DEFAULT_CONTEXT = UploadContext.CONTENT_MANAGEMENT

    CONTEXT_PATH = 'ext-bus-file-store-service/rest'  # не core/files(?)

    HOST = GisServerAddress.PPAK \
        if not GisSession.IS_TEST_SERVER else GisServerAddress.SIT1
    # endregion ПАРАМЕТРЫ ОБМЕНА

    # region ПЕРЕМЕННЫЕ КЛАССА
    logger: Logger = None  # журнал (файлового) клиента

    _upload_id: UUID = None  # идентификатор ГИС ЖКХ файла
    _file_info: dict = {}  # информация о текущем файле
    # endregion ПЕРЕМЕННЫЕ КЛАССА

    # region СТАТИЧЕСКИЕ МЕТОДЫ
    @staticmethod
    def md5_hash(data: bytes) -> str:
        """Дайджест (Base64) данных (файла)"""
        from hashlib import md5
        data_digest: bytes = md5(data).digest()

        return bin_to_b64(data_digest).strip()  # не hex, а Base64

    @staticmethod
    def transliterate(file_name: str) -> str:
        """Получить (ASCII) транслитерацию названия файла"""
        RFC_SPECIAL = {
            '№': '#',  # нет в ASCII
            '<': ' ',
            '>': ' ',
            '?': '',
            ':': ' ',
            '|': '/',
            '*': ' ',
            '%': '',
            '\\': '/',
            '"': "'",
        }  # RFC 2047, RFC 822

        from transliterate import translit  # только не латинские знаки
        translit_name: str = translit(file_name,  # .stem - без расширения
            language_code='ru', reversed=True)

        for wrong, correct in RFC_SPECIAL.items():
            if wrong in translit_name:
                translit_name = translit_name.replace(wrong, correct)

        assert is_latin1(translit_name), \
            f"Имя файла {sb(translit_name)} содержит запрещенные символы"

        return translit_name  # Latin-1 (ISO 8859-1)

    @classmethod
    def rfc_encode(cls, value: str) -> str:
        """Зашифровать значение для атрибута заголовка"""
        return Header(value, charset=cls.HEADER_CHARSET).encode(linesep='')

    @classmethod
    def rfc_decode(cls, value: str) -> str:
        """Расшифровать значение атрибута заголовка"""
        return ''.join(word.decode(cls.HEADER_CHARSET) if encoding  # None-ASCII
            else word for word, encoding in decode_header(value))

    @staticmethod
    def header_date(date_time: str) -> datetime:
        """Извлечь дату и время из заголовка"""
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_time) if date_time else datetime.now()

    @staticmethod
    def read_file(file_path: Path, chunk_size: int = CHUNK_SIZE):
        """
        Прочитать файл поблочно
        """
        with file_path.open(mode='rb') as file:
            # file.seek(offset, 0)  # 0 - с начала, 1 - с позиции, 2 - с конца
            while True:
                chunk: bytes = file.read(chunk_size)
                if chunk:
                    yield chunk  # for byte in chunk...
                else:
                    break  # ~ return None
    # endregion СТАТИЧЕСКИЕ МЕТОДЫ

    # region КЛАССОВЫЕ МЕТОДЫ
    @classmethod
    def _setup_logging(cls):
        """
        Инициализация журнала клиента сервиса
        """
        if cls.logger is None:
            reset_logging()  # сброс параметров базового (root) журнала
            SoapClient.setup_requests_logging()

        # WARN Logger-ы кэшируются и существуют до конца работы интерпретатора
        cls.logger = getLogger(cls.__name__)
        cls.logger.setLevel(SoapClient.LOGGING_LEVEL)  # минимальный уровень

    @classmethod
    def _transfer_error(cls, upload_error: str,
            status_code: int = HTTPStatus.BAD_REQUEST) -> GisTransferError:
        """Ошибка (выполнения) запроса"""
        error_reason: str = cls.UPLOAD_ERRORS.get(upload_error, upload_error)

        return GisTransferError(status_code, error_reason)  # WARN не возбуждаем

    @classmethod
    def get_location_context(cls, location: str) -> str:
        """Извлечь контекст из местоположения файла"""
        from re import search
        pattern: str = f'/{cls.CONTEXT_PATH}/([^/]+)/[-0-9a-f]*'

        match = search(pattern, location)  # : SRE_Match
        assert match, "Контекст не найден в местоположении файла"

        return match.group(1)

    @classmethod
    def get_context_url(cls, upload_context: str) -> str:
        """/<context-path>/<upload-context>"""
        return f"{GisSession.host_url()}" \
            f"{cls.CONTEXT_PATH}/{upload_context}"  # WARN без финального слэша

    @classmethod
    def get_gis_context(cls, object_type: str) -> str:
        """Получить файловый контекст (типа) сущности ГИС ЖКХ"""
        assert object_type in GUID.OBJECT_TAGS, \
            "Некорректный тип сущности ГИС ЖКХ"

        return UploadContext.AGREEMENTS if object_type in {
            GisObjectType.PROVIDER,
            GisObjectType.CHARTER,
            GisObjectType.CONTRACT,
        } else UploadContext.HOME_MANAGEMENT if object_type in {
            GisObjectType.HOUSE,
            GisObjectType.PORCH,
            GisObjectType.LIFT,
            GisObjectType.AREA,
            GisObjectType.ROOM,
        } else cls.DEFAULT_CONTEXT  # контекст по умолчанию

    @classmethod
    def chunk_count(cls, file_length: int, chunk_size: int = CHUNK_SIZE) -> int:
        """Количество частей файла"""
        return -(file_length // -chunk_size) if file_length else 1

    @classmethod
    def chunk_lengths(cls, file_length: int, chunk_size: int = CHUNK_SIZE):
        """Размеры частей файла"""
        while file_length > chunk_size:
            yield chunk_size

            file_length -= chunk_size

        yield file_length  # остатки

    @classmethod
    def chunk_ranges(cls, file_length: int, chunk_size: int = CHUNK_SIZE):
        """
        Диапазоны (байт) частей файла

        WARN последний байт не входит в диапазоны
        """
        part: int = 1  # первая часть

        while file_length > chunk_size * part:
            yield range(chunk_size * (part - 1), chunk_size * part)

            part += 1  # следующая часть

        yield range(chunk_size * (part - 1), file_length)  # остатки

    @classmethod
    def split_data(cls, file_data: bytes, chunk_size: int = CHUNK_SIZE):
        """Разделить большой объем данных на части"""
        while len(file_data) > chunk_size:
            yield file_data[:chunk_size]  # включая chunk_size байт

            file_data: bytes = file_data[chunk_size:]  # последующие байты

        yield file_data
    # endregion КЛАССОВЫЕ МЕТОДЫ

    # region СВОЙСТВА ЭКЗЕМПЛЯРА
    @property
    def request_date(self) -> str:
        """Текущая дата в формате запроса"""
        REQUEST_DATE_FORMAT: str = '%a, %-d %b %Y %H:%M:%S GMT'
        return datetime.now(timezone.utc).strftime(REQUEST_DATE_FORMAT)

    @property
    def upload_context(self) -> str:
        """Контекст (сохранения) файла"""
        return self._upload_context

    @property
    def context_url(self) -> str:
        """/<context-path>/<upload-context>"""
        return self.get_context_url(self.upload_context)

    @property
    def provider_id(self) -> ObjectId:
        """Идентификатор организации"""
        return self._provider_guid.object_id

    @property
    def org_ppa_guid(self) -> str:
        """OrganizationPPAGUID"""
        return str(self._provider_guid.gis)

    @property
    def org_name(self) -> str:
        """Наименование организации"""
        return self._provider_guid.desc \
            or f"орг. с ид. {self._provider_guid.id}"

    @property
    def common_headers(self) -> dict:
        """
        Общая часть заголовка запроса

        Host: адрес сервера (не IP)
        Date: дата и время
        X-Upload-OrgPPAGUID: ид. поставщика данных (было X-Upload-Dataprovider)
        """
        return {'Host': self.HOST,  # подложный адрес, реальный - в url
            # 'Date': self.request_date, генерируется автоматически
            UploadHeaders.ORG_PPA_GUID: self.org_ppa_guid}  # : str

    @property
    def upload_id(self) -> str:
        """Идентификатор ГИС ЖКХ файла"""
        assert isinstance(self._upload_id, UUID), \
            "Отсутствует (корректный) идентификатора файла"

        return str(self._upload_id)

    @property
    def file_info(self) -> dict:
        """Сведения о файле"""
        if self.upload_id != self._file_info.get(UploadHeaders.UPLOAD_ID):
            # загружаем сведения о файле - получаем идентификатор и контекст
            self.inspect_file(self._upload_id)  # : UUID

        return self._file_info

    @property
    def file_name(self) -> str:
        """Название файла в ГИС ЖКХ"""
        header: str = self.file_info[UploadHeaders.FILE_NAME]  # обязательный
        if '=?' in header:  # значение закодировано?
            header = self.rfc_decode(header)

        return header

    @property
    def file_length(self) -> int:
        """Размер файла в байтах"""
        return int(self.file_info[UploadHeaders.LENGTH])  # : str

    @property
    def completed_parts(self) -> list:
        """Список завершенных части"""
        completed_parts: str = self.file_info[UploadHeaders.COMPLETED_PARTS]
        return completed_parts.split(',')

    @property
    def is_completed(self) -> bool:
        """Выгрузка файла завершена?"""
        return self.file_info.get(UploadHeaders.COMPLETED,  # WARN не or
            len(self.completed_parts) == 1 and
                self.file_length < self.CHUNK_SIZE)

    @property
    def file_location(self) -> str:
        """
        Местоположение (хранения) файла

        /ext-bus-file-store-service/rest/[CONTEXT]/[UPLOAD_ID]
        """
        return self.file_info[UploadHeaders.LOCATION]

    @property
    def _upload_date(self) -> datetime:
        """Дата и время выполнения запроса?"""
        return self.header_date(self.file_info['Date'])  # WARN +GMT
    # endregion СВОЙСТВА ЭКЗЕМПЛЯРА

    def __new__(cls, *args, **kwargs):

        cls._setup_logging()

        return super().__new__(cls)  # возвращаем экземпляр клиента

    def __init__(self, provider_id: ObjectId,
            upload_context: str = DEFAULT_CONTEXT):

        self._session = GisSession(logger=self.logger)  # сессия по умолчанию

        # WARN контекст не является обязательным при поиске файла на сервере
        self._upload_context = upload_context
        assert self._upload_context in UPLOAD_CONTEXTS, \
            "Некорректный контекст (сохранения) файла"

        # загружаем данные ГИС ЖКХ поставщика информации
        self._provider_guid: GUID = GUID.objects(
            tag=GisObjectType.PROVIDER, object_id=provider_id
        ).first()
        assert self._provider_guid, \
            "Данные ГИС ЖКХ поставщика информации не загружены"

        self.logger.info(f"Поставщик информации {self.org_name} открыл"
            f" репозиторий {sb(self.upload_context)} файлового сервиса")

    def has_file_guid(self, file_guid: str or UUID) -> bool:
        """Текущий идентификатор файла?"""
        return self._upload_id and self._upload_id == as_guid(file_guid)

    def _put(self, file_data: bytes, request_headers: dict,
            upload_id: str = None) -> str:
        """
        PUT /<context path>/<upload context> HTTP/1.1
            или:
        PUT /<context-path>/<upload-context>/<uploadID> HTTP/1.1

        Дополнительные атрибуты заголовка:
            Content-Length - размер файла в байтах
            Content-MD5 - хэш содержимого файла в кодировке Base64 (не HEX)

            X-Upload-Filename - наименование файла с расширением
        или:
            X-Upload-Partnumber - порядковый номер части

            <данные файла в бинарном формате>

        Ответ сервера ГИС ЖКХ:
            HTTP/1.1 состояние (например, "200 OK")
            Date - дата и время
            Connection: keep-alive
            Server - имя сервера
        Дополнительные атрибуты при простой загрузке:
            Location: /<context-path>/<upload-context>/<uploadID>
            X-Upload-UploadID: идентификатор файла в системе ГИС ЖКХ
        """
        assert not len(file_data) > self.CHUNK_SIZE, \
            f"Размер передаваемых данных превышает {self.CHUNK_SIZE} байт"

        if upload_id:  # выгрузка частями?
            assert UploadHeaders.PART_NUMBER in request_headers \
                and UploadHeaders.FILE_NAME not in request_headers
            if 'Content-Length' not in request_headers:
                request_headers['Content-Length'] = str(len(file_data))
            url: str = f"{self.context_url}/{upload_id}"
        else:  # простая загрузка!
            assert UploadHeaders.FILE_NAME in request_headers \
                and UploadHeaders.PART_NUMBER not in request_headers
            # WARN Content-Length заполняется автоматически
            url: str = self.context_url

        if 'Content-MD5' not in request_headers:
            request_headers['Content-MD5'] = self.md5_hash(file_data)

        request_headers.update(self.common_headers)  # общая часть

        self.logger.debug(f"PUT {url}:\n\t{jn(request_headers)}")
        try:
            response: Response = self._session.put(url,
                data=file_data,  # или files - дополнены (мета) данными о файле
                headers=request_headers)
        except RequestException as error:  # ошибка подключения?
            raise GisTransferError(
                error.response.status_code, error.response.reason
            ) if isinstance(error.response, Response) \
                else GisTransferError(HTTPStatus.BAD_REQUEST, str(error))

        upload_error: str = response.headers.get(UploadHeaders.ERROR)
        if upload_error:  # ошибка выгрузки?
            raise self._transfer_error(upload_error, response.status_code)

        self.logger.debug("Результат успешной выгрузки"
            f" данных файла:\n\t{jn(response.headers)}")
        if not upload_id:  # простая выгрузка файла?
            upload_id: str = response.headers[UploadHeaders.UPLOAD_ID]

        return upload_id  # возвращаем (полученный) идентификатор файла

    def upload_file(self, file_name: str, file_data: bytes = None) -> UUID:
        """
        Выгрузка в ГИС ЖКХ (данных) файла

        Данные больше установленного объема выгружаются частями в рамках сессии
        """
        file_path: Path = Path(file_name)  # путь к файлу и/или название

        content_type: str = self.MIME_TYPE.get(file_path.suffix)
        assert content_type, "Выгрузка в ГИС ЖКХ файлов типа" \
            f" {file_path.suffix} не поддерживается"

        if file_data:  # получены данные файла?
            self.logger.info(f"Получены {len(file_data)} байт"
                f" подлежащего выгрузке файла {sb(file_name)}")
        elif file_path.is_file():  # локальный файл?
            file_data: bytes = file_path.read_bytes()  # TODO читать частями
            self.logger.info(f"Загружены {len(file_data)} байт"
                f" подлежащего выгрузке файла {sb(file_name)}")
        else:  # данные отсутствуют!
            raise GisTransferError(HTTPStatus.NOT_FOUND,
                f"Отсутствуют данные подлежащего выгрузке файла {file_name}")

        encoded_name: str = self.rfc_encode(file_path.name)  # без пути

        file_length: int = len(file_data)  # размер данных (файла) в байтах
        part_count: int = self.chunk_count(file_length)  # количество частей
        if part_count == 1:  # единственная часть (небольшого) файла?
            assert not file_length > self.CHUNK_SIZE, \
                "Размер файла превышает максимальный допустимый"
            request_headers: dict = {
                'Content-Type': content_type,  # 'application/octet-stream'
                UploadHeaders.FILE_NAME: encoded_name,  # WARN Latin-1
            }
            self._upload_id = \
                as_guid(self._put(file_data, request_headers))  # : UUID
            self.logger.info(f"Выгруженный файл {sb(file_name)}"
                f" получил идентификатор {self.upload_id}")
            return self._upload_id  # WARN завершаем выгрузку файла

        # region ВЫГРУЗКА БОЛЬШОГО ФАЙЛА ЧАСТЯМИ
        request_headers: dict = {
            # 'Content-Type': content_type,  # 'application/octet-stream'
            UploadHeaders.FILE_NAME: encoded_name,  # WARN Latin-1
            UploadHeaders.LENGTH: str(file_length),  # : str или bytes
            UploadHeaders.PART_COUNT: str(part_count),
        }
        self._upload_id = \
            as_guid(self._post(request_headers))  # инициализация сессии
        # WARN после завершения сессии будет идентификатором файла в ГИС ЖКХ
        self.logger.info(f"Начата сессия выгрузки принадлежащего"
            f" {self.org_ppa_guid} файла {self.upload_id}")

        for number, chunk in enumerate(self.split_data(file_data), start=1):
            self.logger.info(f"Выгружается {number} часть из {part_count}"
                f" размером {len(chunk)} байт файла {self.upload_id}")
            self._put(chunk, request_headers={
                UploadHeaders.PART_NUMBER: str(number)
            }, upload_id=self.upload_id)  # идентификатор сессии и файла

        self._post(upload_id=self.upload_id)  # завершение сессии
        self.logger.info(f"Завершена сессия выгрузки принадлежащего"
            f" {self.org_ppa_guid} файла {self.upload_id}")

        return self._upload_id
        # endregion ВЫГРУЗКА БОЛЬШОГО ФАЙЛА ЧАСТЯМИ

    def _head(self, upload_id: str) -> CaseInsensitiveDict:
        """
        HEAD /<context-path>/<upload-context>/<uploadID> HTTP/1.1

        Стандартный заголовок
        """
        url: str = f"{self.context_url}/{upload_id}"  # контекст не играет роли

        request_headers: dict = self.common_headers  # общий заголовок

        self.logger.debug(f"HEAD {url}:\n\t{jn(request_headers)}")
        try:
            response: Response = self._session.head(url,
                headers=request_headers)
        except RequestException as error:  # ошибка подключения?
            raise GisTransferError(
                error.response.status_code, error.response.reason
            ) if isinstance(error.response, Response) \
                else GisTransferError(HTTPStatus.BAD_REQUEST, str(error))

        upload_error: str = response.headers.get(UploadHeaders.ERROR)
        if upload_error:  # ошибка загрузки?
            raise self._transfer_error(upload_error, response.status_code)

        self.logger.debug("Результат успешного запроса"
            f" сведений о файле:\n\t{jn(response.headers)}")
        return response.headers  # WARN .content - пустой

    def inspect_file(self, file_guid: str or UUID) -> dict:
        """
        Получение сведений о загруженном/загружаемом файле

        :returns:
            X-Upload-UploadID: идентификатор (сессии загрузки) файла в ГИС ЖКХ
            X-Upload-OrgPPAGUID: идентификатор зарегистрированной организации
            X-Upload-Filename: имя загруженного / загружаемого файла
            X-Upload-Length: размер файла в байтах
            X-Upload-Completed-Parts: список корректно загруженных частей
            X-Upload-Completed: сессия загрузки успешно завершена (файл собран)?
        """
        self._upload_id = as_guid(file_guid)  # WARN выбрасывает исключения

        self.logger.info(f"Загружаются сведения о принадлежащем"
            f" {self.org_ppa_guid} файле {self.upload_id}")
        response: CaseInsensitiveDict = self._head(self.upload_id)  # ~ dict

        self._file_info: dict = {key: value for key, value in response.items()
            if key.startswith(UploadHeaders.PREFIX) or key in {
                UploadHeaders.LOCATION, UploadHeaders.DATE  # без X-Upload-
            }}  # WARN кроме неиспользуемых атрибутов

        location_context: str = self.get_location_context(self.file_location)
        if location_context != self.upload_context:  # DEFAULT_CONTEXT?
            self.logger.warning(f"Текущий контекст {sb(location_context)}"
                f" (сохранения) файла {self.upload_id} извлечен из сведений")
            self._upload_context = location_context

        self.logger.info("Получены сведения о размещенном в"
            f" {sb(self.upload_context)} файле {sb(self.file_name)}")
        return dict(response.items())  # WARN все атрибуты заголовка ответа

    def _get(self, file_guid: str, bytes_range: range = None) -> bytes:
        """
        GET /<context-path>/<upload-context>/<fileGUID>?getfile HTTP/1.1

        Дополнительный атрибут заголовка:
            Range: bytes=[диапазон от(включительно)-до(исключая) в байтах]
            WARN Для файлов меньше 5 МБ атрибут не указывается

        WARN Невозможно выгрузить не размещенный в бизнес-сведениях файл
        """
        url: str = f"{self.context_url}/{file_guid}?getfile"  # HTTP/1.1

        request_headers: dict = self.common_headers  # общая часть

        if bytes_range:  # задан диапазон байт?
            request_headers['Range'] = \
                f"bytes={bytes_range[0]}-{bytes_range[-1]}"
            self.logger.debug("Размер (части) загружаемого файла"
                f" ограничен с {bytes_range[0]} по {bytes_range[-1]}"
                f" (итого {len(bytes_range)} байт)")

        self.logger.debug(f"GET {url}:\n\t{jn(request_headers)}")
        try:
            response: Response = self._session.get(url, headers=request_headers)
        except RequestException as error:  # ошибка подключения?
            raise GisTransferError(
                error.response.status_code, error.response.reason
            ) if isinstance(error.response, Response) \
                else GisTransferError(HTTPStatus.BAD_REQUEST, str(error))

        upload_error: str = response.headers.get(UploadHeaders.ERROR)
        if upload_error:  # ошибка загрузки?
            # WARN в случае наличия (в headers) ошибки content отсутствует
            raise self._transfer_error(upload_error, response.status_code)

        self.logger.debug(f"Успешно получены {len(response.content)} байт"
            f" {'части' if bytes_range else 'содержимого'} файла {file_guid}")
        return response.content  # WARN .text пытается декодировать данные

    def download_file(self, file_guid: str or UUID) -> bytes:
        """
        Загрузка (содержимого) файла из ГИС ЖКХ
        """
        if not self.has_file_guid(file_guid):  # нет или иной идентификатор?
            self.inspect_file(file_guid)  # загружаем сведения о файле

        if not self.is_completed:  # не (полностью) выгружен?
            raise GisTransferError(HTTPStatus.NOT_FOUND,  # 404?
                f"Файл {self.upload_id} не (полностью) выгружен в ГИС ЖКХ")
        elif self.file_length > self.CHUNK_SIZE:  # 'Completed-Parts': 1,2
            file_content: bytes = b''  # ~ bytes()
            for bytes_range in self.chunk_ranges(self.file_length):
                self.logger.info(f"Загружается часть файла {self.upload_id}"
                    f" с {bytes_range[0]} по {bytes_range[-1]} байт")
                file_content += self._get(self.upload_id, bytes_range)
        else:  # загрузка файла целиком!
            self.logger.info(f"Загружается содержимое файла {self.upload_id}"
                f" размером {self.file_length} байт")
            file_content: bytes = self._get(self.upload_id)

        return file_content  # возвращаем содержимое файла

    def save_to_file(self, file_guid: str or UUID, file_name: str) -> str:
        """
        Сохранить с именем данные файла с идентификатором
        """
        path = Path(file_name)
        directory = path.parent if path.suffix else path  # путь сохранения
        # создаем директорию рекурсивно, если отсутствует
        directory.mkdir(parents=True, exist_ok=True)

        file_content: bytes = self.download_file(file_guid)  # WARN inspect_file

        if path.is_dir():  # указана лишь директория?
            path = path / self.file_name  # перегруженный оператор /

        path.write_bytes(file_content)  # сохраняем полученное содержимое

        self.logger.info(f"Принадлежащий {self.org_name}"
            f" файл сохранен как file:///{path.resolve()}")

        return str(path.absolute())  # возвращаем путь сохраненного файла

    def _post(self, request_headers: dict = None, upload_id: str = None) -> str:
        """
        POST /<context-path>/<upload-context>/?upload HTTP/1.1
            или:
        POST /context-path>/<upload-context>/<uploadID>?completed HTTP/1.1

        Дополнительные атрибуты заголовка:
            X-Upload-Filename - имя загружаемого файла
            X-Upload-Length - размер файла в байтах
            X-Upload-Part-Count - количество частей файла для передачи
        """
        if not upload_id:  # инициализация сессии?
            assert UploadHeaders.FILE_NAME in request_headers

            file_length: int = request_headers.get(UploadHeaders.LENGTH)
            assert file_length, "Размер выгружаемого файла не определен"
            if UploadHeaders.PART_COUNT not in request_headers:
                request_headers[UploadHeaders.PART_COUNT] = \
                    str(self.chunk_count(file_length))  # количество частей

            request_headers.update(self.common_headers)  # общая часть
            url: str = f"{self.context_url}/?upload"
        else:  # завершение сессии!
            request_headers = self.common_headers  # WARN X-Upload-OrgPPAGUID
            url: str = f"{self.context_url}/{upload_id}?completed"

        self.logger.debug(f"POST {url}:\n\t{jn(request_headers)}")
        try:
            response: Response = self._session.post(url,
                headers=request_headers)
        except RequestException as error:  # ошибка подключения?
            raise GisTransferError(
                error.response.status_code, error.response.reason
            ) if isinstance(error.response, Response) \
                else GisTransferError(HTTPStatus.BAD_REQUEST, str(error))

        upload_error: str = response.headers.get(UploadHeaders.ERROR)
        if upload_error:  # ошибка выгрузки?
            raise self._transfer_error(upload_error, response.status_code)

        self.logger.debug(f"Результат {'завершения' if upload_id else 'начала'}"
            f" сессии выгрузки данных файла:\n\t{jn(response.headers)}")
        if not upload_id:  # начало загрузки?
            upload_id: str = response.headers[UploadHeaders.UPLOAD_ID]

        # WARN после завершения сессии будет являться ид-ом файла в ГИС ЖКХ
        return upload_id  # идентификатор загрузки в ГИС ЖКХ

    def _upload_big_file(self, file_name: str) -> str:
        """
        Выгрузка в ГИС ЖКХ файла с диска
        """
        file_path: Path = Path(file_name)
        assert file_path.is_file(), f"Ошибка открытия файла {file_name}"

        file_length: int = file_path.stat().st_size  # размер файла в байтах

        content_type: str = self.MIME_TYPE.get(file_path.suffix)
        assert content_type, "Выгрузка в ГИС ЖКХ файлов" \
            f" с расширением {file_path.suffix} не поддерживается"

        translit_name: str = self.transliterate(file_path.name)  # без пути
        self.logger.warning(f"Файл {sb(file_name)}"
            f" подлежит выгрузке как {sb(translit_name)}")

        part_count: int = self.chunk_count(file_length)

        request_headers: dict = {
            # 'Content-Type': content_type,  # 'application/octet-stream'
            UploadHeaders.FILE_NAME: translit_name,  # WARN Latin-1
            UploadHeaders.LENGTH: str(file_length),  # : str или bytes
            UploadHeaders.PART_COUNT: str(part_count),
        }
        # WARN после завершения сессии будет идентификатором файла в ГИС ЖКХ
        self._upload_id = as_guid(self._post(request_headers))  # инициализация
        self.logger.info(f"Начата сессия выгрузки принадлежащего"
            f" {self.org_ppa_guid} файла {self.upload_id}")

        for number, chunk in enumerate(self.read_file(file_path), start=1):
            self.logger.info(f"Выгружается {number} из {part_count} часть"
                f" размером {len(chunk)} байт файла {self.upload_id}")
            self._put(chunk, request_headers={
                UploadHeaders.PART_NUMBER: str(number)
            }, upload_id=self.upload_id)  # выгрузка частями

        self._post(upload_id=self.upload_id)  # завершение сессии
        self.logger.info(f"Завершена сессия выгрузки принадлежащего"
            f" {self.org_ppa_guid} файла {self.upload_id}")

        return self.upload_id


if __name__ == '__main__':

    from mongoengine_connections import register_mongoengine_connections
    register_mongoengine_connections()

    p = ObjectId("54d9d64ff3b7d4398079309d")
    s = FileStore(p, UploadContext.HOME_MANAGEMENT)

    # g = "ce3a8df6-3068-11ee-a5f9-005056b69885"  # Protokol #6
    g = "00dff02b-32d6-11ee-a5f9-005056b69885"  # Протокол №6
    # g = "bdf371ed-307c-11ee-a5f9-005056b69885"  # Ustav

    print('INFO:', s.inspect_file(g)); exit()

    # b: bytes = s.download_file(g)
    # print('BYTES:', b); exit()

    # p = '/home/eav/Загрузки'
    # s.save_to_file(g, p); exit()

    p = "/home/eav/Загрузки/Протокол №6 от 09.04.2006(устав).pdf"
    s.upload_file(p); exit()

    # p = "/home/eav/Загрузки/Устав .pdf"
    # s.upload_big_file(p); exit()
