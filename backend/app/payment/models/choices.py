
class VendorPaymentDocStatus:
    TEMPORARY = 'temp'
    NEW = 'new'
    ACCEPTED = 'accepted'
    FINISHED = 'finished'


VENDOR_PAYMENT_DOC_STATUSES_CHOICES = (
    (VendorPaymentDocStatus.NEW, 'Новый'),
    (VendorPaymentDocStatus.ACCEPTED, 'Подписан'),
    (VendorPaymentDocStatus.FINISHED, 'Проведён'),
)
VENDOR_PAYMENT_DOC_STATUSES_CHOICES_ALL = (
    (VendorPaymentDocStatus.NEW, 'Новый'),
    (VendorPaymentDocStatus.ACCEPTED, 'Подписан'),
    (VendorPaymentDocStatus.FINISHED, 'Проведён'),
    (VendorPaymentDocStatus.TEMPORARY, 'Временный'),
)
