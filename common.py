import logging
from contextlib import contextmanager

import ruamel.yaml
import sqlite3

CONF_FILE = 'conf.yaml'

_conf_cache = None


def create_logger(name: str = 'io'):
    logging.basicConfig(level=logging.DEBUG)
    return logging.getLogger(name)


def get_nested_value(conf, key):
    keys = key.split('.')
    curr = conf
    for k in keys:
        if isinstance(curr, dict) and k in curr:
            curr = curr[k]
        else:
            raise KeyError(f'Key not found: {k} (in path: {key})')
    return curr


def get_conf(key: str):
    global _conf_cache
    if _conf_cache is None:
        yaml = ruamel.yaml.YAML()
        with open(CONF_FILE, 'r', encoding='utf-8') as f:
            _conf_cache = yaml.load(f)
    return get_nested_value(_conf_cache, key)


@contextmanager
def get_db():
    conn = sqlite3.connect(get_conf('db'))
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA journal_mode = WAL')
    try:
        yield conn
    finally:
        conn.close()

IEC_ADDR_TYPE = {
    30: "521",  # Type 30 - Single point information (TS)
    31: "521",  # Type 31 - Single point information with timestamp (TS)
    36: "526",  # Type 36 - Measured value (TI) - float
    37: "526",  # Type 37 - Measured value with timestamp (TI)
    45: "532",  # Type 45 - Single command (TU)
    46: "532",  # Type 46 - Double command (TU)
    50: "526",  # Type 50 - Setpoint (TR) - float
    51: "526",  # Type 51 - Setpoint with timestamp (TR)
    58: "532",  # Type 58 - Step control command (TU)
    59: "532",  # Type 59 - Step control command with timestamp
}

IEC_VAL_TYPE = {
    30: 23,  # bool
    32: 21,  # int
    36: 22,  # float
    45: 23,  # bool
    50: 22   # float
}


if __name__ == '__main__':
    print(get_conf('create.order'))
