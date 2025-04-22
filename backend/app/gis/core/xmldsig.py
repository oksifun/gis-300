from lxml import etree as xml  # НЕ xml.etree!
from lxml.builder import ElementMaker

from app.gis.core.gost import Certificate, get_digest

from app.gis.utils.common import get_guid, get_time

# region ПРОСТРАНСТВА ИМЕН
W3_ORG = 'http://www.w3.org'  # /2001/04/xmldsig-more#
# считаются ссылкми на одни и те же алгоритмы
IETF_URN = 'urn:ietf:params:xml:ns:cpxmlsec:algorithms'

TRANSFORM = {
    # удаление <signature/>
    'XMLDSIG_ENVELOPED': f'{W3_ORG}/2000/09/xmldsig#enveloped-signature',
    # 'XMLDSIG_CORE_ENV': f'{W3_ORG}/TR/2002/REC-xmldsig-core-20020212/'
    #                     'xmldsig-core-schema.xsd#enveloped-signature',
    # Exclusive XML Canonicalization (18.07.2002)
    'EXC_XML_C14N': f'{W3_ORG}/2001/10/xml-exc-c14n#',
}  # C14N и другие трансформации

DIGEST = {
    'GOST_R_34_11_94': f'{W3_ORG}/2001/04/xmldsig-more#gostr3411',
    'GOST_R_34_11_2012': f'{IETF_URN}:gostr34112012-256',
    'GOST_R_34_11_2012_512': f'{IETF_URN}:gostr34112012-512',
}  # HASH

SIGN = {
    # cipher: GOST2001-GOST89-GOST89
    'GOST_R_34_10_2001':
        f'{W3_ORG}/2001/04/xmldsig-more#gostr34102001-gostr3411',
    # GOST2012-GOST8912-GOST8912
    'GOST_R_34_10_2012': f'{IETF_URN}:gostr34102012-gostr34112012-256',
    # --||--
    'GOST_R_34_10_2012_512': f'{IETF_URN}:gostr34102012-gostr34112012-512',
}

XMLDSig_XAdES = 'http://uri.etsi.org/01903'

XADES = {
    'DEFAULT': f'{XMLDSig_XAdES}/v1.3.2#',
    'V141': f'{XMLDSig_XAdES}/v1.4.1#',
}

SCHEMA_NS = {  # общие для всех сервисов пространства имен
    'wsdl': "http://schemas.xmlsoap.org/wsdl/",
    # для SOAP 1.2 указывается другое пространство имен
    'soap': "http://schemas.xmlsoap.org/wsdl/soap/",
    # Envelope, Body, Header
    'env': "http://schemas.xmlsoap.org/soap/envelope/",
    'enc': "http://schemas.xmlsoap.org/soap/encoding/",
    'xs': "http://www.w3.org/2001/XMLSchema",  # xsd
    'xsi': "http://www.w3.org/2001/XMLSchema-instance",
    'ds': "http://www.w3.org/2000/09/xmldsig#",  # ns в WSDL
}

BASE_NS = {  # базовые пространства имен ГИС ЖКХ
    'base': "http://dom.gosuslugi.ru/schema/integration/base/",
    # имеют префикс 'tns' в своих схемах
    'nsi-base': "http://dom.gosuslugi.ru/schema/integration/nsi-base/",
    'organizations-base':
        "http://dom.gosuslugi.ru/schema/integration/organizations-base/",
    'organizations-registry-base': "http://dom.gosuslugi.ru/schema/integration/"
                                   "organizations-registry-base/",
    'individual-registry-base':
        "http://dom.gosuslugi.ru/schema/integration/individual-registry-base/",
    'account-base': "http://dom.gosuslugi.ru/schema/integration/account-base/",
    'house-base': "http://dom.gosuslugi.ru/schema/integration/premises-base/",
    'bills-base': "http://dom.gosuslugi.ru/schema/integration/bills-base/",
    'premises-base':
        "http://dom.gosuslugi.ru/schema/integration/premises-base/",
    'payments-base':
        "http://dom.gosuslugi.ru/schema/integration/payments-base/",
}
# endregion ПРОСТРАНСТВА ИМЕН


# region XML ФУНКЦИИ
def qname(name: str, ns: str = None) -> xml.QName:
    """
    Квалифицированное имя (qualified name)
    НЕ zeep.xsd.QName
    """
    return xml.QName(ns, name)


def from_string(xml_string: str):
    """Преобразовать XML-строку в XML-дерево (элемент)"""
    return xml.fromstring(xml_string)  # root


def from_file(file_name: str, content: dict):
    """
    Корневой элемент дерева из файла-шаблона
    с местами для вставки значений в виде {placeholder}
    """
    with open(file_name) as template_file:
        template = template_file.read()

    return xml.fromstring(template.format(content))


def apply_transformation(xslt_file_like, element_or_tree):
    """
    Применить XSLT-преобразование к XML-документу
    """
    xslt_object = xml.parse(xslt_file_like)
    transformation = xml.XSLT(xslt_object)

    return transformation(element_or_tree)


def wo_ns(element_or_tree):
    # http://wiki.tei-c.org/index.php/Remove-Namespaces.xsl
    xslt = b'''<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:output method="xml" indent="no"/>

    <xsl:template match="/|comment()|processing-instruction()">
        <xsl:copy>
            <xsl:apply-templates/>
        </xsl:copy>
    </xsl:template>

    <xsl:template match="*">
        <xsl:element name="{local-name()}">
            <xsl:apply-templates select="@*|node()"/>
        </xsl:element>
    </xsl:template>

    <xsl:template match="@*">
        <xsl:attribute name="{local-name()}">
            <xsl:value-of select="."/>
        </xsl:attribute>
    </xsl:template>
    </xsl:stylesheet>'''
    import io
    return apply_transformation(io.BytesIO(xslt), element_or_tree)


def get_root(element_or_tree):

    return element_or_tree.getroot() \
        if isinstance(element_or_tree, xml._ElementTree) else element_or_tree


def get_nsmap(element_or_tree) -> dict:

    nsmap: dict = get_root(element_or_tree).nsmap

    for p, n in dict(SCHEMA_NS, **BASE_NS).items():  # переименовываем префиксы
        for prefix in [k for k, v in nsmap.items() if v == n and k != p]:
            nsmap[p] = nsmap.pop(prefix)

    return nsmap


def get_ns_prefix(element, namespace: str) -> str:

    return next(iter(
        k for k, v in get_nsmap(element).items() if v == namespace
    ))


def get_element(parent, path: str, nsmap: dict = None):
    """
    Поиск XML-элемента в дереве или в указанных пространствах имен
    """
    elements = get_root(parent).xpath(path, namespaces=nsmap)
    return next(elements) if elements else None


def get_by_attr(parent, attribute: str, value: str):
    # SyntaxError: cannot use absolute path on element
    # .// - относительный путь
    element = get_root(parent).find(f'.//*[@{attribute}="{value}"]')

    if element is not None:
        return element
    else:
        raise AttributeError(
            f'Элемент с атрибутом {attribute}="{value}" не найден')


def get_attr(element, name: str):
    return element.attrib.get(name, None)  # attrib['Id']


def _fix_indent(elem, level=0):
    """
    Форматирование отступов элемента под авторством Fredrik Lundh
    ВНИМАНИЕ! Изменяет элемент! Каноникализация может быть нарушена!
    """
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            _fix_indent(elem, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def _remove_tails(element_or_tree):
    """
    <tag>text</tag>tail
    Лучше использовать XMLParser(remove_blank_text=True) при парсинге XML!
    """
    for element in element_or_tree.iter():
        element.tail = None


def cleanup(tree_or_element):
    """
    Удаление неиспользуемых пространств имен из дерева
    """
    xml.cleanup_namespaces(
        tree_or_element,  # элемент модифицируется!
        top_nsmap=None,  # пространства имен (префикс, путь)
        # переносимые в заголовок дерева или наивысший элемент
        keep_ns_prefixes=None  # принудительно оставляемые пространства имен
    )


def remove_element(parent, path: str, nsmap: dict):
    """
    Удаление дочернего элемента с заданным путем
    :returns: удаленный элемент или None
    """
    found = get_root(parent).xpath(_path=path, namespaces=nsmap)  # list
    if found:
        element = next(iter(found))  # [0]
        parent = element.getparent()
        parent.remove(element)  # также удаляет tail (текст после элемента)!
        return element
    else:
        return None


def remove_signature(tree_or_element,
        tag_name='{http://www.w3.org/2000/09/xmldsig#}Signature'):
    """
    Удаление подписи из элемента
    http://www.w3.org/2000/09/xmldsig#enveloped-signature

    Ничего не возвращает, изменяет переданный элемент!
    """
    # удалять содержимое элемента между тэгами (text) НЕ нужно!
    xml.strip_elements(
        tree_or_element, tag_name,
        with_tail=False  # текст после подписи (tail) удалять НЕ нужно!
    )


def get_canonic(element_or_tree, is_exclusive=True) -> bytes:
    """
    Каноникализация по алгоритму http://www.w3.org/2001/10/xml-exc-c14n#

    :param element_or_tree: XML элемент или дерево элементов
    :param is_exclusive:
        False - выносить пространства имен в корневой элемент дерева
            (или заголовок)
        True - все используемые ns включаются в элемент
            и он становится портативным (выносным = exclusive)

    :return: бинарная строка каноникализированного элемента
    """
    # xslt.deannotate(element_or_tree, cleanup_namespaces=True, xsi_nil=True)
    canonic_xml: bytes = xml.tostring(
        element_or_tree,
        encoding=None,  # кодировка не указывается (всегда используется UTF-8)
        method='c14n',  # c14n версии 1
        xml_declaration=False,  # XML-заголовок не используется (None)
        pretty_print=False,  # игнорируется при c14n(?)
        with_tail=True,  # оставлять текст, переносы строк, табуляции и пробелы
        # после элементов
        standalone=None,  # добавляет флаг standalone в заголовок (None)
        doctype=None,  # <!DOCTYPE reference
        # PUBLIC "-//OASIS//DTD DITA Reference//EN" "reference.dtd">
        exclusive=is_exclusive,  # вынос во внешние элементы выполняется только,
        # если они содержаться в их ns-карте!
        inclusive_ns_prefixes=None,  # ['wsse', 'SOAP-ENV']
        # <InclusiveNamespaces PrefixList="wsse SOAP-ENV".../>
        with_comments=False,  # коментарии могут удаляться при каноникализации
        # и при парсинге XML
        strip_text=False  # только для C14N 2.0!
    )
    return canonic_xml  # бинарный формат!


def get_pretty(element_or_tree, no_xml_stuff=False) -> str:
    """
    Отформатированный XML
    """
    # objectify.deannotate(element_or_tree, cleanup_namespaces = True)
    return xml.tostring(  # TODO отображать все элементы запроса, даже пустые
        wo_ns(element_or_tree) if no_xml_stuff else element_or_tree,
        encoding='utf-8',  # НЕ для c14n! значения: None, 'utf-8', 'unicode'
        method='xml',  # xml, html, text (plain, w/o tags), c14n, c14n2
        xml_declaration=not no_xml_stuff,  # <xml> заголовок, 'unicode' -> False
        pretty_print=True,  # вывод «ёлочкой»
        exclusive=True,  # выносит наружу пространства имен при c14n
        inclusive_ns_prefixes=None,  # не выносимые ns при c14n: ['ns0', 'ns1']
        with_tail=True,  # оставлять символы (переносы строк, табуляции и др.)
        # после закрывающего тега элемента?
        with_comments=True,  # False только при c14n!
    ).decode('utf-8')
# endregion XML ФУНКЦИИ


class XMLDSig:  # XML Digital Signature

    def __init__(self, certificate: Certificate):
        ds_ns = SCHEMA_NS['ds']
        xades_ns = XADES['DEFAULT']

        self._id = get_guid()  # идентификатор подписи в формате UUID
        self._time = get_time()  # время подписи в формате datetime

        self._certificate = certificate

        self._ds = ElementMaker(namespace=ds_ns, nsmap={'ds': ds_ns})
        self._xades = ElementMaker(namespace=xades_ns,
            nsmap={'xades': xades_ns, 'ds': ds_ns})

    @property
    def signing_certificate(self):
        """
        <xades:SigningCertificate>
            <xades:Cert>
                <xades:CertDigest>
                    <ds:DigestMethod [Algorithm] />
                    <ds:DigestValue />
                </xades:CertDigest>
                <xades:IssuerSerial>
                    <ds:X509IssuerName />
                    <ds:X509SerialNumber />
                </xades:IssuerSerial>
            </xades:Cert>
        </xades:SigningCertificate>
        """
        cert_digest = self._certificate.digest  # хэш сертификата
        cert_issuer_name = self._certificate. \
            get_issuer_name(is_reversed=True, is_lower=True)
        cert_serial_number = str(self._certificate.serial_number)

        signing_cert = self._xades.SigningCertificate(  # кэшируем
            self._xades.Cert(
                self._xades.CertDigest(
                    self._ds.DigestMethod(
                        Algorithm=DIGEST['GOST_R_34_11_2012']),
                    self._ds.DigestValue(cert_digest)
                ),
                self._xades.IssuerSerial(
                    self._ds.X509IssuerName(cert_issuer_name),
                    self._ds.X509SerialNumber(cert_serial_number)
                )
            )
        )
        return signing_cert

    @property
    def xades_bes_props(self):
        """
        XML Advanced Electronic Signatures - Basic Electronic Signature

        <xades:QualifyingProperties [Target]>
            <xades:SignedProperties [Id]=[Target]-signedprops>
                <xades:SignedSignatureProperties>
                    <xades:SigningTime />
                    <xades:SigningCertificate />
                </xades:SignedSignatureProperties>
            </xades:SignedProperties>
        </xades:QualifyingProperties>
        """
        signing_cert_element = self.signing_certificate  # элемент сертификата

        xades_signed_props = self._xades.SignedProperties(
            # xades.SignedDataObjectProperties(...),  # не используется
            self._xades.SignedSignatureProperties(
                self._xades.SigningTime(self._time.isoformat()),
                signing_cert_element,
            ), Id=f"xmldsig-{self._id}-signedprops"
        )
        xades_qualifying_props = self._xades.QualifyingProperties(
            xades_signed_props, Target=f"#xmldsig-{self._id}")
        canonic_signed_props = get_canonic(xades_signed_props,
            is_exclusive=True)  # ОБЯЗАТЕЛЬНА ИСКЛЮЧАЮЩАЯ КАНОНИКАЛИЗАЦИЯ!
        signed_props_digest = get_digest(canonic_signed_props)  # парам. подписи
        return xades_qualifying_props, signed_props_digest

    def assemble(self, data_element):
        """
        <Signature> - данные подписи, включая саму подпись и сертификат.
            <SignedInfo> - информация о подписываемых данных
                    и алгоритмах формировании подписи
                <CanonicalizationMethod [Algorithm]/> - канокализирующий алг.,
                    применяемый к SignedInfo перед вычислением подписи
                <SignatureMethod [Algorithm] /> - алгоритм генерации и валидации
                    подписи канокализированного SignedInfo
                <Reference [URI] [Type] [Id]> - инфо. о подписываемых данных:
                        местоположение данных в документе,
                        алгоритм вычисления хэша данных, преобразования,
                        сам хэш
                    <Transforms> - применяемые к данным(запросу) перобразования:
                        <Transform [Algorithm] />
                        ... - перечисляются все трансформации,
                            применяемые к указанному в Reference элементу
                    </Transforms>
                    <DigestMethod [Algorithm] /> - алгоритм вычисления хэша
                        от результатов Transforms
                    <DigestValue /> - значение хэша от результатов Transforms,
                        на которые указывает Reference URI
                </Reference>
                ... - может встречаться более одного раза
            </SignedInfo>
            <SignatureValue /> - подпись
            <KeyInfo /> - информация о ключе,
                где X509Certificate - это base64encoded сертификат из ключа
            <Object /> - расширение электронной подписи (XAdES-BES)
        </Signature>
        """
        # атрибут подписываемого элемента
        data_container_id = get_attr(data_element, 'Id')
        if data_container_id is None:  # идентификатор должен присутствовать!
            raise AttributeError(
                "Передан элемент с данными без обязательного атрибута")

        data_element.text = ''  # очищаем текстовую часть (переносы строки и тп)
        # перед трансформациями!
        remove_signature(data_element)  # удаляем подпись, если таковая имеется

        canonic_data = get_canonic(data_element,
            is_exclusive=True)  # ОБЯЗАТЕЛЬНА ИСКЛЮЧАЮЩАЯ КАНОНИКАЛИЗАЦИЯ!
        data_digest = get_digest(canonic_data)  # дайджест бизнес-данных

        xades_bes, props_digest = self.xades_bes_props  # элемент параметров
        # подписи в формате XAdES-BES
        #  props_digest = get_digest(get_canonic(xades_bes[0], True))
        # 0 - первый дочерний элемент

        signed_info_element = self._ds.SignedInfo(
            self._ds.CanonicalizationMethod(
                Algorithm=TRANSFORM['EXC_XML_C14N']),
            self._ds.SignatureMethod(Algorithm=SIGN['GOST_R_34_10_2012']),
            self._ds.Reference(
                self._ds.Transforms(
                    self._ds.Transform(
                        Algorithm=TRANSFORM['XMLDSIG_ENVELOPED']),
                    self._ds.Transform(Algorithm=TRANSFORM['EXC_XML_C14N'])
                ),
                self._ds.DigestMethod(Algorithm=DIGEST['GOST_R_34_11_2012']),
                self._ds.DigestValue(data_digest),
                # Id=f"xmldsig-{self._id}-ref",  # нет в 2012
                URI=f"#{data_container_id}"  # подписывая ВЕСЬ документ URI = ''
            ),
            self._ds.Reference(
                self._ds.Transforms(
                    self._ds.Transform(Algorithm=TRANSFORM['EXC_XML_C14N'])
                ),
                self._ds.DigestMethod(Algorithm=DIGEST['GOST_R_34_11_2012']),
                self._ds.DigestValue(props_digest),
                Type=f"{XMLDSig_XAdES}#SignedProperties",
                URI=f"#xmldsig-{self._id}-signedprops"
            )
        )

        # исключающая каноникализация НЕ обязательна
        canonic_signed_info = get_canonic(signed_info_element)
        # ФОРМИРОВАНИЕ ПОДПИСИ
        signature_value = self._certificate.get_signature(canonic_signed_info)

        # можно в одну строку
        cert_base64_encoded = self._certificate.as_base64(split_lines=False)
        # cert_guid = self._certificate.thumb_print  # get_guid()

        signature = self._ds.Signature(
            signed_info_element,
            self._ds.SignatureValue(signature_value,
                Id=f"xmldsig-{self._id}-sigvalue"),
            self._ds.KeyInfo(
                self._ds.X509Data(
                    self._ds.X509Certificate(cert_base64_encoded)),
                # Id=f"xmldsig-{cert_guid}"  # рандомный ид. ключа, нет в 2001
            ),
            self._ds.Object(xades_bes),
            Id=f"xmldsig-{self._id}"
        )
        return signature

    def _from_template(self, envelope,
            signed_data_container_id: str, file_name: str):
        """
        Старый метод формирования элемента подписи из шаблона
        НЕ ИСПОЛЬЗОВАТЬ!
        """
        data = dict(
            c14n_algorithm=TRANSFORM['EXC_XML_C14N'],
            digest_algorithm=DIGEST['GOST_R_34_11_2012'],
            sign_algorithm=SIGN['GOST_R_34_10_2012'],
            signed_id=signed_data_container_id,  # ид. подрисываемого элемента
            signature_id=str(get_guid()),  # идентификатор подписи
            signing_time=get_time().isoformat(),  # время подписи
            x509_issuer_name=self._certificate.get_issuer_name(),
            x509_sn=str(self._certificate.serial_number),
            x590_cert=self._certificate.as_base64(),
        )

        nsmap = get_nsmap(envelope)  # карта пространств имен

        # элемент запроса c атрибутом Id
        request = get_element(envelope,
            '//*[@Id="%s"]' % data['signed_id'], nsmap)
        canonic_request = get_canonic(request, is_exclusive=True)

        # первый digest от каноникализированного элемента запроса
        data['digest1'] = get_digest(canonic_request)

        # второй digest от самого сертификата
        data['digest2'] = self._certificate.digest

        data['digest3'] = ""  # будут заполнены позже
        data['signature_value'] = ""

        # загружаем и заполняем шаблон XML-DSig (включает в себя XAdES-BES)
        xmldsig = from_file(file_name, **data)

        # вставляем полученный элемент подписи в элемент запроса
        get_element(envelope,
            '//*[@Id="%s"]' % data['signed_id'], nsmap).insert(0, xmldsig)

        # элемент свойств подписи XAdES
        signed_props = get_element(envelope,
            '//*[@Id="xmldsig-%s-signedprops"]' % data['signature_id'], nsmap)
        canonic_props = get_canonic(signed_props)
        # третий digest от каноникализированного элемента свойств подписи
        digest3 = get_digest(canonic_props)

        # вставляем полученный дайджест
        path = '//ds:SignedInfo/ds:Reference[@URI="#xmldsig-%s-signedprops"]/' \
               'ds:DigestValue' % data['signature_id']
        digest3_element = get_element(envelope, path, nsmap)
        digest3_element.text = digest3

        # К элементу <ds:SignedInfo> и его содержимому (включая атрибуты)
        # применяется каноникализация на основе результата рассчитывается
        # электронная подпись по алгоритму ГОСТ Р 34.11-2001 и заносится
        # в <ds:SignatureValue> в формате Base64.
        signed_info = get_element(envelope, '//ds:SignedInfo', nsmap)
        canonic_info = get_canonic(signed_info)
        signature = self._certificate.get_signature(canonic_info)
        signature_value = get_element(envelope, '//ds:SignatureValue', nsmap)
        signature_value.text = signature

        return envelope
