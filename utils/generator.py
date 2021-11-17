# -*- coding: utf-8 -*-
"""
数据生成器

@Author  : xujun
@Time    : 2020/8/22 14:46
"""
# import os
import random
import string
import time
import uuid

# from utils.csv_loader import CsvReader, CsvReaderCommunication
from config import DEVICE_MODEL


def text_stream_gen(length=10):
    """
    文本数据生成
    :return:
    """
    letters = [random.choice(string.ascii_letters) for _ in range(length)]
    return ''.join(letters)


def get_time_stamp():
    """
    时间戳
    """
    return int(time.time()*1000)


def device_info_gen() -> dict:
    """
    设备信息生成
    :return:
    """
    # manufacturers = []
    devices = {
        'platform': DEVICE_MODEL,   # apple, android, pc
        'manufacturer': DEVICE_MODEL,
        'device_id': device_id_gen(),
        'os_version': '10'
    }
    return devices


def device_id_gen():
    """
    唯一设备编码生成： uuid4 + timestamp
    :return:
    """
    uid = uuid.uuid4().hex
    _id = str(get_time_stamp()) + uid
    return _id


if __name__ == '__main__':
    pass
