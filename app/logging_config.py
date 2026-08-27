import logging
import json
import sys


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "service": "llm-api",
            "message": record.getMessage(),
        }

        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "model"):
            log_entry["model"] = record.model
        if hasattr(record, "latency_ms"):
            log_entry["latency_ms"] = record.latency_ms
        if hasattr(record, "status"):
            log_entry["status"] = record.status

        return json.dumps(log_entry)


def setup_logging():
    logger = logging.getLogger("llm-api")
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False

    return logger