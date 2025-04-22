import json
import logging

from kafka.consumer.fetcher import ConsumerRecord

from app.telephony.api.v4.selectors.calls_selector import CallsSelector
from app.telephony.api.v4.services.ml_analysis_result_service import MLAnalysisResultService


logger = logging.getLogger("c300")


def process_ml_result(msg: ConsumerRecord):
    logger.info(
        'START PROCESSING MESSAGE FROM %s FOR CALL %s',
        'ml_result', msg.value['call_id']
    )
    CallsSelector \
        .from_call_id(msg.value['call_id']) \
        .to_service(MLAnalysisResultService) \
        .process_ml_data(msg.value)
    logger.info(
        "FINISHED PROCESSING CALL %s",
        msg.value['call_id']
    )
