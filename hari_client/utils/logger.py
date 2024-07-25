import logging


def setup_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
