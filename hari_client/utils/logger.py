import logging


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    logging.basicConfig(
        level=level,
        handlers=[logging.StreamHandler()],
        format=(
            "%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s:"
            " %(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(name)
