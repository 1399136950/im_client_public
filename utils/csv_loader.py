# -*- coding: utf-8 -*-

"""
CSV 文件读取及不同情况返回

"""


def csv_reader(path: str, headers: list, split_flag: str = ',', ignore_head: bool = False, shift=0, count=None) -> list:
    """
    返回迭代器
    :param path: csv文件路径
    :param headers: csv文件各列的列名
    :param split_flag: csv数据划分标记
    :param ignore_head: 是否忽略行首
    :param shift: 偏移量，从多少行读起
    :return: 迭代返回数据
    """
    if count is None:
        count = 0b111111111111111111111111111111111111111111111111111111111111111
    with open(path, 'r') as fd:
        if ignore_head is True:
            fd.readline()   # 忽略1行
        for i in range(shift):
            fd.readline()   # 忽略shift行
        _i = 0
        while True:
            # print('_i:',_i)
            if _i >= count:
                raise RuntimeError('read line > count: ', count)
            line = fd.readline()
            if line == '':
                break
            info = line.strip().split(split_flag)
            data = {}
            for k in headers:
                data[k] = info[headers.index(k)]
            _i += 1
            yield data


def csv_reader_communication(path: str, split_flag: str = ',', ignore_head: bool = True) -> list:
    """
    返回以用户为键的所有数据字典，便于快速索引
    :param path: csv文件路径
    :param split_flag: csv数据划分标记
    :param ignore_head: 是否忽略行首
    :return: <dict> 数据
    """
    res = {}
    with open(path, 'r') as fd:
        if ignore_head is True:
            fd.readline()   # 忽略1行
        while True:
            line = fd.readline()
            if line == '':
                break
            items = line.strip().split(split_flag)
            key = items[0]
            if key not in res.keys():
                res[key] = [{'target_id': items[1], 'communication_id': items[2]}]
            else:
                res[key].append({'target_id': items[1], 'communication_id': items[2]})
    return res


class CsvReader:
    """
    单例模式迭代输出用户数据
    """
    _instance = None
    _loader = None

    def __new__(cls, *arg, **kwargs):
        if not cls._instance:
            cls._instance = object.__new__(cls)
            cls._loader = csv_reader(*arg, **kwargs)
        return cls._instance

    def next(self):
        try:
            line = next(CsvReader._loader)
        except StopIteration as e:
            raise RuntimeError('业务异常：用户池已耗尽')
        return line


class CsvReaderCommunication:
    """
    单例模式迭代输出会话数据
    """
    _instance = None
    _data = None

    def __new__(cls, *arg, **kwargs):
        if not cls._instance:
            cls._instance = object.__new__(cls)
            cls._data = csv_reader_communication(*arg, **kwargs)
        return cls._instance

    @classmethod
    def get_data(cls):
        return cls._data


if __name__ == '__main__':
    pass




