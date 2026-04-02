#!/usr/bin/env python3
'''
Database import/export utility

This module provides functionality to:
    Export data from database to csv files (stored in ref/out folder)
    Import/update database records from csv files (stored in ref/in folder)

Configuration: conf.yaml - contains sql queries and csv structure definitions
'''
import csv
import logging
import os

import common as c

FOLDER_IN = 'ref/in/'
FOLDER_OUT = 'ref/out/'
CSV_DELIM = '\t'
LINETERM = '\n'
LANG_ENCODE = 'utf-8'
FILE_EXT = '.csv'
BATCH_UPDATE = 100


def create_db(log: logging.Logger) -> None:
    conf = c.get_conf('create')
    with c.get_db() as conn:
        cursor = conn.cursor()
        order = conf['order']
        for tbl, vl in order.items():
            if vl == 0:
                continue
            sql = conf[tbl]
            log.info(f'create db {tbl}')
            cursor.execute(sql)
            sql = conf['trg_ins']
            sql = sql.replace('{tbl}', tbl)
            cursor.execute(sql)
            sql = conf['trg_upd']
            sql = sql.replace('{tbl}', tbl)
            cursor.execute(sql)
            conn.commit()


def read_db(tbl: str, log: logging.Logger) -> int:
    '''
    Export data from a database table to a csv file.

    Args:
        tbl: Table name used to look up sql query and column
             definitions in configuration (exp.{tbl}.sql and exp.{tbl}.cols)
        log: Logger instance

    Returns:
        Number of rows exported to csv file
    '''
    os.makedirs(FOLDER_OUT, exist_ok=True)
    sql = c.get_conf(f'exp.{tbl}.sql')
    if not sql:
        raise ValueError(f'No SQL query configured for exp.{tbl}.sql')
    try:
        with c.get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(sql)
            row = cursor.fetchone()
            with open(f'{FOLDER_OUT}{tbl}{FILE_EXT}', 'w', encoding=LANG_ENCODE) as f:
                writer = csv.writer(f, delimiter=CSV_DELIM, lineterminator=LINETERM)
                writer.writerow(c.get_conf(f'exp.{tbl}.cols'))
                cnt_row = 0
                while row is not None:
                    writer.writerow(row)
                    cnt_row += 1
                    row = cursor.fetchone()
    except Exception as e:
        log.error(f'Failed export {tbl}: {e}')
        raise
    return cnt_row


def upd_db(tbl: str, log: logging.Logger) -> int:
    '''
    Update database records from a csv file.

    Reads data from csv file and performs batch updates of the specified table.
    Falls back to row-by-row insert on batch failure.

    Args:
        tbl: Table name used to look up the sql update statement in configuration
        log: Logger instance

    Returns:
        Number of records successfully updated
    '''
    os.makedirs(FOLDER_IN, exist_ok=True)
    try:
        conf = c.get_conf(f'upd.{tbl}')
    except KeyError as e:
        raise ValueError(f'No config for upd.{tbl}: {e}')
    sql = conf.get('sql')
    if not sql:
        raise ValueError(f'No SQL query configured for upd.{tbl}')
    req_fields = conf.get('required', [])
    fname = conf.get('fname', tbl)
    csv_file = f'{FOLDER_IN}{fname}{FILE_EXT}'
    if not os.path.exists(csv_file):
        log.warning(f'Update file not found {csv_file}')
        return 0
    records = []
    skipped = 0
    with open(csv_file, 'r', encoding=LANG_ENCODE) as f:
        reader = csv.DictReader(f, delimiter=CSV_DELIM, lineterminator=LINETERM)
        if not reader.fieldnames:
            log.error(f'No header row found in {csv_file}')
            return 0
        if req_fields:
            missing = set(req_fields) - set(reader.fieldnames)
            if missing:
                log.error(f'csv missing required fields: {missing} in {csv_file}')
                log.debug(f'Available fields: {reader.fieldnames}')
                return 0
        for row_num, row in enumerate(reader, start=2):
            missing = [f for f in req_fields if not row.get(f)]
            if missing:
                log.warning(f'Row {row_num}: {missing}, skipping')
                skipped += 1
                continue
            records.append(row)
    if not records:
        log.warning(f'No valid records in {tbl} (skipped: {skipped})')
        return 0

    with c.get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.executemany(sql, records)
            conn.commit()
            log.info(f'Updated {len(records)} records in {tbl} (skipped: {skipped})')
            return len(records)
        except Exception as e:
            conn.rollback()
            log.warning(f'Batch failed: {e}, switching to row-by-row')

    updated = 0
    errors = 0
    with c.get_db() as conn:
        cursor = conn.cursor()
        for record in records:
            try:
                cursor.execute(sql, record)
                updated += 1
                if updated % BATCH_UPDATE == 0:
                    conn.commit()
            except Exception as e:
                log.debug(f'Skipped record {record}: {e}')
                errors += 1
        conn.commit()
    log.info(f'Row-by-row: updated {updated}, errors {errors}, skipped {skipped}')
    return updated


def run_exp(log: logging.Logger) -> None:
    '''
    Execute export for all tables defined in the configuration.
    '''
    try:
        tables = c.get_conf('exp')
        if not tables:
            log.warning('No tables configured for export under "exp"')
            return
        for tbl in tables:
            try:
                cnt_row = read_db(tbl, log)
                log.info(f'Exported {cnt_row} rows to {FOLDER_OUT}{tbl}{FILE_EXT}')
            except Exception as e:
                log.error(f'Failed to export {tbl}: {e}')
    except KeyError as e:
        log.error(f'Configuration error: {e}')
        raise


def run_exp_sg(log: logging.Logger) -> None:
    '''
    Exports signals to generalization csv file for use
    in configuration MEK 104 servers  
    '''
    conf = c.get_conf('exp.sg')
    with c.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(conf['sql'])
        cols = [desc[0] for desc in cursor.description]
        data = [dict(zip(cols, row)) for row in cursor.fetchall()]

    def_threshold = {45: None, 50: None, 30: 0, 36: 0.1}  # For example threshold float = 0.1
    def_conv = {36: '0,4,10,20'}  # For example 4...20Ma for 0...10MPa

    kps = {}
    for row in data:
        # Get number PLC(kp) for set common address
        parts = row['name'].split('_')
        if len(parts) < 3:
            log.warning(f'Unexpected name format: {row["name"]}, skipping')
            continue
        kp = parts[2]
        if kp not in kps:
            kps[kp] = 0
        else:
            kps[kp] += 1
        asdu = row['iec_asdu']
        row['iec_ca'] = kp
        row['iec_ioa'] = kps[kp]
        row['conv'] = def_conv.get(asdu, None)
        row['threshold'] = def_threshold.get(asdu, None)
        row['iec_cot'] = None

    with open(conf['fname'], 'w', encoding=LANG_ENCODE, newline='') as f:
        writer = csv.DictWriter(f, fieldnames=conf['cols'],
                                delimiter=CSV_DELIM, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(data)
    log.info(f'Signal file written: {conf["fname"]} ({len(data)} rows)')

def create_sg_rel(log: logging.Logger) -> None:
    '''
    Filling in table of relationships between signals,data points,
    and datapoints elements

    todo: this function is made for testing only, so it runs slowly.
    I need to add indexes, temporary tables, perform inserts one at a time
    to avoid violating uniqueness
    '''
    sql = c.get_conf('upd.sg_rel.sql')    
    with c.get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(sql)
            conn.commit()
            log.info(f"Import completed. Добавлено строк: {cursor.rowcount}")
        except conn.Error as e:
            log.warning(f"Error executed SQL: {e}")
            conn.rollback()
        finally:
            conn.close()

def exp_winccoa(is_server: bool, log: logging.Logger):
    '''
    Export signals in dpl file for WinCC OA
    Args:
        is_server - select direction for signals
    '''
    conf = c.get_conf('exp_wcc')
    
    with c.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(conf['dpt'])
        header = ('# ascii dump of database\n\n# DpType\n'
                  'TypeName\n')
        row = cursor.fetchone()
        dpType = []
        dpt = ''
        while row:
            if row[0] != dpt:
                dpt = row[0]
                line = (f'{dpt}.{dpt}','1#0')
                dpType.append(line)
            parts = row[1].split('.')
            tab = 0
            dpe_type = 1
            for name in parts:
                if tab == len(parts) - 1:
                    dpe_type = c.IEC_VAL_TYPE.get(row[2], 23)   
                line = ('\t'*tab, name, f'{dpe_type}#0')
                tab += 1
                dpType.append(line)
            row = cursor.fetchone()
        _write_dpl('dpt.dpl', dpType, header)            
        

        cursor.execute(conf['dp'])
        dp = cursor.fetchall()
        header = ('# ascii dump of database\n\n# Datapoint/DpId\n'
                  'DpName\tTypeName\tID\n')
        _write_dpl('dp.dpl', dp, header)
        
        cursor.execute(conf['distrib'], ('ASC (1)/0', '56', r'\2'))
        
        distrib = cursor.fetchall()
        header = ('# ascii dump of database\n\n# DistributionInfo\n'
                  'Manager/User\tElementName\tTypeName\t'
                  '_distrib.._type\t_distrib.._driver\n')
        _write_dpl('distrib.dpl', distrib, header)
        
        cursor.execute(conf['iec_addr'])
        header =('# ascii dump of database\n\n# PeriphAddrMain\n'
                'Manager/User\tElementName\tTypeName\t_address.._type\t_address.._reference\t'
                '_address.._poll_group\t_address.._connection\t_address.._offset\t'
                '_address.._subindex\t_address.._direction\t_address.._internal\t'
                '_address.._lowlevel\t_address.._active\t_address.._start\t_address.._interval\t'
                '_address.._reply\t_address.._datatype\t_address.._drv_ident\n')
        addr = []
        row = cursor.fetchone()
        while row:
            ref = 'addr'
            dpe = row[0]
            dpt = row[1]
            asdu = row[2]
            num_con = row[3]
            ca = f'{(row[3] >> 8) & 0xFF}.{row[3] & 0xFF}'
            ioa = f'{(row[4] >> 16) & 0xFF}.{(row[4] >> 8) & 0xFF}.{row[4] & 0xFF}'
            if asdu < 44:
                direct = '\\5' if is_server else '\\2'
            else:
                direct = '\\2' if is_server else '\\5'            
            ref = f'KP_{num_con}-{asdu}.{ca}.{ioa}'
            iec_type = c.IEC_ADDR_TYPE.get(asdu, '532')
            line = ('ASC (1)/0', 
                    dpe,  # KP_1_ZDV_1.TU.ToOpen
                    dpt,  # ZDV
                    '16',
                    ref, # "CLN1-45.0.1.0.0.1"
                    '', '', 0, 0,
                    direct, # \5
                    '0', '0', '1', '01.01.1970 00:00:00.000', '01.01.1970 00:00:00.000', '01.01.1970 00:00:00.000',
                    iec_type, 
                    'IEC')
            addr.append(line)
            row = cursor.fetchone()

        if is_server:
            fname = 'addr_srv.dpl'
        else:
            fname = 'addr_cln.dpl'            
        _write_dpl(fname, addr, header)

    #if is_server and asdu > 44:
    #    direct = '\5'

def _write_dpl(fname: str, data:list, header:str) -> None:
    out_file = f'{FOLDER_OUT}{fname}'
    with open(out_file, 'w', encoding=LANG_ENCODE) as f:
        f.write(header)
        for row in data:
            line = '\t'.join(str(item) for item in row)
            f.write(line + '\n')

if __name__ == '__main__':
    log = c.create_logger('db_editor')
    run_exp(log)
