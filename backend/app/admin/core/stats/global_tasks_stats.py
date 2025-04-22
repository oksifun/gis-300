import datetime

from dateutil.relativedelta import relativedelta

from app.autopayment.models.logs import AutoPaymentLog
from app.bankstatements.models.choices import BankStatementSource
from app.bankstatements.models.parse_task import BankStatement
from app.c300.models.choices import BaseTaskState
from app.admin.models.statistics import TasksGlobalStatistics
from app.fiscalization.models.choices import FiscalizationState, \
    FiscalReceiptState
from app.fiscalization.models.receipts import FiscalReceipt
from app.notifications.models.logs import NotifyLogs
from app.registries.models.parse_tasks import RegistryParseTask
from lib.dates import start_of_day
from processing.models.choices import PaymentDocSource


class GlobalTasksStatistics:

    def __init__(self, day_as_date=None):
        self.stats = TasksGlobalStatistics(
            date=start_of_day(day_as_date or datetime.datetime.now()),
        )

    def load_stats(self):
        self._update_instance()

    def fill_all_stats(self):
        self._update_instance()
        self.stats.autopay = self.get_autopay_num()
        self.stats.registry = self.get_registries_num()
        self.stats.registry_mail = self.get_registries_from_mail_num()
        self.stats.registry_mail_error = self.get_registries_error_num()
        self.stats.bank_statement = self.get_bs_num()
        self.stats.bank_statement_mail = self.get_bs_from_mail_num()
        self.stats.fiscal = self.get_fiscal_num()
        self.stats.fiscal_success = self.get_fiscal_success_num()
        self.stats.fiscal_finished = self.get_fiscal_finished_num()
        self.stats.fiscal_exp = self.get_fiscal_exp_num()
        self.stats.bill_notify = self.get_bill_sending_num()
        self.stats.save()

    def get_fiscal_num(self):
        queryset = FiscalReceipt.objects(
            created__gte=self.stats.date,
            created__lt=self.stats.date + relativedelta(days=1),
        )
        return queryset.count()

    def get_fiscal_success_num(self):
        queryset = FiscalReceipt.objects(
            fiscal_date__gte=self.stats.date,
            fiscal_date__lt=self.stats.date + relativedelta(days=1),
            fiscal_state=FiscalizationState.SUCCESS,
        )
        return queryset.count()

    def get_fiscal_finished_num(self):
        queryset = FiscalReceipt.objects(
            updated__gte=self.stats.date,
            updated__lt=self.stats.date + relativedelta(days=1),
            state=FiscalReceiptState.COMPLETED,
        )
        return queryset.count()

    def get_fiscal_exp_num(self):
        queryset = FiscalReceipt.objects(
            updated__gte=self.stats.date,
            updated__lt=self.stats.date + relativedelta(days=1),
            state=FiscalReceiptState.EXPIRED,
        )
        return queryset.count()

    def get_bs_num(self):
        queryset = self._get_bs_queryset()
        return queryset.count()

    def get_bs_from_mail_num(self):
        queryset = self._get_bs_queryset()
        queryset = queryset.filter(
            source=BankStatementSource.SBER,
        )
        return queryset.count()

    def _get_bs_queryset(self):
        return BankStatement.objects(
            created__gte=self.stats.date,
            created__lt=self.stats.date + relativedelta(days=1),
        )

    def get_registries_num(self):
        queryset = self._get_registries_queryset()
        return queryset.count()

    def get_registries_from_mail_num(self):
        queryset = self._get_registries_queryset()
        queryset = queryset.filter(parent=PaymentDocSource.MAIL)
        return queryset.count()

    def get_registries_error_num(self):
        queryset = self._get_registries_queryset()
        queryset = queryset.filter(
            parent=PaymentDocSource.MAIL,
            state=BaseTaskState.ERROR,
        )
        return queryset.count()

    def _get_registries_queryset(self):
        return RegistryParseTask.objects(
            created__gte=self.stats.date,
            created__lt=self.stats.date + relativedelta(days=1),
        )

    def get_autopay_num(self):
        queryset = AutoPaymentLog.objects(
            created__gte=self.stats.date,
            created__lt=self.stats.date + relativedelta(days=1),
            log__startswith='status: success',
        )
        return queryset.count()

    _EMAIL_CHANNELS_FOR_NOTIFICATIONS = (
        'Email',
        'MobileApp, Email',
        'Telegram, Email',
    )

    def get_bill_sending_num(self):
        queryset = NotifyLogs.objects(
            created__gte=self.stats.date,
            created__lt=self.stats.date + relativedelta(days=1),
            notify_event='bills_notifications',
            notify_channel__in=self._EMAIL_CHANNELS_FOR_NOTIFICATIONS,
        )
        return queryset.count()

    def _update_instance(self):
        inst = TasksGlobalStatistics.objects(date=self.stats.date).first()
        if inst:
            self.stats = inst
