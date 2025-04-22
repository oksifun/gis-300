import base64
import subprocess
from io import BytesIO
import qrcode
import settings

from PIL import Image
from PIL import ImageDraw

from processing.data_producers.billing.payment_url import (
    generate_public_url_for_pay
)
from processing.models.billing.accrual import Accrual
from app.house.models.house import House
from processing.models.billing.settings import Settings
from processing.models.choices import ACCRUAL_SECTOR_TYPE_CHOICES_AS_DICT
from decimal import Decimal

# Copied from http://en.wikipedia.org/wiki/Code_128
# Value Weights 128A    128B    128C
CODE128_CHART = """
0       212222  space   space   00
1       222122  !       !       01
2       222221  "       "       02
3       121223  #       #       03
4       121322  $       $       04
5       131222  %       %       05
6       122213  &       &       06
7       122312  '       '       07
8       132212  (       (       08
9       221213  )       )       09
10      221312  *       *       10
11      231212  +       +       11
12      112232  ,       ,       12
13      122132  -       -       13
14      122231  .       .       14
15      113222  /       /       15
16      123122  0       0       16
17      123221  1       1       17
18      223211  2       2       18
19      221132  3       3       19
20      221231  4       4       20
21      213212  5       5       21
22      223112  6       6       22
23      312131  7       7       23
24      311222  8       8       24
25      321122  9       9       25
26      321221  :       :       26
27      312212  ;       ;       27
28      322112  <       <       28
29      322211  =       =       29
30      212123  >       >       30
31      212321  ?       ?       31
32      232121  @       @       32
33      111323  A       A       33
34      131123  B       B       34
35      131321  C       C       35
36      112313  D       D       36
37      132113  E       E       37
38      132311  F       F       38
39      211313  G       G       39
40      231113  H       H       40
41      231311  I       I       41
42      112133  J       J       42
43      112331  K       K       43
44      132131  L       L       44
45      113123  M       M       45
46      113321  N       N       46
47      133121  O       O       47
48      313121  P       P       48
49      211331  Q       Q       49
50      231131  R       R       50
51      213113  S       S       51
52      213311  T       T       52
53      213131  U       U       53
54      311123  V       V       54
55      311321  W       W       55
56      331121  X       X       56
57      312113  Y       Y       57
58      312311  Z       Z       58
59      332111  [       [       59
60      314111  \       \       60
61      221411  ]       ]       61
62      431111  ^       ^       62
63      111224  _       _       63
64      111422  NUL     `       64
65      121124  SOH     a       65
66      121421  STX     b       66
67      141122  ETX     c       67
68      141221  EOT     d       68
69      112214  ENQ     e       69
70      112412  ACK     f       70
71      122114  BEL     g       71
72      122411  BS      h       72
73      142112  HT      i       73
74      142211  LF      j       74
75      241211  VT      k       75
76      221114  FF      l       76
77      413111  CR      m       77
78      241112  SO      n       78
79      134111  SI      o       79
80      111242  DLE     p       80
81      121142  DC1     q       81
82      121241  DC2     r       82
83      114212  DC3     s       83
84      124112  DC4     t       84
85      124211  NAK     u       85
86      411212  SYN     v       86
87      421112  ETB     w       87
88      421211  CAN     x       88
89      212141  EM      y       89
90      214121  SUB     z       90
91      412121  ESC     {       91
92      111143  FS      |       92
93      111341  GS      }       93
94      131141  RS      ~       94
95      114113  US      DEL     95
96      114311  FNC3    FNC3    96
97      411113  FNC2    FNC2    97
98      411311  ShiftB  ShiftA  98
99      113141  CodeC   CodeC   99
100     114131  CodeB   FNC4    CodeB
101     311141  FNC4    CodeA   CodeA
102     411131  FNC1    FNC1    FNC1
103     211412  StartA  StartA  StartA
104     211214  StartB  StartB  StartB
105     211232  StartC  StartC  StartC
106     2331112 Stop    Stop    Stop
""".split()

VALUES = [int(value) for value in CODE128_CHART[0::5]]
WEIGHTS = dict(zip(VALUES, CODE128_CHART[1::5]))
CODE128A = dict(zip(CODE128_CHART[2::5], VALUES))
CODE128B = dict(zip(CODE128_CHART[3::5], VALUES))
CODE128C = dict(zip(CODE128_CHART[4::5], VALUES))

for charset in (CODE128A, CODE128B):
    charset[' '] = charset.pop('space')


def code128_format(data):
    """
    Generate an optimal barcode from ASCII text
    """
    text = str(data)
    pos = 0
    length = len(text)

    # Start Code
    if text[:2].isdigit() and length > 1:
        charset = CODE128C
        codes = [charset['StartC']]
    else:
        charset = CODE128B
        codes = [charset['StartB']]

    # Data
    while pos < length:
        if charset is CODE128C:
            if text[pos:pos+2].isdigit() and length - pos > 1:
                # Encode Code C two characters at a time
                codes.append(int(text[pos:pos+2]))
                pos += 2
            else:
                # Switch to Code B
                codes.append(charset['CodeB'])
                charset = CODE128B
        elif text[pos:pos+4].isdigit() and length - pos >= 4:
            # Switch to Code C
            codes.append(charset['CodeC'])
            charset = CODE128C
        else:
            # Encode Code B one character at a time
            codes.append(charset[text[pos]])
            pos += 1

    # Checksum
    checksum = 0
    for weight, code in enumerate(codes):
        checksum += max(weight, 1) * code
    codes.append(checksum % 103)

    # Stop Code
    codes.append(charset['Stop'])
    return codes


def code128_image(data, height=100, thickness=3, quiet_zone=True):
    if not data[-1] == CODE128B['Stop']:
        data = code128_format(data)

    barcode_widths = []
    for code in data:
        for weight in WEIGHTS[code]:
            barcode_widths.append(int(weight) * thickness)
    width = sum(barcode_widths)
    x = 0

    if quiet_zone:
        width += 20 * thickness
        x = 10 * thickness

    # Monochrome Image
    img = Image.new('1', (width, height), 1)
    draw = ImageDraw.Draw(img)
    draw_bar = True
    for width in barcode_widths:
        if draw_bar:
            draw.rectangle(((x, 0), (x + width - 1, height)), fill=0)
        draw_bar = not draw_bar
        x += width

    return img


def get_barcode_image_io(str_code):
    """
    Выводим штрих-код для квитанции
    """
    img_file = BytesIO()
    barcode = code128_image(str_code, height=40, thickness=1)
    barcode.save(img_file, format="PNG")

    img_file.seek(0)
    content = img_file.read()
    return base64.encodebytes(content).decode()


def code_barcode(period, amount, account_number, prefix_barcode, sector_index,
                 service_code='00'):
    """
    Получение группы цифр для рендера штрих-кода в виде списка (кот Баркод)
    :param period: int ГГГГММ
    :param amount: int сумма платежа в копейках
    """

    def _luhn_checksum(num):
        """
        Определяем валидность 13-значного штрихкода по Луну
        """
        digits = [int(i) for i in str(num)]
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = 0
        checksum += sum(odd_digits)
        for d in even_digits:
            checksum += sum([int(i) for i in str(d * 2)])
        return checksum % 10

    period = str(period)
    period_to_barcode = period[4:6] + period[2:4]

    if amount <= 0:
        summa = '0000000'
    else:
        summa = str(amount)

    sum_len = len(summa)
    if sum_len < 7:
        for i in range(7 - sum_len):
            summa = '0' + summa

    bcode = ''.join(
        [
            el.replace(' ', '') for el in (
                '%13s' % account_number,
                '%02s' % service_code,
                period_to_barcode,
                summa,
            )
        ]
    )
    if not prefix_barcode:
        prefix_barcode = ''
    return (
            prefix_barcode
            + bcode[:13]
            + str(_luhn_checksum(bcode[:13]))
            + str(sector_index)
            + bcode[15:]
    )


def _create_barcode(value, period, number, sector, prefix):
    sectors_list = tuple(ACCRUAL_SECTOR_TYPE_CHOICES_AS_DICT.keys())
    if (prefix is not None and prefix == 'None') or prefix is None:
        # Могут быть организации со строковым значением "None" поля
        # "prefix_barcode", вместо null. Колдунство, не иначе.
        prefix = ''
    barcode = code_barcode(
        period=period,
        amount=value,
        account_number=number,
        sector_index=sectors_list.index(sector),
        prefix_barcode=prefix,
    )
    return barcode


def generate_qrcode(str_code, draw_angle=False):
    return BytesIO(subprocess.check_output(['qrencode', '-v', '1', '-m', '6', str_code, '-o', '-']))


def generate_qr_code(string):
    """Новое слово в генерации QR кода. Без вызова внешних команд."""
    qr_container = BytesIO()
    qrcode.main.make(string).save(qr_container)
    return qr_container.getvalue()


def generate_qr_code_for_blank_edit(provider_domain:str, request_id:str):
    """QR для перехода в раздел редактирования заявки.
    provider_domain: домен упр компании, request_id: индификатор заявки.
    """

    if not provider_domain:
        provider_domain = settings.DEFAULT_URL

    api_url = "/#/requests/edit/"
    url_edit_appeal = \
        f"{settings.DEFAULT_PROTOCOL}://{provider_domain}" \
        f"{api_url}{request_id}"

    return base64.encodebytes(generate_qr_code(url_edit_appeal)).decode()


def generate_qr_code_for_public_pay(
        provider,
        tenant,
        accrual_id=None,
        value=None,
        sector=None,
        source=None,
        **kwargs,
):
    """
    Генерирует QR-код, используя редирект с ЛКЖ на эквайера.

    :param tenant: житель
    :param accrual_id: _id начисления
    :param value: сумма оплаты
    :param sector: направление
    :param provider: модель Provider
    :param source: источник оплаты
    """

    if not isinstance(tenant, dict):
        # Доверяем тому, что передается тенант либо словарём, либо объектом
        # модели.
        tenant = tenant.to_mongo()
    # Чтобы можно было передать тенанта из пипки.
    if tenant.get('account_number'):
        tenant['number'] = tenant['account_number']

    payment_url = generate_public_url_for_pay(
        provider_url=provider.url,
        number=tenant['number'],
        accrual_id=accrual_id,
        value=value,
        sector=sector,
        source=source
    )
    bank_params = create_bank_params(
        provider=provider,
        tenant=tenant,
        sector=sector,
        value=value,
        penalties=kwargs.get('penalties', 0),
        period=kwargs.get('period'),
        tenant_address=kwargs.get('address')
    )
    qrcode_text = f'{bank_params}|QuickPay={payment_url}'
    # Новый метод генерации создает более нагруженный QR-код, чем старый,
    # по дефолту генерируется старым способом.
    if kwargs.get('render_method') == 'new':
        qr_code = BytesIO(generate_qr_code(qrcode_text))
    else:
        qr_code = generate_qrcode(qrcode_text)
    return qr_code


def create_bank_params(
        provider,
        tenant,
        sector,
        value,
        penalties,
        period=None,
        tenant_address=None
) -> str:
    sector_rus = ACCRUAL_SECTOR_TYPE_CHOICES_AS_DICT[sector]
    prepared_num = int(Decimal(value) * 100)
    if period is None:
        period = Accrual.get_last_period_by_sector(
            tenant_id=tenant['_id'],
            sector=sector,
        )
    period_dot = period.strftime('%m.%Y')

    number = tenant['number']
    if not tenant_address:
        # Добавлено в связи с погоней за укорачиванием данных QR-кода.
        house = House.objects(
            id=tenant['area']['house']['_id']
        ).only(
            'street_only',
            'short_address',
        ).as_pymongo().first()
        tenant_address = f'{house["street_only"]}, {house["short_address"]}, ' \
                         f'{tenant["area"]["str_number_full"]}'

    barcode = _create_barcode(
        value=prepared_num,
        period=period.strftime('%Y%m'),
        number=number,
        sector=sector,
        prefix=provider.prefix_barcode,
    )

    # Банковские реквизиты:
    bank_info = _create_bank_info(tenant, sector, provider)

    # Итоговый кортеж с параметрами для ST00012:
    payment_requisites = (
        ('Name', provider.legal_quoted_name),
        ('PersonalAcc', bank_info['bank_account']),
        ('BankName', bank_info['bank_name']),
        ('BIC', bank_info['bic']),
        ('CorrespAcc', bank_info['cs_account']),
        ('PayeeINN', provider.inn),
        ('PayerAddress', tenant_address),
        ('PersAcc', number),
        ('LastName', number),
        ('PaymPeriod', period_dot),
        ('Category', sector_rus),
        ('UIN', barcode),
        ('TechCode', '02'),
        ('Sum', str(prepared_num).zfill(3)),
        ('AddAmount', str(int(penalties * 100)).zfill(3)),
        ('Purpose', f'{number} {sector_rus} {period_dot} {tenant_address}'),
    )

    requisites_str = '|'.join('='.join(param) for param in payment_requisites)
    return f'ST00012|{requisites_str}'


def _create_bank_info(tenant, sector, provider):
    house_settings = Settings.objects(
        house=tenant['area']['house']['_id'],
        provider=provider.id
    ).only(
        'sectors'
    ).first()
    bank_account = ''
    name = ''
    bic = ''
    cs_account = ''
    settings = house_settings.get_sector_by_code(sector)
    if settings:
        bank_account = settings.bank_account
        for area_type in tenant['area']['_type']:
            area_settings = settings.get_sector_by_area_type(area_type)
            if area_settings and area_settings.bank_account:
                bank_account = area_settings.bank_account
                break
    if bank_account:
        for bank in provider.bank_accounts:
            if bank.number == bank_account:
                if bank.bic.bic_body:
                    bic = bank.bic.bic_body[0].BIC
                    cs_account = bank.bic.bic_body[0].Account
                    name = bank.bic.bic_body[0].NameP
    bank_info = dict(
        bank_account=bank_account,
        bank_name=name,
        bic=bic,
        cs_account=cs_account,
    )
    return bank_info


