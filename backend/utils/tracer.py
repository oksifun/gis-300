import logging
from logging import Logger
from logging.handlers import HTTPHandler


def get_local_logger(name: str) -> Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    handler = HTTPHandler(
        '69.420.228.69:9000', '/message/', method='POST', secure=False
    )
    handler.setFormatter(
        logging.Formatter(
            fmt='[%(asctime)s: %(levelname)s] %(message)s, %(data)s'
        )
    )
    logger.addHandler(handler)

    return logger
