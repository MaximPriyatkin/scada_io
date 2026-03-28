import ruamel.yaml
import sqlite3
CONF_FILE = 'conf.yaml'

_conf_cache = None

def get_nested_value(conf, key):
    keys = key.split('.')
    curr = conf
    for k in keys:
        if isinstance(curr, dict) and k in curr:
            curr = curr[k]
        else:
            raise KeyError(f'Ключ {k} не найден')
    return curr

def get_conf(key: str):
    global _conf_cache
    if _conf_cache is None:
        yaml = ruamel.yaml.YAML()
        with open(CONF_FILE, 'r', encoding='utf-8') as f:
            _conf_cache = yaml.load(f)
    return get_nested_value(_conf_cache, key)

def get_db():
    conn = sqlite3.connect(get_conf('db'))
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA journal_mode = WAL')
    return conn


if __name__ == '__main__':
    print(get_conf('create.order'))
