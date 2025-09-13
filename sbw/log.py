import logging, logging.config, yaml, os, sys
from loguru import logger as log

def setup_logging():
    cfg = "/opt/sb-watchbot/configs/logging.yaml"
    if os.path.exists(cfg):
        with open(cfg, "r") as f:
            logging.config.dictConfig(yaml.safe_load(f))
    else:
        logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(name)s - %(message)s")

    class InterceptHandler(logging.Handler):
        def emit(self, record):
            try:
                level = log.level(record.levelname).name
            except Exception:
                level = record.levelno
            log.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())

    for name in list(logging.root.manager.loggerDict.keys()):
        logging.getLogger(name).handlers = [InterceptHandler()]

    log.remove()
    log.add(sys.stdout, enqueue=True, level="INFO")
