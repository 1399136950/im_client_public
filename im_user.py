# coding = utf-8

import asyncio
import os
import time
import json
from threading import Thread
from collections import defaultdict, deque
from random import sample, randint, choice
import uuid
from PIL import Image, ImageTk
from io import BytesIO
from queue import Queue

from sdk_api import *
from demo_api import *
from utils.generator import device_info_gen, device_id_gen
from message import get_bind_message
from message import get_communication_message_by_group
from message import get_communication_message_by_single
from message import decode_communication_message
from message import get_msg_ack_message
from message import get_msg_read_message
from message import get_heartbeat_message
from message import get_batch_msg_ack_message
from message import get_communication_message_by_chat_room
from message import get_read_communication_sync_message
from utils.img2ico import img_to_tk_img

from utils.packer import msg_unpack_length_and_command
import message_type
from message_price import MESSAGE_PRICE


MESSAGE_TYPE = message_type.MESSAGE_TYPE


def get_reply_msg(msg):
    reply_msg = msg.replace('吗', '')
    reply_msg = reply_msg.replace('是不是', '是')
    reply_msg = reply_msg.replace('?', '!')
    reply_msg = reply_msg.replace('我', '你')
    return reply_msg


def get_src_body(buffer):
    buffer = buffer[5:]
    key_len = buffer[0]
    key = buffer[1: 1 + key_len]
    proto_name_len = buffer[1 + key_len]
    proto_name = buffer[2 + key_len: 2 + key_len + proto_name_len]
    proto_body = buffer[2 + key_len + proto_name_len:]
    return proto_name, proto_body


class GUIIMUser:

    DEBUG = True

    INFO = True

    def __init__(self, user_info: dict, chat_room_tree_dict=None, tree=None):
        self.address = None    # 初始化空的im服务器地址
        self.exit = False   # 退出flag
        self.user_info = user_info  # 用户信息
        self.token = None
        self.phone = user_info['phone'] if 'phone' in user_info else None
        self.device_info = device_info_gen()  # 初始化设备信息

        self.chat_room_tree_dict = chat_room_tree_dict
        self.tree = tree    # gui线程的组件, 用于动态显示消息
        self.start = False  # start flag
        self.header_beat_time = 2  # 心跳间隔
        self.communication_info = defaultdict(dict)    # 存放会话信息
        self.communication_msg = defaultdict(deque)     # 存放会话消息,comm_id => msg_list []
        self.chat_room_msg = defaultdict(dict)
        self.commid_tree_index = dict()     # 存放comm id对应tree的下标
        self.last_msg_sequence_id = 0
        self.last_msg_receive_time = ''
        self.commid_to_user_id_dict = {}  # 单聊会话id对应的user_id
        self.already_destroy_comm_id_set = set()    # 存储已经被销毁(解散)的会话ID

        self.r, self.w = None, None
        self.is_login = False
        self.last_send_heartbeat_time = 0
        self.last_send_seq_id = -1

        self.lock = asyncio.Lock()
        if tree is not None:
            Thread(target=self.add_gui_thread).start()
        self.err_msg = None
        self.user_id_to_nickname = {}   # 用户id对应的详细信息
        self.friend_id_list = []        # 存放好友id的列表
        self.user_detail = {}           # 存放用户信息
        self.group_info = {}            # 存放群聊信息
        self.chat_room_info = {}        # 存放聊天室详情
        self.friend_head_img = {}       # 存放好友头像
        self.group_head_img = {}        # 存放群头像
        self.chat_room_head_img = {}    # 存放聊天室头像
        self.group_id_list = []         # 存放群id列表
        self.head_photo_bytes = b''     # 存放自己的头像 (二进制)
        self.tk_img_dict = {}           # 存放tk_img对象
        self.send_msg_details = {
            'communication_type': {},
            'message_type': {},
            'communication_id': {}
        }  # 用来统计发送消息详情
        self.cost = []  # 统计消息延时等

    def debug(self, *args, **kw):
        if self.DEBUG:
            print('[{}] [new_im_user.py]'.format(time.strftime('%Y-%m-%d %H:%M:%S')), *args, **kw)

    def enter_chat_room(self, chat_room_id):
        self.debug('[enter_chat_room]')
        res = chat_room_enter(self.token, chat_room_id)
        return res

    def exit_chat_room(self, chat_room_id):
        self.debug('[exit_chat_room]')
        del self.chat_room_msg[chat_room_id]
        res = chat_room_exit(self.token, chat_room_id)
        return res

    def info(self, *args, **kw):
        if self.INFO:
            print('[{}] [new_im_user.py]'.format(time.strftime('%Y-%m-%d %H:%M:%S')), *args, **kw)

    def login_demo(self):
        _res = login(self.phone, self.user_info['pwd'])
        self.debug('[login_demo]', _res)
        if _res['code'] != '0':
            raise Exception('DEMO服务器登陆失败: ' + str(_res))
        self.user_id = _res['data']['zxUserId']
        self.user_info['user_id'] = _res['data']['zxUserId']
        self.login_demo_res = _res['data']
        self.demo_token = _res['data']['accessToken']
        self.key = ';'.join([self.user_info['app_id'], self.user_info['user_id'], self.device_info['device_id']])
        self.last_msg_seq_json_path = 'runtime/' + self.user_info['user_id'] + '.json'

    def send_redpacket(self, amount, conversation_id, conversation_type, count, to_user_ids, redpacket_type):
        try:
            front_cover = None
            tag = device_id_gen()
            # tradePassword = '123456'
            trade_password = ''  # 支付密码md5加密
            wishes = time.strftime('%Y-%m-%d %H:%M:%S')
            # wishes = 'amount:{},count:{},type:{}'.format(amount, count, type)
            _res = send_redpacket(self.demo_token, amount, conversation_id, conversation_type, count, front_cover, tag, to_user_ids, trade_password, redpacket_type, wishes)
        except Exception as _e:
            _res = _e
        return _res

    def login(self) -> dict:
        """
        主要是给gui线程调用， 测试当前用户能否接口登录，如果有异常就避免开启一个事件循环
        """
        try:
            _r = login_by_sdk(self.user_info, self.device_info, self.login_demo_res['zxSdkLoginToken'])
            # pprint.pprint(_r)
        except Exception as _e:
            self.debug('[login]', _e)
            raise Exception('服务器登陆失败: '+str(_e))
        else:
            self.debug('[login]', _r)
            if 'code' in _r and _r['code'] == '0':
                self.token = _r['data']['access_token']
                self.address = (_r['data']['im_module']['server_addr'], _r['data']['im_module']['socket_port'])
                self.info('[login]', 'self.address: ', self.address)
                self.autoAcceptFriendInvitation = _r['data']['im_module']['user_setting']['autoAcceptFriendInvitation']
                self.autoAcceptGroupInvitation = _r['data']['im_module']['user_setting']['autoAcceptGroupInvitation']
                return self.token
            else:
                raise Exception('SDK服务器登陆失败: ' + str(_r))

    def login_by_sdk(self):
        """
        给单独sdk登录使用
        :return:
        """
        self.key = ';'.join([self.user_info['app_id'], self.user_info['user_id'], self.device_info['device_id']])
        self.user_id = self.user_info['user_id']
        self.last_msg_seq_json_path = 'runtime/' + self.user_info['user_id'] + '.json'
        res = login_by_sdk_old(self.user_info, self.device_info)
        if 'code' in res and res['code'] == '0':
            self.token = res['data']['access_token']
            self.address = (res['data']['im_module']['server_addr'], res['data']['im_module']['socket_port'])
            self.info('[login_by_sdk]', 'self.address: ', self.address)
            self.autoAcceptFriendInvitation = res['data']['im_module']['user_setting']['autoAcceptFriendInvitation']
            self.autoAcceptGroupInvitation = res['data']['im_module']['user_setting']['autoAcceptGroupInvitation']
            return
        raise Exception(res)

    def update_group_head_photo(self, group_id):
        if self.group_info[group_id]['avatar'] is not None and self.group_info[group_id]['avatar'].startswith('http'):
            _r = requests.get(self.group_info[group_id]['avatar'])

            self.info('[update_group_head_photo]', _r, len(_r.content))
            if _r.status_code == 200:
                self.group_head_img[group_id] = _r.content

    def update_user_head_photo(self):
        """
        更新当前用户信息和头像
        :return:
        """
        self.debug('[update_user_head_photo]')
        _res = self.get_user_detail()
        if _res['data']['avatar'] is not None and _res['data']['avatar'] != '':
            try:
                _r = requests.get(_res['data']['avatar'])
            except Exception as _e:
                self.info('[update_user_head_photo] [error]', _e)
            else:
                if _r.status_code == 200:
                    self.head_photo_bytes = _r.content

    def change_group_owner(self, group_id, new_owner_id):   # 更改群主
        _r = change_group_owner(self.token, group_id, new_owner_id)
        if _r['code'] == '0':
            pass
            self.group_info[group_id]['ownerId'] = new_owner_id
        return _r

    async def build_connection(self):
        try:
            self.r, self.w = await asyncio.open_connection(*self.address)
            # self.debug('[build_connection]', self.r, self.w)
        except Exception as _e:
            self.err_msg = str(_e)
            self.slogout()
            raise Exception('connect host error') from _e
        else:
            self.debug('[build_connection] self.token: ', self.token)
            if not self.token:
                return
            msg = get_bind_message(self.token, self.key, self.user_info, self.device_info)
            self.debug('[build_connection] bind_message: ', msg)
            self.start = True
            # await self.write_queue.put(msg)
            self.w.write(msg)
            await self.w.drain()
            while not self.is_login:
                self.debug('[build_connection]', 'await')
                await asyncio.sleep(0.2)
            # 拉取群列表
            self.get_group_list()
            # 拉取好友列表
            self.update_friend_list()
            # 拉取离线消息
            # await self.get_offline_msg()
            try:
                await self.get_sync_msg()
            except Exception as _e:
                print(_e)
            Thread(target=self.get_all_friend_head_img).start()
            Thread(target=self.get_all_group_head_img).start()

    def update_friend_list(self):
        self.debug('[update_friend_list]')
        _r = self.get_friend_list()

        self.debug('[update_friend_list]', _r)

        if _r['code'] == '0':
            self.friend_id_list = []

            for _ in _r['data']:
                if _['userId'] in self.user_detail:
                    self.user_detail[_['userId']].update(_)
                else:
                    self.user_detail[_['userId']] = _
                self.user_detail[_['userId']]['last_update_time'] = time.time()
                self.friend_id_list.append(_['userId'])
                self.commid_to_user_id_dict[_['conversationId']] = _['userId']   # 更新会话id对应的好友id
        else:
            self.debug('[update_friend_list]', _r)

    def clean_msg(self):
        self.communication_info = defaultdict(dict)    # 存放会话信息
        self.communication_msg = defaultdict(deque)     # 存放会话消息,comm_id => msg_list []
        self.commid_tree_index = dict()

    def add_gui_thread(self):
        if self.tree is None:   # 没有传Treeview组件则直接返回不进行下一步
            return
        while not self.exit:
            _comm_id_list = list(self.communication_info.keys())
            for _comm_id in _comm_id_list:
                _info = self.communication_info[_comm_id]
                if _comm_id in self.commid_tree_index:
                    _item = self.commid_tree_index[_comm_id]
                else:
                    continue
                # col = col = ['comm_name', 'comm_id', 'comm_type', 'time', 'msg_count', 'content']
                _last_msg = _info['last_msg']
                tree_msg_count = self.tree.item(_item, 'values')[4]
                tree_last_msg_id = self.tree.item(_item, 'values')[-1]  # msg_id没有在界面显示，隐藏
                communication_type = self.tree.item(_item, 'values')[2]
                if 'messageType' in _last_msg:  # 离线
                    if tree_last_msg_id == _last_msg['messageId'] and tree_msg_count == _info['msg_count']:
                        continue
                    else:
                        self.tree.set(_item, column='content', value=_last_msg['content'] if _last_msg['messageType'] == 1 else '[{}]'.format(MESSAGE_TYPE[_last_msg['messageType']]))  # 设置列'2'的值为'test'
                        if _last_msg['communicationType'] == 2:
                            self.tree.set(_item, column='comm_name', value=self.get_group_name(_comm_id))
                        else:
                            if _last_msg['communicationType'] == 1 and _last_msg['fromUserId'] != self.user_id:
                                self.tree.set(_item, column='comm_name', value=self.get_nickname(_last_msg['fromUserId']))
                        self.tree.set(_item, column='time', value=_info['last_time_stamp'])
                        self.tree.set(_item, column='msg_count', value=_info['msg_count'])
                else:   # 在线
                    if tree_last_msg_id == _last_msg['message_id']:
                        if tree_msg_count != _info['msg_count']:
                            self.tree.set(_item, column='msg_count', value=_info['msg_count'])
                    elif self.tree.index(_item) != 0:
                        before_values = list(self.tree.item(_item, 'values'))
                        if _last_msg['communication_type'] == 2:
                            before_values[0] = self.get_group_name(_comm_id)
                        else:
                            if _last_msg['communication_type'] == 1 and _last_msg['from_user_id'] != self.user_id:
                                before_values[0] = self.get_nickname(_last_msg['from_user_id'])
                        before_values[3] = _info['last_time_stamp']
                        before_values[4] = _info['msg_count']
                        before_values[5] = _last_msg['content'] if _last_msg['message_type'] == 1 else '[{}]'.format(MESSAGE_TYPE.get(_last_msg['message_type'], '未知消息类型'))
                        before_values[6] = _last_msg['message_id']
                        before_values = tuple(before_values)
                        self.tree.delete(_item)
                        if communication_type in {'1', '2'}:
                            if _comm_id not in self.tk_img_dict:
                                if communication_type == '2':
                                    head_img = self.group_head_img[_comm_id]
                                else:
                                    head_img = self.friend_head_img[_last_msg['from_user_id']] if _last_msg['from_user_id'] != self.user_id else self.friend_head_img[_last_msg['to_user_id']]
                                photo = Image.open(BytesIO(head_img))
                                photo = photo.resize((25, 25))
                                img0 = ImageTk.PhotoImage(photo)
                                self.tk_img_dict[_comm_id] = img0
                            new_item = self.tree.insert('', 0, image=self.tk_img_dict[_comm_id], values=before_values)
                        else:
                            new_item = self.tree.insert('', 0, values=before_values)
                        self.commid_tree_index[_comm_id] = new_item
                    else:
                        self.tree.set(_item, column='content', value=_last_msg['content'] if _last_msg['message_type'] == 1 else '[{}]'.format(MESSAGE_TYPE.get(_last_msg['message_type'], '未知消息类型')))  # 设置列'2'的值为'test'
                        if _last_msg['communication_type'] == 2:
                            self.tree.set(_item, column='comm_name', value=self.get_group_name(_comm_id))
                        else:
                            if _last_msg['communication_type'] == 1 and _last_msg['from_user_id'] != self.user_id:
                                self.tree.set(_item, column='comm_name', value=self.get_nickname(_last_msg['from_user_id']))
                        self.tree.set(_item, column='time', value=_info['last_time_stamp'])
                        self.tree.set(_item, column='msg_count', value=_info['msg_count'])
                        self.tree.set(_item, column='msg_id', value=_last_msg['message_id'])
            time.sleep(2)
        self.debug('[add_gui_thread] exit')

    async def logout(self):
        # await self.write_queue.put(None)
        self.exit = True

    def save_last_seq_id_and_timestamp(self):
        """将最后的消息id和消息时间戳保存到文件"""
        if os.path.exists(self.last_msg_seq_json_path):
            with open(self.last_msg_seq_json_path, 'r') as fd:
                data = json.load(fd)
        else:
            data = {}
        # 记录最后心跳消息id和时间戳
        if self.last_msg_sequence_id > 0 and self.last_msg_receive_time:
            data['last_msg_sequence_id'] = self.last_msg_sequence_id
            data['last_msg_receive_time'] = self.last_msg_receive_time

        # 记录每一个会话的最后消息id
        if 'communication_last_id' not in data:
            data['communication_last_id'] = {}

        for communication_id in self.communication_info:

            communication_last_msg = self.communication_info[communication_id]['last_msg']
            data['communication_last_id'][communication_id] = communication_last_msg['message_id'] if 'message_id' in communication_last_msg else communication_last_msg['messageId']
            if type(data['communication_last_id'][communication_id]) == str:
                data['communication_last_id'][communication_id] = int(data['communication_last_id'][communication_id])

        # 已经被解散的会话不需要存储
        data['communication_last_id'] = {communication_id: data['communication_last_id'][communication_id] for communication_id in data['communication_last_id'] if communication_id not in self.already_destroy_comm_id_set}

        self.debug('[save_last_seq_id_and_timestamp]', data)
        with open(self.last_msg_seq_json_path, 'w') as fd:
            json.dump(data, fd, indent=4)

    def slogout(self):
        # await self.write_queue.put(None)
        self.exit = True
        # self.q.put(None)
        self.debug('[slogout] close socket')
        # if self.w:
        #     self.w.close()
        # self.r.close()

    async def send_batch_msg_ack_message(self, from_user_id: str, to_user_id: str, communication_id: str, msg_id_list: list):
        """
        批量发送消息已读回执
        :param from_user_id:
        :param to_user_id:
        :param communication_id:
        :param msg_id_list: 消息id列表，该列表中的消息都是发送从from_user_id发出
        :return:
        """
        self.debug('[send_batch_msg_ack_message]')
        batch_msg_ack_message = get_batch_msg_ack_message(self.key, self.user_info['app_id'], from_user_id, to_user_id, communication_id, msg_id_list)
        self.w.write(batch_msg_ack_message)
        await self.w.drain()

    async def send_custom_msg(self, to_id, comm_id, comm_type, sub_msg_type, count, sleep_time):
        """
        发送自定义消息
        :param to_id:
        :param comm_id:
        :param comm_type:
        :param sub_msg_type: 子消息类型: 名片-card, 合并转发-merge
        :param count: 发送数量
        :param sleep_time: sleep间隔
        """
        msg_type = 9
        await asyncio.sleep(randint(1, 10) / 10)
        if type(comm_type) == str:
            comm_type = int(comm_type)
        self.info('[send_custom_msg]', to_id, comm_id, comm_type, sub_msg_type, count, sleep_time)
        _s = time.time()

        other = json.loads(self.other)

        other['type'] = sub_msg_type

        for i in range(count):
            if sub_msg_type == 'card':
                friend_id = choice(self.friend_id_list)
                friend_detail = self.user_detail[friend_id]
                other['content'] = {
                    'phone': friend_detail['phone'],
                    'name': friend_detail['nickname'],
                    'userId': friend_id,
                    'avatar': friend_detail['avatar']
                }
            if comm_type == 1:
                msg = self.get_single_msg(msg_type, to_id, comm_id, None, other=json.dumps(other))
            elif comm_type == 2:
                msg = self.get_group_msg(msg_type, comm_id, None, other=json.dumps(other))
            elif comm_type == 3:
                msg = self.get_chat_room_msg(msg_type, comm_id, None, other=json.dumps(other))
                proto_name, encrypt_proto_body = get_src_body(msg)
                _msg = decode_communication_message(proto_name, encrypt_proto_body)
                self.chat_room_msg[comm_id][_msg['tag']] = _msg
            else:
                raise Exception('unknow comm_type {}'.format(comm_type))
            self.w.write(msg)
            await self.w.drain()
            await asyncio.sleep(sleep_time)
        _e = time.time()
        self.info('[send_custom_msg] cost: ', _e - _s)
        if comm_type in self.send_msg_details['communication_type']:
            self.send_msg_details['communication_type'][comm_type] += count
        else:
            self.send_msg_details['communication_type'][comm_type] = count

        if msg_type in self.send_msg_details['message_type']:
            self.send_msg_details['message_type'][msg_type] += count
        else:
            self.send_msg_details['message_type'][msg_type] = count

        if comm_id in self.send_msg_details['communication_id']:
            self.send_msg_details['communication_id'][comm_id] += count
        else:
            self.send_msg_details['communication_id'][comm_id] = count
        return comm_id, count

    async def send_chat_msg(self, to_id, comm_id, comm_type, msg_type, count, sleep_time, content_msg=None):
        """
        发送消息函数, 用来在gui线程中异步调用
        """
        await asyncio.sleep(randint(1, 10) / 10)
        if type(comm_type) == str:
            comm_type = int(comm_type)
        self.info('[send_chat_msg]', to_id, comm_id, comm_type, msg_type, count, sleep_time)
        flag = ''.join(sample('abcedfghijklmnopqrstuvwxyzABCEDFGHIJKLMNOPQRSTUVWXYZ0123456789', 6))
        _s = time.time()
        other = None
        if msg_type == -1:   # 阅后即焚
            msg_type = 1
            other = json.loads(self.other)
            other['burn'] = {"burnMsgType": "1", "isClicked": False}
            other = json.dumps(other)
        for i in range(count):
            if msg_type == 1:
                if content_msg is None:
                    _content_msg = '{}-{}-[{}] [{:>03}]'.format(comm_id, flag, time.strftime('%Y-%m-%d %H:%M:%S'), i)
                    # _content_msg = 'ly'
                else:
                    _content_msg = content_msg
            else:
                _content_msg = None
            if comm_type == 1:
                msg = self.get_single_msg(msg_type, to_id, comm_id, _content_msg, other=other)
            elif comm_type == 2:
                msg = self.get_group_msg(msg_type, comm_id, _content_msg, other=other)
            elif comm_type == 3:
                msg = self.get_chat_room_msg(msg_type, comm_id, _content_msg, other=other)
                proto_name, encrypt_proto_body = get_src_body(msg)
                _msg = decode_communication_message(proto_name, encrypt_proto_body)
                self.chat_room_msg[comm_id][_msg['tag']] = _msg
            else:
                raise Exception('unknow comm_type {}'.format(comm_type))
            self.w.write(msg)
            await self.w.drain()
            await asyncio.sleep(sleep_time)
        _e = time.time()
        self.info('[send_chat_msg] cost: ', _e - _s)
        if comm_type in self.send_msg_details['communication_type']:
            self.send_msg_details['communication_type'][comm_type] += count
        else:
            self.send_msg_details['communication_type'][comm_type] = count

        if msg_type in self.send_msg_details['message_type']:
            self.send_msg_details['message_type'][msg_type] += count
        else:
            self.send_msg_details['message_type'][msg_type] = count

        if comm_id in self.send_msg_details['communication_id']:
            self.send_msg_details['communication_id'][comm_id] += count
        else:
            self.send_msg_details['communication_id'][comm_id] = count
        return comm_id, count

    def clear_send_msg_details(self):
        self.send_msg_details = {
            'communication_type': {},
            'message_type': {},
            'communication_id': {}
        }

    def clean_communication_msg_count(self, communication_id):
        self.debug('[clean_communication_msg_count]')
        self.communication_info[communication_id]['msg_count'] = 0

    def del_friend(self, user_id: str) -> dict:
        """
        删除好好友
        :param user_id: 好友id
        :return: json
        """
        _res = del_friend(self.token, user_id)
        self.debug('[del_friend]', _res['code'])
        if _res['code'] == '0':
            try:
                self.friend_id_list.remove(user_id)
            except Exception as _e:
                self.debug('[del_friend]', _e)
        return _res

    def exit_group(self, comm_id: str) -> dict:
        """
        退出群聊
        :param comm_id: 群id
        :return: json
        """
        _res = exit_group(self.token, comm_id)
        self.debug('[exit_group]', _res['code'])
        if _res['code'] == '0':
            self.group_id_list.remove(comm_id)
        return _res

    def remove_group(self, comm_id: str) -> dict:
        """
        删除群聊(群主才能操作)
        :param comm_id: 群id
        :return: json
        """
        _res = remove_group(self.token, comm_id)
        self.debug('[remove_group]', _res['code'])
        # if _res['code'] == '0':
        #     self.group_id_list.remove(comm_id)
        return _res

    def add_friend(self, dst_id: str) -> dict:
        """
        添加好友
        :param dst_id: 好友id
        :return: json
        """
        _res = add_friend(self.token, dst_id)
        self.debug('[add_friend]', _res['code'])
        if 'data' in _res:
            if 'resourceType' in _res['data'] and _res['data']['resourceType'] == 2:
                self.update_friend_list()
        return _res

    def invite_user_to_group(self, group_id: str, user_id_list_str: str) -> dict:
        _res = invite_user_to_group(self.token, group_id, user_id_list_str, 'hello world')
        self.debug('[invite_user_to_group]', _res['code'])
        return _res

    def remove_chat_room(self, chat_room_id):
        self.debug('[remove_chat_room]')
        res = chat_room_remove(self.token, chat_room_id)
        return res

    def remove_group_member(self, group_id: str, user_id_list_str: str) -> dict:     # 群主或管理员踢出多个群组成员
        _res = remove_group_member(self.token, group_id, user_id_list_str)
        self.debug('[remove_group_member]', _res['code'])
        return _res

    def get_group_list(self) -> dict:
        """
        显示群聊, 返回给gui线程显示出来
        """
        self.debug('[get_group_list]')
        _e = None
        for i in range(5):
            try:
                _res = get_group_list(self.token)
            except Exception as _e:
                print(_e)
            else:
                self.group_id_list = []
                for _i in _res['data']:
                    group_id = _i['communicationId']
                    self.group_id_list.append(group_id)
                    if group_id not in self.group_info:
                        self.group_info[group_id] = _i
                    else:
                        self.group_info[group_id].update(_i)
                return _res
        raise Exception('get_group_list error') from _e

    def get_group_user_list(self, group_id: str) -> dict:
        _res = search_group_userlist(self.token, group_id)
        self.debug('[get_group_user_list]', _res['code'])
        return _res

    def get_group_black_list(self, group_id):
        _res = get_group_black_list(self.token, group_id)
        return _res

    def get_group_manager_list(self, group_id):
        _res = get_group_manager_list(self.token, group_id)
        return _res

    def get_group_mute_list(self, group_id):
        _res = get_group_mute_list(self.token, group_id)
        return _res

    def get_group_announcement(self, group_id):
        self.debug('[get_group_announcement]')
        _r = get_group_announcement(self.token, group_id)
        return _r

    def get_friend_list(self) -> dict:
        """
        显示好友, 返回给gui线程显示出来
        """
        _res = get_friend_list(self.token)
        self.debug('[get_friend_list]', _res['code'])
        return _res

    def get_group_name(self, group_id):
        if group_id not in self.group_info:
            _r = get_group_detail(self.token, group_id)
            self.debug('[get_group_name]', _r)
            self.group_info[group_id] = _r['data']
        return self.group_info[group_id]['name']

    def get_group_detail(self, group_id):
        _r = get_group_detail(self.token, group_id)
        self.debug('[get_group_detail]', _r, self.group_info[group_id])
        if group_id not in self.group_info or 'avatar' not in self.group_info[group_id] or _r['data']['avatar'] != self.group_info[group_id]['avatar']:
            self.group_info[group_id] = _r['data']
            self.update_group_head_photo(group_id)
        return _r

    def get_all_group_head_img(self):
        self.get_group_detail_by_multi(self.group_id_list)
        for group_id in self.group_id_list:
            try:
                group_info = self.group_info[group_id]
                resp = requests.get(group_info['avatar'])
                if resp.status_code == 200:
                    self.group_head_img[group_id] = resp.content
            except Exception as _e:
                pass

    def get_group_detail_by_multi(self, group_id_list: list):
        self.debug('[get_group_detail_by_multi]')
        dst_id_list = group_id_list[:]
        step = 100
        start = 0
        while 1:
            tmp = dst_id_list[start: start+step]
            if len(tmp) == 0:
                break
            start += step
            try:
                _res = get_group_detail_by_multi(self.token, tmp)
            except Exception as _e:
                self.debug('[get_group_detail_by_multi]', _e)
                raise Exception(_e)
            else:
                if 'code' in _res and _res['code'] == '0':
                    for group_info in _res['data']:
                        group_id = group_info['communicationId']
                        self.group_info[group_id] = group_info
                else:
                    self.debug('[get_group_detail_by_multi]', _res)
                    raise Exception(_res['code'])
        self.debug('[get_group_detail_by_multi] finished')

    def get_group_share_file_list(self, group_id, count=None, create_time=None):
        _res = group_share_files_list(self.token, group_id, count=count, create_time=create_time)
        # self.debug('[get_group_share_file_list]', _res)
        # for info in _res['data']['fileList']:
        #     self.debug('[get_group_share_file_list]', info)
        return _res

    def get_all_friend_head_img(self):
        self.get_user_detail_by_multi(self.friend_id_list)
        for friend_id in self.friend_id_list:
            try:
                # _r = get_user_detail(self.token, friend_id)
                # self.user_detail[friend_id] = _r['data']
                # self.user_detail[friend_id]['last_update_time'] = time.time()
                friend_info = self.user_detail[friend_id]
                resp = requests.get(friend_info['avatar'])
                if resp.status_code == 200:
                    self.friend_head_img[friend_id] = resp.content
            except Exception:
                pass

    def get_user_black_list(self):  # 獲取好友黑名单
        _r = get_user_black_list(self.token)
        return _r

    def get_nickname(self, user_id):
        # self.debug('[get_nickname]')
        if user_id not in self.user_detail:
            _r = self.get_user_detail(user_id)
        elif time.time() - self.user_detail[user_id]['last_update_time'] > 3600:
            _r = self.get_user_detail(user_id)
        return self.user_detail[user_id]['nickname']

    def get_friend_communication(self, user_id):
        return self.user_detail[user_id]['conversationId']

    def get_user_detail_by_multi(self, user_id_list):
        self.debug('[get_user_detail_by_multi]')
        dst_id_list = [i for i in user_id_list if i not in self.user_detail]
        step = 100
        start = 0
        while 1:
            tmp = dst_id_list[start: start+step]
            if len(tmp) == 0:
                break
            start += step
            try:
                _res = get_user_detail_by_multi(self.token, ','.join(tmp))
            except Exception as _e:
                print(_e)
                raise Exception(_e)
            else:
                if 'code' in _res and _res['code'] == '0':
                    for user_info in _res['data']:
                        # print(user_info)
                        user_id = user_info['userId']
                        self.user_detail[user_id] = user_info
                        self.user_detail[user_id]['last_update_time'] = time.time()
                else:
                    print(_res)
                    raise Exception(_res['code'])
        self.debug('[get_user_detail_by_multi] finished')

    def get_user_detail(self, user_id=None):
        """
        :param user_id:
        :return:
        """
        self.debug('[get_user_detail]', user_id)
        if user_id is None:
            user_id = self.user_info['user_id']
            _r = get_user_detail(self.token, user_id)
            _other = {
                "userinfo": {
                    'username': _r['data']['nickname'].encode('utf-8').decode('utf-8'),
                    'userId': self.user_info['user_id']
                }
            }
            if _r['data']['avatar'] is not None:
                _other['userinfo']['avatarUrl'] = _r['data']['avatar']
            self.other = json.dumps(_other, ensure_ascii=False)
            return _r
        else:
            _r = get_user_detail(self.token, user_id)
            self.debug('[get_user_detail]', _r)
            self.user_detail[user_id] = _r['data']
            self.user_detail[user_id]['last_update_time'] = time.time()
            return _r

    def get_chat_room_detail(self, chat_room_id):
        self.debug('[get_chat_room_detail]')
        res = chat_room_detail(self.token, chat_room_id)
        if res['code'] == '0':
            self.chat_room_info[chat_room_id] = res['data']
        return res

    def get_chat_room_info(self, chat_room_id):
        if chat_room_id not in self.chat_room_info:
            self.get_chat_room_detail(chat_room_id)
        return self.chat_room_info[chat_room_id]

    def get_chat_room_detail_multi(self, chat_room_ids):
        self.debug('[get_chat_room_detail_multi]')
        res = chat_room_detail_list(self.token, chat_room_ids)
        if res['code'] == '0':
            for chat_room_info in res['data']:
                chat_room_id = chat_room_info['communicationId']
                self.chat_room_info[chat_room_id] = res['data']

    def get_chat_room_head_photo_bytes_multi(self, chat_room_id_list):
        self.debug('[get_chat_room_head_photo_bytes_multi]')

        def work_thread(q):
            while q.qsize() > 0:
                _chat_room_id = q.get()
                self.get_chat_room_head_photo_bytes(_chat_room_id)

        q = Queue()
        for chat_room_id in chat_room_id_list:
            q.put(chat_room_id)

        threads = [Thread(target=work_thread, args=(q,)) for i in range(10)]
        [t.start() for t in threads]
        [t.join() for t in threads]

    def get_chat_room_head_photo_bytes(self, chat_room_id):
        self.debug('[get_chat_room_head_photo_bytes]')
        try:
            if chat_room_id not in self.chat_room_info:
                self.get_chat_room_detail(chat_room_id)
            if chat_room_id in self.chat_room_head_img:
                return self.chat_room_head_img[chat_room_id]
            else:
                if chat_room_id in self.chat_room_info and 'avatar' in self.chat_room_info[chat_room_id] and self.chat_room_info[chat_room_id]['avatar']:
                    if self.chat_room_info[chat_room_id]['avatar'].startswith('http'):
                        _r = requests.get(self.chat_room_info[chat_room_id]['avatar'])
                        if _r.status_code == 200:
                            self.chat_room_head_img[chat_room_id] = _r.content
                            return _r.content
        except Exception as _e:
            self.info('[get_chat_room_head_photo_bytes]', _e)
            return None

    def get_group_head_photo_bytes(self, group_id):
        self.debug('[get_group_head_photo_bytes]')
        try:
            if group_id not in self.group_info:
                self.get_group_detail(group_id)
            if group_id in self.group_head_img:
                return self.group_head_img[group_id]
            else:
                if group_id in self.group_info and 'avatar' in self.group_info[group_id] and self.group_info[group_id]['avatar']:
                    if self.group_info[group_id]['avatar'].startswith('http'):
                        _r = requests.get(self.group_info[group_id]['avatar'])
                        if _r.status_code == 200:
                            self.group_head_img[group_id] = _r.content
                            return _r.content
        except Exception as _e:
            self.debug('[get_group_head_photo_bytes]', _e)
            return None

    def get_single_head_photo_bytes(self, comm_id):
        pass

    def get_user_head_photo_bytes(self, user_id=None):
        self.debug('[get_user_head_photo_bytes]')
        if user_id is None:
            user_id = self.user_id

        if user_id == self.user_id:
            if self.head_photo_bytes and self.head_photo_bytes != b'':
                return self.head_photo_bytes

        if user_id in self.friend_head_img:
            return self.friend_head_img[user_id]

        if user_id not in self.user_detail:
            _res = self.get_user_detail(user_id)
        if 'avatar' in self.user_detail[user_id] and self.user_detail[user_id]['avatar'] and self.user_detail[user_id]['avatar'].startswith('http'):
            try:
                _r = requests.get(self.user_detail[user_id]['avatar'])
            except Exception as _e:
                self.debug('[get_user_head_photo_bytes]', _e)
            else:
                if _r.status_code == 200:
                    self.friend_head_img[user_id] = _r.content
                    if user_id == self.user_id:
                        self.head_photo_bytes = _r.content
                    return _r.content
        else:
            self.friend_head_img[user_id] = None
            return None
        return None

    def get_chat_room_list_by_type(self, chat_room_type, create_time=None, count=None):
        self.debug('[get_chat_room_list_by_type]')
        if chat_room_type == 0:
            _res = chat_room_list_public(self.token, create_time=create_time)
        elif chat_room_type == 1:
            _res = chat_room_list_mine(self.token)
        else:
            raise Exception(f'unknow chat_room_type {chat_room_type}')
        # print(_res)
        return _res

    def get_chat_room_member_list(self, chat_room_id, count=40, cur_page=1):
        self.debug('[get_chat_room_member_list]')
        res = chat_room_member_list(self.token, chat_room_id, count, cur_page)
        return res

    def get_chat_room_announcement(self, chat_room_id):
        self.debug('[get_chat_room_announcement]')
        res = chat_room_announcement_get(self.token, chat_room_id)
        return res

    def get_chat_room_description(self, chat_room_id):
        self.debug('[get_chat_room_description]')
        res = self.get_chat_room_detail(chat_room_id)
        return res['data']['description']

    def get_chat_room_black_list(self, chat_room_id):
        self.debug('[get_chat_room_black_list]')
        res = chat_room_black_list(self.token, chat_room_id)
        return res

    def get_chat_room_manager_list(self, chat_room_id):
        self.debug('[get_chat_room_manager_list]')
        res = chat_room_manager_list(self.token, chat_room_id)
        return res

    def get_chat_room_white_list(self, chat_room_id):
        self.debug('[get_chat_room_white_list]')
        res = chat_room_user_mute_white_list(self.token, chat_room_id)
        return res

    def get_chat_room_mute_list(self, chat_room_id):
        self.debug('[get_chat_room_mute_list]')
        res = chat_room_user_multi_list(self.token, chat_room_id)
        return res

    def set_chat_room_description(self, chat_room_id, description):
        self.debug('[set_chat_room_description]')
        res = chat_room_description_update(self.token, chat_room_id, description)
        return res

    def set_group_mute(self, group_id, user_id_list_str, flag):  # 设置群聊禁言
        _res = set_group_mute(self.token, group_id, user_id_list_str, flag)
        return _res

    def set_group_black_list(self, group_id, user_id_list_str, flag=None):
        _res = set_group_black_list(self.token, group_id, user_id_list_str, flag)
        return _res

    def set_group_manager(self, group_id, user_id_list_str, flag):
        _res = set_group_manager(self.token, group_id, user_id_list_str, flag)
        return _res

    def set_group_allow_invite(self, group_id, allow_invite_flag):  # 群设置，是否允许群成员邀请他人入群
        _r = set_group_allow_invite(self.token, group_id, allow_invite_flag)
        return _r

    def set_group_name(self, group_id, group_name):
        _r = update_group_name(self.token, group_id, group_name)
        return _r

    def set_group_description(self, comm_id, description):   # 设置群描述
        _r = set_group_description(self.token, comm_id, description)
        return _r

    def set_group_announcement(self, group_id, announcement):
        self.debug('[set_group_announcement]')
        _r = set_group_announcement(self.token, group_id, announcement)
        return _r

    def set_group_join_apply(self, group_id, need_apply_flag):  # 群设置入群许可,入群需要群主或管理员同意
        _r = set_group_join_apply(self.token, group_id, need_apply_flag)
        return _r

    def set_group_all_mute(self, group_id, mute_status):
        _r = set_group_all_mute(self.token, group_id, mute_status)
        return _r

    def set_user_baseinfo(self, **kw):
        _r = set_user_baseinfo(self.token, **kw)
        return _r

    def set_user_head_photo(self, picture_path):
        _r = user_avatar_update(self.token, picture_path)
        return _r

    def set_auto_add_friend_accept(self, status):
        """
        设置是否自动添加好友
        :param status: 'true' or 'false'
        :return:
        """
        self.debug('[set_auto_add_friend_accept]')
        _r = set_auto_add_friend_accept(self.token, status)
        return _r

    def set_group_auto_accept(self, status):
        """
        设置是否自动入群
        :param status: 'true' or 'false'
        :return:
        """
        self.debug('[set_group_auto_accept]')
        _r = set_group_auto_accept(self.token, status)
        return _r

    def set_group_avatar(self, group_id, avatar_path):
        _r = group_avatar_upload(self.token, group_id, avatar_path)
        return _r

    def set_user_attribute(self, key, val):
        res = user_attribute_set(self.token, key, val)
        self.debug('[set_user_attribute]', res)
        return res

    def set_friend_black_list(self, user_id_list_str, flag):    # 设置通讯录黑名单
        _r = set_friend_black_list(self.token, user_id_list_str, flag)
        return _r

    def set_chat_room_announcement(self, chat_room_id, announcement):
        self.debug('set_chat_room_announcement', announcement)

        res = chat_room_announcement_update(self.token, chat_room_id, announcement)
        return res

    def set_chat_room_manager(self, chat_room_id, manager_ids_str, flag):
        self.debug('[set_chat_room_manager]')
        res = chat_room_manager_multi_set(self.token, chat_room_id, manager_ids_str, flag)
        return res

    def set_chat_room_black_list(self, chat_room_id, black_list_str, flag):
        self.debug('[set_chat_room_black_list]')
        res = chat_room_user_multi_black_set(self.token, chat_room_id, black_list_str, flag)
        return res

    def set_chat_room_white_list(self, chat_room_id, black_list_str, flag):
        self.debug('[set_chat_room_white_list]')
        res = chat_room_user_mute_white_set(self.token, chat_room_id, black_list_str, flag)
        return res

    def set_chat_room_mute(self, chat_room_id, mute_list_str, flag):
        self.debug('[set_chat_room_mute]')
        res = chat_room_user_multi_mute_set(self.token, chat_room_id, mute_list_str, flag)
        return res

    def set_chat_room_member(self, chat_room_id, member_list_str, flag):
        self.debug('[set_chat_room_member]')
        res = chat_room_member_set(self.token, chat_room_id, member_list_str, flag)
        return res

    def set_chat_room_name(self, chat_room_id, name):
        self.debug('[set_chat_room_name]')
        res = chat_room_name_update(self.token, chat_room_id, name)
        return res

    def set_chat_room_all_mute(self, chat_room_id, status):
        self.debug('[set_chat_room_all_mute]')
        res = chat_room_mute_all(self.token, chat_room_id, status)
        return res

    def accept_friend_group(self) -> (dict, dict):
        """
        设置自动入群和加好友
        """
        self.debug('[accept_friend_group]')
        res1 = set_auto_add_friend_accept(self.token, 'true')
        res2 = set_group_auto_accept(self.token, 'true')
        return res1, res2

    def refuse_friend_group(self) -> (dict, dict):
        """
        关闭自动入群和加好友
        """
        self.debug('[refuse_friend_group]')
        res1 = set_auto_add_friend_accept(self.token, 'false')
        res2 = set_group_auto_accept(self.token, 'false')
        return res1, res2

    def recall_msg(self, communication_id, message_id):
        res = recall_msg(self.token, communication_id, message_id)
        self.debug('[recall_msg]', res)
        return res

    def create_group(self, user_list_strs: str) -> dict:
        group_name = '[' + time.strftime('%Y-%m-%d %H:%M:%S') + ']'
        _res = create_group(self.token, group_name, user_list_strs, '', 'hello world', '')
        self.info('[create_group]', _res['code'])
        if _res['code'] == '0':
            data = _res['data']
            self.group_id_list.append(data['communicationId'])
            self.group_info[data['communicationId']] = {
                'ownerId': self.user_info['user_id'],
                'name': data['name']
            }
        return _res

    def create_chat_room(self):
        self.debug('[create_chat_room]')
        name = '{}'.format(time.strftime('%Y-%m-%d %H:%M:%S'))
        _res = chat_room_create(self.token, name, '聊天室测试')
        if 'code' in _res and _res['code'] == '0':
            data = _res['data']
            self.chat_room_info[data['communicationId']] = data
        return _res

    def accept_friend_apply(self, user_id):  # 同意添加好友
        _res = accept_friend_req(self.token, user_id)
        self.info('[accept_friend_apply]', _res)
        if _res['code'] == '0':
            self.update_friend_list()
        return _res

    def refuse_friend_apply(self, user_id):  # 拒绝好友申请
        _res = reject_friend_req(self.token, user_id)
        self.info('[refuse_friend_apply]', _res)
        return _res

    def user_accept_group_invite(self, group_id):   # 用户同意入群
        _res = user_accept_group_invite(self.token, group_id)
        # print(_res)
        self.info('[user_accept_group_invite]', _res)
        if _res['code'] == '0' and _res['data']['inviteStatus'] == 1:   # 入群成功
            # 更新 self.group_id_list
            self.group_id_list.append(group_id)
            # 更新 self.group_info
            self.group_info[group_id] = {
                'name': _res['data']['groupInfo']['name'],
                'ownerId': _res['data']['groupInfo']['ownerId']
            }
        return _res

    def user_reject_group_invite(self, group_id):   # 用户拒绝入群
        _res = user_reject_group_invite(self.token, group_id)
        self.info('[user_reject_group_invite]', _res)
        return _res

    def manager_accept_group_invite(self, group_id, user_id):    # 群成员拉人入群被管理员通过
        _res = manager_accept_group_invite(self.token, group_id, user_id)
        self.info('[manager_accept_group_invite]', _res)
        return _res

    def manager_reject_group_invite(self, group_id, user_id):    # 群成员拉人入群被管理员拒绝
        _res = manager_reject_group_invite(self.token, group_id, user_id)
        self.info('[manager_reject_group_invite]', _res)
        return _res

    def get_single_msg(self, msg_type, to_id, comm_id, msg, other=None) -> bytes:
        _msg = get_communication_message_by_single(msg_type, self.key, self.user_info['app_id'], self.user_info['user_id'], to_id, comm_id, msg, other=self.other if other is None else other)
        return _msg
        
    def get_group_msg(self, msg_type, comm_id, msg, other=None) -> bytes:
        _msg = get_communication_message_by_group(msg_type, self.key, self.user_info['app_id'], self.user_info['user_id'], comm_id, msg, other=self.other if other is None else other)
        return _msg

    def get_chat_room_msg(self, msg_type, comm_id, msg, other=None) -> bytes:
        _msg = get_communication_message_by_chat_room(msg_type, self.key, self.user_info['app_id'], self.user_info['user_id'], comm_id, msg, other=self.other if other is None else other)
        return _msg

    # async def write_thread(self):
    #     """
    #     发送消息协程,不断从协程消息队列获取消息发送出去
    #     """
    #     while not self.start:
    #         await asyncio.sleep(0.1)
    #     while not self.exit:
    #         msg = await self.write_queue.get()
    #         # self.debug('[write_thread] get msg: ', msg)
    #         if msg is None:
    #             self.exit = True
    #             break
    #         self.w.write(msg)
    #         await self.w.drain()
    #     self.debug('[write_thread] write exit')
    #     # self.w.close()
    #     # await self.w.wait_closed()

    async def heartbeat_thread(self):
        """
        心跳协程, 定时产生一条心跳消息到协程队列
        """
        while not self.is_login:
            await asyncio.sleep(0.1)
        while not self.exit:
            # self.debug('[heartbeat_thread]')
            current_timestamp = time.time()
            if current_timestamp - self.last_send_heartbeat_time >= self.header_beat_time:
                async with self.lock:
                    _msg = self.get_heartbeat_msg()
                if _msg:
                    self.w.write(_msg)
                    await self.w.drain()
                await asyncio.sleep(self.header_beat_time)
            else:
                await asyncio.sleep(self.header_beat_time - current_timestamp + self.last_send_heartbeat_time)
        self.debug('[heartbeat_thread] heartbeat_thread exit')
        self.w.close()

    def get_heartbeat_msg(self):
        current_time_stamp = time.time()
        _last_msg_sequence_id = self.last_msg_sequence_id
        _last_send_heartbeat_time = self.last_send_heartbeat_time
        if current_time_stamp - _last_send_heartbeat_time < self.header_beat_time:  # 发送间隔小于心跳间隔
            # if self.last_msg_receive_time == _last_send_heartbeat_time:  # 如果id小于等于上次发送的id就返回空
            if self.last_send_seq_id == self.last_msg_sequence_id:
                return
        # 其他情况下都允许发送一个心跳
        self.last_send_heartbeat_time = time.time()
        self.last_send_seq_id = _last_msg_sequence_id
        msg = get_heartbeat_message(
            self.key,
            device_type=1,
            last_msg_sequence_id=_last_msg_sequence_id,
            last_msg_receive_time=self.last_msg_receive_time
        )
        # self.info('[get_heartbeat_msg] send heartbeat: timestamp:{:.3f}, last_id:{}, last_timestamp: {}'.format(current_time_stamp, self.last_msg_sequence_id, self.last_msg_receive_time))
        return msg
        
    def get_ack_msg(self, from_user_id, to_user_id, communication_id, message_id, tag, msg_no=None) -> bytes:
        msg = get_msg_ack_message(self.key, self.user_info['app_id'], from_user_id, to_user_id, communication_id, message_id, msg_no)
        return msg
        
    def get_read_msg(self, from_user_id, to_user_id, communication_id, message_id, tag, msg_no=None) -> bytes:
        msg = get_msg_read_message(self.key, self.user_info['app_id'], from_user_id, to_user_id, communication_id, message_id, msg_no)
        return msg

    async def send_read_communication_sync_message(self, communication_id, communication_type):
        read_communication_sync_message = get_read_communication_sync_message(self.key, self.user_info['app_id'], communication_id, communication_type)
        # self.debug('[send_read_communication_sync_message]', read_communication_sync_message)
        self.w.write(read_communication_sync_message)
        await self.w.drain()

    async def get_sync_msg(self):
        """
        同步消息记录
        :return:
        """
        if os.path.exists(self.last_msg_seq_json_path):
            with open(self.last_msg_seq_json_path, 'r') as fd:
                data = json.load(fd)
        else:
            data = {
                'last_msg_sequence_id': 0
            }
        communication_last_id_info = data['communication_last_id'] if 'communication_last_id' in data else {}
        sync_communication_list_res = get_sync_communication_list(self.token, 1, data['last_msg_sequence_id'])
        self.debug('[get_sync_msg]', sync_communication_list_res)

        # 处理通知类型消息
        for notify_msg in sync_communication_list_res['data']['notifyMsgList']:
            await self.handle_sync_msg(notify_msg)

        # 处理普通消息
        for communication_info in sync_communication_list_res['data']['conversationRespVoList']:
            communication_id = communication_info['communicationId']
            current_communication_last_id = communication_last_id_info[communication_id] if communication_id in communication_last_id_info else 0   # 当前会话上次最后拉的消息
            # self.debug('[get_sync_msg]', communication_info)
            last_msg_id = communication_info['lastMsgId']
            """
            如果服务器返回的该会话最后一条消息大于current_communication_last_id, 就将这消息插入到新消息中
            因为get_sync_message_list接口逻辑是返回小于传入的消息id,没有取<=
            如果不把该会话的lastMsg保存起来，那么通过get_sync_message_list接口会拉不到这条消息
            """
            if last_msg_id > current_communication_last_id:
                await self.handle_sync_msg(communication_info['lastMsg'])
            while current_communication_last_id < last_msg_id:
                msg_list_res = get_sync_message_list(self.token, communication_id, 50, last_msg_id)
                self.debug('[get_sync_msg]', communication_id, 50, last_msg_id)
                for msg in msg_list_res['data']['msgList']:
                    if msg['messageId'] > current_communication_last_id:
                        await self.handle_sync_msg(msg)
                if len(msg_list_res['data']['msgList']) < 50:   # 拉到的消息小于50条说明没有新消息可拉取
                    break
                last_msg_id = min([_msg['messageId'] for _msg in msg_list_res['data']['msgList']])    # last_msg_id每次取最小msg_id

    async def get_offline_msg(self):
        self.debug('[get_offline_msg]')
        if os.path.exists(self.last_msg_seq_json_path):
            with open(self.last_msg_seq_json_path, 'r') as fd:
                data = json.load(fd)
            if type(data['last_msg_receive_time']) == int:
                data['last_msg_receive_time'] = str(data['last_msg_receive_time'])
        else:
            data = {
                'last_msg_receive_time': '0',
                'last_msg_sequence_id': 0
            }
        # 拉取离线会话需要用到上次的id和时间戳信息
        offline_conversation_list_res = get_offline_conversation_list(self.token, 1, data['last_msg_receive_time'], data['last_msg_sequence_id'])
        self.debug('[get_offline_msg] offline_conversation_list_res: ', offline_conversation_list_res)
        if 'code' not in offline_conversation_list_res or offline_conversation_list_res['code'] != '0':
            return  # 拉取离线会话异常就直接返回
        for _k in ['conversationRespVoList', 'notifyMsgList']:
            for comm_info in offline_conversation_list_res['data'][_k]:
                start_msg_id = self.last_msg_sequence_id
                last_msg_receive_time = self.last_msg_receive_time
                while 1:
                    # 拉取离线会话的消息时，需要上一次拉到的离线消息最小ID,如果是第一次拉取，传登录时服务器返回的seq_id
                    # 时间戳传登录时服务器返回的时间戳
                    offline_msg_res = get_offline_msg_by_cid(self.token, comm_info['communicationId'], 50, 1, start_msg_id, last_msg_receive_time)
                    offline_msg_len = 0
                    if 'msgList' in offline_msg_res['data']:
                        offline_msg_len += len(offline_msg_res['data']['msgList'])
                    if offline_msg_len == 0:
                        break
                    receive_offline_msg_id_list = list()
                    if 'msgList' in offline_msg_res['data']:
                        for _offline_msg in offline_msg_res['data']['msgList']:
                            await self.handle_offline_msg(_offline_msg)
                            receive_offline_msg_id_list.append(_offline_msg['messageId'])
                    start_msg_id = min(receive_offline_msg_id_list)
                    end_msg_id = max(receive_offline_msg_id_list)
                    # 删除消息时，需要用到当前拉到的消息的最大ID和最小ID
                    _res = clean_offline_message(self.token, 1, comm_info['communicationId'], end_msg_id, self.last_msg_receive_time, start_msg_id)
                    self.info('[get_offline_msg] [clean_offline_message]', _res)

    async def handle_offline_msg(self, msg: dict):
        self.debug('[handle_offline_msg]', msg['content'] if 'content' in msg else msg['messageType'])
        if 'communicationType' not in msg or msg['communicationType'] == 0:
            msg['communicationType'] = 100
        if msg['communicationType'] == 100:
            msg['communicationId'] = 'system'
        if 'communicationId' not in msg:
            msg['communicationId'] = 'system'
        try:
            if 'msg_count' in self.communication_info[msg['communicationId']]:
                self.communication_info[msg['communicationId']]['msg_count'] += 1   # 总消息数量
            else:
                self.communication_info[msg['communicationId']]['msg_count'] = 1
            # self.debug('[handle_offline_msg]', self.communication_info[msg['communicationId']]['msg_count'])
            self.communication_info[msg['communicationId']]['last_time_stamp'] = time.strftime('%Y-%m-%d %H:%M:%S')
            if msg['communicationId'] not in self.commid_tree_index:
                self.debug('[handle_offline_msg]', msg)
                if msg['communicationType'] == 1:
                    _nickname = self.get_nickname(msg['fromUserId'])
                elif msg['communicationType'] == 2:
                    _nickname = self.get_group_name(msg['communicationId'])
                elif msg['communicationType'] == 0 or msg['communicationType'] == 100:
                    _nickname = '系统通知'
                else:
                    _nickname = 'unknow'
                if msg['communicationType'] == 2:
                    head_img = self.get_group_head_photo_bytes(msg['communicationId'])
                elif msg['communicationType'] == 1:
                    head_img = self.get_user_head_photo_bytes(msg['fromUserId'])
                else:
                    head_img = None
                if head_img:
                    photo = Image.open(BytesIO(head_img))
                    photo = photo.resize((25, 25))
                    img0 = ImageTk.PhotoImage(photo)
                    self.tk_img_dict[msg['communicationId']] = img0
                    tree_item = self.tree.insert(
                        '',
                        0,
                        image=self.tk_img_dict[msg['communicationId']],
                        values=(
                            _nickname,
                            msg['communicationId'] if 'communicationId' in msg else '',
                            msg['communicationType'] if 'communicationType' in msg else '',
                            self.get_nickname(msg['fromUserId']) if msg['communicationType'] == 2 else msg['fromUserId'],
                            time.strftime('%Y-%m-%d %H:%M:%S'),
                            1,
                            msg['messageId'],
                            msg['content'] if 'content' in msg else 'message type: [{}]'.format(msg['messageType'])
                        )
                    )
                else:
                    tree_item = self.tree.insert(
                        '',
                        0,
                        values=(
                            _nickname,
                            msg['communicationId'] if 'communicationId' in msg else '',
                            msg['communicationType'] if 'communicationType' in msg else '',
                            self.get_nickname(msg['fromUserId']) if msg['communicationType'] == 2 else msg['fromUserId'],
                            time.strftime('%Y-%m-%d %H:%M:%S'),
                            1,
                            msg['messageId'],
                            msg['content'] if 'content' in msg else 'message type: [{}]'.format(msg['messageType'])
                        )
                    )
                self.commid_tree_index[msg['communicationId']] = tree_item
                # self.debug('[handle_offline_msg]', self.commid_tree_index)
            if 'last_msg' not in self.communication_info[msg['communicationId']]:
                self.communication_info[msg['communicationId']]['last_msg'] = msg
            self.communication_msg[msg['communicationId']].appendleft(msg)
        except Exception as _e:
            print(_e, 'handle_offline_msg')

    async def handle_sync_msg(self, msg: dict):
        # self.debug('[handle_sync_msg]', msg['content'] if 'content' in msg else msg['messageType'])
        if 'communicationType' not in msg or msg['communicationType'] == 0:
            msg['communicationType'] = 100
        if msg['communicationType'] == 100:
            msg['communicationId'] = 'system'
        if 'communicationId' not in msg:
            msg['communicationId'] = 'system'
        try:
            if 'msg_count' in self.communication_info[msg['communicationId']]:
                if msg['fromUserId'] != self.user_id:
                    self.communication_info[msg['communicationId']]['msg_count'] += 1   # 总消息数量
            else:
                if msg['fromUserId'] != self.user_id:
                    self.communication_info[msg['communicationId']]['msg_count'] = 1
                else:
                    self.communication_info[msg['communicationId']]['msg_count'] = 0
            # self.debug('[handle_offline_msg]', self.communication_info[msg['communicationId']]['msg_count'])
            self.communication_info[msg['communicationId']]['last_time_stamp'] = time.strftime('%Y-%m-%d %H:%M:%S')
            if msg['communicationId'] not in self.commid_tree_index:
                # self.debug('[handle_sync_msg]', msg)
                if msg['communicationType'] == 1:
                    if msg['communicationId'] in self.commid_to_user_id_dict:
                        _friend_id = self.commid_to_user_id_dict[msg['communicationId']]
                        _nickname = self.get_nickname(_friend_id)
                    else:
                        _nickname = self.get_nickname(msg['fromUserId']) if msg['fromUserId'] != self.user_id else self.get_nickname(msg['toUserId'])
                elif msg['communicationType'] == 2:
                    _nickname = self.get_group_name(msg['communicationId'])
                elif msg['communicationType'] == 0 or msg['communicationType'] == 100:
                    _nickname = '系统通知'
                else:
                    _nickname = 'unknow'
                if msg['communicationType'] == 2:
                    head_img = self.get_group_head_photo_bytes(msg['communicationId'])
                elif msg['communicationType'] == 1:
                    if msg['communicationId'] in self.commid_to_user_id_dict:
                        _friend_id = self.commid_to_user_id_dict[msg['communicationId']]
                        head_img = self.get_user_head_photo_bytes(_friend_id)
                    else:
                        head_img = self.get_user_head_photo_bytes(msg['fromUserId']) if msg['fromUserId'] != self.user_id else self.get_user_head_photo_bytes(msg['toUserId'])
                else:
                    head_img = None
                if head_img:
                    photo = Image.open(BytesIO(head_img))
                    photo = photo.resize((25, 25))
                    img0 = ImageTk.PhotoImage(photo)
                    self.tk_img_dict[msg['communicationId']] = img0
                    tree_item = self.tree.insert(
                        '',
                        'end',
                        image=self.tk_img_dict[msg['communicationId']],
                        values=(
                            _nickname,
                            msg['communicationId'] if 'communicationId' in msg else '',
                            msg['communicationType'] if 'communicationType' in msg else '',
                            # self.get_nickname(msg['fromUserId']) if msg['communicationType'] == 2 else msg['fromUserId'],
                            time.strftime('%Y-%m-%d %H:%M:%S'),
                            1 if msg['fromUserId'] != self.user_id else 0,
                            msg['content'] if msg['messageMainType'] == 1 else '[{}]'.format(MESSAGE_TYPE[msg['messageType']]),
                            msg['messageId']
                        )
                    )
                else:
                    tree_item = self.tree.insert(
                        '',
                        'end',
                        values=(
                            _nickname,
                            msg['communicationId'] if 'communicationId' in msg else '',
                            msg['communicationType'] if 'communicationType' in msg else '',
                            # self.get_nickname(msg['fromUserId']) if msg['communicationType'] == 2 else msg['fromUserId'],
                            time.strftime('%Y-%m-%d %H:%M:%S'),
                            1 if msg['fromUserId'] != self.user_id else 0,
                            msg['content'] if msg['messageMainType'] == 1 else '[{}]'.format(MESSAGE_TYPE[msg['messageType']]),
                            msg['messageId']
                        )
                    )
                self.commid_tree_index[msg['communicationId']] = tree_item
                # self.debug('[handle_offline_msg]', self.commid_tree_index)
            if 'last_msg' not in self.communication_info[msg['communicationId']]:
                self.communication_info[msg['communicationId']]['last_msg'] = msg
            self.communication_msg[msg['communicationId']].appendleft(msg)
        except Exception as _e:
            print(_e, 'handle_sync_msg')

    async def handle_chat_room_msg(self, msg):
        communication_id = msg['communication_id']
        self.chat_room_msg[msg['communication_id']][msg['tag']] = msg
        if communication_id in self.chat_room_tree_dict:
            try:
                tree = self.chat_room_tree_dict[communication_id]
                content = ''
                if msg['message_main_type'] == 100:
                    content_json = json.loads(msg['content'])
                    if 'member' in content_json:
                        member_id = content_json['member']
                        nick_name = self.get_nickname(member_id)
                        content = nick_name + ' : ' + content_json['notifyDesc']
                    elif 'userIds' in content_json:
                        content = content_json['notifyDesc'] + ' : ' + ','.join([self.get_nickname(user_id) for user_id in content_json['userIds'].split(',')])
                    else:
                        content = content_json['notifyDesc']
                elif 'content' in msg:
                    if type(msg['content']) is str:
                        content = msg['content']
                    else:
                        content = str(msg['content'])
                msg_type = MESSAGE_TYPE[msg['message_type']] if msg['message_type'] in MESSAGE_TYPE else '未知消息类型{}'.format(msg['message_type'])
                if msg['message_main_type'] == 100:
                    tree.insert('', 'end', values=('系统通知', msg_type, content, msg['tag']))
                else:
                    if msg['from_user_id'] in self.tk_img_dict:
                        tree.insert('', 'end', image=self.tk_img_dict[msg['from_user_id']], values=('{} [{}]'.format(self.get_nickname(msg['from_user_id']), msg['from_user_id']), msg_type, content, msg['tag']), tags=('self',) if msg['from_user_id'] == self.user_id else '')
                    else:
                        user_head_img = self.get_user_head_photo_bytes(msg['from_user_id'])
                        if user_head_img:
                            tk_img = img_to_tk_img(user_head_img, 15)
                            self.tk_img_dict[msg['from_user_id']] = tk_img
                            tree.insert('', 'end', image=self.tk_img_dict[msg['from_user_id']], values=('{} [{}]'.format(self.get_nickname(msg['from_user_id']), msg['from_user_id']), msg_type, content, msg['tag']), tags=('self',) if msg['from_user_id'] == self.user_id else '')
                        else:
                            tree.insert('', 'end', values=('{} [{}]'.format(self.get_nickname(msg['from_user_id']), msg['from_user_id']), msg_type, content, msg['tag']), tags=('self',) if msg['from_user_id'] == self.user_id else '')
                tree.yview_moveto(1)
            except Exception as _e:
                self.info('[handle_chat_room_msg]', _e)

    async def handle_recv_msg(self, msg):
        if self.tree is None:
            return
        # try:
        #     send_time_stamp = int(msg['tag'][0:13])
        #     current_time_stamp = time.time()*1000
        #     cost = current_time_stamp - send_time_stamp
        #     self.cost.append(cost)
        # except Exception as _e:
        #     self.debug('handle_recv_msg', _e)
        self.debug('[handle_recv_msg]', msg)
        if 'communication_type' in msg and msg['communication_type'] == 3:
            await self.handle_chat_room_msg(msg)
            return
        if msg['from_user_id'] == self.user_info['user_id']:
            if 'message_main_type' in msg and msg['message_main_type'] == 1:
                pass
            if 'communication_type' in msg and msg['communication_type'] in [1, 2] and msg['message_type'] in [1, 2, 3, 4, 5, 6, 7]:
                pass
        if 'communication_type' not in msg or msg['communication_type'] == 0:
            msg['communication_type'] = 100
        elif msg['communication_type'] == 100:
            msg['communication_id'] = 'system'
        if 'communication_id' not in msg:
            msg['communication_id'] = 'system'

        if msg['from_user_id'] != self.user_info['user_id']:
            if 'msg_count' in self.communication_info[msg['communication_id']]:
                self.communication_info[msg['communication_id']]['msg_count'] += 1
            else:
                self.communication_info[msg['communication_id']]['msg_count'] = 1
                self.communication_info[msg['communication_id']]['start'] = 0
        else:
            if 'msg_count' not in self.communication_info[msg['communication_id']]:
                self.communication_info[msg['communication_id']]['msg_count'] = 0

        self.communication_info[msg['communication_id']]['last_time_stamp'] = time.strftime('%Y-%m-%d %H:%M:%S')
        _nickname = ''
        if msg['communication_id'] not in self.commid_tree_index:
            if msg['communication_type'] == 1:
                if msg['from_user_id'] != self.user_id:
                    _nickname = self.get_nickname(msg['from_user_id'])
                    head_img = self.get_user_head_photo_bytes(msg['from_user_id'])
                else:
                    _nickname = self.get_nickname(msg['to_user_id'])
                    head_img = self.get_user_head_photo_bytes(msg['to_user_id'])
            elif msg['communication_type'] == 2:
                _nickname = self.get_group_name(msg['communication_id'])
                head_img = self.get_group_head_photo_bytes(msg['communication_id'])
            elif msg['communication_type'] == 100 or msg['communication_type'] == 0 or msg['communication_id'] == 'system':
                _nickname = '系统通知'
                head_img = None
            else:
                head_img = None
            # head_img = None
            if head_img:
                try:
                    photo = Image.open(BytesIO(head_img))
                    photo = photo.resize((25, 25))
                    img0 = ImageTk.PhotoImage(photo)
                    self.tk_img_dict[msg['communication_id']] = img0
                    tree_item = self.tree.insert(
                        '',
                        0,
                        image=self.tk_img_dict[msg['communication_id']],
                        values=(
                            _nickname,
                            msg['communication_id'] if 'communication_id' in msg else '',
                            msg['communication_type'] if 'communication_type' in msg else '',
                            time.strftime('%Y-%m-%d %H:%M:%S'),
                            1 if msg['from_user_id'] != self.user_info['user_id'] else 0,
                            msg['content'] if msg['message_type'] == 1 else '[{}]'.format(MESSAGE_TYPE.get(msg['message_type'], '未知消息类型')),
                            msg['message_id']
                        )
                    )
                except Exception as _ee:
                    # print(_ee)
                    self.debug('[handle_recv_msg]', _ee)
                    return
            else:
                tree_item = self.tree.insert(
                    '',
                    0,
                    values=(
                        _nickname,
                        msg['communication_id'] if 'communication_id' in msg else '',
                        msg['communication_type'] if 'communication_type' in msg else '',
                        time.strftime('%Y-%m-%d %H:%M:%S'),
                        1 if msg['from_user_id'] != self.user_id else 0,
                        msg['content'] if msg['message_type'] == 1 else '[{}]'.format(MESSAGE_TYPE.get(msg['message_type'], '未知消息类型')),
                        msg['message_id']
                    )
                )
            self.commid_tree_index[msg['communication_id']] = tree_item
        self.communication_info[msg['communication_id']]['last_msg'] = msg
        self.communication_msg[msg['communication_id']].append(msg)

        if msg['message_type'] == 10:    # 红包消息
            _r = open_redpacket(self.token, self.get_nickname(self.user_info['user_id']), msg['message_id'])
            # 领取红包
            self.debug('[handle_recv_msg] [open_redpacket]', _r)
        elif msg['message_type'] == 106:    # 好友关系确认
            self.update_friend_list()
        elif msg['message_type'] == 107:  # 删除好友
            try:
                self.friend_id_list.remove(msg['from_user_id'])
            except Exception as _e:
                self.debug('[handle_recv_msg]', _e)
        elif msg['message_type'] == 110:  # 删除后重新添加好友
            if msg['from_user_id'] == self.user_id:
                self.update_friend_list()
        elif msg['message_type'] == 111:    # 用户信息更新
            self.update_user_head_photo()  # 更新头像
        elif msg['message_type'] in {304, 324}:    # 被踢,群被解散
            current_group_id = json.loads(msg['content'])['groupId']
            if current_group_id in self.group_id_list:
                self.group_id_list.remove(current_group_id)
            if msg['message_type'] == 324:  # 群解散
                self.already_destroy_comm_id_set.add(current_group_id)
        elif msg['message_type'] == 301:    # 自动入群
            if msg['from_user_id'] == self.user_info['user_id']:
                return
            group_id = json.loads(msg['content'])['groupId']
            self.get_group_name(group_id)
            self.group_id_list.append(group_id)
        elif msg['message_type'] == 323:    # 群主变更
            try:
                _data = json.loads(msg['content'])
                group_id = _data['groupId']
                new_owner = _data['newOwner']
                self.group_info[group_id]['ownerId'] = new_owner
            except Exception as _e:
                self.debug('[handle_recv_msg]', _e)
        elif msg['message_type'] == 325:    # 群名变更
            group_id = json.loads(msg['content'])['groupId']
            new_group_name = json.loads(msg['content'])['newGroupName']
            self.group_info[group_id]['name'] = new_group_name
        elif msg['message_type'] == 326:    # 群列表变更
            self.get_group_list()
        elif msg['message_type'] == 332:    # 群头像变更
            _data = json.loads(msg['content'])
            self.group_info[msg['communication_id']]['avatar'] = _data['groupAvatarUrl']
            self.update_group_head_photo(msg['communication_id'])

    async def handle_read(self):
        """
        读取数据协程,整体逻辑和locust脚本一样，只不过同步方法都改为异步
        """
        while not self.start:
            await asyncio.sleep(0.1)
        # while self.r is None:
        #     await asyncio.sleep(0.1)
        while not self.exit:
            try:
                buffer = await self.r.read(5)  # 前4个字节代表包的长度
                lens = len(buffer)
                while lens < 5:
                    _d = await self.r.read(5-lens)
                    if _d is None or _d == b'':
                        self.debug('[handle_read] read_head', _d, buffer)
                        raise Exception('[handle_read] get header error')
                    else:
                        buffer += _d
                    lens = len(buffer)
                length, command = msg_unpack_length_and_command(buffer)  # 解析包长度及类型
                if not length or not command:
                    print(length, command)
                length -= 1  # 上面读了5字节数据,总长度:4bytes,command:1bytes,相当于多读了1字节，所以实际长度-1
                buffer = await self.r.read(length)
            except Exception as exce:
                self.debug('[handle_read] recv get error: ', exce)
                # self.q.put(None)
                self.w.close()
                self.exit = True   # 退出flag
                self.debug('[handle_read] set exit: ', self.exit)
                self.save_last_seq_id_and_timestamp()
                self.err_msg = str(exce)
                self.info(self.err_msg)
                raise Exception('recv eror') from exce
            else:
                buff_len = len(buffer)
                while buff_len < length:
                    buffer += await self.r.read(length-buff_len)
                    buff_len = len(buffer)
                key_len = buffer[0]
                key = buffer[1: 1+key_len]
                protoname_len = buffer[1+key_len]
                protoname = buffer[2+key_len: 2+key_len+protoname_len]
                proto_body = buffer[2+key_len+protoname_len:]
                self.debug('[handle_read]', protoname)
                if proto_body:
                    res = decode_communication_message(protoname, proto_body)
                    self.debug('[handle_read]', res)
                    if protoname == b'RspBindUserChannel':
                        self.is_login = True
                        # self.last_msg_receive_time = int(res['last_msg_receive_time'])
                        self.last_msg_receive_time = res['last_msg_receive_time']
                        self.last_msg_sequence_id = int(res['last_msg_sequence_id'])
                    elif protoname == b'CommunicationMessageProto':
                        await self.handle_recv_msg(res)  # 处理接收的消息
                    elif protoname == b'ReplyCommandSendMsgReq':
                        # now_time_stamp = int(time.time()*1000)
                        # cost_time = now_time_stamp - int(res['tag'][0:13])
                        # self.debug('[handle_read] [ReplyCommandSendMsgReq] cost time: {}ms'.format(cost_time))
                        if res['communication_type'] == 3:
                            tag = res['tag']
                            communication_id = res['communication_id']
                            if 'resp' in res and 'ret' in res['resp']:
                                self.debug('[handle_read] [ReplyCommandSendMsgReq]', res['resp']['ret'])
                                self.chat_room_msg[communication_id][tag] = res
                                if communication_id in self.chat_room_tree_dict:
                                    tree = self.chat_room_tree_dict[communication_id]
                                    tree.insert('', 'end', values=('系统', '消息发送异常', res['resp']['errorCode'], tag), tags=('self',))
                            else:
                                self.chat_room_msg[communication_id][tag]['message_id'] = res['message_id']
                                await self.handle_chat_room_msg(self.chat_room_msg[communication_id][tag])
                    elif protoname == b'ForceLogoutProto':
                        # self.w.close()
                        self.err_msg = '[handle_read] ForceLogoutProto'
                        self.debug('[handle_read] ForceLogoutProto')
                        self.slogout()
                        await self.logout()
                        await asyncio.sleep(2.5)  # 等待心跳协程退出
                        raise Exception('ForceLogoutError')
                    elif protoname == b'HeartBeatAckMsg':
                        """
                        新版本的心跳响应包,需要重新处理
                        """
                        if 'chatMsg' in res:
                            current_max_sequence_id = int(res['last_msg_sequence_id'])
                            current_max_receive_time = res['last_msg_receive_time']
                            self.last_msg_sequence_id = current_max_sequence_id
                            self.last_msg_receive_time = current_max_receive_time
                            # meg_id_list = list()
                            for _msg in res['chatMsg']:
                                # meg_id_list.append(int(_msg['message_id']))
                                await self.handle_recv_msg(_msg)  # 处理接收的消息
                            self.info('[handle read] chatMsg size: ', len(res['chatMsg']))
                            if len(res['chatMsg']) >= 50:
                                _heartbeat_msg = self.get_heartbeat_msg()
                                if _heartbeat_msg:
                                    async with self.lock:
                                        self.w.write(_heartbeat_msg)
                                        await self.w.drain()
                    elif protoname == b'RespErrorResultProto':
                        raise Exception(f'RecvError: {res}')
                    elif protoname == b'MessageAckProto':
                        self.debug('[handle_read] [MessageAckProto]', res)
                    elif protoname == b'ReadCommunicationSyncProto':
                        self.debug('[handle_read] [ReadCommunicationSyncProto]', command, res)
                        self.clean_communication_msg_count(res['communication_id'])  # 清空会话未读数
        self.debug('[handle_read]', 'read exit')
        self.w.close()

    async def handle_sync_callback(self, coroutine_name, *args, callback=None):
        """
        该函数主要是被gui线程通过asyncio.run_coroutine_threadsafe调用
        gui线程通过asyncio.run_coroutine_threadsafe方法，将需要调用事异步函数的名称以及参数传过来,
        :param coroutine_name: 需要调用事异步函数的名称
        :param args: 该异步函数的参数
        :param callback: 异步函数执行完后，再调用gui线程传的回调函数
        :return:
        """
        main_loop = asyncio.get_running_loop()
        coroutine = getattr(self, coroutine_name)
        task = main_loop.create_task(coroutine(*args))
        if callback:
            def sync_callback(_task):
                callback(_task.result())
            task.add_done_callback(sync_callback)
        await task

    async def async_work(self):
        await asyncio.sleep(10)
        print(self)
        return '这是异步返回结果'

    def analysis_msg_cost(self):
        if len(self.cost) == 0:
            return
        print('len', len(self.cost))
        print('min', min(self.cost))
        print('max', max(self.cost))
        print('avg', sum(self.cost)/len(self.cost))


if __name__ == "__main__":
    import config

    _user_info = {
        'phone': '12618400077',
        'app_id': '5751a0ff7c93eb26eb1ee2d45fe4a185#zhuanliao',
        'pwd': '123456'
    }
    a = GUIIMUser(_user_info, tree=None)
    a.login_demo()
    a.login()
    loop = asyncio.get_event_loop()
    tasks = [
        a.build_connection(),
        a.heartbeat_thread(),
        a.handle_read()
    ]
    loop.run_until_complete(asyncio.wait(tasks))
