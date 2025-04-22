import json
import logging
import logging.config

from kafka import KafkaConsumer
from kafka.consumer.fetcher import ConsumerRecord

from loggingconfig import DICT_CONFIG
from settings import KAFKA_CONNECTION_URL
from scripts.utils import mongo_connected
from kafka_handlers.ml_transcription import process_ml_result


kafka_callbacks = dict(
    ml_result=process_ml_result
)
logging.config.dictConfig(DICT_CONFIG)
logger = logging.getLogger("c300")


def route_msg(msg: ConsumerRecord):
    logger.info(
        "GOT MESSAGE FOR TOPIC: %s, MESSAGE: %s",
        msg.topic, msg.value
    )
    topic = msg.topic
    callback = kafka_callbacks[topic]
    callback(msg)


def deserializer(value: bytes) -> dict:
    return json.loads(value)


@mongo_connected
def consume():
    logger.info(
        "START KAFKA CONSUMER FOR %s",
        KAFKA_CONNECTION_URL
    )
    consumer = KafkaConsumer(
        "ml_result",
        bootstrap_servers=KAFKA_CONNECTION_URL,
        value_deserializer=deserializer
    )
    while True:
        try:
            for msg in consumer:
                route_msg(msg)
        except Exception as err:
            logger.exception(err)


if __name__ == "__main__":
    consume()
