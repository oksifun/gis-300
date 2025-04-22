from zeep import Plugin
from zeep.client import logger as client_logger
from zeep.plugins import HistoryPlugin

from app.gis.core.gost import Certificate
from app.gis.core import xmldsig as xml
from app.gis.core.xmldsig import SCHEMA_NS, XMLDSig, cleanup


class SamplePlugin(Plugin):

    # выполняется ДО отправки запроса на сервер
    def egress(self, envelope, http_headers, operation, binding_options):

        return envelope, http_headers  # возвращаем измененные объекты!

    # выполняется ПОСЛЕ получения ответа сервера
    def ingress(self, received_envelope, http_headers, operation):

        return received_envelope, http_headers


class DebugPlugin(HistoryPlugin):

    @property
    def sent_envelope(self) -> bytes or None:
        if self._buffer:  # deque
            sent = self.last_sent.get('envelope') \
                if self.last_sent else None
            return xml.get_canonic(sent) if sent is not None else None

    @property
    def received_envelope(self) -> bytes or None:
        if self._buffer:  # deque
            received = self.last_received.get('envelope') \
                if self.last_received else None
            # FutureWarning: Use specific 'len(elem)' or 'elem is not None'.
            return xml.get_canonic(received) if received is not None else None


class NoSignaturePlugin(Plugin):
    """
    Плагин для работы с тестовыми серверами (без электронной подписи)
    """

    def __init__(self):

        client_logger.warn("Подключен плагин для работы с"
            " тестовыми серверами (без электронной подписи)")

    def egress(self, envelope, http_headers, operation, binding_options):

        return envelope, http_headers


class XAdESPlugin(Plugin):
    """
    Плагин подписывающий данные электронной подписью в формате XAdES-BES.

    ДАЙДЖЕСТ 1: содержимое тега <ns1:Body> (элемент запроса с Id атрибутом)
    без первого и последнего перевода строки
    канонизируется алгоритмом C14N (exclusive = True), считается хеш-сумма
    по ГОСТ-у и выводится в виде BASE64.
    openssl dgst -engine gost -md_gost94  -binary | base64
    * ГОСТ-engine указан явно, но можно прописать его в openssl.cnf

    ДАЙДЖЕСТ 2: сертификат в x509 декодируется из BASE64,
    считается его хеш-сумма и кодируется в BASE64.

    ДАЙДЖЕСТ 3: формируется блок <xades:SignedProperties>,
    канонизируется алгоритмом C14N (exclusive = False)
    и кодируется в BASE64.

    ПОДПИСЬ: элемент <ds:SignedInfo> канонизируется алгоритмом C14N
    (exclusive = False), подписывается по ГОСТ-у
    без первого и последнего перевода строки и кодируется в BASE64.
    openssl dgst -sign private.key -engine gost -md_gost94 -binary | base64
    """

    def __init__(self, certificate: Certificate):

        self._certificate = certificate

        client_logger.debug("Плагин подписывающий данные электронной"
            " подписью в формате XAdES-BES подключен")

    def egress(self, envelope, http_headers: dict, operation,
            binding_options, *args, **kwargs):

        # найдем элемент запроса по идентификатору (атрибуту) Id
        request = envelope.find('.//env:Body//*[@Id]', namespaces=SCHEMA_NS)
        if request is None:  # запрос без ид. не подписывается
            # (getState или нешифрованное соединение)
            return envelope, http_headers

        # формируем элемент подписи
        signature = XMLDSig(self._certificate).assemble(request)
        request.insert(0, signature)  # добавляем подпись в начало
        # элемента запроса (append - в конец)

        cleanup(envelope)  # финальная очистка сообщения перед отправкой
        # (лишние пространства имен)

        return envelope, http_headers
