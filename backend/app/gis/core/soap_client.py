from datetime import time, datetime
from pathlib import Path

from logging import Logger, getLogger, DEBUG, INFO, WARNING

from ssl import SSLContext, SSLError, \
    OPENSSL_VERSION, OP_NO_SSLv2, OP_NO_SSLv3, \
    PROTOCOL_TLS, OP_NO_TLSv1_1, OP_NO_TLSv1_2, OP_NO_TLSv1_3, \
    CERT_REQUIRED  # CERT_OPTIONAL, CERT_NONE

from socket import socket, gethostbyname, gethostbyname_ex, gethostname, \
    AF_INET, SOCK_DGRAM

from urllib3 import add_stderr_logger, disable_warnings
from urllib3.exceptions import InsecureRequestWarning
from urllib3.response import HTTPResponse
from urllib3.connection import HTTPConnection
from urllib3.util.retry import Retry  # WARN не из HTTPAdapter
from requests.models import Response
# requests.sessions на базе urllib.request на базе http.client
from requests.sessions import Session as RequestsSession, \
    DEFAULT_REDIRECT_LIMIT, default_headers, default_hooks, cookiejar_from_dict
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth  # или HTTPDigestAuth или OAuth1
from requests.exceptions import RequestException, \
    ConnectionError as RequestConnectionError, \
    Timeout, SSLError as RequestsSSLError, HTTPError

# TODO from zeep.asyncio import AsyncTransport  # aiohttp.ClientSession
from zeep import Transport as ZeepTransport, Settings as ZeepSettings
from zeep.client import Client as ZeepClient, \
    logger as client_logger  # дефолтный logger клиента zeep
from zeep.cache import InMemoryCache, \
    logger as cache_logger
from zeep.wsdl.wsdl import Definition, Document as wsdlDocument, \
    logger as wsdl_logger
from zeep.xsd.schema import logger as schema_logger
from zeep.xsd.visitor import logger as visitor_logger
from zeep.exceptions import Fault, \
    ValidationError, NamespaceError, LookupError, XMLParseError, TransportError

from app.gis.core import xmldsig as xml
from app.gis.core.gost import Certificate
from app.gis.core.plugins import NoSignaturePlugin, XAdESPlugin, DebugPlugin
from app.gis.core.exceptions import RestartSignal, \
    GisTransferError, GisProcessError

from app.gis.utils.common import sb, pf

from settings import GIS, APP_DIR


class GisServerAddress:
    PPAK = 'api.dom.gosuslugi.ru'
    SIT1 = 'sit01.dom.test.gosuslugi.ru'  # api.?
    SIT2 = 'sit02.dom.test.gosuslugi.ru'  # api.?


GIS_SERVER_IP = {
    GisServerAddress.PPAK: "217.107.108.116",
    GisServerAddress.SIT1: "217.107.108.147",
    GisServerAddress.SIT2: "217.107.108.156",
}

GIS_SERVER_PORT = {
    'sTunnel': 1443,  # WARN http
    GisServerAddress.PPAK: 443,  # https
    GisServerAddress.SIT1: 10081,  # https
    GisServerAddress.SIT2: 10082,  # WARN http
}


# region КАСТОМНЫЕ КЛАССЫ
class SSLAdapter(HTTPAdapter):
    """
    Установка HTTPS-соединения (всегда инициирует клиент):
    1. "Handshake"
    1.1. версия протокола и набор шифров (клиент предлагает, сервер выбирает);
    1.2. аутентификация сервера (доверенный?) и (опц.) клиента (сертификат);
    2. "Data" - обмен зашифрованными сессионным ключом (из 1.2) данными.
    Асимметричные алгоритмы шифрования - ресурсоемки, используем симметричные!
    """
    # алгоритмы шифрования через ":", eNULL - выключен по умолчанию
    CIPHERS = 'GOST2012-GOST8912-GOST8912'  # :HIGH+TLSv1:!DH:!aNULL:!MD5:!SHA1
    # 'HIGH:!DH:!aNULL' - решает "dh key too small", disable_warnings() - нет

    @property
    def context(self) -> SSLContext:
        """SSL-контекст"""
        return self._context

    @property
    def available_ciphers(self) -> list:
        """
        Доступные алгоритмы шифрования контекста

        :returns: [ {
            'id', 'name', 'protocol', 'description', 'symmetric',
            'strength_bits', 'alg_bits', 'aead', 'digest', 'kea', 'auth'
        },... ]
        """
        return [
            cipher for cipher in self.context.get_ciphers()
            # WARN в CIPHERS OpenSSL 1.1.1+ всегда три TLS 1.3 алгоритма
            if cipher['id'] not in {50336514, 50336515, 50336513}
        ] if hasattr(self.context, 'get_ciphers') else []

    def __init__(self, max_retries):
        """
        SSL connection using TLSv1.2 / GOST2012-GOST8912-GOST8912
        """
        # patch_https_connection()  # передача сертификата при подключении
        # patch_http_response()  # передача сертификата сервера в ответе

        self._context = SSLContext(PROTOCOL_TLS)  # поддерживаемая версия
        # по умолчанию OP_NO_COMPRESSION, OP_NO_TLSv1

        # WARN клиентский и сертификат сервера загружаются в сессии
        self._context.verify_mode = CERT_REQUIRED  # проверка обоих сертификатов
        # TODO self._context.verify_flags = VerifyFlags.?
        self._context.check_hostname = False  # WARN приоритет над PoolManager!

        # OP_ALL - ОБЯЗАТЕЛЬНАЯ ОПЦИЯ: важные исправления протокола SSL
        # OP_CIPHER_SERVER_PREFERENCE - использовать порядок алгоритмов сервера
        # ^ OP_NO_COMPRESSION - ВКЛЮЧИТЬ компрессию (неупакованных) данных
        # OP_NO_RENEGOTIATION - TLSv1.2: без HelloRequest и игнор. ClientHello
        # OP_SINGLE_(EC)DH_USE - НЕ использовать один ключ (EC)DH для SSL-сессий
        # OP_ENABLE_MIDDLEBOX_COMPAT - TLSv1.3: пустое CCS, аналогичное TLSv1.2
        # TODO OP_NO_SSLv2 не добавляется, если есть OP_NO_SSLv3?
        self._context.options |= (OP_NO_SSLv2 | OP_NO_SSLv3)  # устаревший SSL
        # WARN GOST2012 поддерживает только TLSv1
        self._context.options |= (OP_NO_TLSv1_1 | OP_NO_TLSv1_2 | OP_NO_TLSv1_3)

        # TODO TLSVersion поддерживается начиная с Python 3.7
        # context.minimum_version = TLSVersion.TLSv1  # мин. поддерживаемая вер.
        # context.maximum_version = TLSVersion.TLSv1_2  # макс. версия протокола

        self._context.set_alpn_protocols(["http/1.1"])  # WARN НЕ "h2" (HTTP/2)
        try:  # Next Protocol Negotiation
            self._context.set_npn_protocols(["h2", "http/1.1"])
        except (AttributeError, NotImplementedError):
            pass  # поддержка не обязательна

        try:  # WARN исключение если не установлен OpenSSL с поддержкой ГОСТ
            self._context.set_ciphers(SSLAdapter.CIPHERS)
        except SSLError:  # ssl.SSLError
            raise GisTransferError(503,
                "Ошибка инициализации алгоритма шифрования (ГОСТ)")

        super().__init__(max_retries=max_retries)  # WARN после SSL-контекста

    def _load_certs(self, cert_file, key_file=None, ca_file=None, ca_path=None):

        # context.load_default_certs()  # системные сертификаты

        if cert_file:
            self._context.load_cert_chain(cert_file, key_file)  # клиентский
        if ca_file or ca_path:
            self._context.load_verify_locations(ca_file, ca_path)  # УЦ

    def init_poolmanager(self, *args, **kwargs):
        """
        Подключение без прокси
        """
        kwargs['ssl_context'] = self._context  # добавляем SSL контекст
        # WARN assert_hostname перекрывается SSL-контекстом?

        super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        """
        Подключение с использованием прокси
        """
        kwargs['ssl_context'] = self._context  # добавляем SSL контекст
        # WARN assert_hostname перекрывается SSL-контекстом?

        return super().proxy_manager_for(*args, **kwargs)

    def _build_response(self, req, resp):  # WARN не используется

        assert isinstance(resp, HTTPResponse) \
            and isinstance(resp.connection, HTTPConnection)

        response: Response = super().build_response(req, resp)

        # None - не предоставлен, {} - не прошел валидацию
        assert resp.connection.peer_certificate, \
            "Сертификат сервера не предоставлен или не прошел валидацию"

        response.peer_certificate = resp.connection.peer_certificate  # : dict

        return response


class GisSession(RequestsSession):

    # region ПАРАМЕТРЫ СЕРВЕРА
    IS_TEST_SERVER = not GIS.get('use_prod_server')
    BASIC_AUTH = ('sit', 'xw{p&&Ee3b9r8?amJv*]') if IS_TEST_SERVER else None

    # адрес шифрующего прокси, None - без sTunnel
    STUNNEL_ACCEPT = GIS.get('cipher_proxy')  # None - собственное или без
    VPN_CIDR_MASK = None  # '172.30.1.0/24'  # None - VPN не используется

    # Path.absolute() не задокументирована и подлежит устранению в новых версиях
    GIS_DATA_PATH = Path(APP_DIR, 'gis', 'data').resolve()  # данные

    CERT_PATH = Path(GIS_DATA_PATH, 'certificates')  # серверные и клиентские
    SERVER_CERTIFICATE = GIS.get('verify_server_cert') \
        if not IS_TEST_SERVER else GIS.get('verify_test_cert')  # или None
    CLIENT_CERTIFICATE = GIS['client_certificate']  # клиентский сертификат

    IS_SECURE_CONNECTION = not STUNNEL_ACCEPT  # and not IS_TEST_SERVER
    # endregion ПАРАМЕТРЫ СЕРВЕРА

    @staticmethod
    def get_local_ips(remote_ip: str or None = '8.8.8.8') -> list:
        """
        Получить внешний IP-адрес (требуется подключенной к интернету)
        """
        host_name: str = gethostname()
        host_name, aliases, addresses = gethostbyname_ex(host_name)
        ips: set = {ip for ip in addresses if not ip.startswith('127.')}
        # ips = ips[:1]  # список с 1 элементом или пустой

        if remote_ip:
            with socket(AF_INET, SOCK_DGRAM) as remote:  # без close
                address: tuple = (remote_ip, 53)
                remote.connect(address)
                ip, port = remote.getsockname()
                ips.add(ip)

        return list(ips)

    @classmethod
    def get_host_ip(cls, host_name: str) -> str:
        """Получить IP-адрес по URL сервера"""
        return GIS_SERVER_IP.get(host_name) or gethostbyname(host_name)

    @classmethod
    def _vpn_proxy(cls) -> dict:

        proxies: dict = {}
        if not cls.VPN_CIDR_MASK:
            return proxies

        import ipaddress as v4v6
        vpn_network = v4v6.ip_network(cls.VPN_CIDR_MASK)
        for address in cls.get_local_ips(None):
            ip_address = v4v6.ip_address(address)

            if ip_address in vpn_network:
                for server_ip in GIS_SERVER_IP.values():
                    proxies[server_ip] = str(ip_address - 1)  # DHCP-сервер
                break

        return proxies  # 'протокол (и хост)': 'урл прокси'

    @classmethod
    def host_url(cls, ip_address: bool = True) -> str:
        """
        Адрес (конечной точки) сервера

        ППАК - промышленный программно-аппаратный комплекс ГИС ЖКХ:
            https://api.dom.gosuslugi.ru:443
        СИТ - стенд интеграционного тестирования ГИС ЖКХ:
            http(s)://[sit01/sit02].dom.test.gosuslugi.ru:[(10081)/10082]
        СИТ-01 с форматами обмена и версией сервисов ГИС ЖКХ, аналогичной ППАК
        СИТ-02 с перспективными форматами обмена и версией ГИС ЖКХ (+ СМЭВ)

        sTunnel: адрес подключения должен совпадать с CN сертификата сервера:
            connect = *.dom.test.gosuslugi.ru:10081

        :returns: http(s)://host_ip_address:port/
            [ext-bus-service-name/services/ServiceNameAsync]
        """
        # запросы в sTunnel отправляются по http, а оттуда уходят уже по https
        scheme: str = "https" if cls.IS_SECURE_CONNECTION else "http"

        if cls.STUNNEL_ACCEPT:  # шифрующий прокси?
            host = cls.STUNNEL_ACCEPT  # WARN запросы на адрес прокси
        elif not cls.IS_TEST_SERVER:  # производственный контур?
            host = GisServerAddress.PPAK
        elif cls.IS_SECURE_CONNECTION:  # шифрованное подключение?
            host = GisServerAddress.SIT1
        else:  # нешифрованное подключение!
            host = GisServerAddress.SIT2  # более полные ошибки

        if cls.STUNNEL_ACCEPT:  # порты до 1024 зарезервированы системой
            port = 1443 if not cls.IS_TEST_SERVER else 10081  # 20082 - sit02
        else:  # https: 443, 10081; http: 10082
            port = 443 if not cls.IS_TEST_SERVER else \
                10081 if cls.IS_SECURE_CONNECTION else 10082

        if ip_address:  # получить ip-адрес?
            host = cls.get_host_ip(host)

        return f"{scheme}://{host}:{port}/"  # WARN с финальным слэшем

    @property
    def certificate(self) -> Certificate:
        """Клиентский сертификат"""
        return self._certificate

    def __init__(self, max_retries: Retry = 0, logger: Logger = None):
        """
        Инициализация сессии (полностью переписана)
        """
        object.__init__(self)  # pass ~ устраняем предупреждение

        self.logger = logger or getLogger('requests')  # urllib3?

        self.trust_env = False  # параметры среды (os): сертификаты, прокси, ...

        # WARN по клиентскому сертификату идентифицируется поставщик информации
        client_cert_path = \
            Path(self.CERT_PATH, self.CLIENT_CERTIFICATE).resolve()  # !absolute
        self._certificate = Certificate.load(client_cert_path)

        self.headers = default_headers()  # регистр символов не имеет значения
        if not self.IS_SECURE_CONNECTION:  # нешифрованное (http) соединение?
            self.headers.update(  # добавляем заголовок с отпечатком сертификата
                {'X-Client-Cert-Fingerprint': self.certificate.thumb_print})
        self.logger.debug(f"Подготовлены HTTP-заголовки запроса:\n\t"
            + '\n\t'.join(f"{key}: {value}" for key, value in
                self.headers.items()))  # ~ dict

        if self.IS_TEST_SERVER:  # Basic[Base64]-авторизация обязательна для СИТ
            self.auth: HTTPBasicAuth = HTTPBasicAuth(*self.BASIC_AUTH)
            self.logger.warning("Подключена базовая авторизация серверов"
                f" ГИС ЖКХ - {self.auth.username}: {self.auth.password}")
        else:  # авторизация промышленного сервера основана на сертификатах
            self.auth = None

        self.proxies = self._vpn_proxy()  # 'протокол (и хост)': 'урл прокси'
        # прокси не внедряется на уровне транспорта, заменяется адрес сервиса

        self.hooks = default_hooks()  # event-handling hooks
        self.params = {}  # dict of querystring data to attach to each Request
        self.stream = False  # stream response content default

        if self.STUNNEL_ACCEPT:  # соединение средствами шифрующего прокси?
            self.verify = False  # клиент принимает любой сертификат сервера
            self.logger.warning("Проверка серверного сертификата"
                " и предоставление клиентского осуществляется sTunnel")
        elif (self.IS_SECURE_CONNECTION and  # проверка сертификата сервера?
                isinstance(self.SERVER_CERTIFICATE, str)):  # True - локальные
            self.verify = str(Path(  # доверенные сертификаты УЦ
                self.CERT_PATH, self.SERVER_CERTIFICATE  # файл или каталог
            ).resolve(strict=True))  # WARN исключение в случае отсутствия файла
            self.logger.info("Удостоверяющий сертификат сервера"
                f" file://{self.verify}")
        else:  # незащищенное соединение!
            self.verify = False  # клиент принимает любой сертификат сервера
            disable_warnings(InsecureRequestWarning)  # отключаем предупреждение
            self.logger.warning("Проверка сертификата сервера не осуществляется"
                " и соответсвующее предупреждение модуля urllib3 отключено")

        # путь к файлу сертификата ИС в виде строки (или кортеж с путем ключа)
        self.cert = str(self.certificate.cert_path)  # для авторизации клиента
        self.logger.info(f"Сертификат клиента file://{self.cert}")

        self.max_redirects = DEFAULT_REDIRECT_LIMIT  # 30

        self.cookies = cookiejar_from_dict({})  # по умолчанию куки сессии пусты

        self.adapters = {}  # был OrderedDict
        # по умолчанию HTTP(S)Adapter.max_retries = 0 - без повторов
        self.mount('http://', HTTPAdapter(max_retries=max_retries))  # необходим

        if self.STUNNEL_ACCEPT:
            self.logger.info("Устанавливается защищенное соединение с"
                f" {self.host_url()} средствами шифрующего прокси (sTunnel)")
        elif self.IS_SECURE_CONNECTION:
            ssl_adapter = SSLAdapter(max_retries=max_retries)

            self.logger.debug(f"Шифрование средствами {OPENSSL_VERSION}"
                f" с параметрами:\n\t{repr(ssl_adapter.context.options)}")
            self.logger.debug("Доступные алгоритмы SSL-контекста:\n\t"
                + ('\n\t'.join(cipher['description']  # название и протокол
                for cipher in ssl_adapter.available_ciphers) or 'ОТСУТСВУЮТ'))

            self.mount('https://', ssl_adapter)  # адаптер https-соединений

            self.logger.info("Устанавливается защищенное соединение с"
                f" {self.host_url()} основанное на проверке сертификатов")
        else:  # ни шифрующего прокси, ни сертификата сервера!
            self.logger.warning("Устанавливается незащищенное (нешифрованное)"
                f" соединение с {self.host_url()} без проверки сертификата")


class GisTransport(ZeepTransport):

    OPERATION_TIMEOUT = 30 if GisSession.IS_TEST_SERVER else 60  # None - вечно
    # TODO установить единый таймаут можно переопределив Session.request()
    TIMEOUT_THRESHOLD = 60  # макс. время подключения к серверу и загрузки схем
    LOAD_TIMEOUT = 10  # время ожидания подключения к серверу и загрузки схем

    def __init__(self, request_session: RequestsSession):

        schema_cache = InMemoryCache(timeout=3600 * 8)  # срок актуальности
        # или SqliteCache(path="\AppData\Local\[Author]\zeep\Cache\cache.db")

        super().__init__(
            cache=schema_cache,
            timeout=self.LOAD_TIMEOUT,  # по умолчанию = 300 сек.
            operation_timeout=self.OPERATION_TIMEOUT,  # для GET / POST
            session=request_session,
        )  # инициализируется logger

        # транспортный протокол
        self.logger.setLevel(SoapClient.SUB_LOGGING_LEVEL)

    def load(self, url: str):
        """
        Выполняется при загрузке схем, позволяет загружать из других источников
        """
        for external, internal in SoapClient.CACHED_SCHEMAS.items():
            if url.startswith(external):
                path = Path(SoapClient.CACHED_PATH, internal)
                url: str = path.absolute().as_uri()  # WARN локальный адрес

                self.logger.info(f"Используется кэшированная схема {url}")

        # file:///path - сокращение для file://localhost/path - НЕ Windows!
        # url = url.replace('file:///', 'file://')  # WARN только Windows
        return super().load(url)

    def get(self, address: str, params, headers: dict) -> Response:
        """
        Запрос (GET) и обработка данных
        """
        return super().get(address, params, headers)

    def post(self, address: str, message: bytes, headers: dict) -> Response:
        """
        Отправка (POST) и обработка данных (логирование)

        Метод полностью переписан - вызов super().post(...) не требуется!
        """
        if self.logger.isEnabledFor(DEBUG):
            decoded_xml: str = message.decode("utf-8")

            pretty_xml: str = xml.get_pretty(xml.from_string(decoded_xml))
            self.logger.debug(f"Отправка на {address} запроса:\n{pretty_xml}")

        # headers - HTTP (НЕ SOAP/XML)-заголовки запроса
        response: Response = self.session.post(address,
            data=message, headers=headers, timeout=self.operation_timeout)

        if self.logger.isEnabledFor(DEBUG):  # форматированный XML в ответе
            # SOAP-заголовки передаются отдельно (в теле) от HTTP-заголовков
            self.logger.debug(f"HTTP-заголовки ответа: {response.headers}")

            from zeep.utils import get_media_type
            media_type: str = get_media_type(
                response.headers.get('Content-Type', 'text/xml')
            )

            if media_type == 'multipart/related':
                self.logger.warning(f"Получен ответ в формате {sb(media_type)}")
                decoded_xml: str = response.text  # response.encoding / chardet
            else:  # 'text/xml'
                self.logger.debug(f"Получен ответ в формате {sb(media_type)}")
                # кодировка НЕ из заголовка (response.encoding='ISO-8859-1')
                decoded_xml: str = response.content.decode('utf-8') \
                    if isinstance(response.content, bytes) else response.text

            self.logger.debug(f"Ответ со статусом {response.status_code}"
                f" с {address}:\n{decoded_xml}")

        return response

    def post_xml(self, address: str, envelope: bytes, headers: dict):
        """
        Отправка сообщения на указанный адрес с заданными заголовками
        Здесь можно изменить XML-сериализацию сообщения
        По умолчанию используется zeep.wsdl.utils.etree_to_string
        """
        message: bytes = xml.get_canonic(envelope)

        return self.post(address, message, headers)
# endregion КАСТОМНЫЕ КЛАССЫ


# region ОБЕЗЬЯНЬИ ПАТЧИ
def patch_http_client_debug(enable_logging: bool = False):
    """
    Заменяет печать методом print на вывод в лог заголовков и тела запроса

    :param enable_logging: активировать режим отладки?
    """
    http_client_logger = getLogger('http.client')  # изначально не определен
    http_client_logger.setLevel(SoapClient.REQUEST_LOG_LEVEL)  # все сообщения

    def patched_print(*args):
        http_client_logger.log(SoapClient.REQUEST_LOG_LEVEL, ' '.join(args))

    from http import client
    client.print = patched_print  # заменяем встроенный метод
    client.HTTPConnection.debuglevel = 1 if enable_logging else 0  # > 0 - print


def patch_https_connection():

    from urllib3.connectionpool import HTTPSConnection
    original_connect = HTTPSConnection.connect

    def patched_connect(self):

        original_connect(self)  # оригинальный метод
        try:
            self.peer_certificate = self.sock.getpeercert()  # ssl.SSLSocket
        except AttributeError:
            pass

    HTTPSConnection.connect = patched_connect  # WARN подменяем метод


def patch_http_response():

    original__init__ = HTTPResponse.__init__

    def patched__init__(self, *args, **kwargs):

        original__init__(self, *args, **kwargs)  # оригинальная инициализация
        try:
            self.peer_certificate = self._connection.peer_certificate
        except AttributeError:
            pass

    HTTPResponse.__init__ = patched__init__  # WARN подменяем метод


def patch_zeep_float():
    """
    Преобразование чисел с плавающей запятой в XML

    Преобразование экспоненциальной записи в дестяичную
    """
    from decimal import Context, Decimal

    from zeep.xsd import check_no_collection
    from zeep.xsd.types.builtins import Float as ZeepFloat

    @check_no_collection
    def patched_xmlvalue(_self: ZeepFloat, value: float or Decimal) -> str:

        context = Context()  # создаем Decimal.Context
        context.prec = 20  # 20 цифр после запятой должно хавтить

        decimal = context.create_decimal(repr(value))  # создаем Decimal

        return format(decimal, 'f')  # было str(value).upper()

    ZeepFloat.xmlvalue = patched_xmlvalue


def patch_zeep_date(nullify_1900=True, nullify_5000=True):
    """
    Преобразование дат в даты со временем ~ Cannot encode object: datetime.date
    Особая обработка специальных дат ГИС ЖКХ (01.01.1900 и 01.01.5000)
    """
    from zeep.xsd.types.builtins import Date

    def patched_pythonvalue(_self: Date, value: str):
        from isodate import parse_date
        _date = parse_date(value)

        if (nullify_1900 and _date.year == 1900) or \
                (nullify_5000 and _date.year == 5000):
            return None

        return datetime.combine(_date, time.min)  # в BSON тип Date = DateTime

    Date.pythonvalue = patched_pythonvalue


def patch_zeep_datetime(nullify_1900=True, nullify_5000=True):
    """
    Особая обработка специальных дат со временем (1900-01-01 или 5000-01-01)
    5000 год передается в виде длинного целого числа
    """
    from zeep.xsd.types.builtins import DateTime

    def patched_pythonvalue(_self: DateTime, value: str):
        date_time_value = value + "T00:00:00" \
            if len(value) == 10 else value  # под видом datetime передан date?

        from isodate import parse_datetime
        date_time = parse_datetime(date_time_value)

        if (nullify_1900 and date_time.year == 1900) or \
                (nullify_5000 and date_time.year == 5000):
            return None

        return date_time

    DateTime.pythonvalue = patched_pythonvalue


def patch_zeep_soap_send():

    from zeep.wsdl.bindings.soap import SoapBinding  # HttpBinding

    def patched_send(self: SoapBinding, client: ZeepClient,
            options: dict, operation, args: tuple, kwargs: dict):

        envelope, http_headers = self._create(operation, args, kwargs,
            client=client, options=options)
        response = client.transport.post_xml(options['address'],
            envelope, http_headers)

        operation_obj = self.get(operation)

        if client.settings.raw_response:
            return response

        # код из process_reply
        if response.status_code in (201, 202) and not response.content:
            return None
        elif response.status_code not in (200, 400) and not response.content:
            raise TransportError(  # добавлена ошибка 400
                f"Ошибка выполнения запроса {response.status_code}",
                status_code=response.status_code)

        return self.process_reply(client, operation_obj, response)

    SoapBinding.send = patched_send


def patch_zeep_fault():  # НЕ ИСПОЛЬЗУЕТСЯ! ПРИМЕНЯЕТСЯ ПАРСИНГ

    def patched_init(self, message,
                     code=None, actor=None, detail=None, subcodes=None):

        super(Fault, self).__init__(message)

        if code.endswith('Server'):  # env:Server
            self.code, self.message = \
                message.split(': ', 1)  # "FaultCode: FaultMessage"
            self.detail = str(detail)  # lxml.etree._Element
        else:
            self.code, self.message, self.detail = code, message, detail

        self.actor = actor
        self.subcodes = subcodes

    Fault.__init__ = patched_init
# endregion ОБЕЗЬЯНЬИ ПАТЧИ


class SoapClient(ZeepClient):  # Simple Object Access Protocol

    # region ПАРАМЕТРЫ КЛИЕНТА
    LOGGING_LEVEL = INFO  # zeep.client
    SUB_LOGGING_LEVEL = WARNING  # zeep.xsd/wsdl/transports/cache
    REQUEST_LOG_LEVEL = WARNING  # urllib3, requests, Session, SSL

    # Path.absolute() не задокументирована и подлежит устранению в новых версиях
    GIS_DATA_PATH = Path(APP_DIR, 'gis', 'data').resolve()  # данные

    DEFAULT_ENDPOINT_PATH = "ext-bus-{0}-service/services/{1}Async",  # tns,name
    ENDPOINT_PATHS = {  # soap:address.location
        'CapitalRepair':  "ext-bus-{0}-programs-service/services/{1}Async",
        'Infrastructure': "ext-bus-rki-service/services/{1}Async",
        'OrgRegistry': "ext-bus-org-registry-service/services/"
                       "OrgRegistryAsync",
        'OrgRegistryCommon': "ext-bus-org-registry-common-service/services/"
                             "OrgRegistryCommonAsync",
        'Organization': "ext-bus-organization-service/services/"
                        "OrganizationAsync"
    }  # нестандартные адреса конечных точек сервисов

    SCHEMA_VERSION = GIS['schema_version']  # версия схемы сервиса
    # если путь к схемам не указан (None) - будет использоваться адрес сервиса
    SCHEMA_PATH = Path(GIS_DATA_PATH, f"hcs_wsdl_xsd_v.{SCHEMA_VERSION}")
    CACHED_PATH = Path(GIS_DATA_PATH, 'cached_wsdl_xsd')  # место хранения схем
    CACHED_SCHEMAS = {  # 'http://schema.url/': 'schema_file_name.xsd'
        'http://schemas.xmlsoap.org/': 'schemas.xmlsoap.org.xsd'
    }  # сохраненные XML-схемы
    WSDL_PATTERN = "{0}/hcs-{0}-service-async.wsdl"  # вид имени схемы сервиса

    MAX_RETRIES: int = 2  # максимальное кол-во повторов запроса после ошибки
    REQUEST_RETRY_ERRORS = {
        500: 'Internal Server Error',
        502: 'Bad Gateway',
        503: 'Service Unavailable',
        504: 'Gateway Timeout',
    }  # Response.status_code: int : Response.reason: str

    REDEEMABLE_FAULTS = {  # вызывающие перезапуск запроса ошибки ГИС ЖКХ
        'EXP001000': "Ошибка при передаче данных",  # ГИС ЖКХ перегружен?
    }
    REDEEMABLE_ERRORS = {  # вызывающие перезапуск запроса ошибки сервера
        104: "Connection reset by peer",  # слишком много запросов?
    }
    # endregion ПАРАМЕТРЫ КЛИЕНТА

    # region СВОЙСТВА
    @property
    def service(self):
        return self._proxy_service

    @property
    def schema(self):
        """
        zeep.xsd.schema.Schema[Document] - global или [tns]
        """
        return self.wsdl.types

    @property
    def definition(self):
        # key = (definition.target_namespace, definition.location)
        definitions = self.wsdl._definitions.values()
        root_definition: Definition = next(iter(definitions), None)
        return root_definition

    @property
    def binding(self):
        from zeep.wsdl.bindings.soap import SoapBinding

        bindings = self.wsdl.bindings.values()  # key = binding.name
        first_binding: SoapBinding = next(iter(bindings), None)
        return first_binding

    @property
    def version(self):
        # self.schema.get_attribute('base:version')  # <xs:schema...version />
        return self.SCHEMA_VERSION
    # endregion СВОЙСТВА

    @classmethod
    def serialize(cls, obj, output=dict, lightweight: bool = True):
        """
        Serialize zeep objects to native python data structures

        Аналог from zeep.helpers import serialize_object
        """
        if isinstance(obj, list):
            return [cls.serialize(sub, output) for sub in obj]

        from zeep.xsd import CompoundValue
        if isinstance(obj, (dict, CompoundValue)):
            result = output()  # создаем новый контейнер

            for key in obj:  # ~ dict
                value = obj[key]  # значение атрибута (элемента) объекта

                if lightweight and key in {'Signature', 'version',  # балласт
                        'Id', 'MessageGUID', 'RequestState', 'ErrorMessage'}:
                    continue  # пропускаем "ненужные" элементы
                elif not value and not str(value).replace('.', '', 1).isdigit():
                    continue  # пропускаем пустые значения (кроме 0 и 0.0)

                result[key] = cls.serialize(value, output)

            return result

        return obj

    def _get_proxy_service(self, proxy_host):
        """
        Получить реальный адрес сервиса на основе указанного в схеме
        """
        default_host = f"https://{GisServerAddress.PPAK}/"

        default_binding = self._default_service._binding
        default_address: str = self._default_service._binding_options['address']

        proxy_address = default_address.replace(default_host, proxy_host, 1)
        # create_service(binding_name, service_address)

        from zeep.proxy import ServiceProxy
        proxy_service = ServiceProxy(self, default_binding,
            address=proxy_address)

        return proxy_service

    def _load_schema(self, service_name: str, service_tns: str):
        """
        Загрузить схемы сервиса
        """
        if self.SCHEMA_PATH:  # загружаем схему из файла
            wsdl_file_name = self.WSDL_PATTERN.format(service_tns)
            schema_path = Path(self.SCHEMA_PATH, wsdl_file_name)
            schema_absolute_path = schema_path.resolve(strict=True)
            schema_location: str = schema_absolute_path.as_uri()
        else:  # загружаем из сети схему сервиса (wsdl) и описания типов (xsd)
            endpoint_path = self.ENDPOINT_PATHS.get(service_name,
                self.DEFAULT_ENDPOINT_PATH)
            schema_location = self.session.host_url() \
                + endpoint_path.format(service_tns, service_name)

        client_logger.debug(f"Загружается схема {schema_location}")

        try:  # загружаем схемы сервиса
            return wsdlDocument(schema_location, self.transport,
                base=None, settings=self.settings)  # ~ XML - документ
        except Timeout:  # время ожидания подключения или загрузки схем истекло
            if GisTransport.LOAD_TIMEOUT < GisTransport.TIMEOUT_THRESHOLD:
                GisTransport.LOAD_TIMEOUT *= 2  # удваиваем время ожидания
                client_logger.warning("Время ожидания загрузки схем сервиса"
                    f" увеличено до {GisTransport.LOAD_TIMEOUT} секунд")
                self.transport.load_timeout = GisTransport.LOAD_TIMEOUT

                return self._load_schema(service_name, service_tns)  # попытка
        except RequestException:  # ошибки передачи данных?
            raise  # последнее обработанное исключение
        except Fault:  # ошибка при загрузке схемы?
            raise  # TODO: обрабатывать ошибки загрузки схем

    def _map_namespaces(self, **nsmap):
        """
        Регистрация пространств имен - xmlns:[ns]
        """
        for prefix, ns in nsmap.items():
            self.set_ns_prefix(prefix, ns)  # ~ self.wsdl.types.set_ns_prefix

    @classmethod
    def setup_requests_logging(cls):
        """
        Инициализация логирования модуля requests (urllib3)
        """
        patch_http_client_debug(enable_logging=False)  # REQUESTS_LOGGING_LEVEL

        # добавляем отладочный обработчик логирования urllib3
        add_stderr_logger(cls.REQUEST_LOG_LEVEL)  # WARN stream=sys.stderr
        url_lib_logger = getLogger('urllib3')  # используется requests
        url_lib_logger.setLevel(WARNING)  # информация о подключении
        url_lib_logger.propagate = True  # передавать сообщения уровнем выше

        requests_logger = getLogger('requests')  # не используется
        requests_logger.setLevel(cls.REQUEST_LOG_LEVEL)

    @classmethod
    def _setup_logging(cls):
        """
        Инициализация журнала (модулей) SOAP-клиента
        """
        client_logger.setLevel(cls.LOGGING_LEVEL)
        # getLogger('zeep').setLevel(...)

        cache_logger.setLevel(cls.SUB_LOGGING_LEVEL)  # кэширование схем
        # getLogger('zeep.cache')

        schema_logger.setLevel(cls.SUB_LOGGING_LEVEL)  # регистрация элементов
        # getLogger('zeep.xsd.schema').setLevel(...)

        visitor_logger.setLevel(cls.SUB_LOGGING_LEVEL)  # загрузка схем
        # getLogger('zeep.xsd.visitor').setLevel(...)

        wsdl_logger.setLevel(cls.SUB_LOGGING_LEVEL)  # формирование запроса
        # getLogger('zeep.wsdl.wsdl').setLevel(...)

    @classmethod
    def default_retries(cls) -> Retry:
        """
        Параметры повторных подключений по умолчанию
        """
        return Retry(
            total=cls.MAX_RETRIES,  # максимальное кол-во повторов после ошибки
            connect=cls.MAX_RETRIES // 2,  # макс. ошибок отправки запроса
            read=cls.MAX_RETRIES // 2,  # макс. ошибок получения ответа
            status=cls.MAX_RETRIES // 2,  # макс. ошибок сервера (forcelist)
            status_forcelist=[*cls.REQUEST_RETRY_ERRORS],
            redirect=0, raise_on_redirect=True,  # 301, 302, 303, 307, 308
            backoff_factor=1,  # backoff_factor * 2 ** (retries - 1) сек.
        )

    def __new__(cls, *args, **kwargs):

        cls.setup_requests_logging()  # журнал выполнения запроса
        cls._setup_logging()  # журнал (модулей) клиента

        return super().__new__(cls)  # возвращаем экземпляр клиента

    def __init__(self, service, debug_mode: bool = False):
        """
        Инициализация SOAP-клиента для веб-сервиса (полностью переписана)

        :param service: класс веб-сервиса
        :param debug_mode: выполнение в режиме отладки?
        """
        object.__init__(self)  # pass ~ устраняем предупреждение

        service_name = service.get_name()  # название сервиса
        service_tns = service.get_tns()  # целевое пространство имен сервиса

        client_logger.info("Создается новый экземпляр SOAP-клиента"
            f" для сервиса ГИС ЖКХ {sb(service_name)}")

        patch_zeep_date(False)  # "Cannot encode object" и 1900 / 5000 -> None
        patch_zeep_datetime(False)  # 1900-01-01 00:00:00.000+03:00 -> None

        patch_zeep_soap_send()  # Fault -> RequestException (TransferException)

        # region ИНИЦИАЛИЗАЦИЯ ~ super().__init__()
        self.settings = ZeepSettings(
            strict=False,  # ТОЛЬКО False! choice имеет некорректный XML
            raw_response=False,  # True - возвращает requests.Response
            # force_https=True,  # True - https, если схемы загружены по https
            # extra_http_headers=[],  # доп. загловки транспортного протокола
            # xml_huge_tree=False,  # True - поддержка больших деревьев
            # и длинных строк средставми lxml
            # forbid_dtd=False,  # запрет XML с инструкцией обработки <!DOCTYPE>
            # forbid_entities=True,  # запрет XML с декларациями <!ENTITY>
            # forbid_external=True,  # запрет на обращение к внешним ресурсам
            # xsd_ignore_sequence_order = False,  # True - сервер без sequence
        )
        self.session = GisSession(self.default_retries())  # объект сессии
        self.transport = GisTransport(self.session)
        self.wsdl = self._load_schema(service_name, service_tns)  # диск / сеть
        self.wsse = None  # расширение SOAP (header) в области безопасности
        self.plugins = [XAdESPlugin(self.session.certificate)  # подписывающий
            if self.session.IS_SECURE_CONNECTION else NoSignaturePlugin()]

        if debug_mode:
            self.debug_plugin = DebugPlugin(1)  # последняя транзакция (in/out)
            self.plugins.append(self.debug_plugin)  # исп. в порядке объявления

            client_logger.warning("Подключен отладочный плагин и XML последней"
                " транзакции (запроса и ответа) хранится в памяти")

        self._default_soapheaders = None  # заголовки по умолчанию для запросов
        self._default_service_name = None  # используется первый сервис схемы
        self._default_port_name = None  # используется первый порт схемы
        self._default_service = self.bind(
            service_name=self._default_service_name,
            port_name=self._default_port_name)
        # endregion ИНИЦИАЛИЗАЦИЯ

        # WARN _proxy_service ПОСЛЕ _default_service!
        self._proxy_service = self._get_proxy_service(self.session.host_url())
        # SOAP 1.1: http://schemas.xmlsoap.org/wsdl/soap/
        # SOAP 1.2: http://schemas.xmlsoap.org/wsdl/soap12/
        self._map_namespaces(**xml.SCHEMA_NS)  # стандартные XML схемы
        self._map_namespaces(**xml.BASE_NS)  # базовые схемы ГИС ЖКХ

        # 'tns': tns/targetNamespace из wsdl, 'abbr': tns/targetNamespace из xsd
        integration_schema_url = \
            f"http://dom.gosuslugi.ru/schema/integration/{service_tns}"
        abbr = ''.join([w[0] for w in service_tns.split('-')])  # ro/ls/hm...
        nsmap = {'tns': f"{integration_schema_url}-service-async/",
            abbr: f"{integration_schema_url}/"}
        self._map_namespaces(**nsmap)  # специфические пространства имен сервиса

        self._cached_types = {}  # кэш. типы или self.type_factory('ns0')?
        self._cached_elements = {}  # кэш. элементы (для повторных запросов)
        self._cached_operations = {}  # кэшированные методы сервиса

    def __str__(self):

        def parse(elements):

            DO_NOT_PARSE: set = {'Signature'}

            parsed: dict = {}
            for name, element in elements:
                if name in DO_NOT_PARSE:
                    parsed[name] = element.type.name
                elif hasattr(element.type, 'elements'):
                    parsed[name] = parse(element.type.elements)
                else:
                    parsed[name] = element.type.name or 'Any'
            return parsed

        interface = {}  # полный интерфейс сервиса
        for service in self.wsdl.services.values():
            interface[service.name] = {}  # доступные порты
            for port in service.ports.values():
                operations = {}  # доступные операции
                for operation in port.binding._operations.values():
                    input_elements = parse(operation.input.body.type.elements)
                    operations[operation.name] = input_elements

                    output_elements = parse(operation.output.body.type.elements)
                    operations[operation.name + '[Response]'] = output_elements

                interface[service.name][port.name] = \
                    dict(sorted(operations.items(), key=lambda o: o[0]))

        return pf(interface)

    # region XML-МЕТОДЫ
    def get_service_operation(self, operation_name: str):
        if operation_name in self._cached_operations:
            return self._cached_operations[operation_name]

        try:  # hasattr() - вызывает getattr и обрабатывает исключение
            service_operation = getattr(self.service, operation_name)
        except AttributeError:
            raise AttributeError(
                f"Метод {operation_name} в {self.service.name} не найден")
        else:  # кэшируем метод сервиса
            self._cached_operations[operation_name] = service_operation
            return service_operation

    def _call_service_operation(self, operation_name: str, **kwargs):
        try:
            return self.service[operation_name](**kwargs)
        except TypeError:
            raise

    def _get_request_xml(self, operation_name: str, **kwargs):
        """
        Получить XML запроса в текстовом виде
        """
        # with self.settings(raw_response = True):  # временные параметры
        try:
            # для service._binding._create обязательны args = () и client!
            # envelope, http_headers = self.service._binding._create(
            # operation_name, (), kwargs, client = self)
            envelope = self.create_message(self.service,
                operation_name, **kwargs)
        except (ValidationError, TypeError):
            raise
        else:
            return xml.get_pretty(envelope)

    def _get_xml_element(self, element_name: str):
        """
        client.get_element(element_name)

        :param element_name: аргумент "name" элемента
        :return: функциональный объект элемента (zeep.xsd.Element)
        """
        if element_name in self._cached_elements:
            return self._cached_elements[element_name]

        for ns in self.schema.prefix_map:  # _prefix_map_auto
            try:
                # self.wsdl.types.get_element(f"{ns}:{element_name}")  # ns0:nm1
                xml_element = self.get_element(f'{ns}:{element_name}')
            except (NamespaceError, LookupError):  # zeep.exceptions.LookupError
                continue  # игнорируем ошибки во время поиска
            else:
                self._cached_elements[element_name] = xml_element
                return xml_element
        # элемент не найден?!
        raise LookupError(f"Элемент {sb(element_name)} не найден"
            f" в схемах {self.schema.prefix_map}")

    def _get_xml_type(self, type_name: str):

        if type_name in self._cached_elements:
            return self._cached_types[type_name]

        for ns in self.schema.prefix_map:
            try:
                # self.wsdl.types.get_type(f'{ns}:{type_name}')
                xml_type = self.get_type(f'{ns}:{type_name}')
            except (NamespaceError, LookupError):
                continue
            else:
                self._cached_types[type_name] = xml_type
                return xml_type

        raise LookupError(f"Тип {sb(type_name)} не найден"
            f" в схемах {self.schema.prefix_map}")

    def create_xml_element(self, element_name: str, **kwargs):
        """
        Создать экземпляр XML-элемента

        Для <xsd:choice> значения задаются как _value_N = {...},
            где N - номер варианта в родительком типе.
        Если maxOccurs != 1 (unbounded) задается как список словарей:
            [{'el_1':'val_1'},{'el_2':'val_2'}]

        :return: объект элемента с указанными аргументами
        """
        return self._get_xml_element(element_name)(**kwargs)

    def create_xml_type(self, type_name: str, **kwargs):
        """
        Создать экземпляр XML-типа
        :return: объект типа с указанными аргументами
        """
        return self._get_xml_type(type_name)(**kwargs)

    @staticmethod
    def _check_choice(dictionary: dict, *choice_fields: str):

        choices = {name: value for name, value in dictionary.items()
            if name in choice_fields and value is not None}
        assert len(choices) == 1, \
            f"Должен быть один и только один элемент: {', '.join(choices)}"

    @staticmethod
    def _has_one_of_values(complex_object, *element_name_s: str):

        for full_name in element_name_s:
            current_object = complex_object
            for name in full_name.split('.'):  # a.b.c
                current_object = getattr(current_object, name, None)
                if current_object is None:
                    break
            if current_object:
                return True
        return False
    # endregion XML-МЕТОДЫ

    def _exception_from(self, fault: Fault):

        if fault.code is None:  # Unknown fault occured?
            """
            <env:Envelope xmlns:...>
                <env:Body>
                    <ns13:getStateResult ns4:version="10.0.1.1" Id=...>
                        ...
                    <ns4:RequestState>3</ns4:RequestState>
                    <ns4:MessageGUID>...</ns4:MessageGUID>
            <ns4:ErrorMessage>
                <ns4:ErrorCode>EXP001000</ns4:ErrorCode>
                <ns4:Description>Произошла ошибка при передаче данных.
                    Попробуйте осуществить передачу данных повторно.
                    В случае, если повторная передача данных не проходит
                    - направьте обращение в службу поддержки
                    пользователей ГИС ЖКХ.
                </ns4:Description>
            </ns4:ErrorMessage>
                    </ns13:getStateResult>
                </env:Body>
            </env:Envelope>
            """
            fault_detail = str(fault.detail, 'utf-8')  # в UTF!

            return GisProcessError.from_fault(fault_detail)
        elif (fault.code.endswith('Server') and  # env:Server
                fault.detail is not None and len(fault.detail) > 0):
            """
            <env:Fault>
                <faultcode>env:Server</faultcode> ---> fault.code
                <faultstring>
                    EXP001000: Произошла ошибка при передаче данных...
                </faultstring> ---> fault.message
                <detail> ---> fault.detail ~ XML: fault_node.find("detail")
                    <Fault>
                        <ErrorCode>EXP001000</ErrorCode>
                        <ErrorMessage>
                            Произошла ошибка при передаче данных...
                        </ErrorMessage>
                    </Fault> --- единственный элемент списка!
                </detail>
            </env:Fault>
            """
            # fault.message.split(': ', 1)
            gis_fault = self.schema.deserialize(fault.detail[0])
            # : zeep.objects.Fault - НЕ zeep.exceptions.Fault!
            stack_trace = gis_fault.StackTrace if gis_fault.StackTrace else None

            fault_error_message = "Внутренняя ошибка ГИС ЖКХ" \
                if gis_fault.ErrorMessage == 'Unknown fault occured' \
                else gis_fault.ErrorMessage  # WARN ошибка в написании "occured"

            return GisProcessError(gis_fault.ErrorCode,
                fault_error_message, stack_trace)

        # иначе возвращаем полученную ошибку ГИС ЖКХ в первоначальном виде
        return GisProcessError(fault.code, fault.message, fault.detail)

    def send_message(self, name: str, header: dict, body: dict):
        """
        Инициировать обработку запроса веб-сервисом
        """
        if (name != 'getState' and  # запрос квитанции (НЕ состояния)?
                self.session.IS_SECURE_CONNECTION):  # защищенное соединение?
            body['Id'] = 'signed-data-container'  # значение по умолчанию
            client_logger.debug("Добавлен постоянный атрибут"
                f" Id={sb(body['Id'])} элемента запроса квитанции")

        client_logger.debug(f"Содержимое заголовка запроса:\n\t{header}")
        client_logger.debug(f"Содержимое (тела) запроса:\n\t{body}")

        service_operation = self.get_service_operation(name)

        header_type = 'RequestHeader' if 'orgPPAGUID' in header \
            else 'ISRequestHeader'  # задается в Message.header
        header_element = self.create_xml_element(header_type, **header)

        client_logger.debug("Формирование и отправка XML запроса"
            f" операции ГИС ЖКХ {name} с заголовком {header_type}")

        try:  # response (envelope) = { header, body }
            # XML-элементы создаются zeep из переданных именованных атрибутов
            response = service_operation(_soapheaders=[header_element], **body)
        except SystemExit as system:  # pygost/gost34112012.py;billiard/pool.py?
            raise RestartSignal(system)  # перезапуск запроса операции?
        except TypeError:  # ошибка в структуре запроса?
            # в запросе ожидается kwargs, а передается args ~ dict.items()?
            raise  # будет обработано как стандартное исключение
        except ValidationError:  # ошибка в структуре запроса?
            raise  # будет обработано как стандартное исключение
        except XMLParseError as xml_error:  # кроме UnexpectedElementError
            error_message = getattr(xml_error, 'message', str(xml_error))
            raise GisProcessError('XML', error_message)
        except Fault as fault:  # серверная ошибка ГИС ЖКХ?
            # TODO if fault.code is None:
            #  assert response is None or response.body is None
            #  return self.schema.deserialize(fault.detail.?)
            processing = self._exception_from(fault)
            # полученная ошибка носит временный характер?
            if processing.error_code in self.REDEEMABLE_FAULTS:
                raise RestartSignal(processing)  # перезапуск?
            raise processing  # выбрасываем сформированной исключение
        except RequestsSSLError as error:  # ошибка защищенного соединения?
            if error.response:  # получен ответ от сервера?
                raise GisTransferError(error.response.status_code,
                    error.response.reason)  # SSLError : ConnectionError
            raise GisTransferError(495, str(error))  # WARN новое исключение
        except RequestConnectionError as connect:  # ошибка подключения?
            raise RestartSignal(connect)  # перезапускаем запрос!
        except Timeout:  # 011: Socket timeout, 408: Request Timeout
            # WARN время ожидания и повторы настраиваются на уровне транспорта
            raise GisTransferError(408,
                "Время ожидания выполнения операции истекло")
        except HTTPError as error:  # 400: Bad Request
            # 401: Unauthorized, 403: Forbidden, 404: Not Found
            raise GisTransferError(error.response.status_code,
                error.response.reason)
        except RequestException as error:
            # RequestException.response : requests.Response
            raise GisTransferError(error.response.status_code,
                error.response.reason)
        else:  # WARN необработанные ошибки будут возбуждены в неизменном виде!
            # заголовок и тело ответа во внутреннем формате zeep ~ dict
            client_logger.debug(f"Заголовок ответа: {response.header}")
            client_logger.debug(f"Тело ответа: {response.body}")
            # zeep.objects поддерживают получение значений через '.'
            # и удаление атрибутов оператором del
            # zeep.objects.[ObjectType] = {__values__: OrderedDict}
            return response.body  # : AckRequest или getStateResult - оболочки
