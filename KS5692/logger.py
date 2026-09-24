import logging
from config import LOG_DIR

def get_logger(name="ks5692"):
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s %(message)s")
        handler = logging.FileHandler(LOG_DIR / "simulation.log", encoding="utf-8")
        handler.setFormatter(fmt); logger.addHandler(handler)
    return logger

