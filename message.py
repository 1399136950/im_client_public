# -*- coding: utf-8
"""
消息序列化及封装处理
@author xujun
"""
from enum import Enum
from typing import List

from proto import MessageProBuf_pb2
from proto import GlobalBoProto_pb2
from utils.encrypt import aes_decrypt
from utils.generator import get_time_stamp, device_id_gen  # , get_communication_info,  text_stream_gen
from utils.packer import msg_pack
from google.protobuf.json_format import MessageToJson
import json
from random import choice

from config import ENV_MODEL


class CommandType(Enum):
    COMMAND_ERROR = -1                      # 失败错误
    COMMAND_BIND_USER = 3                   # 绑定用户请求
    COMMAND_BIND_USER_RESP = 4              # 响应绑定用户
    COMMAND_SYSTEM_NOTIFY = 5               # 系统通知
    COMMAND_MESSAGE_ACK = 6	                # 消息送达ack
    COMMAND_MESSAGE_READ = 7	            # 消息已读ack
    COMMAND_FORCE_LOGOUT = 8                # 被踢出通知
    COMMAND_SEND_MSG_REQ = 10               # 发送消息请求
    COMMAND_SEND_MSG_RSP = 11               # 聊天消息回执
    COMMAND_TEST = 12                       # 测试类型
    COMMAND_PULL_MSG_REQ = 13               # 拉消息命令
    COMMAND_PULL_MSG_RESP = 14              # 服务器响应拉消息命令
    COMMAND_SYNC_SELF_REQ = 15              # 同步自己其他端
    COMMAND_SYNC_SELF_RESP = 16             # 同步自己请求响应
    COMMAND_MESSAGE_READ_RSP = 17           # 消息已读应答
    COMMAND_COMMUNICATION_READ_SYNC = 18    # 会话已读同步
    COMMAND_INPUT_STATUS_REQ = 19           # 用户输入状态请求
    COMMAND_INPUT_STATUS_ACK = 20           # 用户输入状态响应
    COMMAND_INPUT_STATUS_NOTIFY = 21        # 用户输入状态通知
    COMMAND_PING = 98                       # 心跳
    COMMAND_PONG = 99                       # 心跳
    COMMAND_SUCCESS = 100                   # 成功请求


RECEIVE_TYPE = {
    2: 'HANDSHAKE_RESP',
    4: 'BIND_USER_RESP',
    5: 'COMMAND_AUTH_REQ',
    6: 'MESSAGE_ACK',
    7: 'MESSAGE_READ',
    8: 'FORCE_LOGOUT',
    10: 'SEND_MSG_REQ',
    11: 'SEND_MSG_RSP',
    12: 'SEND_MSG_RSP_TEST',
    99: 'PONG',
}


class CommunicationType(Enum):
    """联系通道类型：单聊/群聊"""
    SINGLE_PERSON = 1


class MessageType(Enum):
    """消息类型"""
    TEXT = 1
    EMOJI = 2
    FILE = 3
    IMAGE = 4
    AUDIO = 5
    VIDEO = 6
    ADDRESS = 7


ProtoBuffers = {
    'CommunicationMessageProto': MessageProBuf_pb2.CommunicationMessageProto,
    'ReqBindUserChannel': MessageProBuf_pb2.ReqBindUserChannel,
    'RspBindUserChannel': MessageProBuf_pb2.RspBindUserChannel,
    'ReplyCommandSendMsgReq': MessageProBuf_pb2.ReplyCommandSendMsgReq,
    'MessageAckProto': MessageProBuf_pb2.MessageAckProto,
    'RespErrorResultProto': GlobalBoProto_pb2.RespErrorResultProto,
    'ForceLogoutProto': MessageProBuf_pb2.ForceLogoutProto,
    'HeartBeatMsg': MessageProBuf_pb2.HeartBeatMsg,
    'HeartBeatAckMsg': MessageProBuf_pb2.HeartBeatAckMsg,
    'BaseRespProto': GlobalBoProto_pb2.BaseRespProto,
    'ReplyBatchMessageAckReq': MessageProBuf_pb2.ReplyBatchMessageAckReq,
    'ReadCommunicationSyncProto': MessageProBuf_pb2.ReadCommunicationSyncProto,
    'InputStatusMsgReq': MessageProBuf_pb2.InputStatusMsgReq,
    'InputStatusMsgAck': MessageProBuf_pb2.InputStatusMsgAck,
    'InputStatusMsgNotify': MessageProBuf_pb2.InputStatusMsgNotify
}


def create_message(pb_instance, command, key, pb_name, body):
    """
    消息内容填充、序列化、打包
    """
    if body:
        [setattr(pb_instance, k, v) for k, v in body.items() if v is not None]
    data = pb_instance.SerializeToString()
    message = msg_pack(command, key, pb_name, data)

    return message


def decode_message(pb_name, pb_body):
    """
    消息解码
    """
    pb = ProtoBuffers.get(pb_name.decode('utf8'))
    if not pb:
        raise RuntimeError('该消息类型无法解码：{}'.format(pb_name))
    pb_instance = pb()
    try:
        pb_instance.ParseFromString(pb_body)
    except TypeError:
        return None
    else:
        # return pb_instance
        json_string_request = MessageToJson(pb_instance, preserving_proto_field_name=True)
        return json.loads(json_string_request)


def decode_all_message(msg):
    import struct
    length = msg[0:4]
    command_type = msg[4]
    key_len = msg[5]
    key = msg[6:6+key_len]
    proto_name_len = msg[6+key_len]
    proto_name = msg[6+key_len+1 : proto_name_len+6+1+key_len]
    print(proto_name)
    proto_body = msg[proto_name_len+6+1+key_len:]
    proto_body = aes_decrypt(proto_body)
    r = decode_message(proto_name, proto_body)
    return r 


def get_bind_message(token: str, key: str, user_info: dict, device_info: dict):
    """
    用户绑定消息
    """
    if token:
        body = {
            'app_id': user_info['app_id'],
            'user_id': user_info['user_id'],
            'token': token,
            'manufacturer': device_info['manufacturer'],
            'device_id': device_info['device_id'],
            'os_version': device_info['os_version']
        }
        pb = MessageProBuf_pb2.ReqBindUserChannel()
        message = create_message(pb, CommandType.COMMAND_BIND_USER.value, key, 'ReqBindUserChannel', body)
        return message
    else:
        return None


# def get_communication_message(key, user_info):
#     """
#     获取单聊消息
#     """
#     info = get_communication_info(user_info['user_id'])
#     friend_id = info.get('target_id')
#     communication_id = info.get('communication_id')
#
#     body = {
#         'app_id': user_info['app_id'],
#         'from_user_id': user_info['user_id'],
#         'to_user_id': friend_id or user_info['friend'],
#         'communication_id': communication_id or None,
#         'send_time': get_time_stamp(),
#         'communication_type': MessageType.TEXT.value,
#         'message_type': CommunicationType.SINGLE_PERSON.value,
#         'content': text_stream_gen(),
#         'tag': device_id_gen()
#     }
#     pb = MessageProBuf_pb2.CommunicationMessageProto()
#     message = create_message(pb, CommandType.COMMAND_SEND_MSG_REQ.value, key, 'CommunicationMessageProto', body)
#     return message


IMG_INFO = [
    {
            'file_name': 'c9f0af0dce59fa5fcd7ea878f65579cc.jpg',
            'file_size': 125596,
            'file_uri': 'http://dev-im-sdk.phh4.com/other/9d934dce2316b70a217dcffc5e6ef433.jpg',
            'file_suffix': 'jpg',
            'image_width': 400,
            'image_height': 400,
            'file_md5': 'c9f0af0dce59fa5fcd7ea878f65579cc'
    },
    {
        'file_name': 'a67fcf905bd481d7bed714dc37a2df8f.gif',
        'file_size': 572652,
        'file_uri': 'http://dev-im-sdk.phh4.com/other/6c507adbab87a57ca355bea637782c06.gif',
        'file_suffix': 'gif',
        'image_width': 1038,
        'image_height': 1036,
        'file_md5': 'a215f8b50d173907938dc27d006fd5ea'
    },
    {
        'file_name': '1585488076670933.png',
        'file_size': 115726,
        'file_uri': 'http://dev-im-sdk.phh4.com/other/fc34dc6c39cb3426fa10da666fa3e0e6.png',
        'file_suffix': 'png',
        'image_width': 980,
        'image_height': 398,
        'file_md5': 'a637a09d72cd62abc00b74f93a094612'
    },
    {'file_name': 'mmexport1611745202335.jpg', 'file_size': 36618, 'file_uri': 'http://dev-im-sdk.phh4.com/other/25f28a7abc76ae3e42c4fdabb834633a.jpg', 'file_suffix': 'jpg', 'image_width': 690, 'image_height': 675, 'file_md5': '25f28a7abc76ae3e42c4fdabb834633a'},
    {'file_name': 'mmexport1611831922103.jpg', 'file_size': 30433, 'file_uri': 'http://dev-im-sdk.phh4.com/other/30c6ff96f0232982bae3b4e547112958.jpg', 'file_suffix': 'jpg', 'image_width': 440, 'image_height': 440, 'file_md5': '30c6ff96f0232982bae3b4e547112958'},
    {'file_name': 'mmexport1613032678390.jpg', 'file_size': 45658, 'file_uri': 'http://dev-im-sdk.phh4.com/other/75dcf4eb901540eabcf3b1fab03bc927.jpg', 'file_suffix': 'jpg', 'image_width': 720, 'image_height': 540, 'file_md5': '75dcf4eb901540eabcf3b1fab03bc927'},
    {'file_name': 'mmexport1613438276677.jpg', 'file_size': 56397, 'file_uri': 'http://dev-im-sdk.phh4.com/other/04af3a8e058d8f6f4716b8681db97857.jpg', 'file_suffix': 'jpg', 'image_width': 720, 'image_height': 720, 'file_md5': '04af3a8e058d8f6f4716b8681db97857'},
    # {'file_name': '1619156413354200.gif', 'file_size': 4115, 'file_uri': 'http://dev-im-sdk.phh4.com/other/908d01f2198517377e128434b85ccca6.gif', 'file_suffix': 'jpg', 'image_width': 224, 'image_height': 211, 'file_md5': '908d01f2198517377e128434b85ccca6'},
    # {'file_name': '1619156404803350.gif', 'file_size': 16442, 'file_uri': 'http://dev-im-sdk.phh4.com/other/623a16d0a9661c63e7c0d52b888becda.gif', 'file_suffix': 'jpg', 'image_width': 479, 'image_height': 479, 'file_md5': '623a16d0a9661c63e7c0d52b888becda'},
    {'file_name': 'mmexport1617274011996.jpg', 'file_size': 44333, 'file_uri': 'http://dev-im-sdk.phh4.com/other/451d10a8d7c24e131b49f7e6fb86fe15.jpg', 'file_suffix': 'jpg', 'image_width': 720, 'image_height': 590, 'file_md5': '451d10a8d7c24e131b49f7e6fb86fe15'},
    {'file_name': 'mmexport1618360289767.jpg', 'file_size': 20286, 'file_uri': 'http://dev-im-sdk.phh4.com/other/68b8a307b75692a8584b1c630150922a.jpg', 'file_suffix': 'jpg', 'image_width': 690, 'image_height': 699, 'file_md5': '68b8a307b75692a8584b1c630150922a'},
    {'file_name': 'mmexport1618275200089.jpg', 'file_size': 25536, 'file_uri': 'http://dev-im-sdk.phh4.com/other/d45eb5c08da4f0a396166ed730d9d90a.jpg', 'file_suffix': 'jpg', 'image_width': 653, 'image_height': 636, 'file_md5': 'd45eb5c08da4f0a396166ed730d9d90a'},
    {'file_name': 'mmexport1619019948666.jpg', 'file_size': 22706, 'file_uri': 'http://dev-im-sdk.phh4.com/other/ab87cba71572b1dab6bd48f5a9db7c03.jpg', 'file_suffix': 'jpg', 'image_width': 698, 'image_height': 651, 'file_md5': 'ab87cba71572b1dab6bd48f5a9db7c03'},
    {'file_name': 'mmexport1619102286224.jpg', 'file_size': 30072, 'file_uri': 'http://dev-im-sdk.phh4.com/other/54540c3ab5d97c7af504e7f2257b8abb.jpg', 'file_suffix': 'jpg', 'image_width': 584, 'image_height': 511, 'file_md5': '54540c3ab5d97c7af504e7f2257b8abb'},
    {'file_name': 'mmexport1605140919307.jpg', 'file_size': 30928, 'file_uri': 'http://dev-im-sdk.phh4.com/other/e3579a19bad81928463639318febe49d.jpg', 'file_suffix': 'jpg', 'image_width': 612, 'image_height': 608, 'file_md5': 'e3579a19bad81928463639318febe49d'},
    {'file_name': '1619337061711869.gif', 'file_size': 8021, 'file_uri': 'http://dev-im-sdk.phh4.com/other/6657f904ba841ba5f6ce5eeeb99971dc.gif', 'file_suffix': 'jpg', 'image_width': 238, 'image_height': 238, 'file_md5': '6657f904ba841ba5f6ce5eeeb99971dc'},
    {'file_name': 'mmexport1599452635871.jpg', 'file_size': 29478, 'file_uri': 'http://dev-im-sdk.phh4.com/other/cc4b0edf97f976e386d86f183f2d3246.jpg', 'file_suffix': 'jpg', 'image_width': 720, 'image_height': 720, 'file_md5': 'cc4b0edf97f976e386d86f183f2d3246'},
    {'file_name': 'mmexport1599452625491.jpg', 'file_size': 39980, 'file_uri': 'http://dev-im-sdk.phh4.com/other/b76b9f57100952bea00688e9d60307cf.jpg', 'file_suffix': 'jpg', 'image_width': 719, 'image_height': 655, 'file_md5': 'b76b9f57100952bea00688e9d60307cf'},
    {'file_name': 'mmexport1598025729295.jpg', 'file_size': 41969, 'file_uri': 'http://dev-im-sdk.phh4.com/other/2c077612f1466ef4a52fe9096c753e1d.jpg', 'file_suffix': 'jpg', 'image_width': 700, 'image_height': 700, 'file_md5': '2c077612f1466ef4a52fe9096c753e1d'},
    {'file_name': 'mmexport1597490128424.jpg', 'file_size': 20246, 'file_uri': 'http://dev-im-sdk.phh4.com/other/70df3d27e7e35feeb272a3e8e4075516.jpg', 'file_suffix': 'jpg', 'image_width': 390, 'image_height': 414, 'file_md5': '70df3d27e7e35feeb272a3e8e4075516'},
    {'file_name': 'mmexport1595565690845.jpg', 'file_size': 28239, 'file_uri': 'http://dev-im-sdk.phh4.com/other/2394e748e96fb3282dc74504ea57e35d.jpg', 'file_suffix': 'jpg', 'image_width': 580, 'image_height': 580, 'file_md5': '2394e748e96fb3282dc74504ea57e35d'},
    {'file_name': 'mmexport1595468980982.jpg', 'file_size': 23561, 'file_uri': 'http://dev-im-sdk.phh4.com/other/9a7138f758d53d8e33b9800e53537e36.jpg', 'file_suffix': 'jpg', 'image_width': 500, 'image_height': 490, 'file_md5': '9a7138f758d53d8e33b9800e53537e36'},
    {'file_name': 'mmexport1595289713621.jpg', 'file_size': 43310, 'file_uri': 'http://dev-im-sdk.phh4.com/other/6f224e14a90fc1d183f2e24f0ee2cdf7.jpg', 'file_suffix': 'jpg', 'image_width': 718, 'image_height': 817, 'file_md5': '6f224e14a90fc1d183f2e24f0ee2cdf7'},
    {'file_name': 'mmexport1593754348487.jpg', 'file_size': 20771, 'file_uri': 'http://dev-im-sdk.phh4.com/other/4fe179061f7c910d1e25742790a00a65.jpg', 'file_suffix': 'jpg', 'image_width': 720, 'image_height': 549, 'file_md5': '4fe179061f7c910d1e25742790a00a65'},
    {'file_name': 'mmexport1607765959833.jpg', 'file_size': 33187, 'file_uri': 'http://dev-im-sdk.phh4.com/other/e0a12204bfe161484f4572e2edd86580.jpg', 'file_suffix': 'jpg', 'image_width': 640, 'image_height': 640, 'file_md5': 'e0a12204bfe161484f4572e2edd86580'},
    {'file_name': 'mmexport1607261294164.jpg', 'file_size': 39389, 'file_uri': 'http://dev-im-sdk.phh4.com/other/586979242164fe8ea33029632558884e.jpg', 'file_suffix': 'jpg', 'image_width': 690, 'image_height': 690, 'file_md5': '586979242164fe8ea33029632558884e'},
    {'file_name': 'mmexport1607261249816.jpg', 'file_size': 39591, 'file_uri': 'http://dev-im-sdk.phh4.com/other/17f2a9d732085f77266b46e46ef73f22.jpg', 'file_suffix': 'jpg', 'image_width': 690, 'image_height': 690, 'file_md5': '17f2a9d732085f77266b46e46ef73f22'},
    # {'file_name': '1619337485198144.gif', 'file_size': 16442, 'file_uri': 'http://dev-im-sdk.phh4.com/other/623a16d0a9661c63e7c0d52b888becda.gif', 'file_suffix': 'jpg', 'image_width': 479, 'image_height': 479, 'file_md5': '623a16d0a9661c63e7c0d52b888becda'},
    {'file_name': 'mmexport1619610293228.jpg', 'file_size': 31745, 'file_uri': 'http://mgim-sdk.zhuanxin.com/other/f0a717acfc097a5064140dba2b3e53bc.jpg', 'file_suffix': 'jpg', 'image_width': 500, 'image_height': 500, 'file_md5': 'f0a717acfc097a5064140dba2b3e53bc'},
    {'file_name': 'mmexport1619610295581.jpg', 'file_size': 57038, 'file_uri': 'http://mgim-sdk.zhuanxin.com/other/b3e7538dfb69d312e9f749576cd6d90c.jpg', 'file_suffix': 'jpg', 'image_width': 700, 'image_height': 701, 'file_md5': 'b3e7538dfb69d312e9f749576cd6d90c'},
    {'file_name': 'mmexport1619610297649.jpg', 'file_size': 42293, 'file_uri': 'http://mgim-sdk.zhuanxin.com/other/b46da8af4ced65de942deb37a4e158a8.jpg', 'file_suffix': 'jpg', 'image_width': 700, 'image_height': 700, 'file_md5': 'b46da8af4ced65de942deb37a4e158a8'},
    {'file_name': 'mmexport1619610299749.jpg', 'file_size': 90308, 'file_uri': 'http://mgim-sdk.zhuanxin.com/other/19d3823d9db426769d0c8c6d820a10f6.jpg', 'file_suffix': 'jpg', 'image_width': 810, 'image_height': 806, 'file_md5': '19d3823d9db426769d0c8c6d820a10f6'},
    {'file_name': 'mmexport1619610301867.jpg', 'file_size': 27480, 'file_uri': 'http://mgim-sdk.zhuanxin.com/other/668a3a6572d1ec122a1c014ac67f05b0.jpg', 'file_suffix': 'jpg', 'image_width': 670, 'image_height': 669, 'file_md5': '668a3a6572d1ec122a1c014ac67f05b0'},
    {'file_name': 'mmexport1619610304014.jpg', 'file_size': 54063, 'file_uri': 'http://mgim-sdk.zhuanxin.com/other/3ea95a833f18832067c08dd80a4d20ea.jpg', 'file_suffix': 'jpg', 'image_width': 720, 'image_height': 714, 'file_md5': '3ea95a833f18832067c08dd80a4d20ea'},
    {'file_name': 'mmexport1619610306559.jpg', 'file_size': 91811, 'file_uri': 'http://mgim-sdk.zhuanxin.com/other/dbb715c1b1f2d85db6fd87e77857d7cb.jpg', 'file_suffix': 'jpg', 'image_width': 1000, 'image_height': 1000, 'file_md5': 'dbb715c1b1f2d85db6fd87e77857d7cb'},
    {'file_name': 'mmexport1619610308667.jpg', 'file_size': 19268, 'file_uri': 'http://mgim-sdk.zhuanxin.com/other/3c75456d22a12b6ccf6d46b33a58fecd.jpg', 'file_suffix': 'jpg', 'image_width': 540, 'image_height': 540, 'file_md5': '3c75456d22a12b6ccf6d46b33a58fecd'},
    {'file_name': 'mmexport1619610311361.jpg', 'file_size': 72124, 'file_uri': 'http://mgim-sdk.zhuanxin.com/other/f372f5b4021dc0748b43a444dfde2064.jpg', 'file_suffix': 'jpg', 'image_width': 1000, 'image_height': 1000, 'file_md5': 'f372f5b4021dc0748b43a444dfde2064'},
    {'file_name': 'mmexport1619610313496.jpg', 'file_size': 28349, 'file_uri': 'http://mgim-sdk.zhuanxin.com/other/2aae4c91f7546b82dd2db4bb681ed551.jpg', 'file_suffix': 'jpg', 'image_width': 500, 'image_height': 500, 'file_md5': '2aae4c91f7546b82dd2db4bb681ed551'},
    {'file_name': 'mmexport1619610315755.jpg', 'file_size': 21886, 'file_uri': 'http://mgim-sdk.zhuanxin.com/other/e532464d278be6eb8a6d791ec0c2ce07.jpg', 'file_suffix': 'jpg', 'image_width': 500, 'image_height': 500, 'file_md5': 'e532464d278be6eb8a6d791ec0c2ce07'},
    {'file_name': 'mmexport1619610317919.jpg', 'file_size': 29321, 'file_uri': 'http://mgim-sdk.zhuanxin.com/other/dd84807a6904c37f72afd4f85357fd1c.jpg', 'file_suffix': 'jpg', 'image_width': 500, 'image_height': 500, 'file_md5': 'dd84807a6904c37f72afd4f85357fd1c'},
    {'file_name': '161961099280883.jpeg', 'file_size': 118005, 'file_uri': 'http://mgim-sdk.zhuanxin.com/other/8f9378b613c19b02845247b94c6ea493.jpeg', 'file_suffix': 'jpg', 'image_width': 1080, 'image_height': 2260, 'file_md5': '8f9378b613c19b02845247b94c6ea493'},
    {'file_name': '55bd8e8681ce46ddae66337c9f80c206.gif', 'file_size': 45223, 'file_uri': 'http://dev-im-sdk.phh4.com/other/bdeac8ace738ed60ae13df76d1b9d53d.gif', 'file_suffix': 'gif', 'image_width': 180, 'image_height': 197, 'file_md5': 'bdeac8ace738ed60ae13df76d1b9d53d'},
    {'file_name': 'mmexport1613599444071.gif', 'file_size': 1176853, 'file_uri': 'http://dev-im-sdk.phh4.com/other/dadfe86f449f02b6b6274eb0884048cb.gif', 'file_suffix': 'gif', 'image_width': 479, 'image_height': 479, 'file_md5': 'dadfe86f449f02b6b6274eb0884048cb'},
    {'file_name': 'mmexport1616167914650.gif', 'file_size': 899514, 'file_uri': 'http://dev-im-sdk.phh4.com/other/406a963a0dddaf9cb2fbadeecb3a594f.gif', 'file_suffix': 'gif', 'image_width': 224, 'image_height': 211, 'file_md5': '406a963a0dddaf9cb2fbadeecb3a594f'},
    {'file_name': 'mmexport1599802284947.gif', 'file_size': 1228327, 'file_uri': 'http://dev-im-sdk.phh4.com/other/9b11cfd174228e45bd0d02c1d4e49f72.gif', 'file_suffix': 'gif', 'image_width': 238, 'image_height': 238, 'file_md5': '9b11cfd174228e45bd0d02c1d4e49f72'},
    {'file_name': 'mmexport1602308563134.gif', 'file_size': 187276, 'file_uri': 'http://dev-im-sdk.phh4.com/other/0e556620d787354d2905ae22d8af8b96.gif', 'file_suffix': 'gif', 'image_width': 640, 'image_height': 360, 'file_md5': '0e556620d787354d2905ae22d8af8b96'},
    {'file_name': 'wx_20210513145320.jpg', 'file_size': 28056, 'file_uri': 'http://dev-im-sdk.phh4.com/other/e16a589a4e1bfe35db36d93cfb428425.jpg', 'file_suffix': 'jpg', 'image_width': 690, 'image_height': 690, 'file_md5': 'e16a589a4e1bfe35db36d93cfb428425'},
    {'file_name': 'wx_20210513145320.png', 'file_size': 69521, 'file_uri': 'http://dev-im-sdk.phh4.com/other/2f7dcb91d8d219d264203233fe095509.png', 'file_suffix': 'png', 'image_width': 275, 'image_height': 248, 'file_md5': '2f7dcb91d8d219d264203233fe095509'},
    {'file_name': 'wx_202105131453201.jpg', 'file_size': 67876, 'file_uri': 'http://dev-im-sdk.phh4.com/other/9ae6767717fcd6c8961cf2d7298c2b3e.jpg', 'file_suffix': 'jpg', 'image_width': 500, 'image_height': 500, 'file_md5': '9ae6767717fcd6c8961cf2d7298c2b3e'},
    {'file_name': 'wx_202105131453202.jpg', 'file_size': 33261, 'file_uri': 'http://dev-im-sdk.phh4.com/other/ba952a7a46a284aa0712143cda4907e1.jpg', 'file_suffix': 'jpg', 'image_width': 552, 'image_height': 585, 'file_md5': 'ba952a7a46a284aa0712143cda4907e1'},
    {'file_name': 'wx_202105131453203.jpg', 'file_size': 69652, 'file_uri': 'http://dev-im-sdk.phh4.com/other/b778a45abcc6c7c42845987e34dac66d.jpg', 'file_suffix': 'jpg', 'image_width': 828, 'image_height': 828, 'file_md5': 'b778a45abcc6c7c42845987e34dac66d'},
    {'file_name': 'wx_202105131453204.jpg', 'file_size': 107032, 'file_uri': 'http://dev-im-sdk.phh4.com/other/c6ca3a636c6230ccac71c3bfbf1461cb.jpg', 'file_suffix': 'jpg', 'image_width': 828, 'image_height': 828, 'file_md5': 'c6ca3a636c6230ccac71c3bfbf1461cb'},
    {'file_name': 'wx_202105131453205.jpg', 'file_size': 21898, 'file_uri': 'http://dev-im-sdk.phh4.com/other/2c637094646c7b0bc870f9e4fdd8d017.jpg', 'file_suffix': 'jpg', 'image_width': 365, 'image_height': 365, 'file_md5': '2c637094646c7b0bc870f9e4fdd8d017'},
    {'file_name': 'wx_202105131453206.jpg', 'file_size': 128079, 'file_uri': 'http://dev-im-sdk.phh4.com/other/d3cd985812321b81068005a2dd92103d.jpg', 'file_suffix': 'jpg', 'image_width': 960, 'image_height': 960, 'file_md5': 'd3cd985812321b81068005a2dd92103d'},
    {'file_name': 'wx_202105131453207.jpg', 'file_size': 67922, 'file_uri': 'http://dev-im-sdk.phh4.com/other/57227e704dfb52e943f4cd3aa83a7171.jpg', 'file_suffix': 'jpg', 'image_width': 933, 'image_height': 960, 'file_md5': '57227e704dfb52e943f4cd3aa83a7171'},
    {'file_name': '112.gif', 'file_size': 54631, 'file_uri': 'http://dev-im-sdk.phh4.com/other/18ec8c7cdee0c975d54bd2cc602d9c66.gif', 'file_suffix': 'gif', 'image_width': 103, 'image_height': 107, 'file_md5': '18ec8c7cdee0c975d54bd2cc602d9c66'},
    {'file_name': '113.gif', 'file_size': 90255, 'file_uri': 'http://dev-im-sdk.phh4.com/other/3f92c5d4f740d4c4a65083c315c7faee.gif', 'file_suffix': 'gif', 'image_width': 100, 'image_height': 107, 'file_md5': '3f92c5d4f740d4c4a65083c315c7faee'},
    {'file_name': '114.gif', 'file_size': 92514, 'file_uri': 'http://dev-im-sdk.phh4.com/other/c5faaad16899de1c32b3abae3593519d.gif', 'file_suffix': 'gif', 'image_width': 102, 'image_height': 103, 'file_md5': 'c5faaad16899de1c32b3abae3593519d'},
    {'file_name': '115.gif', 'file_size': 88977, 'file_uri': 'http://dev-im-sdk.phh4.com/other/7061077bf5f9ea93ee7c8578feccaf43.gif', 'file_suffix': 'gif', 'image_width': 117, 'image_height': 113, 'file_md5': '7061077bf5f9ea93ee7c8578feccaf43'},
    {'file_name': '116.gif', 'file_size': 47118, 'file_uri': 'http://dev-im-sdk.phh4.com/other/c3dd8dd0dc51ad50041c8887168adbbc.gif', 'file_suffix': 'gif', 'image_width': 98, 'image_height': 105, 'file_md5': 'c3dd8dd0dc51ad50041c8887168adbbc'},
    {'file_name': '117.gif', 'file_size': 90157, 'file_uri': 'http://dev-im-sdk.phh4.com/other/5249d54218afa8e37020827caaded485.gif', 'file_suffix': 'gif', 'image_width': 93, 'image_height': 103, 'file_md5': '5249d54218afa8e37020827caaded485'}
]


if ENV_MODEL == 'produce':
    '''
    线上环境的文件消息
    '''
    FILE_INFO = [
        {'file_name': '2020-11-27-20-54.tar.gz', 'file_size': 300472, 'file_uri': 'http://mgim-sdk.zhuanxin.com/other/3464b5528bbff24b0520d693fca0f99c.gz', 'file_suffix': 'gz', 'file_md5': '83449f3dca7568265766d5418e8d973f'},
        {'file_name': '1.mp3', 'file_size': 5056888, 'file_uri': 'http://mgim-sdk.zhuanxin.com/other/b18b0d554dd011fa059a249929cfb781.mp3', 'file_suffix': 'mp3', 'file_md5': '4b10c67ef1959433b9ac9280b9698156'},
        {'file_name': '单聊场景网络切换测试结果.xls', 'file_size': 22016, 'file_uri': 'http://mgim-sdk.zhuanxin.com/other/06183d8ed939ed1d06596d5aaad317aa.xls', 'file_suffix': 'xls', 'file_md5': '5f7b0b2ee9e9a643100947b84fa72fa1'},
        {'file_name': '会合APP需求说明书_20200619(1)(1).doc', 'file_size': 3463841, 'file_uri': 'http://mgim-sdk.zhuanxin.com/other/3ad54547584f91c28864e010fb3acdc7.doc', 'file_suffix': '.doc', 'file_md5': '7aadf72b623bc12e2332c368f8ec31a6'},
        {'file_name': '2021年01月23日产品发布清单.pdf', 'file_size': 35576, 'file_uri': 'http://mgim-sdk.zhuanxin.com/other/fabb2cefe3efa4079f05e3863b00002f.pdf', 'file_suffix': 'pdf', 'file_md5': 'a91ff471564292149ceea9a5fd7fe7bd'},
        {'file_name': '会合专信交流对接项目组.pptx', 'file_size': 6572453, 'file_uri': 'http://mgim-sdk.zhuanxin.com/other/b9c25c2b2513d0f1f6d392318b7c60a4.pptx', 'file_suffix': 'pptx', 'file_md5': '7565ae21608d87991fe6fe793ab383cc'},
        {'file_name': 'cmcc-sso-3.2.4.0.zip', 'file_size': 342333, 'file_uri': 'http://mgim-sdk.zhuanxin.com/other/943724ea1d3d914886f367a9ad9f1ee5.zip', 'file_suffix': 'zip', 'file_md5': '943724ea1d3d914886f367a9ad9f1ee5'},
        {'file_name': '新建DOCX 文档.docx', 'file_size': 11086, 'file_uri': 'http://mgim-sdk.zhuanxin.com/other/38eef5502cf0dd050ce8ab4294c9369b.docx', 'file_suffix': 'docx', 'file_md5': '38eef5502cf0dd050ce8ab4294c9369b'},
        {'file_name': '测试.doc', 'file_size': 9728, 'file_uri': 'http://mgim-sdk.zhuanxin.com/other/4bf74a4e1cce4195ea696957b84155fe.doc', 'file_suffix': 'doc', 'file_md5': '4bf74a4e1cce4195ea696957b84155fe'},
        {'file_name': '新建文本文档.txt', 'file_size': 18, 'file_uri': 'http://mgim-sdk.zhuanxin.com/other/5c4890d9ff35448281eb09f35712235b.txt', 'file_suffix': 'txt', 'file_md5': '5c4890d9ff35448281eb09f35712235b'},
        {'file_name': '测试.xlsx', 'file_size': 9958, 'file_uri': 'http://mgim-sdk.zhuanxin.com/other/be4d5ea9f37c913aefb305779a6835e0.xlsx', 'file_suffix': 'xlsx', 'file_md5': 'be4d5ea9f37c913aefb305779a6835e0'}
    ]
    AUDIO_INFO = [
        {'file_name': 'voice.aac', 'file_size': 51419, 'file_uri': 'http://mgim-sdk.zhuanxin.com/other/75b4639bb9077017e6e2a9844f792c20.aac', 'file_suffix': 'aac', 'file_duration': 6, 'file_md5': '79ba87f7daa8206d68288c61f8eeb433'}
    ]
elif ENV_MODEL == 'dev':
    '''
    dev环境的文件消息
    '''
    FILE_INFO = [
        {'file_name': 'IM项目周报-20201225(1).pdf', 'file_size': 301979, 'file_uri': 'http://dev-im-sdk.phh4.com/other/ea0baaf172c5444f92adbe045f1fef4d.pdf', 'file_suffix': 'pdf', 'file_md5': '461039b5a6931edcfd7eb1534ac866b9'},
        {'file_name': '群聊消息优化_测试场景.xlsx', 'file_size': 13696, 'file_uri': 'http://dev-im-sdk.phh4.com/other/2bc332b8daf9cc2bd041e4921f35088a.xlsx', 'file_suffix': 'xlsx', 'file_md5': '5bac094ee5264b182e569f3eb5fce4dd'},
        {'file_name': '1.mp3', 'file_size': 5056888, 'file_uri': 'http://dev-im-sdk.phh4.com/other/b18b0d554dd011fa059a249929cfb781.mp3', 'file_suffix': 'mp3', 'file_md5': '4b10c67ef1959433b9ac9280b9698156'},
        {'file_name': '核心接口文档.docx', 'file_size': 43497, 'file_uri': 'http://dev-im-sdk.phh4.com/other/b904d4794c1cc97299c8546ba5e4714f.docx', 'file_suffix': 'docx', 'file_md5': 'bd60ac6a613c2ac1cf3af3e73a5571ee'},
        {'file_name': 'b9c25c2b2513d0f1f6d392318b7c60a4.pptx', 'file_size': 6572453, 'file_uri': 'http://dev-im-sdk.phh4.com/other/b9c25c2b2513d0f1f6d392318b7c60a4.pptx', 'file_suffix': 'pptx', 'file_md5': '7565ae21608d87991fe6fe793ab383cc'},
        {'file_name': '3464b5528bbff24b0520d693fca0f99c.gz', 'file_size': 300472, 'file_uri': 'http://dev-im-sdk.phh4.com/other/3464b5528bbff24b0520d693fca0f99c.gz', 'file_suffix': 'gz', 'file_md5': '83449f3dca7568265766d5418e8d973f'},
        {'file_name': 'cmcc-sso-3.2.4.0.zip', 'file_size': 342333, 'file_uri': 'http://dev-im-sdk.phh4.com/other/943724ea1d3d914886f367a9ad9f1ee5.zip', 'file_suffix': 'zip', 'file_md5': '943724ea1d3d914886f367a9ad9f1ee5'},
        {'file_name': 'requirements.txt', 'file_size': 845, 'file_uri': 'http://dev-im-sdk.phh4.com/other/2de1bc8387cb183c9f214785e5f37623.txt', 'file_suffix': 'txt', 'file_md5': '2de1bc8387cb183c9f214785e5f37623'},
        {'file_name': 'upload.html', 'file_size': 217, 'file_uri': 'http://dev-im-sdk.phh4.com/other/4fc8b660e8fbe3e4c278f3b3cffc85d0.html', 'file_suffix': 'html', 'file_md5': '4fc8b660e8fbe3e4c278f3b3cffc85d0'}
    ]
    AUDIO_INFO = [
        {'file_name': 'voice.aac', 'file_size': 47538, 'file_uri': 'http://dev-im-sdk.phh4.com/other/e6887c990a48b0081ba29ff79e5d4d05.aac', 'file_suffix': 'aac', 'file_duration': 5, 'file_md5': '5078932d8c0b3446ce39b7e798ec8f4d'},
        {
            "file_name": "voice.aac",
            "file_size": 488715,
            "file_uri": "http://dev-im-sdk.phh4.com/other/3a858b91a37acc4c902d515bafd11de0.aac",
            "file_suffix": "aac",
            "file_duration": 60,
            "file_md5": "c64203cab35a9870ee70c32a31c0f783"
        }
    ]


VIDEO_INFO = [
    {
        'file_name': 'c8e03ff4-278c-11ea-a37a-965276b5d811.mp4',
        'file_pic': 'http://dev-im-sdk.phh4.com/other/4e3a6cb05fba798c641a8b69e94a6ed5.jpg',
        'file_size': 1678210,
        'file_uri': 'http://dev-im-sdk.phh4.com/other/52116e73840a5ce4587c23d4b1f017b2.mp4',
        'file_suffix': 'mp4',
        'file_duration': 26,
        'image_width': 800,
        'image_height': 800,
        'file_md5': '52116e73840a5ce4587c23d4b1f017b2'
    },
    {
        'file_name': 'a94e1518-3dc0-11ea-b12e-7aadf741f5a6.mp4',
        'file_pic': 'http://dev-im-sdk.phh4.com/other/06ef2b6efc4aa2eb778094ce17ce68f1.jpg',
        'file_size': 839620,
        'file_uri': 'http://dev-im-sdk.phh4.com/other/a4064186722b190d2920661ceb264339.mp4',
        'file_suffix': 'mp4',
        'file_duration': 12,
        'image_width': 376,
        'image_height': 640,
        'file_md5': 'a4064186722b190d2920661ceb264339'
    },
    {'file_name': '162081983167355.mp4', 'file_pic': 'http://dev-im-sdk.phh4.com/other/7b7b67b67cade292b341ab732fd803b1.png', 'file_size': 1741653, 'file_uri': 'http://dev-im-sdk.phh4.com/other/cbdad6fdb5d7767fc315ee863286ac4b.mp4', 'file_suffix': 'mp4', 'file_duration': 19, 'image_width': 276, 'image_height': 480, 'file_md5': '4f78689d4dcb8fcd2a555f88f0b001b3'},
    {'file_name': '74ba0552-b8ef-11e8-9f30-0242ac112a12.mp4', 'file_pic': 'http://dev-im-sdk.phh4.com/other/910d56060bc9f184afe31b02ba8a5ca6.png', 'file_size': 2320304, 'file_uri': 'http://dev-im-sdk.phh4.com/other/21422c88c53c5cc89eaec139412400de.mp4', 'file_suffix': 'mp4', 'file_duration': 21, 'image_width': 480, 'image_height': 848, 'file_md5': '21422c88c53c5cc89eaec139412400de'},
    {'file_name': '2fac220c-60fa-11e9-bc98-0a580a4b83d9.mp4', 'file_pic': 'http://dev-im-sdk.phh4.com/other/5b35a81cae9b0a37dbd27d8d27c22a14.png', 'file_size': 2728838, 'file_uri': 'http://dev-im-sdk.phh4.com/other/d8fa231fbe448e8cb20e75c545e8cec4.mp4', 'file_suffix': 'mp4', 'file_duration': 39, 'image_width': 480, 'image_height': 480, 'file_md5': 'd8fa231fbe448e8cb20e75c545e8cec4'},
    {'file_name': 'v3_1c11fb00-8741-11e9-a1a8-0a580a45cfd0.mp4', 'file_pic': 'http://dev-im-sdk.phh4.com/other/3615ca7ead6801a7c77bb4383eac1431.png', 'file_size': 5928087, 'file_uri': 'http://dev-im-sdk.phh4.com/other/2ddb594b604d92ccc572b76a10f74002.mp4', 'file_suffix': 'mp4', 'file_duration': 55, 'image_width': 408, 'image_height': 720, 'file_md5': '2ddb594b604d92ccc572b76a10f74002'},
    {'file_name': '0979a462-0d1e-11ea-93d3-ce8170e729ce.mp4', 'file_pic': 'http://dev-im-sdk.phh4.com/other/a1e01aa6cbdd9a5175ffa2e56a53bff3.png', 'file_size': 13452450, 'file_uri': 'http://dev-im-sdk.phh4.com/other/9c0a5ea61faffff40840909dfffc08bd.mp4', 'file_suffix': 'mp4', 'file_duration': 202, 'image_width': 640, 'image_height': 360, 'file_md5': '9c0a5ea61faffff40840909dfffc08bd'},
    {'file_name': 'ac87216fbd41731afe62bf00daa3988d.mp4', 'file_pic': 'http://dev-im-sdk.phh4.com/other/d32e72a47e41a6826a69b93c8c621909.png', 'file_size': 3732950, 'file_uri': 'http://dev-im-sdk.phh4.com/other/2802d0a680f4b3a758a090cf0211665e.mp4', 'file_suffix': 'mp4', 'file_duration': 15, 'image_width': 720, 'image_height': 1280, 'file_md5': '2802d0a680f4b3a758a090cf0211665e'}
]


LOCATION_INFO = [
    {'latitude': 22.535839, 'longitude': 113.953115, 'address': '广东省深圳市南山区科技园高新南六道10号', 'pic_url': 'http://mgim-sdk.zhuanxin.com/other/fd2365ade4492cdc0695c1c8db2f5ba0.jpg', 'name': '朗科大厦'},
    {'latitude': 22.519731, 'longitude': 113.93033, 'address': '广东省深圳市南山区海德二道288号', 'pic_url': 'http://dev-im-sdk.phh4.com/other/f304df5d491e61fcdae895b4b0b2509e.jpg', 'name': '茂业·时代广场'},
    {'latitude': 22.535146, 'longitude': 113.936713, 'address': '广东省深圳市南山区深大北路', 'pic_url': 'http://dev-im-sdk.phh4.com/other/0e5f3d79192525392affe43ae9664b17.jpg', 'name': '深圳大学科技楼'}
]


EMOJI_INFO = [
    # {'emoji_id': 'waiwai-4', 'emoji_group': 'waiwai', 'emoji_url': 'http://dev-im-sdk.phh4.com/imoji/b7b6812e484c4f6a1de2c2a61e738f94.jpg', 'width': 319, 'height': 274},
    # {'emoji_id': 'ggy-5', 'emoji_group': 'guaiguaiyang1', 'emoji_url': 'http://dev-im-sdk.phh4.com/emoji/ggy/ggy-5.gif', 'width': 300, 'height': 300},
    # {'emoji_id': 'ggy-7', 'emoji_group': 'guaiguaiyang1', 'emoji_url': 'http://dev-im-sdk.phh4.com/emoji/ggy/ggy-7.jpg', 'width': 300, 'height': 300},
    # {'emoji_id': 'ggy-3', 'emoji_group': 'guaiguaiyang1', 'emoji_url': 'http://dev-im-sdk.phh4.com/emoji/ggy/ggy-3.gif', 'width': 300, 'height': 300},
    # {'emoji_id': 'ggy-2', 'emoji_group': 'guaiguaiyang1', 'emoji_url': 'http://dev-im-sdk.phh4.com/emoji/ggy/ggy-3.gif', 'width': 300, 'height': 300},
    # {'emoji_id': 'ggy-8', 'emoji_group': 'guaiguaiyang1', 'emoji_url': 'http://dev-im-sdk.phh4.com/emoji/ggy/ggy-8.gif', 'width': 300, 'height': 300},
    # {'emoji_id': 'ggy-1', 'emoji_group': 'guaiguaiyang1', 'emoji_url': 'http://dev-im-sdk.phh4.com/emoji/ggy/ggy-1.jpg', 'width': 300, 'height': 300},
    # {'emoji_id': 'ggy-6', 'emoji_group': 'guaiguaiyang1', 'emoji_url': 'http://dev-im-sdk.phh4.com/emoji/ggy/ggy-6.gif', 'width': 300, 'height': 300},
    # {'emoji_id': 'waiwai-1', 'emoji_group': 'waiwai', 'emoji_url': 'http://dev-im-sdk.phh4.com/imoji/f660a54a55227c154e9694caa8aece57.jpg', 'width': 240, 'height': 240},
    # {'emoji_id': 'waiwai-6', 'emoji_group': 'waiwai', 'emoji_url': 'http://dev-im-sdk.phh4.com/imoji/a5ca61f015f84c3a7a75237fbf6f0613.jpg', 'width': 240, 'height': 240},
    # {'emoji_id': 'waiwai-5', 'emoji_group': 'waiwai', 'emoji_url': 'http://dev-im-sdk.phh4.com/imoji/b76391faab6d0e3db10ec2212c3bd994.gif', 'width': 300, 'height': 300},
    # {'emoji_id': 'waiwai-4', 'emoji_group': 'waiwai', 'emoji_url': 'http://dev-im-sdk.phh4.com/imoji/b7b6812e484c4f6a1de2c2a61e738f94.jpg', 'width': 319, 'height': 274},
    # {'emoji_id': 'waiwai-7', 'emoji_group': 'waiwai', 'emoji_url': 'http://dev-im-sdk.phh4.com/imoji/4f808293e68383d40418054b2bbb7479.jpg', 'width': 300, 'height': 300},
    # {'emoji_id': 'waiwai-8', 'emoji_group': 'waiwai', 'emoji_url': 'http://dev-im-sdk.phh4.com/imoji/4d40464e5f98aec5f7a1521502337670.jpg', 'width': 300, 'height': 300},
    # {'emoji_id': 'waiwai-2', 'emoji_group': 'waiwai', 'emoji_url': 'http://dev-im-sdk.phh4.com/imoji/ff5e3bf48cdb3fcb84c418d1711a5df5.gif', 'width': 300, 'height': 300},
    # {'emoji_id': 'waiwai-3', 'emoji_group': 'waiwai', 'emoji_url': 'http://dev-im-sdk.phh4.com/imoji/c95efd9d38fd370b13467c0d2b89fc95.gif', 'width': 300, 'height': 300},
    {
        "emoji_id": "231",
        "emoji_group": "28",
        "emoji_url": "http://dev-im-sdk.phh4.com/emoji/20210409/76aaceb010c31bcb224038d09616b283/17喷鼻涕.gif",
        "width": 120,
        "height": 120
    },
    {
        "emoji_id": "238",
        "emoji_group": "28",
        "emoji_url": "http://dev-im-sdk.phh4.com/emoji/20210409/76aaceb010c31bcb224038d09616b283/24委屈.gif",
        "width": 120,
        "height": 120
    },
    {
        "emoji_id": "182",
        "emoji_group": "26",
        "emoji_url": "http://dev-im-sdk.phh4.com/emoji/20210409/b061e99232769d2d8c2eac140b4c703d/1指.gif",
        "width": 120,
        "height": 120
    },
    {
        "emoji_id": "190",
        "emoji_group": "26",
        "emoji_url": "http://dev-im-sdk.phh4.com/emoji/20210409/b061e99232769d2d8c2eac140b4c703d/2踢.gif",
        "width": 120,
        "height": 120
    },
    {
        "emoji_id": "192",
        "emoji_group": "26",
        "emoji_url": "http://dev-im-sdk.phh4.com/emoji/20210409/b061e99232769d2d8c2eac140b4c703d/6闻手.gif",
        "width": 120,
        "height": 120
    },
    {
        "emoji_id": "237",
        "emoji_group": "28",
        "emoji_url": "http://dev-im-sdk.phh4.com/emoji/20210409/76aaceb010c31bcb224038d09616b283/23约吗.gif",
        "width": 120,
        "height": 120
    },
    {
        "emoji_id": "235",
        "emoji_group": "28",
        "emoji_url": "http://dev-im-sdk.phh4.com/emoji/20210409/76aaceb010c31bcb224038d09616b283/21装酷.gif",
        "width": 120,
        "height": 120
    },
    {
        "emoji_id": "223",
        "emoji_group": "28",
        "emoji_url": "http://dev-im-sdk.phh4.com/emoji/20210409/76aaceb010c31bcb224038d09616b283/09认错.gif",
        "width": 120,
        "height": 120
    },
    {
        "emoji_id": "222",
        "emoji_group": "28",
        "emoji_url": "http://dev-im-sdk.phh4.com/emoji/20210409/76aaceb010c31bcb224038d09616b283/08烦.gif",
        "width": 120,
        "height": 120
    },
    {
        "emoji_id": "206",
        "emoji_group": "27",
        "emoji_url": "http://dev-im-sdk.phh4.com/emoji/20210409/4ba65bdc2772798ee2d7d84eba38f066/09嗯嗯.gif",
        "width": 120,
        "height": 120
    },
    {
        "emoji_id": "204",
        "emoji_group": "27",
        "emoji_url": "http://dev-im-sdk.phh4.com/emoji/20210409/4ba65bdc2772798ee2d7d84eba38f066/07思考.gif",
        "width": 120,
        "height": 120
    },
    {
        "emoji_id": "209",
        "emoji_group": "27",
        "emoji_url": "http://dev-im-sdk.phh4.com/emoji/20210409/4ba65bdc2772798ee2d7d84eba38f066/12这么点.gif",
        "width": 120,
        "height": 120
    },
    {
        "emoji_id": "183",
        "emoji_group": "26",
        "emoji_url": "http://dev-im-sdk.phh4.com/emoji/20210409/b061e99232769d2d8c2eac140b4c703d/10蹲墙角.gif",
        "width": 120,
        "height": 120
    },
    {
        "emoji_id": "194",
        "emoji_group": "26",
        "emoji_url": "http://dev-im-sdk.phh4.com/emoji/20210409/b061e99232769d2d8c2eac140b4c703d/7摔手机.gif",
        "width": 120,
        "height": 120
    },
    {
        "emoji_id": "182",
        "emoji_group": "26",
        "emoji_url": "http://dev-im-sdk.phh4.com/emoji/20210409/b061e99232769d2d8c2eac140b4c703d/1指.gif",
        "width": 120,
        "height": 120
    },
    {
        "emoji_id": "184",
        "emoji_group": "26",
        "emoji_url": "http://dev-im-sdk.phh4.com/emoji/20210409/b061e99232769d2d8c2eac140b4c703d/11惊.gif",
        "width": 120,
        "height": 120
    }
]


def set_img_msg_file(pb):
    msg_pb = pb.msg_file
    _img_info = choice(IMG_INFO)
    for k, v in _img_info.items():
        setattr(msg_pb, k, v)


def set_msg_emoji(pb):
    emoji_pb = pb.msg_emoji
    _emoji_info = choice(EMOJI_INFO)
    for k, v in _emoji_info.items():
        setattr(emoji_pb, k, v)


def set_video_msg_file(pb):
    msg_pb = pb.msg_file
    _file_info = choice(VIDEO_INFO)
    for k, v in _file_info.items():
        setattr(msg_pb, k, v)
        
        
def set_msg_location(pb):
    location_pb = pb.msg_location
    _location_info = choice(LOCATION_INFO)
    for k, v in _location_info.items():
        setattr(location_pb, k, v)


def set_audio_msg_file(pb):
    msg_pb = pb.msg_file
    _file_info = choice(AUDIO_INFO)
    for k, v in _file_info.items():
        setattr(msg_pb, k, v)


def set_file_msg_file(pb):
    msg_pb = pb.msg_file
    _file_info = choice(FILE_INFO)
    for k, v in _file_info.items():
        setattr(msg_pb, k, v)


def get_communication_message_by_single(msg_type, key, app_id, user_id, target_id, communication_id, content, other=None):
    """

    :param msg_type:
    :param key:
    :param app_id:
    :param user_id:
    :param target_id:
    :param communication_id:
    :param content:
    :param other:用户信息，如头像链接，id，昵称等
    :return:
    """
    _time_stamp = get_time_stamp()

    body = {
        'app_id': app_id,
        'from_user_id': user_id,
        'to_user_id': target_id,
        'communication_id': communication_id,
        'send_time': _time_stamp,
        'communication_type': CommunicationType.SINGLE_PERSON.value,
        'message_type': msg_type,
        'message_main_type': 1,
        'tag': device_id_gen()
    }

    if other is not None:
        body['other'] = other

    pb = MessageProBuf_pb2.CommunicationMessageProto()
    if msg_type == MessageType.TEXT.value:       # 文本
        body['content'] = content
    elif msg_type == MessageType.EMOJI.value:     # 动图表情
        set_msg_emoji(pb)
    elif msg_type == MessageType.FILE.value:     # 文件
        body['setting'] = '{"read":false,"arrived":false,"read_delete":false,"dont_disturb":false}'
        set_file_msg_file(pb)
    elif msg_type == MessageType.IMAGE.value:     # 图片
        set_img_msg_file(pb)
    elif msg_type == MessageType.AUDIO.value:     # 语音消息
        set_audio_msg_file(pb)
    elif msg_type == MessageType.VIDEO.value:     # 视频
        body['setting'] = '{"read":false,"arrived":false,"read_delete":false,"dont_disturb":false}'
        set_video_msg_file(pb)
    elif msg_type == MessageType.ADDRESS.value:     # 位置消息
        set_msg_location(pb)
        body['content'] = pb.msg_location.address
    message = create_message(pb, CommandType.COMMAND_SEND_MSG_REQ.value, key, 'CommunicationMessageProto', body)
    return message


def get_communication_message_by_group(msg_type, key, app_id, user_id, communication_id, content, other=None):
    """
    生成群聊消息
    """
    body = {
        'app_id': app_id,
        'from_user_id': user_id,
        'communication_id': communication_id,
        'send_time': get_time_stamp(),
        'communication_type': 2,
        'message_type': msg_type,
        'message_main_type': 1,
        'tag': device_id_gen()
    }

    if other is not None:
        body['other'] = other
    pb = MessageProBuf_pb2.CommunicationMessageProto()
    if msg_type == MessageType.TEXT.value:      # 文本
        body['content'] = content
    elif msg_type == MessageType.EMOJI.value:    # 动图表情
        set_msg_emoji(pb)
    elif msg_type == MessageType.FILE.value:    # 文件
        set_file_msg_file(pb)
        body['setting'] = '{"read":false,"arrived":false,"read_delete":false,"dont_disturb":false}'
    elif msg_type == MessageType.IMAGE.value:    # 图片
        set_img_msg_file(pb)
        body['setting'] = '{"read":false,"arrived":false,"read_delete":false,"dont_disturb":false}'
    elif msg_type == MessageType.AUDIO.value:    # 语音消息
        body['setting'] = '{"read":false,"arrived":false}'
        set_audio_msg_file(pb)
    elif msg_type == MessageType.VIDEO.value:     # 视频
        body['setting'] = '{"read":false,"arrived":false,"read_delete":false,"dont_disturb":false}'
        set_video_msg_file(pb)
    elif msg_type == MessageType.ADDRESS.value:     # 位置消息
        set_msg_location(pb)
        body['content'] = pb.msg_location.address
    message = create_message(pb, CommandType.COMMAND_SEND_MSG_REQ.value, key, 'CommunicationMessageProto', body)
    return message


def get_communication_message_by_chat_room(msg_type, key, app_id, user_id, communication_id, content=None, other=None):
    """
    生成聊天室消息
    """
    body = {
        'app_id': app_id,
        'from_user_id': user_id,
        'communication_id': communication_id,
        'send_time': get_time_stamp(),
        'communication_type': 3,
        'message_type': msg_type,
        'message_main_type': 1,
        'tag': device_id_gen()
    }

    if other is not None:
        body['other'] = other
    pb = MessageProBuf_pb2.CommunicationMessageProto()
    if msg_type == MessageType.TEXT.value:      # 文本
        body['content'] = content
    elif msg_type == MessageType.EMOJI.value:    # 动图表情
        set_msg_emoji(pb)
    elif msg_type == MessageType.FILE.value:    # 文件
        set_file_msg_file(pb)
        body['setting'] = '{"read":false,"arrived":false,"read_delete":false,"dont_disturb":false}'
    elif msg_type == MessageType.IMAGE.value:    # 图片
        set_img_msg_file(pb)
        body['setting'] = '{"read":false,"arrived":false,"read_delete":false,"dont_disturb":false}'
    elif msg_type == MessageType.AUDIO.value:    # 语音消息
        body['setting'] = '{"read":false,"arrived":false}'
        set_audio_msg_file(pb)
    elif msg_type == MessageType.VIDEO.value:     # 视频
        body['setting'] = '{"read":false,"arrived":false,"read_delete":false,"dont_disturb":false}'
        set_video_msg_file(pb)
    elif msg_type == MessageType.ADDRESS.value:     # 位置消息
        set_msg_location(pb)
        body['content'] = pb.msg_location.address
    message = create_message(pb, CommandType.COMMAND_SEND_MSG_REQ.value, key, 'CommunicationMessageProto', body)
    return message


def get_heartbeat_message(key, from_id=None, device_type=None, manufacturer=None, last_msg_sequence_id=0, last_msg_receive_time='', version=None, interface_up_time=None):
    # 发送请求消息响应只要三个参数device_type, last_msg_sequence_id, last_msg_receive_time 就可以
    """
    string from_id = 1;                         //发送人id
    int32 device_type = 2;                      //设备类型  1：移动端，2：WEB端，3：PC端
    int32 manufacturer = 3;                		//设备厂商 0=谷歌;1=苹果; 2=华为;3=小米;4=OPPO;5=魅族;6=VIVO;7=其他;
    int64 last_msg_sequence_id = 4;             //序列id
    int64 last_msg_receive_time = 5;            //最大时间
    string version = 6;                         //版本号
    int64 interface_up_time = 7;                //客户端接口升级时间戳
    """
    body = {
        'from_id': from_id,
        'device_type': device_type,
        'manufacturer': manufacturer,
        'last_msg_sequence_id': last_msg_sequence_id,
        'last_msg_receive_time': last_msg_receive_time,
        'version': version,
        'interface_up_time': interface_up_time
    }
    # print(body)
    pb = MessageProBuf_pb2.HeartBeatMsg()
    command_key = CommandType.COMMAND_PULL_MSG_REQ.value
    message = create_message(pb, command_key, key, 'HeartBeatMsg', body)
    return message
    

def decode_communication_message(proto_name, proto_body):
    """
    聊天消息解码
    """
    proto_body = aes_decrypt(proto_body)
    message = decode_message(proto_name, proto_body)
    return message


def get_msg_ack_message(key, app_id, from_user_id, to_user_id, communication_id, message_id, tag, last_receive_msg_no=None):
    """
    获取ack msg
    :param key:
    :param app_id:
    :param from_user_id:
    :param to_user_id:
    :param communication_id:
    :param message_id:
    :param tag:
    :param last_receive_msg_no:群消息的id序号,单聊不用此参数
    :return: bin data
    """
    pb = MessageProBuf_pb2.MessageAckProto()
    body = {
        'message_id': message_id,
        'app_id': app_id,
        'msg_from_user_id': from_user_id,
        'msg_to_user_id': to_user_id,
        'communication_id': communication_id,
        'tag': tag
    }
    command_key = CommandType.COMMAND_MESSAGE_ACK.value
    if last_receive_msg_no:
        body['last_receive_msg_no'] = last_receive_msg_no	
        command_key = CommandType.COMMAND_MESSAGE_ACK.value
    message = create_message(pb, command_key, key, 'MessageAckProto', body)
    return message


def get_msg_read_message(key, app_id, from_user_id, to_user_id, communication_id, message_id, tag, last_receive_msg_no=None):
    """
    聊天消息解码
    """
    pb = MessageProBuf_pb2.MessageAckProto()
    body = {
        'message_id': message_id,
        'app_id': app_id,
        'msg_from_user_id': from_user_id,
        'msg_to_user_id': to_user_id,
        'communication_id': communication_id,
        'tag': tag
    }
    command_key = CommandType.COMMAND_MESSAGE_READ.value
    if last_receive_msg_no:
        body['last_receive_msg_no'] = last_receive_msg_no	
        command_key = CommandType.COMMAND_MESSAGE_READ.value
    message = create_message(pb, command_key, key, 'MessageAckProto', body)
    return message


def get_batch_msg_ack_message(key: str, app_id: str, from_user_id: str, to_user_id: str, communication_id: str, msg_id_list: List[str]) -> bytes:
    """
    批量消息已读回执
    :param key:
    :param app_id:
    :param from_user_id:
    :param to_user_id:
    :param communication_id:
    :param msg_id_list: 消息列表
    :return:
    """
    pb = MessageProBuf_pb2.BatchMessageAckProto()
    body = {
        'app_id': app_id,
        'communication_id': communication_id,
        'tag': device_id_gen()
    }
    for msg_id in msg_id_list:
        item = pb.items.add()  # 批量消息状态回执条目
        item.message_id = msg_id
        item.msg_from_user_id = from_user_id
        item.msg_to_user_id = to_user_id
    command_key = CommandType.COMMAND_MESSAGE_READ.value
    message = create_message(pb, command_key, key, 'BatchMessageAckProto', body)
    return message


def get_read_communication_sync_message(key: str, app_id: str, communication_id: str, communication_type: int):
    """
    多端设备的消息未读数同步
    :param key:
    :param app_id:
    :param communication_id:
    :param communication_type: 1: 单聊, 2: 群聊, 3: 聊天室
    :return:
    """
    pb = MessageProBuf_pb2.ReadCommunicationSyncProto()
    body = {
        'app_id': app_id,
        'communication_id': communication_id,
        'communication_type': communication_type
    }
    command_key = CommandType.COMMAND_COMMUNICATION_READ_SYNC
    message = create_message(pb, command_key, key, 'ReadCommunicationSyncProto', body)
    return message


if __name__ == '__main__':
    msg = b'\x00\x00\x01i\x03da89edb8276052c0a411d1fb32f051f5c#test_count;1234567890;1626091109918870db3fa5cca4e25baea5ac86ba83fa7\x12ReqBindUserChannel}\xc4\xa5;\x0c\xfc\x7f\xa9\x81g>)\x81\x01\xe1\x16E\xe8\xa9\t\x16N\x14\x97m\x91n\x1f\x12\xb1\xe0\x8a\xfe<>\x88Nh\xed\xe9w,\xee%\x9d4\xbc\x7f\x06\xb2\xe1\x17\xac10f\xd6\x0es\xe7N\xfbm\n)0QKI\x17\xf6\x1d\ne\\\xd9S\x19(\xff\x04k\xb0A\xb7K(o\xfd\xcc\xb3\x18\xfaZ3\xa0\xb77\x1eOV\x91\xdbMH\xc9\x86U\x14zW\x0b\xc9\xbb\x84\xa9\x0e\xa1@\xba\xdbEJg\xa0\x97\x87\'\xbfQ*\xeaM\\\x81\xae\x81\x88\x80Uq\xdf\xf0\xab\xc0\xc1$\x9c\xf8\xb3\xe3\xcd.\xc5\x1b\xff\xdeC\xa0>\xdb\xe3\x1eG\xe8\x04o?O\xb8ky\xf1ed\xea\xb2\x0eg\xe9K]l\xfc\xe7\xf81F\x88\rws&\x92\xf8\xa3A\xc8\xc5\x81\xa1,:\xf5\xa4" P\xabYe\x94"\\\xb3\xbdm\xde+_bx\x95\xec}\x18\xe3\x7f\xe2\x12.B.\xfe\x7f5I&\x9b\xd1'
    r = decode_all_message(msg)
    print(r)
