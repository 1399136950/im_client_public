# -*- coding: utf-8

"""
报文封装
@author xujun
"""
import struct

from utils.encrypt import aes_encrypt


def msg_pack(command, key, proto_name, proto):
    """
    报文组装
    A. 包体长度 （4byte）
    B. 命令码 （1byte）
    C. keystr长度（1byte）
    D. keyStr内容（x byte）
    E. protoName长度 (1byte)
    F. protoName (x byte）
    G.消息体body（x byte）

    详细参考：http://120.78.191.170:8090/pages/viewpage.action?pageId=1114157
            https://docs.python.org/3/library/struct.html
    :param command: 命令枚举值
    :param key: appId;userId;deviceId
    :param proto_name: Proto名称
    :param proto:  Proto二进制数数据
    :return: 拼接完成的二进制数据
    """

    if proto:
        proto = aes_encrypt(proto)    # aes 加密

    data = struct.pack('>IBB{}sB{}s'.format(len(key.encode('utf8')), len(proto_name.encode('utf8'))),
                       1 + 1 + len(key.encode('utf8')) + 1 + len(proto_name.encode('utf8')) + len(proto),
                       command,
                       len(key.encode('utf8')),
                       key.encode('utf8'),
                       len(proto_name.encode('utf8')),
                       proto_name.encode('utf8'),
                       )
    return data + proto


def load_user_from_csv(file):
    """
    加载用户数据
    :return:
    """
    yield {'phone': '18599999999'}