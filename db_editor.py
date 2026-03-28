#!/usr/bin/env python3
'''
Database import/export utility

This module proviedes functionality to:
    Export data from database to csv.files (stored in ref/out folder)
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

def create_logger():
    '''
    defining the logger object for entire utility
    '''
    logging.basicConfig(level=logging.DEBUG)
    log = logging.getLogger('import')
    return log
 
def create_db(log: logging.Logger) -> None:
    with c.get_db() as conn:
        cursor = conn.cursor()
        order = c.get_conf('create.order')
        for tbl, vl in order.items():
            if vl == 0:
                continue
            sql = c.get_conf('create.' + tbl)
            log.info(f'create db {tbl}')
            cursor.execute(sql)
            conn.commit()

def read_db(tbl: str, log: logging.Logger) -> int:
    '''
    Export data from a database tables to to csv files

    Read data from the specified table using a configured SQL query,
    and writes the result to a tab-separated csv file with headers.

    Args:
        tbl(str): Table name used to look up sql query and column
        definitions in configurations (exp.{tbl}.sql and exp.{tbl}.cols)

    Return:
        int: Number of row exporter to csv file

    Raises:
        KeyError: If configuration for the table is not found
        Exception: If database query fails
    '''
    # create output folder if not exists, without error
    os.makedirs(FOLDER_OUT, exist_ok=True)
    sql = c.get_conf(f'exp.{tbl}.sql')
    if not sql:
        raise ValueError(f'No SQL query configured for the exp.{tbl}.sql')
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
    else:
        return cnt_row

def upd_db(tbl: str, log: logging.Logger) -> int:
    '''
    Update database records from a csv file

    Reads data from csv file and performs batch updates of the specified table

    Args:
        tbl(str): table name used to look up the sql update statement in configuration
        (upd.{tbl})

    Returns:
        int: Number of records successfully updated
    '''

    os.makedirs(FOLDER_IN, exist_ok=True)
    try:
        conf = c.get_conf(f'upd.{tbl}')
    except KeyError as e:
        raise ValueError(f'No config for the upd.{tbl} : {e}')
    sql = conf.get('sql')
    if not sql:
        raise ValueError(f'No SQL query configured for the upd.{tbl} ')
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
    use_row_by_row = False
    with c.get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.executemany(sql, records)
            conn.commit()
            log.info(f'Updated {len(records)} records in {tbl} (skipped: {skipped})')
            return len(records)
        except Exception as e:
            conn.rollback()
            log.warning(f'FK violation, maybe: {e}, switch to row-by-row')
            use_row_by_row = True
        conn.commit()
    if use_row_by_row:
        updated = 0
        with c.get_db() as conn:
            cursor = conn.cursor()
            for idx, record in enumerate(records):
                try:
                    cursor.execute(sql, record)
                    updated +=1
                    if updated % BATCH_UPDATE == 0:
                        conn.commit()
                except Exception as e:
                    conn.rollback()
                    log.debug(f'Error to record {record} : {e}')
            conn.commit()



def run_exp(log: logging.Logger) -> None:
    '''
    Execute export for all tables defined in the configuration
    
    Itterates through all table configuration under 'exp' in conf.yaml,
    export each table to its respective CSV file, and logs export
    statics.
    '''    
    try:
        tables = c.get_conf('exp')
        if not tables:
            log.warning('No tables configured for export under "exp"')
            return
        for tbl in tables:
            try:
                cnt_row = read_db(tbl, log)  # passing the logger object on
                log.info(f'Exported {cnt_row} rows to {FOLDER_OUT}{tbl}{FILE_EXT}')
            except Exception as e:
                log.error(f'Failed to export {tbl}: {e}')
    except KeyError as e:
        log.error(f'Configuration error: {e}')
        raise    

def run_relation_sg(log: logging.Logger)-> None:
    sql = '''
    SELECT 
    ROW_NUMBER() OVER (ORDER BY dp.id, dpe.id) as id,
    sys.name || ":" || dp.name || '.' || dpe.name as name, 
    dp.dsc || ' ' || dpe.dsc as dsc,
    grp.type as iec_asdu
    FROM dp
    JOIN dpe ON dpe.dpt = dp.dpt
    JOIN dpt ON dpe.dpt = dpt.id
    JOIN sys ON sys.id = dpt.sys
    JOIN grp ON grp.id = dpe.grp
    '''
    with c.get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(sql)
        cols = [desc[0] for desc in cursor.description]
        data = [dict(zip(cols, row)) for row in cursor.fetchall()]
    
    def_threshold = {45:None, 50:None, 30:0, 36:0.1}
    def_conv = {36:'0,4,10,20'}

    kps = {}
    for row in data:
        split_name = row['name'].split('_')
        kp = split_name[2]
        if kp not in kps:
            kps[kp] = 0
        else:
            kps[kp] += 1
        asdu =  row['iec_asdu']
        row['iec_ca'] = kp
        row['iec_ioa'] = kps[kp]
        conv = def_conv.get(asdu, None)
        row['conv'] = conv
        th = def_threshold.get(asdu, None)
        row['threshold'] = th
        row['iec_cot'] = None
    with open('ref/in/sg_.csv', 'w', encoding=LANG_ENCODE, newline='') as f:
        fieldnames = ['id','name','dsc','disable','iec_asdu','iec_ca','iec_ioa','iec_cot','threshold','conv']
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=CSV_DELIM)
        writer.writeheader()
        writer.writerows(data)
          



def main():
    log = create_logger()
    # Create tables and database if not exists
    sel_oper = input('Create table? [Y,N] ').upper()
    if sel_oper == 'Y':
        create_db(log)
    # Run export for all configured tables
    sel_oper = input('Export file [Y,N] ').upper()
    if sel_oper == 'Y':
        run_exp(log)

    # Import updates for specifiec tables
    # Each updates is independent - failure is one doesn't affect others
    sel_oper = input('Import data [Y,N] ').upper()
    if sel_oper == 'Y':        
        for table in ['sys', 'dpt', 'grp', 'dpe', 'dp', 'sg', 'iec_addr']:
            try:
                upd_db(table, log)
            except Exception as e:
                log.error(f'Failed to update {table}: {e}')
    sel_oper = input('Export signal [Y,N]').upper()
    if sel_oper == 'Y':
        run_relation_sg(log)


if __name__ == '__main__':
    main()            
