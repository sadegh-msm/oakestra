import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from csv_logger import CsvLogger
import logging
from time import sleep

filename = 'logs/log.csv'
delimiter = ';'
level = logging.INFO
custom_additional_levels = ['SCHEDULE_REQUEST','DELETE_REQUEST', 'SCHEDULED']
fmt = f'%(asctime)s{delimiter}ROOT_ORCH{delimiter}%(levelname)s{delimiter}%(message)s'
datefmt = '%s'
max_size = 1024  # 1 kilobyte
max_files = 4  # 4 rotating files
header = ['timestamp', 'service', 'event', 'value']
csvlogger=CsvLogger(filename=filename,
                     delimiter=delimiter,
                     level=level,
                     add_level_names=custom_additional_levels,
                     add_level_nums=None,
                     fmt=fmt,
                     datefmt=datefmt,
                     header=header)

def get_csv_logger():
    return csvlogger


def configure_logging():
    format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    formatter = logging.Formatter(format_str)
    my_filename = 'sm.log'

    logging.basicConfig(filename=my_filename, format=format_str, level=logging.INFO)
    my_logger = logging.getLogger("system_manager")

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    stdout_handler.setFormatter(formatter)
    my_logger.addHandler(stdout_handler)

    rotating_handler = RotatingFileHandler(my_filename, maxBytes=1500, backupCount=2)
    my_logger.addHandler(rotating_handler)

    return my_logger
