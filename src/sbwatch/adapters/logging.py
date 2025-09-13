import logging, logging.config, os, yaml  # type: ignore
def setup_logging(config_path: str = "configs/logging.yaml") -> None:
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f)
        logging.config.dictConfig(cfg)
    else:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
