# -*- coding: utf-8

"""
装饰器相关

"""
from time import sleep, time, strftime, localtime


def count_time(func):
    """
    时长统计
    :param func:
    :return:
    """
    def warp(*args, **kw):
        start_time = time()
        print('[start %s]' % func.__name__)
        ret = func(*args, **kw)
        print('[stop  %s], cost: ' % func.__name__, time()-start_time)
        return ret
    return warp

