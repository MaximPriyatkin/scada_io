import logging
import common as c
import db_editor as ed


def _cmd_exit(_args, _log):
    """
    exit - stop program
    Example: > exit
    """
    return False


def _cmd_help(_args, _log):
    """
    this help
    Example: > help
               help <command>
    """
    print('=== Available commands ===\n')
    for name, (n, _) in COMMANDS.items():
        print(f' {name} ' + ('<arg> ' * n if n else ''))
    print('\nFor command help: help <command>\n')


def _cmd_create(_args, log):
    """
    create database tables
    Example: > create
    """
    ed.create_db(log)


def _cmd_export(_args, log):
    """
    export all tables to csv
    Example: > export
    """
    ed.run_exp(log)


def _cmd_import(args, log):
    """
    import csv to database table
    Example: > import sys
             > import dp
    """
    ed.upd_db(args[0], log)


def _cmd_exp_sg(_args, log):
    """
    generate signal relation file
    Example: > signal
    """
    ed.run_exp_sg(log)

def _cmd_create_sg_rel(_args, log):
    """
    generate signal relation file
    Example: > signal
    """
    ed.create_sg_rel(log)

def _cmd_exp_wcc(args, log):
    '''
    export for wincc oa
    '''
    if args[0] == 'srv':
        is_server = True
    else:
        is_server = False
    ed.exp_winccoa(is_server,log)

COMMANDS = {
    'exit':   (0, _cmd_exit),
    'help':   (0, _cmd_help),
    'create': (0, _cmd_create),
    'export': (0, _cmd_export),
    'import': (1, _cmd_import),
    'exp_sg': (0, _cmd_exp_sg),
    'sg_rel': (0, _cmd_create_sg_rel),
    'exp_wcc': (1, _cmd_exp_wcc),
}


def db_handler(log: logging.Logger, prompt: str = '> '):
    while True:
        try:
            line = input(prompt).strip().lower()
        except (EOFError, KeyboardInterrupt):
            log.info('exit')
            break

        if not line:
            continue
        parts = line.split()
        cmd_name, args = parts[0], parts[1:]

        if cmd_name == 'help' and args:
            cmd_help = args[0]
            if cmd_help in COMMANDS:
                _, handler = COMMANDS[cmd_help]
                print(handler.__doc__ or f'Help for {cmd_help} not found')
            else:
                print(f'Unknown command: {cmd_help}')
            continue

        entry = COMMANDS.get(cmd_name)
        if entry is None:
            print(f'Unknown command: {cmd_name}. Type help for list of commands')
            continue
        n_args, handler = entry
        if len(args) < n_args:
            print(f'Expected at least {n_args} args for {cmd_name}, got {len(args)}')
            continue
        try:
            result = handler(args, log)
            if result is False:
                break
        except Exception as e:
            log.exception('Error executing command %s: %s', cmd_name, e)
            print('Error:', e)


if __name__ == '__main__':
    log = c.create_logger('db_control')
    db_handler(log)
