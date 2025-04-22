class RequestStatus(object):
    PERFORMED = 'performed'
    ACCEPTED = 'accepted'
    RUN = 'run'
    DELAYED = 'delayed'
    ABANDONMENT = 'abandonment'
    REFUSAL = 'refusal'
    HIDDEN = 'hidden'


REQUEST_STATUS_PUBLIC_CHOICES = (
    (RequestStatus.PERFORMED, 'выполнена'),
    (RequestStatus.ACCEPTED, 'принята к исполнению'),
    (RequestStatus.RUN, 'на исполнении'),
    (RequestStatus.DELAYED, 'отложена'),
    (RequestStatus.ABANDONMENT, 'отказ от исполнения'),
    (RequestStatus.REFUSAL, 'отказ от заявки'),
)
REQUEST_STATUS_CHOICES = (
    (RequestStatus.PERFORMED, 'выполнена'),
    (RequestStatus.ACCEPTED, 'принята к исполнению'),
    (RequestStatus.RUN, 'на исполнении'),
    (RequestStatus.DELAYED, 'отложена'),
    (RequestStatus.ABANDONMENT, 'отказ от исполнения'),
    (RequestStatus.REFUSAL, 'отказ от заявки'),
    (RequestStatus.HIDDEN, 'на оформлении'),
)


class RequestPayableType:
    NONE = 'none'
    PRE = 'pre'
    POST = 'post'


REQUEST_PAYABLE_TYPE_CHOICES = (
    (RequestPayableType.NONE, 'не требует оплаты'),
    (RequestPayableType.PRE, 'предоплата'),
    (RequestPayableType.POST, 'по факту выполнения'),
)


class RequestPayStatus:
    NOT_PAID = 'not_paid'
    ON_THE_WAY = 'on_the_way'
    GOT_REGISTRY = 'got_registry'
    PAID = 'paid'


REQUEST_PAY_STATUS_CHOICES = (
    (RequestPayStatus.NOT_PAID, 'не оплачена'),
    (RequestPayStatus.ON_THE_WAY, 'деньги в пути'),
    (RequestPayStatus.GOT_REGISTRY, 'реестр получен'),
    (RequestPayStatus.PAID, 'деньги пришли на РС/загружена выписка'),
)


class RequestTag(object):
    CATALOGUE = 'catalogue'
    SETL_HOME = 'setl_home'


REQUEST_TAGS_CHOICES = (
    (RequestTag.CATALOGUE, 'Из каталога'),
    (RequestTag.SETL_HOME, 'Из приложения SETL HOME'),

)
