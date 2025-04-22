from base64 import encodebytes, b64encode, b64decode
# b64encode ~ binascii.b2a_base64, b64decode ~ binascii.a2b_base64

from asn1crypto import pem, x509  # from pyasn1.type.univ import OctetString

from pygost.gost341194 import new as gost_2001_hash
from pygost.gost34112012256 import new as gost_2012_hash  # BIG-endian hash
from pygost.gost3410 import CURVES, public_key as get_public_key, \
    sign as gost_3410_sign, verify as gost_3410_verify, \
    prv_unmarshal, pub_marshal  # pub_unmarshal

# MODE (не используется с 5.0) - длина дайджеста и подписи:
# 2001 - 32/64 байта, 2012 - 64/128 байта
GOST_CURVE = CURVES[  # openssl pkey -text -in [private_key_file].pem
    "id-GostR3410-2001-CryptoPro-XchA-ParamSet"
]  # эллиптическая кривая (параметры шифрования)


def b2str(binary_data: bytes, delimiter='', is_upper=False) -> str:
    template = '%.2X' if is_upper else '%.2x'

    # ''.join('%02x' % x for x in list(data))
    result = delimiter.join([template % x for x in binary_data])
    return result


def binary(data) -> bytes:
    """
    Бинарное представление данных
    """
    if isinstance(data, bytes):  # unicode
        return data
    elif isinstance(data, str):
        return data.encode(encoding='utf-8')  # ~ bytes(data, 'ascii')
    else:
        raise TypeError("Данные должны быть в строковом или бинарном формате")


def bin_to_b64(bin_data: bytes) -> str:
    """
    Кодирование данных в Base64
    """
    b64_data = b64encode(bin_data).decode('utf-8')  # b2str(binary_data)
    return b64_data


def b64_to_bin(data) -> bytes:
    """
    Раскодирование данных из Base64
    Если данные не закодированы, будет возвращено бинарное представление
    """
    try:  # пытаемся раскодировать данные (в конце должен быть знак =)
        bin_data = b64decode(data, validate=True)
    except ValueError:  # binascii.Error
        bin_data = binary(data)

    return bin_data


def calc_hash(bin_data: bytes, is_big_endian=True) -> bytes:
    """
    Стрибог: 256-битный (на выходе 32 байта) хэш по алгоритму ГОСТ Р 34.11-2012
    openssl dgst -binary -md_gost12_256 <der_encoded_cert_public_key.cer>

    ГИС ЖКХ требует хэш в BIG-endian, CryptoPro возвращает в little-endian!
    """
    data_hash: bytes = gost_2012_hash(bin_data).digest()  # BIG-endian

    if not is_big_endian:
        data_hash = data_hash[::-1]  # инвертируем последовательность байтов

    return data_hash


def calc_old_hash(data: bytes) -> str:
    """
    Вычислить хэш по алгоритму ГОСТ Р 34.11-2001
    openssl dgst -md_gost94 <file_name>
    """
    return gost_2001_hash(data).hexdigest()


def get_digest(data) -> str:
    """
    Дайджест произвольных данных:
    1. считаем хэш данных по алгоритму ГОСТ Р 34.11-2012
    2. кодируем в Base64 и возвращаем строковое представление в UTF-8
    """
    binary_data = binary(data)

    data_hash = calc_hash(binary_data, True)

    data_digest = bin_to_b64(data_hash)
    return data_digest


# @app.task(name='gost.get_digest')
def get_b64_digest(data: str) -> str:
    """
    Задача вычисления дайджеста данных:
    1. считаем хэш данных по алгоритму ГОСТ Р 34.11-2012
    2. кодируем в Base64 и возвращаем строковое представление в UTF-8
    """
    binary_data = b64_to_bin(data)

    data_hash = calc_hash(binary_data, True)

    b64_digest = bin_to_b64(data_hash)
    return b64_digest


def get_digest_async(data) -> str:
    """
    Вычисление дайджеста данных по алгоритму ГОСТ Р 34.11-2012
    """
    b64_data = bin_to_b64(binary(data))

    async_task = get_b64_digest.delay(b64_data)
    b64_digest = async_task.get()

    return b64_digest


def sign_data(data: bytes, key: bytes) -> bytes:
    """
    Подпись данных по алгоритму ГОСТ 34.10-2012-256
    Подпись может быть декодирована в iso-8859-1
    openssl dgst -sign [private_key.file] -binary
            -md_gost12_256 [data.file] > signed.file
    """
    # вычисляем хэш данных в little-endian
    data_digest: bytes = calc_hash(data, False)

    prv: int = prv_unmarshal(key)  # распаковка приватного ключа
    bin_sign: bytes = gost_3410_sign(GOST_CURVE, prv, data_digest)

    return bin_sign


# @app.task(name='gost.sign_data')
def sign_b64_data(data: str, key: str) -> str:
    """
    Задача подписи данных по алгоритму ГОСТ 34.10-2012-256
    """
    bin_data = b64_to_bin(data)  # декодируем дайджест из Base64
    bin_key = b64_to_bin(key)  # декодируем бинарный ключ из Base64

    # синхронный вызов функции подписи в процессе задачи
    bin_sign = sign_data(bin_data, bin_key)

    # кодируем результат в строковое представление Base64
    b64_sign = bin_to_b64(bin_sign)
    return b64_sign


def verify_sign(data: bytes, signature: bytes, key: bytes) -> bool:
    """
    Проверка подписи данных по алгоритму ГОСТ 34.10-2012-256
    openssl x509 -pubkey -noout -in cert.pem > pubkey.pem
    openssl dgst -verify pubkey.pem -signature signature_file data_file
    """
    # распаковка приватного ключа (преобразование в long int)
    prv: int = prv_unmarshal(key)
    # публичный ключ из закрытого
    pub: tuple = get_public_key(GOST_CURVE, prv)

    # OpenSSL формирует подпись на основе little-endian дайджеста
    data_digest: bytes = calc_hash(data, False)

    try:
        result: bool = gost_3410_verify(GOST_CURVE, pub, data_digest, signature)
    except ValueError:
        result = False
    return result


# @app.task(name='gost.verify_sign')
def verify_b64_sign(data: str, signature: str, key: str) -> bool:
    """
    Задача проверки подписи данных (НЕ дайджеста)
    по алгоритму ГОСТ 34.10-2012-256
    """
    bin_data = b64_to_bin(data)
    bin_sign = b64_to_bin(signature)
    bin_key = b64_to_bin(key)

    bool_result = verify_sign(bin_data, bin_sign, bin_key)

    return bool_result


class Certificate:

    loaded: dict = {}  # загруженные сертификаты

    @classmethod
    def load(cls, cert_path, key_path=None):
        """
        pem: ---BEGIN CERTIFICATE---base64.encodebytes(DER)---END CERTIFICATE---

        :param cert_path: str / Path - путь файла PEM-сертификата (X.509 ASCII)
            или DER
        :param key_path: путь файла приватного ключа в формате DER
        """
        loaded_cert = cls.loaded.get(str(cert_path), None)
        if loaded_cert:  # сертификат уже загружен?
            return loaded_cert

        with open(cert_path, mode='rb') as cert_stream:
            cert_bytes = cert_stream.read()  # загрузка сертификата

        _certificate = _private_key = _public_key = None

        if pem.detect(cert_bytes):  # PEM
            for type_name, headers, der_bytes \
                    in pem.unarmor(cert_bytes, multiple=True):
                if type_name == 'CERTIFICATE':
                    _certificate = der_bytes
                elif type_name == 'PRIVATE KEY':
                    _private_key = der_bytes
                elif type_name == 'PUBLIC KEY':
                    _public_key = der_bytes  # public_key = _public_key[-64:]
                else:
                    pass  # игнорируем
        else:  # DER
            _certificate = cert_bytes

            with open(key_path, mode='rb') as key_stream:
                _private_key = key_stream.read()

        loaded_cert = cls(_certificate, _private_key)  # конструктор

        loaded_cert.cert_path = cert_path  # сохраняем путь сертификата
        cls.loaded[str(cert_path)] = loaded_cert  # кэшируем загруженный серт.

        return loaded_cert

    def __init__(self, certificate: bytes, private_key: bytes = None):
        """
        Квалифицированный сертификат
        :param certificate: сертификат в бинарном формате
            open('der.cer','rb').read()
        :param private_key: закрытый ключ в бинарном формате
        """
        # пути по умолчанию не определены, как вариант: io.BytesIO(...)
        self.cert_path = self.key_path = None
        # кэшируемые свойства сертификата
        self._digest = self._serial = self._thumb = None

        # бинарный сертификат
        self._certificate: bytes = certificate
        # загружаем сертификат
        x509_cert: x509.Certificate = x509.Certificate.load(certificate)

        if private_key:
            # openssl pkey -text -in key_file.pem
            self.private_key: bytes = private_key[-32:]  # последние 32 байта

            # распаковка приватного ключа (преобразование в long int)
            prv: int = prv_unmarshal(self.private_key)
            # получаем публичный ключ из закрытого
            self._public_coords: tuple = get_public_key(GOST_CURVE, prv)

            self.public_key: bytes = pub_marshal(self._public_coords)
        else:
            self.private_key = None

            # openssl x509 -pubkey -noout -in key_file.pem  # последние 64 байта
            self.public_key = x509_cert.public_key

        # openssl x509 -noout -serial -in [certificate_file]
        # win: hex(decimal_serial_number)
        self.serial_number: int = x509_cert.serial_number

        cert_hash: bytes = x509_cert.sha1  # хэш в SHA1 формате
        self.thumb_print = cert_hash.hex().upper()  # b2str(self._x509.sha1)

        self.digest = get_digest(certificate)  # дайджест сертификата

        self._issuer = x509_cert.issuer

    def as_base64(self, split_lines=True) -> str:
        """
        x509 сертификат в Base64 (PEM-формат)
        :param split_lines: разбить на строки по 64 байта (символа)
        """
        if split_lines:
            encoded = encodebytes(self._certificate)  # RFC 2045 (MIME)
        else:
            encoded = b64encode(self._certificate)

        return encoded.decode('utf-8')

    def get_issuer_name(self, is_reversed=False, is_lower=False):
        """
        <ds:X509IssuerName>
            1.2.840.113549.1.9.1=ca_tensor@tensor.ru,
            1.2.643.100.1=1027600787994,
            1.2.643.3.131.1.1=007605016030,
            C=RU,ST=76 Ярославская область,L=г. Ярославль,
            STREET=Московский проспект д.12,
            OU=Удостоверяющий центр,O=ООО \"КОМПАНИЯ \"ТЕНЗОР\",
            CN=ООО \"КОМПАНИЯ \"ТЕНЗОР\"
        </ds:X509IssuerName>
        """
        # openssl x509 -noout -issuer -nameopt sep_multiline,utf8 -in cert.file
        # issuer, _ = fsb795.issuerCert()
        # объектные идентификаторы (приказ ФСБ РФ от 27 декабря 2011 г. № 795)
        x509.NameType._map.update({  # объектный ид. типа атрибута: 1.2.643 - RU
            '2.5.4.3': 'CN',  # Common Name
            '2.5.4.6': 'C',  # Country
            '2.5.4.7': 'L',  # Locality Name
            '2.5.4.8': 'ST',  # State or Province
            '2.5.4.9': 'STREET',  # Street (Address)
            '2.5.4.10': 'O',  # Organization Name
            '2.5.4.11': 'OU',  # Organizational Unit Name
            '1.2.840.113549.1.9.1': '1.2.840.113549.1.9.1',  # emailAddress
            '1.2.643.3.131.1.1': '1.2.643.3.131.1.1',  # INN
            '1.2.643.100.1': '1.2.643.100.1',  # ogrn
            '1.2.643.100.3': '1.2.643.100.3',  # SNILS
            '1.2.643.100.5': '1.2.643.100.5',  # OGRNIP
        })
        x509_issuer_name: x509.Name = self._issuer
        # native (OrderedDict) представление данных (рекурсивное)
        issuer = x509_issuer_name.native

        # перевернутый список?
        parts = list(issuer.items())[::-1] if is_reversed else issuer.items()

        normal = lambda k: str(k).lower() if is_lower else str(k)
        escape = lambda v: str(v).replace('"', '\\"').replace(',', '\\,')
        # replace(' ', '')?

        name = ','.join(f"{normal(k)}={escape(v)}" for k, v in parts)
        return name

    def get_signature(self, data, write_sig_file=False) -> str:
        """
        Подпись данных в СИНХРОННОМ режиме:
        1. считаем хэш по алгоритму ГОСТ Р 34.11-2012
        2. подписываем данные по алгоритму ГОСТ 34.10-2012-256
        3. кодируем в Base64 и возвращаем строковое представление в UTF-8
        """
        bin_data = binary(data)

        bin_sign = sign_data(bin_data, self.private_key)  # iso-8859-1

        if write_sig_file:
            with open('pygost.sig', mode='wb') as sig:
                sig.write(bin_sign)

        b64_sign = bin_to_b64(bin_sign)  # OctetString(binary_signature)
        return b64_sign

    def get_signature_async(self, data) -> str:
        """
        Подпись данных в асинхронном режиме:
        1. считаем хэш по алгоритму ГОСТ Р 34.11-2012
        2. подписываем данные по алгоритму ГОСТ 34.10-2012-256
        3. кодируем в Base64 и возвращаем строковое представление в UTF-8
        """
        # данные могут быть как в строковом, так и бинарном формате
        bin_data = binary(data)
        b64_data = bin_to_b64(bin_data)  # данные для подписи в Base64

        # приватный ключ содержит не ASCII символы
        b64_key = bin_to_b64(self.private_key)

        async_task = sign_b64_data.delay(b64_data, b64_key)  # AsyncResult
        b64_sign = async_task.get()  # подпись в виде Base64 - строки

        return b64_sign

    def check_signature(self, data, signature) -> bool:
        """
        Синхронная проверка подписи данных
        """
        bin_data = b64_to_bin(data)
        bin_sign = b64_to_bin(signature)

        check_result = verify_sign(bin_data, bin_sign, self.private_key)

        return check_result

    def check_signature_async(self, data, signature) -> bool:
        """
        Асинхронная проверка подписи данных
        :param data: данные для проверки
        :param signature: подпись данных
        """
        bin_data = b64_to_bin(data)  # данные могут быть закодированы в Base64?
        b64_data = bin_to_b64(bin_data)  # кодируем в Base 64 для передачи

        bin_sign = b64_to_bin(signature)
        b64_sign = bin_to_b64(bin_sign)

        # приватный ключ содержит не ASCII символы
        b64_key = bin_to_b64(self.private_key)

        async_task = verify_b64_sign.delay(b64_data, b64_sign, b64_key)
        check_result = async_task.get()  # True - подпись соответствует данным

        return check_result
