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

    data = struct.pack(
        '>IBB{}sB{}s'.format(len(key.encode('utf8')), len(proto_name.encode('utf8'))),
        1 + 1 + len(key.encode('utf8')) + 1 + len(proto_name.encode('utf8')) + len(proto),
        command,
        len(key.encode('utf8')),
        key.encode('utf8'),
        len(proto_name.encode('utf8')),
        proto_name.encode('utf8'),
    )
    return data + proto


def msg_unpack_without_length(buffer, package_length):
    """
    报文数据数据解析(4个字节后的数据)
    """
    try:
        command, = struct.unpack_from('<B', buffer, 0)
        key_length, = struct.unpack_from('<B', buffer, 1)
        key, = struct.unpack_from('<{}s'.format(key_length), buffer, 2)
        proto_name_length, = struct.unpack_from('<B', buffer, key_length + 2)
        proto_name, = struct.unpack_from(f'<{proto_name_length}s', buffer, key_length + 3)
        proto_body_len = package_length - 1 - 1 - key_length - 1 - proto_name_length
        proto_body, = struct.unpack_from(f'<{proto_body_len}s', buffer, key_length + 3 + proto_name_length)

    except struct.error as e:
        return {}

    data = {
        'command': command,
        'proto_name': proto_name,
        'proto_body': proto_body  # not dencrypt
    }
    return data


def msg_unpack_length_and_command(buffer):
    """
    解析长度及类型信息
    """
    length, command = None, None
    try:
        length, command = struct.unpack('>IB', buffer)
    except struct.error as error:
        print(buffer)
        raise ValueError('') from error
    return length, command


def msg_unpack_with_length(buffer):
    """
    报文总长度解析
    """
    try:
        length, = struct.unpack('>I', buffer)
    except struct.error as e:
        return None
    else:
        return length
