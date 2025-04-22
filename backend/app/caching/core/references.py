from app.caching.tasks.filter_data_prepare import prepare_accrual_doc_data, \
    prepare_accounts_balance
from processing.models.choices import FilterPurpose


PREPARE_FUNCS = {
    FilterPurpose.ACCRUAL_DOC_VIEW: (
        prepare_accrual_doc_data,
        prepare_accounts_balance,
    ),
}

