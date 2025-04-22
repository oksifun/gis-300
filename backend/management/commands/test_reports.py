import datetime
import logging.config

import dill
from bson import ObjectId

from app.personnel.models.personnel import Worker
from app.reports.core.splitting_payments.services_trial_balance import \
    DeprecatedSplittingPaymentsByBanksReport
from loggingconfig import DICT_CONFIG
from mongoengine_connections import register_mongoengine_connections
from app.reports.tasks.reports import prepare_report_rows, \
    prepare_multireport_rows
from processing.data_producers.associated.base import get_binded_houses
from processing.models.billing.provider.main import Provider

if __name__ == "__main__":
    register_mongoengine_connections()
    logger = logging.getLogger('c300')
    logging.config.dictConfig(DICT_CONFIG)
    provider = Provider.objects(
        pk=ObjectId("526234b3e0e34c4743822066"),
    ).get()
    worker = Worker.objects(pk=ObjectId("5e413dc05dd7680020f60c94")).get()
    houses = get_binded_houses(provider.pk)
    report = DeprecatedSplittingPaymentsByBanksReport(
        provider=provider,
        binds=provider._binds_permissions,
        # binds=None,
        actor=worker,

        **{
            "sectors": ["rent"],
            "date_from": "2023-06-01",
            "date_till": "2023-06-30",
            "by_bank": True,
            "area_types": ["ParkingArea", "NotLivingArea", "LivingArea"],
            "is_developer": False,
            "houses": ["5a38c1d95aeaa0001f90baa7", "54e769f4f3b7d4645b6dbba6"],
        },
    )
    d = datetime.datetime.now()
    logger.debug('STARTED %s', d)

    # обычный отчёт
    report.get_rows()
    logger.debug('TOTAL TIME %s', datetime.datetime.now() - d)
    result = prepare_report_rows(None, report.pseudo_serialized_data)
    if result['extended_scheme']:
        schema = dill.loads(result['extended_scheme'].encode('latin1'))
    else:
        schema = None
    report.get_json(
        header=result['header'],
        rows=result['rows'],
        schema=schema,
    )
    report.get_xlsx(
        header=result['header'],
        rows=result['rows'],
        schema=schema,
    )

    # мультиотчёт
    # rr = report.get_subreports()
    # results = []
    # schemas = []
    # for sub_report in rr:
    #     result = prepare_report_rows(None, sub_report)
    #     results.append(result)
    #     # result = report.get_rows()
    #     # schema = report.get_extended_scheme(result)
    #     if result['extended_scheme']:
    #         schema = dill.loads(result['extended_scheme'].encode('latin1'))
    #     else:
    #         schema = None
    #
    #     schemas.append(schema)
    #     sub_report.get_json(
    #         header=result['header'],
    #         rows=result['rows'],
    #         schema=schema,
    #     )
    #     sub_report.get_xlsx(
    #         header=result['header'],
    #         rows=result['rows'],
    #         schema=schema,
    #     )
    # result = prepare_multireport_rows(results, report.__class__.__name__)
    # report.get_xlsx(
    #     header=result['header'],
    #     rows=result['rows'],
    #     subreports=rr,
    #     schema=result['extended_scheme']
    # )
    #
    # pprint(result)
    # print(len(result['rows']))
    print('report', datetime.datetime.now() - d)
