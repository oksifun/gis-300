from rest_framework.routers import DefaultRouter

from app.payment.api.v4.views import VendorPaymentReportViewSet, \
    VendorPaymentViewSet, VendorPaymentsConstantsViewSet, \
    VendorPaymentReceiptsViewSet, VendorReceiptDocViewSet, \
    PaymentRegistryReparseViewSet

payments_router = DefaultRouter()


payments_router.register(
    'payment/registry_reparse',
    PaymentRegistryReparseViewSet,
    basename='payment_registry_reparse',
)

payments_router.register(
    'vendor_payment/report',
    VendorPaymentReportViewSet,
    basename='vendor_payments_report',
)
payments_router.register(
    'models/vendor_payments',
    VendorPaymentViewSet,
    basename='vendor_payment',
)
payments_router.register(
    'models/vendor_receipt_docs',
    VendorReceiptDocViewSet,
    basename='vendor_receipt_doc',
)
payments_router.register(
    'forms/vendor_payments/constants',
    VendorPaymentsConstantsViewSet,
    basename='vendor_payment_constants',
)
payments_router.register(
    'vendor_payment/receipts',
    VendorPaymentReceiptsViewSet,
    basename='vendor_payment_receipts',
)
