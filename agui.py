# coding = utf-8
import tkinter
from tkinter import ttk, messagebox, filedialog
from threading import Thread, current_thread
import json
import os
from time import sleep, strftime, localtime, time
import re
import base64
from io import BytesIO
import asyncio
import pprint

import win32gui
import qrcode
from PIL import Image, ImageTk
import requests

from im_user import GUIIMUser
from utils.img2ico import img2ico, img_to_tk_img
import message_type
from message_price import MESSAGE_PRICE


MESSAGE_TYPE = message_type.MESSAGE_TYPE


'''隔行显色的背景色'''
# TREE_ROW_BG = '#eeeeee'    # 浅灰色
TREE_ROW_BG = '#d9ead3'  # 浅绿色


# TREE_ROW_BG = '#d0e0e3'     # 浅蓝色


def delete_tree_all_items(tree):
    items = tree.get_children()
    for item in items:
        tree.delete(item)


def load_json_from_file(path):
    if os.path.exists(path):
        with open(path, encoding='utf-8') as fd:
            data = json.load(fd)
    else:
        data = None
    return data


def del_from_file(key, path):
    if os.path.exists(path):
        with open(path, encoding='utf-8') as fd:
            data = json.load(fd)
        exists = False
        for val in data:
            if key == val:
                exists = True
                break
        if exists:
            del data[key]
            with open(path, 'w', encoding='utf-8') as fd:
                json.dump(data, fd, indent=4, ensure_ascii=False)
        else:
            pass


def add_json_to_file(data, path):
    with open(path, 'w', encoding='utf-8') as fd:
        json.dump(data, fd, indent=4, ensure_ascii=False)


def mkdir(path):
    if not os.path.exists(path):
        os.mkdir(path)


def get_root_center_coordinate(wd_name):  # 获取窗口名的中心坐标
    hwnd = win32gui.FindWindow(None, wd_name)
    x1, y1, x2, y2 = win32gui.GetWindowRect(hwnd)
    return (x1 + x2) / 2, (y1 + y2) / 2


def get_put_coordinate(win_width: float, win_height: float, parent_wd_name: str):
    """
    获取当前窗口放置的坐标(放在父窗口的中心区域)
    :param win_width:当前控件 宽
    :param win_height:当前控件 高
    :param parent_wd_name:父窗口标题
    :return:
    """
    root_center_x, root_center_y = get_root_center_coordinate(parent_wd_name)
    x = int(root_center_x - (win_width / 2))
    y = int(root_center_y - (win_height / 2))
    return x, y


def clean_selection(tree):
    """
    清除treeview所选中内容
    :param tree: Treeview object
    :return: None
    """
    for _item in tree.selection():
        tree.selection_remove(_item)


def show_tree_selection_count(event, tree_view):
    selection_len = len(tree_view.selection())
    menu = tkinter.Menu(tree_view, tearoff=0)
    menu.add_command(label=f'当前选中{selection_len}项')
    menu.post(event.x_root, event.y_root)


class SubTop:

    def __init__(self, title=None, parent=None):
        self._top = tkinter.Toplevel(parent)
        self._top.overrideredirect(False)
        self._top.resizable(0, 0)
        self._top.title(title)
        self._parent = parent

    def get_handle(self):
        return self._top

    def show(self):
        self._top.update()
        if self._parent is not None:
            _x, _y = get_put_coordinate(self._top.winfo_width(), self._top.winfo_height(), self._parent.title())
            self._top.geometry("+{}+{}".format(_x, _y))
        self._top.mainloop()


class Gui:
    CFG_PATH = 'cfg/config.json'

    RUNTIME_FILE = 'runtime/runtime'

    ICO_PATH = None

    # IM_ADDR = IM_SERVER_ADDRESS

    DEBUG = False

    INFO = False

    IM_USER_DEBUG = True

    IM_USER_INFO = True

    def __init__(self):
        if os.path.exists(self.RUNTIME_FILE):
            root = tkinter.Tk()
            root.withdraw()  # ****实现主窗口隐藏
            self.debug('runtime_file exists, exit')
            messagebox.showerror('错误', '存在runtime')
            exit(0)
        self.wdname = 'im_client'
        self.init_tk()  # 初始化gui控件

        self.exit_flag = False  # gui线程退出flag
        self.top = None
        self.setting_flag = True  # 组件状态
        self.user_setting_flag = True  # 组件状态
        self.login_status = False  # im user登录状态
        self.show_group = True  # 组件状态
        self.show_friend = True  # 组件状态
        self.im_user = None  # 当前登录的GUIIMUser对象
        self.loop = None
        self.app_id = ''  # app_id
        self.user_id = ''  # user_id
        self.user_name = ''  # user_name
        self.phone = ''  # phone
        self.pwd = ''  # pwd
        self.msg_sleep_time = 0.5  # 发送消息间隔
        self.auto_login = False  # 自动登录flag
        self.group_info = {}
        self.head_imgs = {}
        self.chat_room_pages = {}   # 存放聊天室页面 tree view对象
        self.already_send_ack_msg_id_set = set()  # 存放已经发送消息回执的id
        mkdir('runtime')
        mkdir('cfg')

    def debug(self, *args, **kw):
        if self.DEBUG:
            print('[{}] [agui.py] '.format(strftime('%Y-%m-%d %H:%M:%S')), *args, **kw)

    def info(self, *args, **kw):
        if self.INFO:
            print('[{}] [agui.py] '.format(strftime('%Y-%m-%d %H:%M:%S')), *args, **kw)

    def init_tk(self):
        def fixed_map(option):
            # Returns the style map for 'option' with any styles starting with
            # ("!disabled", "!selected", ...) filtered out
            # style.map() returns an empty list for missing options, so this should
            # be future-safe
            return [elm for elm in style.map("Treeview", query_opt=option) if elm[:2] != ("!disabled", "!selected")]

        self.root = tkinter.Tk()  # 生成root主窗口3

        '''修复官方库设置背景色无效的bug'''
        style = ttk.Style(self.root)
        style.map(
            "Treeview",
            foreground=fixed_map("foreground"),
            background=fixed_map("background")
        )

        self.root.geometry("+600+300")
        self.root.title(self.wdname)
        self.root.iconbitmap(self.ICO_PATH)

        self.root.resizable(0, 0)
        menu_bar = tkinter.Menu(self.root)
        # menu_bar.add_command(label="登录", command=self.show_add_work)
        # menu_bar.add_command(label="会话", command=self.show_info)
        menu_bar.add_command(label="本地设置", command=self.setting)
        menu_bar.add_command(label="用户设置", command=self.user_setting)
        menu_bar.add_command(label="好友", command=self.show_friend_list)
        menu_bar.add_command(label="群聊", command=self.show_group_list)
        menu_bar.add_command(label="聊天室", command=self.show_chat_room_list)
        # menu_bar.add_command(label="开启自动加好友和入群", command=self.accept_friend_group)
        # menu_bar.add_command(label="关闭自动加好友和入群", command=self.refuse_friend_group)
        menu_bar.add_command(label="清空会话和消息", command=self.clean_msg)
        menu_bar.add_command(label="我的二维码", command=lambda: self.show_qrcode(self.root))
        menu_bar.add_command(label="发送消息统计", command=self.show_send_msg_details)
        menu_bar.add_command(label="退出登录", command=self.logout)
        menu_bar.add_command(label="cost 分析", command=self.analysis_msg_cost)

        # menu_bar.add_command(label="测试", command=self.submit_work_to_loop_thread)

        self.root.config(menu=menu_bar)  # 设置菜单

        self.add_frame = tkinter.Frame(self.root)

        self.add_work_frame = tkinter.Frame(self.add_frame)
        v = tkinter.StringVar(self.root, value='')
        v1 = tkinter.StringVar(self.root, value='')
        self.username_variable = v
        self.pwd_variable = v1
        username_label = tkinter.Label(self.add_work_frame, text='手机号', width=25)
        pwd_label = tkinter.Label(self.add_work_frame, text='密码', width=25)

        username_label.grid(row=0, column=0, sticky=tkinter.W)  # 左对齐
        pwd_label.grid(row=1, column=0, sticky=tkinter.W)

        self.username_entry = tkinter.Entry(self.add_work_frame, width=80, textvariable=v)
        self.pwd_entry = tkinter.Entry(self.add_work_frame, width=80, textvariable=v1)
        self.username_entry.grid(row=0, column=1, sticky=tkinter.W)
        self.pwd_entry.grid(row=1, column=1, sticky=tkinter.W)

        self.login_button = tkinter.Button(self.add_work_frame, text='登录', width=40, fg='blue',
                                           command=lambda: self.run_user(None, None))
        # self.add_work_text = tkinter.Text(self.add_work_frame)
        self.add_work_tree = ttk.Treeview(self.add_work_frame, columns=['info'], height=18, show="headings")
        self.add_work_tree.column('info', width=800)

        '''设置行间距'''
        col_count, row_count = self.add_work_frame.grid_size()
        for row in range(row_count):
            self.add_work_frame.grid_rowconfigure(row, minsize=30)

        self.login_button.grid(row=3, column=0, columnspan=2)
        self.add_work_tree.grid(row=4, column=0, columnspan=2)
        vsb = ttk.Scrollbar(self.add_work_frame, orient="vertical", command=self.add_work_tree.yview)
        vsb.grid(column=2, row=4, sticky=tkinter.NS)
        self.add_work_tree.configure(yscrollcommand=vsb.set)
        self.add_frame.grid()
        self.add_work_frame.grid()

        self.info_frame = tkinter.Frame(self.root)
        col = ['comm_name', 'comm_id', 'comm_type', 'time', 'msg_count', 'content', 'msg_id']
        ttk.Style().configure('main.Treeview', rowheight=30)
        self.tree = ttk.Treeview(self.info_frame, columns=col, height=12, style='main.Treeview')
        self.tree.heading("comm_name", text="会话名")  # 设置表头
        self.tree.heading("comm_id", text="会话id")  # 设置表头
        self.tree.heading("comm_type", text="会话类型")  # 设置表头
        # self.tree.heading("sender", text="消息发送方")  # 设置表头
        self.tree.heading("time", text="时间")
        self.tree.heading("msg_count", text="新消息数量")
        self.tree.heading("msg_id", text="消息id")
        self.tree.heading("content", text="内容")
        self.tree.column("time", width=160)  # 设置列宽等属性
        self.tree.column("msg_count", width=70)  # 设置列宽等属性
        self.tree.column("comm_type", width=60)  # 设置列宽等属性
        self.tree.column("msg_id", width=150)  # 设置列宽等属性
        self.tree.column("#0", width=60)  # 设置列宽等属性
        # self.tree.column("msg_id", width=300)    # 设置列宽等属性
        vsb = ttk.Scrollbar(self.info_frame, orient="vertical", command=self.tree.yview)
        self.tree.bind("<Button-3>", lambda event: self.popupmenu(self.tree, event))
        self.tree.bind("<Double-Button-1>", self.show_communication)
        self.tree.grid(column=0, row=0)
        vsb.grid(column=1, row=0, sticky=tkinter.NS)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.tag_configure('diff', background=TREE_ROW_BG)
        self.add_work_tree.tag_configure('diff', background=TREE_ROW_BG)
        self.root.protocol("WM_DELETE_WINDOW", self.close_window)  # 绑定函数,触发窗口关闭会执行close_window

    def insert_add_tree(self, msg):
        _msg = "[{}]  {}".format(strftime('%Y-%m-%d %H:%M:%S'), msg)
        self.add_work_tree.insert('', -1, values=(_msg,))

    def submit_work_to_loop_thread(self, coroutine_name='async_work'):
        print('[{}][submit_work_to_loop_thread] current_thread: {}'.format(strftime('%Y-%m-%d %H:%M:%S'),
                                                                           current_thread()))
        asyncio.run_coroutine_threadsafe(
            self.im_user.handle_sync_callback(coroutine_name, callback=self.finished_callback),
            loop=self.loop
        )

    def finished_callback(self, result):
        print('[{}][finished_callback] current_thread: {}, result: {}'.format(strftime('%Y-%m-%d %H:%M:%S'),
                                                                              current_thread(), result))

    def logout(self):
        """
        退出当前登录的im user
        """
        # if self.im_user is None:
        #     messagebox.showwarning('warning', '当前未登录')
        #     return
        try:
            im_user = getattr(self, 'im_user')
        except Exception as e:
            self.debug('[logout]', e)
        else:
            if im_user is not None:
                im_user.slogout()  # 让线程退出
                loop = self.loop
                f = asyncio.run_coroutine_threadsafe(self.im_user.logout(), loop)  # 异步调用im_user的logout方法
                f.result()
                self.im_user.save_last_seq_id_and_timestamp()
                # self.im_user = None
                loop.call_later(5, loop.stop)
                # result = future.result()
                # self.loop = None
            else:
                if self.loop is not None:
                    self.loop.call_later(5, self.loop.stop)
                    # self.loop = None

            self.show_add_work()

    # def refuse_friend_group(self):
    #     """
    #     调用im user的accept_friend_group并弹窗显示结果
    #     """
    #     if self.im_user is None:
    #         messagebox.showwarning('warning', '当前未登录')
    #         return
    #     try:
    #         res1, res2 = self.im_user.refuse_friend_group()
    #     except Exception as e:
    #         messagebox.showerror('error', e)
    #     else:
    #         messagebox.showinfo('info', str(res1) + '\n' + str(res2))
    #
    # def accept_friend_group(self):
    #     """
    #     调用im user的accept_friend_group并弹窗显示结果
    #     """
    #     if self.im_user is None:
    #         messagebox.showwarning('warning', '当前未登录')
    #         return
    #     try:
    #         res1, res2 = self.im_user.accept_friend_group()
    #     except Exception as e:
    #         messagebox.showerror('error', e)
    #     else:
    #         messagebox.showinfo('info', str(res1) + '\n' + str(res2))

    def set_group_allow_invite(self, group_id, allow_invite_flag, parent):
        _r = self.im_user.set_group_allow_invite(group_id, allow_invite_flag)
        messagebox.showinfo('info', _r, parent=parent)

    def set_group_join_apply(self, group_id, need_apply_flag, parent):  # 群设置入群许可,入群需要群主或管理员同意
        _r = self.im_user.set_group_join_apply(group_id, need_apply_flag)
        messagebox.showinfo('info', _r, parent=parent)

    def set_group_all_mute(self, group_id, mute_status, parent):    # 设置群全员禁言
        _r = self.im_user.set_group_all_mute(group_id, mute_status)
        messagebox.showinfo('info', _r, parent=parent)

    def run_loop_thread(self, user_info):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        im_user = GUIIMUser(user_info, self.chat_room_pages, tree=self.tree)
        im_user.DEBUG = self.IM_USER_DEBUG
        im_user.INFO = self.IM_USER_INFO
        try:
            im_user.login_demo()
            im_user.login()
            _r = im_user.get_user_detail()
        except Exception as err:
            messagebox.showerror('error', err)
            im_user.slogout()
            self.login_status = False
            self.wdname = 'im_client'
            self.root.title(self.wdname)
            return
        else:
            self.debug('[run_loop_thread] no error')
            self.user_id = im_user.user_id
            self.wdname = _r['data']['nickname'] if _r['data']['nickname'] is not None else _r['data']['userId']
            self.root.title(self.wdname)
            try:
                user_head_img = im_user.get_user_head_photo_bytes()
            except Exception as _e:
                messagebox.showerror('error', _e)
                self.root.iconbitmap('default.ico')
            else:
                if user_head_img:
                    tmp_icon_path = str(time() * 1000) + '.icon'
                    with open(tmp_icon_path, 'wb') as fd:
                        fd.write(user_head_img)
                    img2ico(tmp_icon_path, tmp_icon_path)
                    self.root.iconbitmap(tmp_icon_path)
                    os.remove(tmp_icon_path)
                else:
                    self.root.iconbitmap('default.ico')

        self.loop = loop
        self.im_user = im_user
        # self.im_user.phone = self.phone  # 设置手机号， 用于登录demo
        tasks = list()
        tasks.append(im_user.build_connection())
        tasks.append(im_user.handle_read())
        # tasks.append(im_user.write_thread())
        tasks.append(im_user.heartbeat_thread())
        self.show_info()
        try:
            loop.run_until_complete(asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION))
        except Exception as e:
            self.debug('[run_loop_thread] ', e)
            try:
                messagebox.showerror('warning', e)
            except:
                pass
        self.info('[run_loop_thread] 事件循环完毕')
        self.exit_flag = True
        self.login_status = False
        if self.im_user and self.im_user.err_msg is not None:
            try:
                messagebox.showerror('error', self.im_user.err_msg)
            except Exception:
                pass
        self.im_user = None
        self.wdname = 'im_client'
        # self.root.title(self.wdname)
        try:
            self.insert_add_tree('[logout]')
            self.root.title(self.wdname)
        except Exception as e1:
            self.info('[run_loop_thread] ', e1)
        self.im_user = None
        self.user_id = ''
        self.user_name = ''
        self.phone = ''
        self.pwd = ''
        self.debug('[run_loop_thread] exit')

    def run_user(self, user_name=None, pwd=None):
        """
        登录一个im user
        """
        self.debug('run_user')
        self.exit_flag = False
        if not self.login_status:
            try:
                if user_name is None:
                    user_name = self.username_entry.get()
                    self.insert_add_tree('[初始化] [{}]\t[{}]'.format('user_id', user_name))
                if pwd is None:
                    pwd = self.pwd_entry.get()
                    self.insert_add_tree('[初始化] [{}]\t[{}]'.format('pwd', pwd))
                self.debug('[run_user]', user_name, pwd)
                if not user_name or not pwd:
                    messagebox.showerror('error', '[run user] 空的输入!')
                    return
                user_info = {
                    'app_id': self.app_id,
                    'pwd': pwd,
                    'phone': user_name
                }
                t = Thread(target=self.run_loop_thread, args=(user_info,))
                t.start()
            except Exception as e:
                self.insert_add_tree('[登录失败]\t' + str(e))
                messagebox.showerror('error', '[run user] ' + str(e))
                self.wdname = 'im_client'
                self.root.title(self.wdname)
            else:
                self.root.title('登陆中')
                self.wdname = '登陆中'
                self.login_status = True
                self.user_id = user_name
                self.pwd = pwd
                self.insert_add_tree('[登录成功]')
        else:
            messagebox.showwarning('warning', '已经登录')

    def show_info(self):
        self.debug('show_info')
        if not self.im_user:
            messagebox.showwarning('warning', '当前未登录')
        else:
            self.add_frame.grid_forget()
            self.info_frame.grid()

    def show_add_work(self):
        self.debug('show_add_work')
        self.info_frame.grid_forget()
        self.add_frame.grid()

    def set_user_black_list_by_type(self, _top, _tree, old_menu_bar, operation, before_user_black_list):
        self.debug('set_user_black_list_by_type')
        selected_item_list = _tree.selection()  # 返回的是选中的id list
        selected_user_list = []
        for _item in selected_item_list:
            user_id = _tree.item(_item, 'values')[0]
            selected_user_list.append(user_id)
        if len(selected_user_list) == 0:
            if operation == 'add':
                for x in _tree.get_children():
                    _tree.delete(x)
                for user_id in before_user_black_list:
                    _tree.insert('', 'end', values=(user_id, self.im_user.get_nickname(user_id)))
            _top.config(menu=old_menu_bar)
        else:
            try:
                _r = self.im_user.set_friend_black_list(','.join(selected_user_list), operation)
            except Exception as _e:
                messagebox.showerror('error', _e, parent=_top)
                return
            else:
                messagebox.showinfo('info', _r, parent=_top)
                if _r['code'] == '0':
                    _top.config(menu=old_menu_bar)
                    if operation == 'add':
                        for x in _tree.get_children():
                            if _tree.item(x, 'values')[0] in selected_user_list:
                                pass
                            else:
                                _tree.delete(x)
                        for user_id in before_user_black_list:
                            _tree.insert('', 'end', values=(user_id, self.im_user.get_nickname(user_id)))
                    elif operation == 'remove':
                        for x in _tree.get_children():
                            if _tree.item(x, 'values')[0] in selected_user_list:
                                _tree.delete(x)

    def update_user_black_list_by_type(self, _top, _tree, old_menu_bar, operation):
        self.debug('[update_user_black_list_by_type]')
        before_user_black_list = []
        for x in _tree.get_children():
            before_user_black_list.append(_tree.item(x, 'values')[0])
        if operation == 'add':
            for x in _tree.get_children():
                _tree.delete(x)
            # 展示不在黑名单中的好友
            for _user_id in self.im_user.friend_id_list:
                if _user_id not in before_user_black_list:
                    _tree.insert('', 0, values=(_user_id, self.im_user.get_nickname(_user_id)))
        new_menu_bar = tkinter.Menu(_top)
        new_menu_bar.add_command(label="完成",
                                 command=lambda: self.set_user_black_list_by_type(_top, _tree, old_menu_bar, operation,
                                                                                  before_user_black_list))
        new_menu_bar.add_command(label="重新选择", command=lambda: clean_selection(_tree))
        _top.config(menu=new_menu_bar)

    def show_friend_black_list(self, parent_top):
        self.debug('[show_friend_black_list]')
        sub_top_obj = SubTop('通讯录黑名单', parent_top)
        top = sub_top_obj.get_handle()

        _r = self.im_user.get_user_black_list()
        tree = ttk.Treeview(top, columns=['user_id', 'nickname'], height=18, show="headings")
        tree.heading("user_id", text="用户ID")  # 设置表头
        tree.heading("nickname", text="用户昵称")  # 设置表头

        menu_bar = tkinter.Menu(top)
        menu_bar.add_command(label="增加",
                             command=lambda: self.update_user_black_list_by_type(top, tree, menu_bar, 'add'))
        menu_bar.add_command(label="删除",
                             command=lambda: self.update_user_black_list_by_type(top, tree, menu_bar, 'remove'))
        top.config(menu=menu_bar)

        for _info in _r['data']:
            tree.insert('', 0, values=(_info['userId'], _info['nickname']))
        tree.grid()
        sub_top_obj.show()

    def set_user_head_photo(self, top):
        pic = tkinter.filedialog.askopenfilename(parent=top)
        self.debug('[set_user_head_photo]', pic, len(pic))
        if pic:
            if os.path.isfile(pic):
                if os.path.splitext(pic)[-1].lower() in {'.png', '.jpg', '.jpeg', '.gif', '.jfif'}:
                    if self.im_user is not None:
                        _r = self.im_user.set_user_head_photo(pic)
                        messagebox.showinfo('info', _r, parent=top)
                else:
                    messagebox.showwarning('warning', '请选择图片格式', parent=top)
            else:
                messagebox.showwarning('warning', '非文件类型', parent=top)

    def set_user_sex(self, parent_top, sex_type: str):
        """
        :param parent_top:
        :param sex_type: 1为男，2为女
        :return:
        """
        self.debug('[set_user_sex]')
        try:
            res = self.im_user.set_user_baseinfo(sex=sex_type)
        except Exception as _e:
            messagebox.showerror('error', _e, parent=parent_top)
        else:
            messagebox.showinfo('info', res, parent=parent_top)

    def set_group_avatar(self, group_id, window):
        avatar_path = filedialog.askopenfilename(parent=window)
        if avatar_path and os.path.splitext(avatar_path)[-1].lower() in {'.jpg', '.png', '.jiff', '.gif', '.jpeg', '.jfif'}:
            try:
                res = self.im_user.set_group_avatar(group_id, avatar_path)
            except Exception as e:
                messagebox.showerror('error', e, parent=window)
            else:
                messagebox.showinfo('info', res, parent=window)
        elif avatar_path:
            messagebox.showwarning('warning', '请选择正确的图片文件!', parent=window)

    def set_auto_add_friend_accept(self, window, status: bool):
        """
        设置自动加好友
        :param window:
        :param status: bool
        :return:
        """
        try:
            if status:
                _r = self.im_user.set_auto_add_friend_accept('true')
            else:
                _r = self.im_user.set_auto_add_friend_accept('false')
        except Exception as _e:
            messagebox.showerror('error', _e, parent=window)
        else:
            if 'code' in _r and _r['code'] == '0':
                self.im_user.autoAcceptFriendInvitation = status
            messagebox.showinfo('info', _r, parent=window)

    def set_group_auto_accept(self, window, status: bool):
        """
        设置自动入群
        :param window:
        :param status: bool
        :return:
        """
        try:
            if status:
                _r = self.im_user.set_group_auto_accept('true')
            else:
                _r = self.im_user.set_group_auto_accept('false')
        except Exception as _e:
            messagebox.showerror('error', _e, parent=window)
        else:
            if 'code' in _r and _r['code'] == '0':
                self.im_user.autoAcceptGroupInvitation = status
            messagebox.showinfo('info', _r, parent=window)

    def user_setting(self):

        def close_user_setting_window(_father):
            self.user_setting_flag = True
            _father.destroy()

        def save_user_setting():
            new_nickname = nickname_entry.get()
            try:
                res = self.im_user.set_user_baseinfo(nickname=new_nickname)
            except Exception as _e:
                res = _e
            else:
                if res['code'] == '0':
                    self.root.title(new_nickname)
                    self.wdname = new_nickname
            messagebox.showinfo('info', res, parent=top)

        self.debug('[user_setting]')
        if not self.im_user:
            messagebox.showwarning('warning', '当前未登录')
            return
        if self.user_setting_flag:
            self.user_setting_flag = False
            top_obj = SubTop('用户设置', self.root)
            top = top_obj.get_handle()
            top.iconbitmap(self.ICO_PATH)

            menu_bar = tkinter.Menu(top)
            menu_bar.add_command(label="通讯录黑名单", command=lambda: self.show_friend_black_list(top))
            menu_bar.add_command(label="设置头像", command=lambda: self.set_user_head_photo(top))
            # menu_bar.add_command(label="我的二维码", command=lambda: self.show_qrcode(top))
            top.config(menu=menu_bar)

            _res = self.im_user.get_user_detail()
            _row = 0
            for k, v in _res['data'].items():
                _label = tkinter.Label(top, width=40, text='{}: '.format(k))
                val_obj = tkinter.StringVar(top, value=v)
                if k == 'nickname' or k == 'avatar':
                    _entry = tkinter.Entry(top, width=40, textvariable=val_obj)
                    if k == 'nickname':
                        nickname_entry = _entry
                    _label.grid(row=_row, column=0)
                    _entry.grid(row=_row, column=1, columnspan=2)
                elif k == 'sex':
                    invite_val = tkinter.IntVar()
                    invite_man_radio = tkinter.Radiobutton(top, value=1, text="男", variable=invite_val, command=lambda: self.set_user_sex(top, '1'))
                    invite_woman_radio = tkinter.Radiobutton(top, value=2, text="女", variable=invite_val, command=lambda: self.set_user_sex(top, '2'))
                    if _res['data']['sex'] == '1':
                        invite_val.set(1)
                    elif _res['data']['sex'] == '2':
                        invite_val.set(2)

                    _label.grid(row=_row, column=0)
                    invite_man_radio.grid(row=_row, column=1)
                    invite_woman_radio.grid(row=_row, column=2)
                else:
                    _entry = tkinter.Entry(top, state='disabled', width=40, textvariable=val_obj)
                    _label.grid(row=_row, column=0)
                    _entry.grid(row=_row, column=1, columnspan=2)
                _row += 1

            auto_add_friend_val = tkinter.IntVar()
            auto_add_friend_val.set(1) if self.im_user.autoAcceptFriendInvitation else auto_add_friend_val.set(0)
            auto_add_friend_label = tkinter.Label(top, width=40, text='自动加好友:')
            auto_add_friend_true_radio = tkinter.Radiobutton(top, value=1, text="开启", variable=auto_add_friend_val, command=lambda: self.set_auto_add_friend_accept(top, True))
            auto_add_friend_false_radio = tkinter.Radiobutton(top, value=0, text="关闭", variable=auto_add_friend_val, command=lambda: self.set_auto_add_friend_accept(top, False))
            auto_add_friend_label.grid(row=_row, column=0)
            auto_add_friend_true_radio.grid(row=_row, column=1)
            auto_add_friend_false_radio.grid(row=_row, column=2)
            _row += 1

            auto_add_group_val = tkinter.IntVar()
            auto_add_group_val.set(1) if self.im_user.autoAcceptGroupInvitation else auto_add_group_val.set(0)
            auto_add_group_label = tkinter.Label(top, width=40, text='自动入群:')
            auto_add_group_true_radio = tkinter.Radiobutton(top, value=1, text="开启", variable=auto_add_group_val, command=lambda: self.set_group_auto_accept(top, True))
            auto_add_group_false_radio = tkinter.Radiobutton(top, value=0, text="关闭", variable=auto_add_group_val, command=lambda: self.set_group_auto_accept(top, False))
            auto_add_group_label.grid(row=_row, column=0)
            auto_add_group_true_radio.grid(row=_row, column=1)
            auto_add_group_false_radio.grid(row=_row, column=2)
            _row += 1

            button = tkinter.Button(top, text='修改昵称', width=20, command=save_user_setting)
            button.grid(row=_row, column=0, columnspan=3)
            _row += 1

            top.protocol("WM_DELETE_WINDOW", lambda: close_user_setting_window(top))
            top.overrideredirect(False)
            top.resizable(0, 0)

            top_obj.show()
        else:
            try:
                hwnd = win32gui.FindWindow(None, '用户设置')
                win32gui.SetForegroundWindow(hwnd)
            except Exception as e:
                messagebox.showerror('error', e)

    def setting(self):
        self.debug('setting')

        def save_setting():
            old_cfg = load_json_from_file(self.CFG_PATH)
            if old_cfg is None:
                old_cfg = {}
            old_cfg['app_id'] = app_id_entry.get()
            # old_cfg['user_id'] = user_id_entry.get()
            old_cfg['pwd'] = pwd_entry.get()
            old_cfg['msg_sleep_time'] = float(msg_sleep_time_entry.get())
            old_cfg['phone'] = phone_entry.get()
            # old_cfg['user_name'] = user_name_entry.get()
            old_cfg['auto_login'] = True if auto_login_val.get() else False

            old_cfg['DEBUG'] = True if gui_debug_val.get() else False

            old_cfg['IM_USER_DEBUG'] = True if im_user_debug_val.get() else False

            for _k in old_cfg:
                if _k == 'user_id':  # 跳过user_id设置
                    continue
                if _k == 'IM_USER_DEBUG':
                    if self.im_user is not None:
                        setattr(self.im_user, 'DEBUG', old_cfg[_k])
                        setattr(self, _k, old_cfg[_k])
                else:
                    setattr(self, _k, old_cfg[_k])

            add_json_to_file(old_cfg, self.CFG_PATH)
            close_setting_window(top)

        def close_setting_window(_father):
            self.setting_flag = True
            _father.destroy()

        if self.setting_flag:
            self.setting_flag = False

            cfg = load_json_from_file(self.CFG_PATH)
            self.debug('[setting]', cfg)

            sub_top_obj = SubTop('本地设置', self.root)
            top = sub_top_obj.get_handle()

            top.overrideredirect(True)
            top.iconbitmap(self.ICO_PATH)

            if cfg is not None:

                # if 'user_id' in cfg:
                #     user_id = tkinter.StringVar(top, value=cfg['user_id'])
                # else:
                #     user_id = tkinter.StringVar(top, value=self.user_id)

                if 'app_id' in cfg:
                    app_id = tkinter.StringVar(top, value=cfg['app_id'])
                else:
                    app_id = tkinter.StringVar(top, value=self.app_id)

                if 'pwd' in cfg:
                    pwd = tkinter.StringVar(top, value=cfg['pwd'])
                else:
                    pwd = tkinter.StringVar(top, value=self.pwd)
                if 'phone' in cfg:
                    phone = tkinter.StringVar(top, value=cfg['phone'])
                else:
                    phone = tkinter.StringVar(top, value=self.phone)
                # if 'user_name' in cfg:
                #     user_name = tkinter.StringVar(top, value=cfg['user_name'])
                # else:
                #     user_name = tkinter.StringVar(top, value=self.user_name)
                if 'msg_sleep_time' in cfg:
                    msg_sleep_time = tkinter.StringVar(top, value=cfg['msg_sleep_time'])
                else:
                    msg_sleep_time = tkinter.StringVar(top, value=self.msg_sleep_time)

                auto_login_val = tkinter.IntVar(top)
                if 'auto_login' in cfg and cfg['auto_login']:
                    auto_login_val.set(1)
                else:
                    auto_login_val.set(self.auto_login)

                gui_debug_val = tkinter.IntVar(top)
                if 'DEBUG' in cfg:
                    gui_debug_val.set(1) if cfg['DEBUG'] else gui_debug_val.set(0)
                else:
                    gui_debug_val.set(self.DEBUG)

                im_user_debug_val = tkinter.IntVar(top)
                if 'IM_USER_DEBUG' in cfg:
                    im_user_debug_val.set(1) if cfg['IM_USER_DEBUG'] else im_user_debug_val.set(0)
                else:
                    im_user_debug_val.set(self.IM_USER_DEBUG)
            else:
                # user_id = tkinter.StringVar(top, value=self.user_id)
                app_id = tkinter.StringVar(top, value=self.app_id)
                pwd = tkinter.StringVar(top, value=self.pwd)
                phone = tkinter.StringVar(top, value=self.phone)
                # user_name = tkinter.StringVar(top, value=self.user_name)
                msg_sleep_time = tkinter.StringVar(top, value=self.msg_sleep_time)
                auto_login_val = tkinter.IntVar(top)
                auto_login_val.set(self.auto_login)
                gui_debug_val = tkinter.IntVar(top)
                gui_debug_val.set(self.DEBUG)
                im_user_debug_val = tkinter.IntVar(top)
                im_user_debug_val.set(self.IM_USER_DEBUG)

            app_id_label = tkinter.Label(top, width=40, text='appid: ')
            app_id_entry = tkinter.Entry(top, width=40, textvariable=app_id)

            # user_id_label = tkinter.Label(top, width=40, text='userid: ')
            # user_id_entry = tkinter.Entry(top, width=40, textvariable=user_id)

            # user_name_label = tkinter.Label(top, width=40, text='user_name: ')
            # user_name_entry = tkinter.Entry(top, width=40, textvariable=user_name)

            phone_label = tkinter.Label(top, width=40, text='phone: ')
            phone_entry = tkinter.Entry(top, width=40, textvariable=phone)

            pwd_label = tkinter.Label(top, width=40, text='pwd: ')
            pwd_entry = tkinter.Entry(top, width=40, textvariable=pwd)

            msg_sleep_time_label = tkinter.Label(top, width=40, text='msg_sleep_time: ')
            msg_sleep_time_entry = tkinter.Entry(top, width=40, textvariable=msg_sleep_time)

            auto_login_label = tkinter.Label(top, text='auto login: ')
            auto_login_true_radio = tkinter.Radiobutton(top, value=1, text="开启", variable=auto_login_val)
            auto_login_false_radio = tkinter.Radiobutton(top, value=0, text="关闭", variable=auto_login_val)

            gui_debug_label = tkinter.Label(top, text='gui_debug: ')
            gui_debug_true_radio = tkinter.Radiobutton(top, value=1, text="开启", variable=gui_debug_val)
            gui_debug_false_radio = tkinter.Radiobutton(top, value=0, text="关闭", variable=gui_debug_val)

            im_user_debug_label = tkinter.Label(top, text='im_user_debug: ')
            im_user_debug_true_radio = tkinter.Radiobutton(top, value=1, text="开启", variable=im_user_debug_val)
            im_user_debug_false_radio = tkinter.Radiobutton(top, value=0, text="关闭", variable=im_user_debug_val)

            app_id_label.grid(row=0, column=0)
            app_id_entry.grid(row=0, column=1, columnspan=2)

            # user_id_label.grid(row=1, column=0)
            # user_id_entry.grid(row=1, column=1, columnspan=2)

            # user_name_label.grid(row=2, column=0)
            # user_name_entry.grid(row=2, column=1, columnspan=2)

            phone_label.grid(row=1, column=0)
            phone_entry.grid(row=1, column=1, columnspan=2)

            pwd_label.grid(row=2, column=0)
            pwd_entry.grid(row=2, column=1, columnspan=2)

            msg_sleep_time_label.grid(row=3, column=0)
            msg_sleep_time_entry.grid(row=3, column=1, columnspan=2)

            auto_login_label.grid(row=4, column=0)
            auto_login_true_radio.grid(row=4, column=1)
            auto_login_false_radio.grid(row=4, column=2)

            gui_debug_label.grid(row=5, column=0)
            gui_debug_true_radio.grid(row=5, column=1)
            gui_debug_false_radio.grid(row=5, column=2)

            im_user_debug_label.grid(row=6, column=0)
            im_user_debug_true_radio.grid(row=6, column=1)
            im_user_debug_false_radio.grid(row=6, column=2)

            button = tkinter.Button(top, text='保存', width=20, command=save_setting)
            button.grid(row=7, column=0, columnspan=3)

            top.protocol("WM_DELETE_WINDOW", lambda: close_setting_window(top))
            top.overrideredirect(False)
            top.resizable(0, 0)

            sub_top_obj.show()
        else:
            try:
                hwnd = win32gui.FindWindow(None, '本地设置')
                win32gui.SetForegroundWindow(hwnd)
            except Exception as e:
                messagebox.showerror('error', e)

    def close_window(self):

        def tmp_close():
            try:
                self.debug('[tmp_close] start destroy')
                self.root.destroy()
                self.debug('[tmp_close] destroy')
                sleep(5)
                self.root.quit()
                self.debug('[close_window][tmp_close] window quit success!')
            except Exception as error:
                self.debug('[close_window][tmp_close]', error)

        # ans = messagebox.askyesno('info', '是否退出')
        ans = True
        if ans:
            self.logout()
            self.exit_flag = True
            if os.path.exists(self.RUNTIME_FILE):
                os.remove(self.RUNTIME_FILE)
            t = Thread(target=tmp_close)
            t.daemon = True
            t.start()

    def clean_msg(self):
        if self.im_user is None:
            messagebox.showwarning('warning', '当前未登录')
            return
        self.debug('[clean_msg]')
        if self.im_user is not None:
            self.im_user.clean_msg()
        x = self.tree.get_children()
        for item in x:
            # print(item)
            self.tree.delete(item)

    def load_from_cfg(self):
        self.debug('[load_from_cfg]')
        cfg_dict = load_json_from_file(self.CFG_PATH)
        # print(cfg_dict)
        if cfg_dict:
            for _k in cfg_dict:
                setattr(self, _k, cfg_dict[_k])
                self.insert_add_tree('[初始化] [{}]\t[{}]'.format(_k, cfg_dict[_k]))
                if _k == 'phone':
                    self.username_variable.set(cfg_dict[_k])
                elif _k == 'pwd':
                    self.pwd_variable.set(cfg_dict[_k])
            if self.auto_login:
                self.run_user(cfg_dict['phone'], cfg_dict['pwd'])
        with open(self.RUNTIME_FILE, 'w+') as fd:
            fd.write('1')

    def send_msg(self, to_id, comm_id, comm_type, msg_type, count):
        im_user = getattr(self, 'im_user')
        loop = self.loop
        self.debug('[send_msg] self.msg_sleep_time: ', self.msg_sleep_time)
        future = asyncio.run_coroutine_threadsafe(
            im_user.send_chat_msg(to_id, comm_id, comm_type, msg_type, count, self.msg_sleep_time), loop)
        # self.debug('[send_msg]', future.result())

    def send_customize_msg(self, parent_window, to_id, comm_id, comm_type, msg_type, count):
        def _run_coroutine():
            content = text_entry.get()
            self.debug('[send_customize_msg]', len(content))
            if len(content) > 0:
                text_entry.delete(0, 'end')
                im_user = getattr(self, 'im_user')
                loop = self.loop
                self.debug('[send_msg] self.msg_sleep_time: ', self.msg_sleep_time)
                future = asyncio.run_coroutine_threadsafe(
                    im_user.send_chat_msg(to_id, comm_id, comm_type, msg_type, count, self.msg_sleep_time, content_msg=content), loop)
                tree.insert('', 'end', values=('', content))
        if comm_type == '1':
            window_name = self.im_user.get_nickname(to_id)
        elif comm_type == '2':
            window_name = self.im_user.get_group_name(comm_id)
        else:
            raise Exception('unknow type: {}'.format(comm_type))
        sub_top_obj = SubTop(window_name, parent_window)
        sub_top = sub_top_obj.get_handle()
        tree = ttk.Treeview(sub_top, columns=['', 'info'], height=18, show="headings")
        tree.grid(row=0, column=0, columnspan=2)
        text_entry = tkinter.Entry(sub_top, width=45)
        button = tkinter.Button(sub_top, text='发送', command=_run_coroutine)
        text_entry.grid(row=1, column=0)
        button.grid(row=1, column=1)
        sub_top_obj.show()

    def send_custom_msg(self, to_id, comm_id, comm_type, sub_msg_type, times):
        im_user = getattr(self, 'im_user')
        loop = self.loop
        self.debug('[send_custom_msg] self.msg_sleep_time: ', self.msg_sleep_time)
        future = asyncio.run_coroutine_threadsafe(
            im_user.send_custom_msg(to_id, comm_id, comm_type, sub_msg_type, times, self.msg_sleep_time), loop)

    def send_redpacket(self, parent_top, amount, conversation_id, conversation_type, count, to_ids, _type):
        if type(conversation_type) == str:
            conversation_type = int(conversation_type)
        if conversation_type == 2:  # 群红包
            group_user_list_res = self.im_user.get_group_user_list(conversation_id)
            to_ids = ','.join([_i['userId'] for _i in group_user_list_res['data']])
            count = 5
        else:
            count = 1
        _res = self.im_user.send_redpacket(amount, conversation_id, conversation_type, count, to_ids, _type)
        messagebox.showinfo('info', _res, parent=parent_top)

    def show_friend_list(self):
        self.debug('[show_friend_list]')

        def close_friend_list_window(father):
            self.show_friend = True
            father.destroy()

        def delete_multi_friend(top_tree):
            select_item = top_tree.selection()
            res_list = []
            for _item in select_item:
                _id = top_tree.item(_item, 'values')[1]
                _res = self.im_user.del_friend(_id)
                res_list.append(_res)
            all_count = 0
            error_count = 0
            success_count = 0
            for _res in res_list:
                all_count += 1
                if _res['code'] == '0':
                    success_count += 1
                else:
                    error_count += 1
            messagebox.showinfo('info', '一共{}个请求,成功{}个， 失败{}个'.format(all_count, success_count, error_count),
                                parent=top_tree)

        def delete_friend(dst_id, top_tree):
            try:
                _res = self.im_user.del_friend(dst_id)
            except Exception as error:
                messagebox.showerror('error', error, parent=top)
            else:
                tree_children_list = top_tree.get_children()  # 获取行对象
                for item in tree_children_list:
                    _id = tree.item(item, "values")[1]
                    if _id == dst_id:
                        top_tree.delete(item)
                        break
                messagebox.showinfo('info', _res, parent=top)

        def add_friend(id_entry: tkinter.Entry, sub_top: tkinter.Toplevel, top_tree: ttk.Treeview):
            _id = id_entry.get()
            self.debug('[add_friend]', _id)
            if _id == '':
                messagebox.showwarning('warning', '输入为空', parent=sub_top)
            else:
                try:
                    _res = self.im_user.add_friend(_id)
                except Exception as error:
                    messagebox.showerror('error', error, parent=sub_top)
                else:
                    if _res['code'] == '0':
                        top_tree.insert('', 0, values=('', _id, '', 1))
                        messagebox.showinfo('info', _res, parent=sub_top)
                        sub_top.destroy()
                    else:
                        messagebox.showwarning('warning', _res, parent=sub_top)

        def show_add_friend():
            sub_top_obj = SubTop('添加好友', top)
            sub_top = sub_top_obj.get_handle()
            sub_top.resizable(0, 0)
            user_id_label = tkinter.Label(sub_top, text='用户id', width=25)
            user_id_label.grid(row=0, column=0, sticky=tkinter.W)  # 左对齐
            user_id_entry = tkinter.Entry(sub_top, width=50)
            user_id_entry.grid(row=0, column=1)  # 左对齐
            button = tkinter.Button(sub_top, text="添加", command=lambda: add_friend(user_id_entry, sub_top, tree))
            button.grid(row=1, column=0, columnspan=2)

            sub_top_obj.show()

        def post_send_single_msg_menu(father, event, parent_window):
            menu = tkinter.Menu(father, tearoff=0)
            text_menu = tkinter.Menu(father, tearoff=0)
            file_menu = tkinter.Menu(father, tearoff=0)
            img_menu = tkinter.Menu(father, tearoff=0)
            video_menu = tkinter.Menu(father, tearoff=0)
            audio_menu = tkinter.Menu(father, tearoff=0)
            location_menu = tkinter.Menu(father, tearoff=0)
            red_packet_menu = tkinter.Menu(father, tearoff=0)
            read_destroy_menu = tkinter.Menu(father, tearoff=0)
            emoji_menu = tkinter.Menu(father, tearoff=0)
            card_menu = tkinter.Menu(father, tearoff=0)

            selected_item_list = father.selection()
            selected_item_list_len = len(selected_item_list)
            if selected_item_list_len == 1:
                cur_item = father.focus()
                if cur_item != '':
                    _info = father.item(cur_item, 'values')
                    # print(_info)
                    name = _info[0]
                    if type(name) == int:
                        name = str(name)
                    new_name = name
                    if len(new_name) > 23:
                        new_name = name[0:21] + '...'
                    menu.add_command(label=new_name)
                    menu.add_separator()
                    try:
                        _nickname, _to_id, _comm_id, _comm_type = _info
                    except Exception as _e:
                        return
                    if type(_to_id) == int:
                        _to_id = str(_to_id)

                    for _menu, msg_type, menu_content in zip((text_menu, file_menu, img_menu, video_menu, audio_menu, location_menu, read_destroy_menu, emoji_menu), (1, 3, 4, 6, 5, 7, -1, 2), ('文本消息', '文件消息', '图片消息', '视频消息', '语音消息', '位置消息', '阅后即焚消息', '表情消息')):
                        _menu.add_command(label=menu_content)
                        _menu.add_separator()
                        for i in (1, 10, 50, 200, 500, 1000, 2000, 5000, 10000):
                            _menu.add_command(label=f"发送{i}条消息", command=lambda to_id=_to_id, comm_id=_comm_id, comm_type=_comm_type, msg_type=msg_type, times=i: self.send_msg(to_id, comm_id, comm_type, msg_type, times))  # 增加菜单栏
                    text_menu.add_command(label="发送自定义消息", command=lambda to_id=_to_id, comm_id=_comm_id, comm_type=_comm_type: self.send_customize_msg(parent_window, to_id, comm_id, comm_type, 1, 1))

                    card_menu.add_command(label='名片消息')
                    card_menu.add_separator()
                    for i in (1, 10, 50, 100, 1000, 2000, 5000, 10000):
                        card_menu.add_command(label=f"发送{i}条消息",
                                              command=lambda to_id=_to_id, comm_id=_comm_id, comm_type=1, times=i: self.send_custom_msg(to_id, comm_id, comm_type, 'card', times))  # 增加菜单栏

                    red_packet_menu.add_command(label='红包消息')
                    red_packet_menu.add_separator()
                    red_packet_menu.add_command(
                        label="发送1个红包",
                        command=lambda to_id=_to_id, comm_id=_comm_id, comm_type=_comm_type: self.send_redpacket(father, 0.1, comm_id, comm_type, 1, to_id, 2)
                    )  # 增加菜单栏

                    menu.add_cascade(label='发送文本消息', menu=text_menu)
                    menu.add_cascade(label='发送图片消息', menu=img_menu)
                    menu.add_cascade(label='发送文件消息', menu=file_menu)
                    menu.add_cascade(label='发送视频消息', menu=video_menu)
                    menu.add_cascade(label='发送语音消息', menu=audio_menu)
                    menu.add_cascade(label='发送位置消息', menu=location_menu)
                    menu.add_cascade(label='发送阅后即焚消息', menu=read_destroy_menu)
                    menu.add_cascade(label='发送表情消息', menu=emoji_menu)
                    menu.add_cascade(label='发送名片消息', menu=card_menu)
                    menu.add_cascade(label='发送红包消息', menu=red_packet_menu)
                    menu.add_command(label='删除好友', command=lambda: delete_friend(_to_id, tree))
            elif selected_item_list_len > 1:
                work_name_list = []
                for _item in selected_item_list:
                    item = father.item(_item)
                    work_name_list.append(item['values'][0])  # work name
                menu.add_command(label='当前选中{}个对象'.format(selected_item_list_len))
                menu.add_separator()
                text_menu.add_command(label="发送1条消息", command=lambda: self.send_msg_multi(father, 1, 'single'))  # 增加菜单栏
                text_menu.add_command(label="发送10条消息", command=lambda: self.send_msg_multi(father, 10, 'single'))
                text_menu.add_command(label="发送50条消息", command=lambda: self.send_msg_multi(father, 50, 'single'))
                text_menu.add_command(label="发送200条消息", command=lambda: self.send_msg_multi(father, 200, 'single'))
                text_menu.add_command(label="发送500条消息", command=lambda: self.send_msg_multi(father, 500, 'single'))
                text_menu.add_command(label="发送1000条消息", command=lambda: self.send_msg_multi(father, 1000, 'single'))
                text_menu.add_command(label="发送2000条消息", command=lambda: self.send_msg_multi(father, 2000, 'single'))
                text_menu.add_command(label="发送5000条消息", command=lambda: self.send_msg_multi(father, 5000, 'single'))
                text_menu.add_command(label="发送20000条消息", command=lambda: self.send_msg_multi(father, 20000, 'single'))
                menu.add_cascade(label='发送文本消息', menu=text_menu)
                menu.add_command(label='删除选中的好友', command=lambda: delete_multi_friend(tree))
            menu.post(event.x_root, event.y_root)

        if self.im_user is None:
            messagebox.showwarning('warning', '当前未登录')
            return
        if self.show_friend is False:
            try:
                hwnd = win32gui.FindWindow(None, '好友列表')
                win32gui.SetForegroundWindow(hwnd)
            except Exception as e:
                messagebox.showerror('error', e)
            return

        try:
            getattr(self, 'im_user')
            # res = im_user.get_friend_list()
        except Exception as e:
            messagebox.showerror('error', e)
        else:
            self.show_friend = False

            top_obj = SubTop('好友列表', self.root)
            top = top_obj.get_handle()

            menu_bar = tkinter.Menu(top)
            menu_bar.add_command(label="添加好友", command=show_add_friend)
            top.config(menu=menu_bar)
            col = ['nickname', 'user_id', 'comm_id', 'comm_type']
            ttk.Style().configure('friend_list.Treeview', rowheight=55)
            tree = ttk.Treeview(top, columns=col, height=12, style='friend_list.Treeview')
            tree.heading("nickname", text="昵称")  # 设置表头
            tree.heading("user_id", text="ID")  # 设置表头
            tree.heading("comm_id", text="会话ID")  # 设置表头
            tree.heading("comm_type", text="会话类型")
            tree.column("comm_type", width=60)  # 设置列宽等属性
            tree.column("#0", width=80)  # 设置列宽等属性
            vsb = ttk.Scrollbar(top, orient="vertical", command=tree.yview)
            tree.bind("<Button-3>", lambda event: post_send_single_msg_menu(tree, event, top))
            tree.grid(column=0, row=0)
            vsb.grid(column=1, row=0, sticky=tkinter.NS)
            tree.config(yscrollcommand=vsb.set)  # 绑定设置滚动条

            img_obj_dict = {}

            id_name = [[_i, self.im_user.get_nickname(_i)] for _i in self.im_user.friend_id_list]
            id_name = sorted(id_name, key=lambda x: x[1], reverse=True)
            for _i, _name in id_name:
                val = (
                    _name,
                    _i,
                    self.im_user.get_friend_communication(_i),
                    1
                )
                try:
                    friend_img_head = self.im_user.get_user_head_photo_bytes(_i)
                except Exception as _e:
                    tree.insert('', 0, values=val)
                    # messagebox.showerror('error', _e, parent=self.root)
                else:
                    if friend_img_head:
                        try:
                            photo = Image.open(BytesIO(friend_img_head))
                            photo = photo.resize((50, 50))
                            img0 = ImageTk.PhotoImage(photo)
                            img_obj_dict[_i] = img0
                        except Exception as _e:
                            tree.insert('', 0, values=val)
                        else:
                            tree.insert('', 0, image=img_obj_dict[_i], values=val)
                    else:
                        tree.insert('', 0, values=val)
            top.resizable(0, 0)
            top.protocol("WM_DELETE_WINDOW", lambda: close_friend_list_window(top))

            top_obj.show()

    def show_communication(self, event):
        self.debug('[show_communication]')

        def show_msg_detail(window, msg):
            sub_top_obj = SubTop('消息详情', window)
            sub_top = sub_top_obj.get_handle()
            text = tkinter.Text(sub_top)
            json_str = json.dumps(msg, indent=4, ensure_ascii=False)
            text.insert('end', json_str)
            text.grid()
            sub_top_obj.show()

        def msg_operate(_event, msg_top, msg_tree, comm_id):
            focus_item = msg_tree.focus()  # 返回的是选中行的id号，字符串类型
            values = msg_tree.item(focus_item, 'values')  # 根据id号获取行对象
            if focus_item == '':    # 没有聚焦到treeview
                return
            _msg_id = values[1]
            msg_index = msg_id_dict[_msg_id]
            msg = self.im_user.communication_msg[comm_id][msg_index]
            if 'message_id' in msg:
                _k = 'message_type'
                msg_from_user_id = msg['from_user_id']
                _msg_id = msg['message_id']
                # msg_to_user_id = msg['to_user_id']
            else:
                _k = 'messageType'
                msg_from_user_id = msg['fromUserId']
                _msg_id = msg['messageId']
                # msg_to_user_id = msg['toUserId']

            menu = tkinter.Menu(msg_top, tearoff=0)

            if msg[_k] in {101, 305, 308, 331}:
                if msg[_k] == 101:  # 好友申请
                    invite_info = json.loads(msg['content'])
                    menu_title = '{} [{}] 申请加您为好友: {}'.format(self.im_user.get_nickname(invite_info['inviter']),
                                                              invite_info['inviter'], invite_info['reason'])
                    _accept = lambda: messagebox.showinfo('', self.im_user.accept_friend_apply(invite_info['inviter']),
                                                          parent=msg_top)
                    _refuse = lambda: messagebox.showinfo('', self.im_user.refuse_friend_apply(invite_info['inviter']),
                                                          parent=msg_top)
                elif msg[_k] == 305:  # 用户申请入群
                    menu_title = '用户申请入群'
                elif msg[_k] == 308:  # 邀请入群
                    invite_info = json.loads(msg['content'])
                    _accept = lambda: messagebox.showinfo('', self.im_user.user_accept_group_invite(invite_info['groupId']),
                                                          parent=msg_top)
                    _refuse = lambda: messagebox.showinfo('', self.im_user.user_reject_group_invite(invite_info['groupId']),
                                                          parent=msg_top)
                    menu_title = '{} [{}] 邀请您加入群聊 {}: {}'.format(self.im_user.get_nickname(invite_info['inviter']),
                                                                 invite_info['inviter'], invite_info['groupName'],
                                                                 invite_info['reason'] if 'reason' in invite_info else '')
                elif msg[_k] == 331:  # 非管理员邀请入群
                    invite_info = json.loads(msg['content'])
                    menu_title = '{}[{}] 邀请 {}[{}] 加入群聊 {}'.format(invite_info['inviter'],
                                                                   self.im_user.get_nickname(invite_info['inviter']),
                                                                   invite_info['invitee'],
                                                                   self.im_user.get_nickname(invite_info['invitee']),
                                                                   invite_info['groupName'])
                    _accept = lambda: messagebox.showinfo('',
                                                          self.im_user.manager_accept_group_invite(invite_info['groupId'],
                                                                                                   invite_info['invitee']),
                                                          parent=msg_top)
                    _refuse = lambda: messagebox.showinfo('',
                                                          self.im_user.manager_reject_group_invite(invite_info['groupId'],
                                                                                                   invite_info['invitee']),
                                                          parent=msg_top)
                menu.add_command(label=menu_title)  # 增加菜单栏
                menu.add_separator()  # 画分割线
                menu.add_command(label='同意', command=_accept)
                menu.add_command(label='拒绝', command=_refuse)
            else:
                menu.add_command(label=MESSAGE_TYPE[msg[_k]] if msg[_k] in MESSAGE_TYPE else f'未知消息类型: {msg[_k]}')  # 增加菜单栏
                menu.add_separator()  # 画分割线
                if msg[_k] in {1, 2, 3, 4, 5, 6, 7, 8} and msg_from_user_id == self.user_id:
                    menu.add_command(label='撤回消息', command=lambda: self.recall_msg(msg_top, comm_id, _msg_id, msg_tree, focus_item, msg_index))

            menu.add_command(label='查看详情', command=lambda: show_msg_detail(msg_top, msg))
            menu.post(_event.x_root, _event.y_root)

        _item = self.tree.focus()  # 返回的是选中行的id号，字符串类型
        if self.im_user is not None:
            try:
                _nick_name, _comm_id, _comm_type = self.tree.item(_item, "values")[0:3]  # 获取行的`values`属性
                _comm_type = _comm_type if type(_comm_type) is int else int(_comm_type)
            except Exception as e:
                print(e)
                return

            # 同步会话未读数量
            if _comm_type in {1, 2}:
                asyncio.run_coroutine_threadsafe(
                    self.im_user.send_read_communication_sync_message(_comm_id, _comm_type),
                    self.loop
                )

            self.im_user.clean_communication_msg_count(_comm_id)    # 清空会话未读数

            top_obj = SubTop('', self.root)
            top = top_obj.get_handle()

            col = ['sender', 'id', 'type', 'content']
            tree = ttk.Treeview(top, columns=col, height=18, show="headings")
            tree.heading("content", text="内容")
            tree.heading("id", text="id")
            tree.heading("sender", text="发送方")
            tree.heading("type", text="type")
            tree.column("content", width=400)  # 设置列宽等属性
            tree.column("type", width=100)  # 设置列宽等属性
            vsb = ttk.Scrollbar(top, orient="vertical", command=tree.yview)
            tree.grid(column=0, row=0)
            vsb.grid(column=1, row=0, sticky=tkinter.NS)
            tree.configure(yscrollcommand=vsb.set)
            _count = 0
            msg_last_index = dict()  # 存放上一条消息的序号，验证消息接收的顺序及完整性
            rule = re.compile(r"(?P<flag>\w+-\w+)-\[.*?\] \[(?P<index>\d+)\]")
            msg_id_dict = dict()  # 字典, k : 消息id, v:该消息在 im_user.communication_msg 中的下标位置
            err_count = 0  # err msg 统计
            _index = 0
            _tmp_msg_list = self.im_user.communication_msg[_comm_id].copy()  # 避免RuntimeError, copy一份
            msgs_by_sender = {}
            for _msg in _tmp_msg_list:  # 遍历消息
                res = rule.match(_msg['content']) if 'content' in _msg else None
                _tag = 'true'  # tree的标签
                if res:
                    flag = res.group('flag')
                    index = int(res.group('index'))
                    if flag in msg_last_index and index - msg_last_index[flag] != 1:
                        err_count += 1
                        _tag = 'error'
                    msg_last_index[flag] = index
                if 'message_id' in _msg:
                    if _msg['message_id'] in msg_id_dict:
                        _index += 1
                        continue
                    msg_id_dict[_msg['message_id']] = _index

                    if _msg['message_type'] in {1, 2, 3, 4, 5, 6, 7, 9}:
                        msg_id = _msg['message_id'] if type(_msg['message_id']) is int else int(_msg['message_id'])
                        if _msg['from_user_id'] != self.user_id and msg_id not in self.already_send_ack_msg_id_set:
                            from_user_id = _msg['from_user_id']
                            self.already_send_ack_msg_id_set.add(msg_id)
                            if from_user_id in msgs_by_sender:
                                msgs_by_sender[from_user_id].append(msg_id)
                            else:
                                msgs_by_sender[from_user_id] = [msg_id]

                    tree.insert(
                        '',
                        0,
                        values=(
                            self.im_user.get_nickname(_msg['from_user_id']) if _msg['message_main_type'] != 100 else '系统通知',
                            _msg['message_id'],
                            MESSAGE_TYPE[_msg['message_type']] if _msg[
                                                                      'message_type'] in MESSAGE_TYPE else '未知消息类型{}'.format(
                                _msg['message_type']),
                            _msg['content'] if 'content' in _msg else ''
                        ),
                        tags=(_tag,)
                    )
                else:  # 离线
                    if _msg['messageId'] in msg_id_dict:
                        _index += 1
                        continue

                    if _msg['messageType'] in {1, 2, 3, 4, 5, 6, 7, 9}:
                        msg_id = _msg['messageId'] if type(_msg['messageId']) is int else int(_msg['messageId'])
                        if _msg['fromUserId'] != self.user_id and msg_id not in self.already_send_ack_msg_id_set:
                            from_user_id = _msg['fromUserId']
                            self.already_send_ack_msg_id_set.add(msg_id)
                            if from_user_id in msgs_by_sender:
                                msgs_by_sender[from_user_id].append(msg_id)
                            else:
                                msgs_by_sender[from_user_id] = [msg_id]

                    if type(_msg['messageId']) == int:
                        _msg['messageId'] = str(_msg['messageId'])
                    msg_id_dict[_msg['messageId']] = _index
                    msg_type = _msg['messageType']
                    if type(msg_type) == str:
                        msg_type = int(msg_type)
                    tree.insert(
                        '',
                        0,
                        values=(
                            self.im_user.get_nickname(_msg['fromUserId']) if _msg['messageMainType'] != 100 else '系统通知',
                            _msg['messageId'],
                            MESSAGE_TYPE[msg_type] if msg_type in MESSAGE_TYPE else '未知消息类型{}'.format(msg_type),
                            _msg['content'] if 'content' in _msg else ''
                        ),
                        tags=(_tag,)
                    )
                _count += 1
                _index += 1
            for sender in msgs_by_sender:
                # todo 批量发送消息已读回执
                asyncio.run_coroutine_threadsafe(
                    self.im_user.send_batch_msg_ack_message(sender, self.user_id, _comm_id, msgs_by_sender[sender]),
                    self.loop
                )
            tree.tag_configure('error', background='orange')
            tree.tag_configure('true', background=TREE_ROW_BG)
            top.title('{} [{}] ({}, error:{})'.format(_nick_name, _comm_id, _count, err_count))

            tree.bind("<Button-3>", lambda _event: msg_operate(_event, top, tree, _comm_id))  # 消息操作，拒绝， 同意，查看详情
            top_obj.show()

    def show_send_msg_details(self):
        if not self.im_user:
            messagebox.showwarning('warning', '当前未登录')
            return

        def clean_send_msg_detail_by_type(_tree):
            children_list = _tree.get_children()
            for _child in children_list:
                _tree.delete(_child)
            if self.im_user is not None:
                self.im_user.clear_send_msg_details()

        def show_send_msg_detail_by_type(_tree, _type):
            info = None
            if _type == 'communication_type':
                info = {
                    1: '单聊',
                    2: '群聊',
                    3: '聊天室'
                }
            elif _type == 'message_type':
                info = {
                    0: '未知',
                    1: '文本',
                    2: "表情",
                    3: "文件",
                    4: "图片",
                    5: "语音",
                    6: "视频",
                    7: "位置",
                    8: "命令",
                    9: "自定义消息"
                }
            children_list = _tree.get_children()
            for _child in children_list:
                _tree.delete(_child)
            _tree.config(columns=[_type, 'count'])
            tree.heading(_type, text=_type)
            tree.heading("count", text="数量")
            if _type == 'communication_id':
                for sub_k in self.im_user.send_msg_details[_type]:
                    _tree.insert('', 0, values=(sub_k, self.im_user.send_msg_details[_type][sub_k]))
            elif _type == 'communication_type':
                for sub_k in self.im_user.send_msg_details[_type]:
                    _tree.insert('', 0, values=(info[sub_k], self.im_user.send_msg_details[_type][sub_k]))
            elif _type == 'message_type':
                for sub_k in self.im_user.send_msg_details[_type]:
                    _tree.insert(
                        '',
                        0,
                        values=(
                            info[sub_k],
                            '{} (价格: {:.5f})'.format(self.im_user.send_msg_details[_type][sub_k], self.im_user.send_msg_details[_type][sub_k] * MESSAGE_PRICE[sub_k])
                        )
                    )

        sub_top_obj = SubTop('发送消息详情', self.root)
        sub_top = sub_top_obj.get_handle()

        col = ['message_type', 'count']
        tree = ttk.Treeview(sub_top, columns=col, height=18, show="headings")
        tree.heading("message_type", text="message_type")
        tree.heading("count", text="数量")

        menu_bar = tkinter.Menu(sub_top)
        menu_bar.add_command(label="按会话类型", command=lambda: show_send_msg_detail_by_type(tree, 'communication_type'))
        menu_bar.add_command(label="按会话id", command=lambda: show_send_msg_detail_by_type(tree, 'communication_id'))
        menu_bar.add_command(label="按消息类型", command=lambda: show_send_msg_detail_by_type(tree, 'message_type'))
        menu_bar.add_command(label="清除发送记录", command=lambda: clean_send_msg_detail_by_type(tree))
        sub_top.config(menu=menu_bar)

        show_send_msg_detail_by_type(tree, 'message_type')
        tree.grid()
        sub_top_obj.show()

    def add_group_user(self, _top: tkinter.Toplevel, comm_id: str, _tree: ttk.Treeview, before_member_list, after_menu):
        """
        :param _top:
        :param comm_id:
        :param _tree:
        :param before_member_list: 添加之前的群成员列表
        :param after_menu:
        :return: 之前的菜单
        """
        self.debug('[add_group_user]')
        _top.config(menu=after_menu)
        children = _tree.get_children()

        user_lists = list()
        for _item in _tree.selection():
            _id = _tree.item(_item, 'values')[0]
            user_lists.append(_id)
        if len(user_lists) > 0:
            try:
                res = self.im_user.invite_user_to_group(comm_id, ','.join(user_lists))
            except Exception as e:
                messagebox.showerror('error', e, parent=after_menu)
            else:
                messagebox.showinfo('info', res, parent=after_menu)
                for item in children:
                    _tree.delete(item)
        else:
            # 删除不在该群的用户
            for item in children:
                if item in _tree.selection():
                    _tree.item(item, tags=[])
                    continue
                if 'add' in _tree.item(item, 'tags'):
                    _tree.delete(item)
        # 重新显示之前的群成员和新增加的成员
        for user_id in before_member_list + user_lists:
            identity = ''
            if user_id == self.group_info[comm_id]['ownerId']:
                identity = '[群主] '
            elif user_id in self.group_info[comm_id]['managerList']:
                identity = '[管理员] '
            group_member_head_img = self.im_user.get_user_head_photo_bytes(user_id)
            if group_member_head_img:
                img0 = self.img_to_tk_img(group_member_head_img, 25)
                self.head_imgs[user_id] = img0
                _tree.insert('', 'end', image=self.head_imgs[user_id], values=(user_id, identity+self.im_user.get_nickname(user_id)))
            else:
                _tree.insert('', 'end', values=(user_id, identity+self.im_user.get_nickname(user_id)))

    def change_group_owner(self, parent_top_tree, _top, comm_id, _tree, menu_bar, after_menu_bar):
        """
        转让群主操作
        :param parent_top_tree: 当前top的父top
        :param _top: 当前top
        :param comm_id: comm_id
        :param _tree: 当前top的treeview
        :param menu_bar: 之前的菜单栏
        :param after_menu_bar: 之后的菜单栏
        :return:
        """
        self.debug('[change_group_owner]')
        user_lists = list()
        for _item in _tree.selection():
            _id = _tree.item(_item, 'values')[0]
            user_lists.append(_id)
        _res = None
        if len(user_lists) == 1:
            try:
                _res = self.im_user.change_group_owner(comm_id, user_lists[0])
            except Exception as e:
                messagebox.showerror('error', e, parent=menu_bar)
            else:
                messagebox.showinfo('info', _res, parent=menu_bar)
                if _res['code'] == '0':
                    _top.config(menu=after_menu_bar)
                    for _x in parent_top_tree.get_children():
                        _values = parent_top_tree.item(_x, 'values')
                        if _values[0] == comm_id:
                            parent_top_tree.set(_x, column='owner_id', value=user_lists[0])
                            break
        identity = '[群主] '
        if _res and _res['code'] == '0':
            _top.config(menu=after_menu_bar)
            identity = ''
            for _x in _tree.get_children():
                _values = _tree.item(_x, 'values')
                if _values[0] == user_lists[0]:
                    _tree.set(_x, column='nickname', value='[群主] '+self.im_user.get_nickname(user_lists[0]))
                    break
        else:
            _top.config(menu=menu_bar)
        self_head_img = self.im_user.get_user_head_photo_bytes()
        if self_head_img:
            tk_img = self.img_to_tk_img(self_head_img, 25)
            self.head_imgs[self.user_id] = tk_img
            _tree.insert('', 0, image=self.head_imgs[self.user_id], values=(self.user_id, identity+self.im_user.get_nickname(self.user_id)))
        else:
            _tree.insert('', 0, values=(self.user_id, identity+self.im_user.get_nickname(self.user_id)))

    def img_to_tk_img(self, src_img: bytes, size: int):
        """
        将二进制图片转为tkinter可用的格式
        :param src_img: 原始图片数据，二进制
        :param size: 期望图片宽高
        :return: tk_img
        """
        photo = Image.open(BytesIO(src_img))
        photo = photo.resize((size, size))
        tk_img = ImageTk.PhotoImage(photo)
        return tk_img

    def del_group_user(self, _top: tkinter.Toplevel, comm_id: str, _tree: ttk.Treeview, menu_bar: tkinter.Menu):
        """
        :param _top:
        :param comm_id:
        :param _tree:
        :param menu_bar:
        :return:
        """
        self.debug('[del_group_user]')
        user_lists = list()
        for _item in _tree.selection():
            _id = _tree.item(_item, 'values')[0]
            user_lists.append(_id)
        if len(user_lists) > 0:
            try:
                res = self.im_user.remove_group_member(comm_id, ','.join(user_lists))
            except Exception as e:
                messagebox.showerror('error', e, parent=menu_bar)
            else:
                messagebox.showinfo('info', res, parent=menu_bar)
                for _item in _tree.selection():
                    _tree.delete(_item)
        _top.config(menu=menu_bar)
        self_head_img = self.im_user.get_user_head_photo_bytes()
        identity = ''
        if self.user_id == self.group_info[comm_id]['ownerId']:
            identity = '[群主] '
        elif self.user_id in self.group_info[comm_id]['managerList']:
            identity = '[管理员] '
        if self_head_img:
            tk_img = self.img_to_tk_img(self_head_img, 25)
            self.head_imgs[self.user_id] = tk_img
            _tree.insert('', 0, image=self.head_imgs[self.user_id], values=(self.user_id, identity+self.im_user.get_nickname(self.user_id)))
        else:
            _tree.insert('', 0, values=(self.user_id, identity+self.im_user.get_nickname(self.user_id)))

    def send_msg_multi(self, _tree, count, flag):
        self.debug('[send_msg_multi]')
        selected_item_list = _tree.selection()
        _im_user = getattr(self, 'im_user')
        loop = self.loop
        future_list = []
        for selected_item in selected_item_list:
            item_val = _tree.item(selected_item, 'values')
            if flag == 'group':
                comm_id, to_id, owner_id, comm_type = item_val
            elif flag == 'single':
                nickname, to_id, comm_id, comm_type = item_val
            else:
                raise Exception('send_msg_multi error')
            future = asyncio.run_coroutine_threadsafe(
                _im_user.send_chat_msg(to_id, comm_id, comm_type, 1, count, self.msg_sleep_time), loop)
            future_list.append(future)
        # res = []
        # for _future in future_list:
        #     res.append(_future.result())
        # messagebox.showinfo('info', res, parent=_tree)

    def edit_group_name(self, comm_id, _top, parent_tree, _entry, from_src):
        """
        :param comm_id:
        :param _top:
        :param parent_tree:
        :param _entry:
        :param from_src: 来源, 0是root, 1是群列表界面
        :return:
        """
        self.debug('[edit_group_name]')
        new_group_name = _entry.get()
        _r = self.im_user.set_group_name(comm_id, new_group_name)
        if _r['code'] == '0':
            self.im_user.group_info[comm_id]['name'] = new_group_name  # 更新用户群信息缓存的值
            # done 更新tree上的name显示
            child_list = parent_tree.get_children()
            if from_src == 0:
                for _item in child_list:
                    tree_comm_id = parent_tree.item(_item, "values")[1]
                    if tree_comm_id == comm_id:
                        parent_tree.set(_item, column='comm_name', value=new_group_name)
            elif from_src == 1:
                for _item in child_list:
                    tree_comm_id = parent_tree.item(_item, "values")[0]
                    if tree_comm_id == comm_id:
                        parent_tree.set(_item, column='comm_name', value=new_group_name)
        messagebox.showinfo('info', _r, parent=_top)

    def edit_group_description(self, comm_id, _top, group_description_entry):
        self.debug('[edit_group_description]')
        new_group_description = group_description_entry.get()
        _r = self.im_user.set_group_description(comm_id, new_group_description)
        messagebox.showinfo('info', _r, parent=_top)

    def set_group_announcement(self, parent_top, announcement_text, group_id):
        announcement = announcement_text.get('0.0', 'end').strip()
        try:
            _resp = self.im_user.set_group_announcement(group_id, announcement)
        except Exception as _e:
            messagebox.showerror('error', _e, parent=parent_top)
        else:
            messagebox.showinfo('info', _resp, parent=parent_top)

    def show_group_announcement(self, parent_top, group_id, user_identity):
        try:
            _res = self.im_user.get_group_announcement(group_id)
        except Exception as _e:
            messagebox.showerror('error', _e, parent=parent_top)
        else:
            if _res['code'] == '0':
                sub_top_obj = SubTop(f'群公告 - {self.im_user.get_group_name(group_id)}', parent_top)
                sub_top = sub_top_obj.get_handle()
                publish_name = _res['data']['publisherName']
                avatar = _res['data']['avatar']
                publisher_head_img = None
                if avatar:
                    resp = requests.get(avatar)
                    if resp.status_code == 200:
                        publisher_head_img = resp.content
                if publisher_head_img:
                    tk_img = self.img_to_tk_img(publisher_head_img, 50)
                    publisher_avatar_label = tkinter.Label(sub_top, image=tk_img)
                else:
                    publisher_avatar_label = tkinter.Label(sub_top, text=avatar)
                announcement = _res['data']['announcement']
                publish_time = _res['data']['noticePublishTime']
                if publish_time:
                    publish_time = strftime('%Y-%m-%d %H:%M:%S', localtime(int(publish_time)/1000))
                publisher_name_label = tkinter.Label(sub_top, text=publish_name if publish_name else '')

                publish_time_label = tkinter.Label(sub_top, text=publish_time if publish_time else '')
                announcement_text = tkinter.Text(sub_top)
                announcement_text.insert('end', announcement) if announcement else announcement_text.insert('end', '')
                publisher_avatar_label.grid(row=0, column=0, rowspan=2)
                publisher_name_label.grid(row=0, column=1)
                publish_time_label.grid(row=1, column=1)

                announcement_text.grid(row=2, column=0, columnspan=2)

                if user_identity > 0:
                    button = tkinter.Button(sub_top, text='保存', command=lambda: self.set_group_announcement(sub_top, announcement_text, group_id))
                    button.grid(row=3, column=0, columnspan=2)
                else:
                    announcement_text.config(state='disable')
                sub_top_obj.show()
            else:
                messagebox.showwarning('warning', _res, parent=parent_top)

    def set_chat_room_announcement(self, parent_top, announcement_text, chat_room_id):
        res = self.im_user.set_chat_room_announcement(chat_room_id, announcement_text.get('0.0', 'end').strip())
        # res = self.im_user.set_chat_room_announcement(chat_room_id, '0123456789'*50)
        messagebox.showinfo('info', res, parent=parent_top)

    def set_chat_room_description(self, parent_top, description_text, chat_room_id):
        res = self.im_user.set_chat_room_description(chat_room_id, description_text.get('0.0', 'end'))
        messagebox.showinfo('info', res, parent=parent_top)

    def show_chat_room_announcement(self, parent_top, chat_room_id, user_identity):
        try:
            _res = self.im_user.get_chat_room_announcement(chat_room_id)
        except Exception as _e:
            messagebox.showerror('error', _e, parent=parent_top)
        else:
            if _res['code'] == '0':
                sub_top_obj = SubTop('聊天室公告', parent_top)
                sub_top = sub_top_obj.get_handle()
                publish_name = _res['data']['publisherName']
                avatar = _res['data']['avatar']
                publisher_head_img = None
                if avatar:
                    resp = requests.get(avatar)
                    if resp.status_code == 200:
                        publisher_head_img = resp.content
                if publisher_head_img:
                    tk_img = self.img_to_tk_img(publisher_head_img, 50)
                    publisher_avatar_label = tkinter.Label(sub_top, image=tk_img)
                else:
                    publisher_avatar_label = tkinter.Label(sub_top, text=avatar)
                announcement = _res['data']['announcement']
                publish_time = _res['data']['noticePublishTime']
                if publish_time:
                    publish_time = strftime('%Y-%m-%d %H:%M:%S', localtime(int(publish_time)/1000))
                publisher_name_label = tkinter.Label(sub_top, text=publish_name if publish_name else '')

                publish_time_label = tkinter.Label(sub_top, text=publish_time if publish_time else '')
                announcement_text = tkinter.Text(sub_top)
                announcement_text.insert('end', announcement) if announcement else announcement_text.insert('end', '')
                publisher_avatar_label.grid(row=0, column=0, rowspan=2)
                publisher_name_label.grid(row=0, column=1)
                publish_time_label.grid(row=1, column=1)

                announcement_text.grid(row=2, column=0, columnspan=2)

                if user_identity == 'normal':
                    announcement_text.config(state='disable')
                else:
                    button = tkinter.Button(sub_top, text='保存', command=lambda: self.set_chat_room_announcement(sub_top, announcement_text, chat_room_id))
                    button.grid(row=3, column=0, columnspan=2)
                sub_top_obj.show()
            else:
                messagebox.showwarning('warning', _res, parent=parent_top)

    def show_chat_room_description(self, parent_top, chat_room_id, user_identity):
        try:
            _res = self.im_user.get_chat_room_detail(chat_room_id)
        except Exception as _e:
            messagebox.showerror('error', _e, parent=parent_top)
        else:
            if _res['code'] == '0':
                sub_top_obj = SubTop('聊天室描述', parent_top)
                sub_top = sub_top_obj.get_handle()
                # publish_name = _res['data']['publisherName']
                # avatar = _res['data']['avatar']
                # publisher_head_img = None
                # if avatar:
                #     resp = requests.get(avatar)
                #     if resp.status_code == 200:
                #         publisher_head_img = resp.content
                # if publisher_head_img:
                #     tk_img = self.img_to_tk_img(publisher_head_img, 50)
                #     publisher_avatar_label = tkinter.Label(sub_top, image=tk_img)
                # else:
                #     publisher_avatar_label = tkinter.Label(sub_top, text=avatar)
                description = _res['data']['description']
                # publish_time = _res['data']['noticePublishTime']
                # if publish_time:
                #     publish_time = strftime('%Y-%m-%d %H:%M:%S', localtime(int(publish_time)/1000))
                # publisher_name_label = tkinter.Label(sub_top, text=publish_name if publish_name else '')
                #
                # publish_time_label = tkinter.Label(sub_top, text=publish_time if publish_time else '')
                description_text = tkinter.Text(sub_top)
                description_text.insert('end', description) if description else description_text.insert('end', '')
                # publisher_avatar_label.grid(row=0, column=0, rowspan=2)
                # publisher_name_label.grid(row=0, column=1)
                # publish_time_label.grid(row=1, column=1)

                description_text.grid(row=2, column=0, columnspan=2)

                if user_identity == 'normal':
                    description_text.config(state='disable')
                else:
                    button = tkinter.Button(sub_top, text='保存', command=lambda: self.set_chat_room_description(sub_top, description_text, chat_room_id))
                    button.grid(row=3, column=0, columnspan=2)
                sub_top_obj.show()
            else:
                messagebox.showwarning('warning', _res, parent=parent_top)

    def show_chat_room_name(self, window, chat_room_id):

        def set_chat_room_name():
            new_name = name_entry.get()
            _res = self.im_user.set_chat_room_name(chat_room_id, new_name)
            messagebox.showinfo('info', _res, parent=top)
            if 'code' in _res and _res['code'] == '0':
                before_name = re.findall(r'\[\w+ - (.*?)\]', window.wm_title())[0]
                window.title(re.sub(before_name, new_name, window.wm_title()))

        sub_top_obj = SubTop('聊天室名称', window)
        top = sub_top_obj.get_handle()
        res = self.im_user.get_chat_room_detail(chat_room_id)
        # print(res)
        variable = tkinter.StringVar(top, value=res['data']['name'])
        name_label = tkinter.Label(top, text='聊天室名称: ')
        name_entry = tkinter.Entry(top, textvariable=variable)
        button = tkinter.Button(top, text='保存', command=set_chat_room_name)
        name_label.grid(row=0, column=0)
        name_entry.grid(row=0, column=1)
        button.grid(row=1, column=0, columnspan=2)
        sub_top_obj.show()

    def show_chat_room_all_mute(self, window, chat_room_id):

        def set_chat_room_all_mute():
            mute_status = variable.get()
            if mute_status:
                _res = self.im_user.set_chat_room_all_mute(chat_room_id, True)
            else:
                _res = self.im_user.set_chat_room_all_mute(chat_room_id, False)
            messagebox.showinfo('info', _res, parent=top)

        sub_top_obj = SubTop('聊天室全员禁言', window)
        top = sub_top_obj.get_handle()
        variable = tkinter.IntVar(top)
        mute_label = tkinter.Label(top, text='全员禁言: ')
        radio_enable = tkinter.Radiobutton(top, value=1, text="开启", variable=variable, command=set_chat_room_all_mute)
        radio_disable = tkinter.Radiobutton(top, value=0, text="关闭", variable=variable, command=set_chat_room_all_mute)
        mute_label.grid(row=0, column=0)
        radio_enable.grid(row=0, column=1)
        radio_disable.grid(row=0, column=2)
        res = self.im_user.get_chat_room_detail(chat_room_id)
        # print(res)
        variable.set(1) if res['data']['settings']['mute'] else variable.set(0)
        sub_top_obj.show()

    def show_group_detail_setting(self, res_json, comm_id, parent_top, parent_tree, src):
        self.debug('[show_group_detail_setting]')
        if res_json is None:
            # res_json = self.im_user.get_group_detail(comm_id)
            # if res_json['code'] != '0':
            #     messagebox.showerror('error', res_json, parent=parent_top)
            #     return
            res_json = self.group_info[comm_id]
            setting_info = self.group_info[comm_id]['settings']
        else:
            setting_info = res_json['data']['settings']
            res_json = res_json['data']
        _sub_top = SubTop(f'群设置 - {self.im_user.get_group_name(comm_id)} [{comm_id}]', parent_top)
        _top = _sub_top.get_handle()

        menu = tkinter.Menu(_top)
        menu.add_command(label='设置头像', command=lambda: self.set_group_avatar(comm_id, _top))
        _top.config(menu=menu)

        invite_val = tkinter.IntVar(_top)
        invite_label = tkinter.Label(_top, text='群邀请开关:')

        join_approve_val = tkinter.IntVar(_top)
        join_approve_label = tkinter.Label(_top, text='入群验证:')

        group_mute_val = tkinter.IntVar(_top)
        group_mute_label = tkinter.Label(_top, text='全员禁言:')

        invite_true_radio = tkinter.Radiobutton(_top, value=1, text="开启", variable=invite_val,
                                                command=lambda: self.set_group_allow_invite(comm_id, True, _top))
        invite_false_radio = tkinter.Radiobutton(_top, value=0, text="关闭", variable=invite_val,
                                                 command=lambda: self.set_group_allow_invite(comm_id, False, _top))
        invite_val.set(1) if setting_info['allowInvites'] else invite_val.set(0)
        invite_label.grid(row=0, column=0)
        invite_true_radio.grid(row=0, column=1)
        invite_false_radio.grid(row=0, column=2)

        join_approve_true_radio = tkinter.Radiobutton(_top, value=1, text="开启", variable=join_approve_val,
                                                      command=lambda: self.set_group_join_apply(comm_id, True, _top))
        join_approve_false_radio = tkinter.Radiobutton(_top, value=0, text="关闭", variable=join_approve_val,
                                                       command=lambda: self.set_group_join_apply(comm_id, False, _top))
        join_approve_val.set(1) if setting_info['joinApprove'] else join_approve_val.set(0)
        join_approve_label.grid(row=1, column=0)
        join_approve_true_radio.grid(row=1, column=1)
        join_approve_false_radio.grid(row=1, column=2)

        group_mute_true_radio = tkinter.Radiobutton(_top, value=1, text="开启", variable=group_mute_val, command=lambda: self.set_group_all_mute(comm_id, True, _top))
        group_mute_false_radio = tkinter.Radiobutton(_top, value=0, text="关闭", variable=group_mute_val, command=lambda: self.set_group_all_mute(comm_id, False, _top))
        group_mute_val.set(1) if setting_info['mute'] else group_mute_val.set(0)
        group_mute_label.grid(row=2, column=0)
        group_mute_true_radio.grid(row=2, column=1)
        group_mute_false_radio.grid(row=2, column=2)

        group_name_val = tkinter.StringVar(_top, value=res_json['name'])
        group_name_label = tkinter.Label(_top, text='群聊名称:')
        group_name_entry = tkinter.Entry(_top, textvariable=group_name_val, width=40)

        group_name_label.grid(row=3, column=0)
        group_name_entry.grid(row=3, column=1, columnspan=2)

        save_setting_button = tkinter.Button(_top, text='修改群名', width=30, command=lambda: self.edit_group_name(comm_id, _top, parent_tree, group_name_entry, src))
        save_setting_button.grid(row=4, column=0, columnspan=3)

        group_description_val = tkinter.StringVar(_top, value=res_json['description'])
        group_description_label = tkinter.Label(_top, text='群聊描述:')
        group_description_entry = tkinter.Entry(_top, textvariable=group_description_val, width=40)

        group_description_label.grid(row=5, column=0)
        group_description_entry.grid(row=5, column=1, columnspan=2)

        save_setting_button = tkinter.Button(_top, text='修改群聊描述', width=30, command=lambda: self.edit_group_description(comm_id, _top, group_description_entry))
        save_setting_button.grid(row=6, column=0, columnspan=3)

        # set_group_avatar_button = tkinter.Button(_top, text='设置头像', width=30, command=lambda: self.set_group_avatar(comm_id, _top))
        # set_group_avatar_button.grid(row=7, column=0, columnspan=3)

        _sub_top.show()

    def operate_members_list_by_type(self, members_list_type, operation, before_user_list, _top, _tree, group_id,
                                     before_menu_bar, grandparent_top_tree=None):
        """

        :param members_list_type: 群成员列表类型: mute, manager, black
        :param operation: 操作: add or remove
        :param before_user_list: 之前的用户列表
        :param _top: 父窗口
        :param _tree:
        :param group_id:
        :param before_menu_bar: 之前的菜单控件
        :param grandparent_top_tree: 祖父窗口的treeview
        :return:
        """
        self.debug('[operate_members_list_by_type]')
        funcs = {
            'mute': self.im_user.set_group_mute,
            'manager': self.im_user.set_group_manager,
            'black': self.im_user.set_group_black_list
        }
        selected_item_list = _tree.selection()  # 返回的是选中的id list
        if len(selected_item_list) == 0:
            _top.config(menu=before_menu_bar)
            # 列表还得恢复为以前的列表
            children_items = _tree.get_children()
            for item in children_items:
                _tree.delete(item)
            for _id in before_user_list:
                _tree.insert('', 'end', values=(_id, self.im_user.get_nickname(_id)))
            return
        selected_user_id_list = []
        for _item in selected_item_list:
            user_id = _tree.item(_item, 'values')[0]
            selected_user_id_list.append(user_id)
        try:
            _res = funcs[members_list_type](group_id, ','.join(selected_user_id_list), operation)
        except Exception as _e:
            _res = _e
            messagebox.showerror('error', _res, parent=_top)
        else:
            messagebox.showinfo('info', _res, parent=_top)
            if _res['code'] == '0':
                _top.config(menu=before_menu_bar)
                current_user_list = before_user_list[:]  # 现在的成员列表
                current_user_list.extend(selected_user_id_list)
                children_items = _tree.get_children()
                if operation == 'remove':
                    # 删除那些被删除的用户
                    for item in children_items:
                        if _tree.item(item, 'values')[0] in selected_user_id_list:
                            _tree.delete(item)
                    if members_list_type == 'manager':
                        # 重新设置祖父treeview的列表身份
                        x = grandparent_top_tree.get_children()  # 获取行对象
                        for item in x:
                            user_id = grandparent_top_tree.item(item, "values")[0]
                            if user_id in selected_user_id_list:
                                grandparent_top_tree.set(item, column='nickname', value=self.im_user.get_nickname(user_id))
                elif operation == 'add':
                    # 插入之前就存在的用户
                    for _id in before_user_list:
                        group_member_head_img = self.im_user.get_user_head_photo_bytes(_id)
                        if group_member_head_img:
                            tk_img = self.img_to_tk_img(group_member_head_img, 25)
                            self.head_imgs[_id] = tk_img
                            _tree.insert('', 'end', image=self.head_imgs[_id], values=(_id, self.im_user.get_nickname(_id)))
                        else:
                            _tree.insert('', 'end', values=(_id, self.im_user.get_nickname(_id)))
                    # 删除不在列表的用户
                    for item in children_items:
                        if _tree.item(item, 'values')[0] not in current_user_list:
                            _tree.delete(item)
                    if members_list_type == 'manager':
                        x = grandparent_top_tree.get_children()  # 获取行对象
                        for item in x:
                            user_id = grandparent_top_tree.item(item, "values")[0]
                            if user_id in selected_user_id_list:
                                grandparent_top_tree.set(item, column='nickname', value='[管理员] '+self.im_user.get_nickname(user_id))
            else:
                pass

    def update_members_list_by_type(self, _top, _tree, group_id, members_list_type, operation, all_user_list,
                                    before_menu_bar, grandparent_tree):
        self.debug('[update_members_list_by_type]', members_list_type, operation)
        current_user_list = []
        children_items = _tree.get_children()
        for item in children_items:
            current_user_list.append(_tree.item(item, 'values')[0])
        new_menu_bar = tkinter.Menu(_top)
        new_menu_bar.add_command(label="完成",
                                 command=lambda: self.operate_members_list_by_type(members_list_type, operation,
                                                                                   current_user_list, _top, _tree,
                                                                                   group_id, before_menu_bar, grandparent_tree))
        new_menu_bar.add_command(label="重新选择", command=lambda: clean_selection(_tree))
        _top.config(menu=new_menu_bar)
        if operation == 'add':
            # 不显示已有的成员列表
            x = _tree.get_children()
            for item in x:
                _tree.delete(item)

            new_user_list = [i for i in all_user_list if i not in current_user_list]
            for _user_id in new_user_list:
                _tree.insert(
                    '',
                    0,
                    values=(_user_id, self.im_user.get_nickname(_user_id))
                )
        elif operation == 'delete':
            pass

    def show_group_list_by_type(self, group_members_list, group_id, parent_top, parent_tree, show_type='manager', grandparent_tree=None):
        self.debug('[show_group_list_by_type]')
        funcs = {
            'manager': self.im_user.get_group_manager_list,
            'mute': self.im_user.get_group_mute_list,
            'black': self.im_user.get_group_black_list
        }
        titles = {
            'manager': '管理员列表',
            'mute': '禁言列表',
            'black': '黑名单列表'
        }

        _res = funcs[show_type](group_id)
        # current_user_list = [_i['userId'] for _i in _res['data']]
        sub_top_obj = SubTop(titles[show_type], parent_top)
        sub_top = sub_top_obj.get_handle()

        user_list_tree = ttk.Treeview(sub_top, columns=['user_id', 'nickname'], show="headings", height=16)
        user_list_tree.heading('user_id', text='用户ID')
        user_list_tree.heading('nickname', text='用户昵称')
        for _user_info in _res['data']:
            user_list_tree.insert(
                '',
                0,
                values=(_user_info['userId'], self.im_user.get_nickname(_user_info['userId']))
            )

        menu_bar = tkinter.Menu(sub_top)
        menu_bar.add_command(label="新增",
                             command=lambda: self.update_members_list_by_type(sub_top, user_list_tree, group_id,
                                                                              show_type, 'add', group_members_list,
                                                                              menu_bar, parent_tree))
        menu_bar.add_command(label="删除",
                             command=lambda: self.update_members_list_by_type(sub_top, user_list_tree, group_id,
                                                                              show_type, 'remove', group_members_list,
                                                                              menu_bar, parent_tree))
        sub_top.config(menu=menu_bar)

        user_list_tree.grid()
        sub_top_obj.show()

    def add_friend(self, user_id, parent):
        try:
            res = self.im_user.add_friend(user_id)
        except Exception as _e:
            messagebox.showerror('error', _e, parent=parent)
        else:
            messagebox.showinfo('info', res, parent=parent)

    def group_member_operation(self, event, _top, _tree):
        self.debug('[group_member_operation]')
        selected_item_list = _tree.selection()  # 返回的是选中的id list
        selected_user_list = []
        for _item in selected_item_list:
            user_id = _tree.item(_item, 'values')[0]
            selected_user_list.append(user_id)
        if len(selected_user_list) >= 1:
            if len(selected_user_list) == 1 and selected_user_list[0] != self.user_id:
                menu = tkinter.Menu(_top, tearoff=0)
                menu.add_command(label=selected_user_list[0])
                menu.add_separator()
                if selected_user_list[0] not in self.im_user.friend_id_list:
                    menu.add_command(label="添加好友", command=lambda:  self.add_friend(selected_user_list[0], _top))
                elif selected_user_list[0] in self.im_user.friend_id_list:
                    menu.add_command(label='发送消息', command=lambda: self.send_msg(selected_user_list[0],
                                                                                 self.im_user.get_friend_communication(
                                                                                     selected_user_list[0]), 1, 1, 10))
                menu.post(event.x_root, event.y_root)
            elif len(selected_user_list) > 1:
                menu = tkinter.Menu(_top, tearoff=0)
                menu.add_command(label='共选中{}个用户'.format(len(selected_user_list)))
                menu.post(event.x_root, event.y_root)

    def group_manager(self, comm_id, parent_top, parent_tree, flag):

        def group_user_operation(group_members_list, _top, _comm_id, _tree, _flag, **kw):  # 1: add, 0:delete
            if not _flag:  # delete
                new_menu_bar = tkinter.Menu(_top)
                new_menu_bar.add_command(label="完成",
                                         command=lambda: self.del_group_user(_top, _comm_id, _tree, menu_bar))
                new_menu_bar.add_command(label="重新选择", command=lambda: clean_selection(_tree))
                _top.config(menu=new_menu_bar)
                for _item in _tree.get_children():
                    user_id = _tree.item(_item, 'values')[0]
                    if user_id == self.user_id:
                        _tree.detach(_item)
                        break
            elif _flag == 1:  # add
                group_user_id_list = []

                for _item in _tree.get_children():
                    user_id = _tree.item(_item, 'values')[0]
                    _tree.delete(_item)
                    group_user_id_list.append(user_id)

                new_menu_bar = tkinter.Menu(_top)

                new_menu_bar.add_command(label="完成",
                                         command=lambda: self.add_group_user(_top, _comm_id, _tree, group_user_id_list,
                                                                             **kw))
                new_menu_bar.add_command(label="重新选择", command=lambda: clean_selection(_tree))
                _top.config(menu=new_menu_bar)

                new_user_list = [i for i in self.im_user.friend_id_list if i not in group_user_id_list]  # 不在群聊内的好友列表

                for user_id in new_user_list:
                    group_member_head_img = self.im_user.get_user_head_photo_bytes(user_id)
                    if group_member_head_img:
                        _tk_img = self.img_to_tk_img(group_member_head_img, 25)
                        self.head_imgs[user_id] = _tk_img
                        _tree.insert('', 0, image=self.head_imgs[user_id], values=(user_id, self.im_user.get_nickname(user_id)), tags=('add',))
                    else:
                        _tree.insert('', 0, values=(user_id, self.im_user.get_nickname(user_id)), tags=('add',))
            elif _flag == 2:  # 转让群主
                new_menu_bar = tkinter.Menu(_top)

                after_menu_bar = tkinter.Menu(group_user_list_top)
                after_menu_bar.add_command(label="邀请好友",
                                           command=lambda: group_user_operation(group_members_list, group_user_list_top,
                                                                                comm_id, group_user_list_tree, 1,
                                                                                after_menu=after_menu_bar))
                new_menu_bar.add_command(label="完成",
                                         command=lambda: self.change_group_owner(parent_tree, _top, comm_id, _tree,
                                                                                 menu_bar, after_menu_bar))
                new_menu_bar.add_command(label="重新选择", command=lambda: clean_selection(_tree))
                _top.config(menu=new_menu_bar)
                for _item in _tree.get_children():
                    _user_id = _tree.item(_item, 'values')[0]
                    if _user_id == self.user_id:
                        _tree.detach(_item)
                        break
            elif _flag == 3:  # 管理员
                self.show_group_list_by_type(group_members_list, _comm_id, _top, _tree, 'manager')
            elif _flag == 4:  # 黑名单
                self.show_group_list_by_type(group_members_list, _comm_id, _top, _tree, 'black')
            elif _flag == 5:  # 禁言
                self.show_group_list_by_type(group_members_list, _comm_id, _top, _tree, 'mute')

        group_user_list_res = self.im_user.get_group_user_list(comm_id)
        if comm_id not in self.group_info:
            self.group_info[comm_id] = self.im_user.get_group_detail(comm_id)['data']
        group_detail_res = self.group_info[comm_id]
        if group_user_list_res['code'] != '0':
            messagebox.showerror('error', group_user_list_res, parent=parent_top)
            return

        group_user_list_top_obj = SubTop(f'群成员列表 - {self.im_user.get_group_name(comm_id)}', parent_top)
        group_user_list_top = group_user_list_top_obj.get_handle()

        group_id_label = tkinter.Label(group_user_list_top, text='group id: ' + comm_id)
        group_id_label.grid(row=0, column=0)
        ttk.Style().configure('group_member_list.Treeview', rowheight=30)
        group_user_list_tree = ttk.Treeview(group_user_list_top, columns=['user_id', 'nickname'], height=16, style='group_member_list.Treeview')
        group_user_list_tree.heading('user_id', text='用户ID')
        group_user_list_tree.heading('nickname', text='用户昵称')
        group_user_list_tree.column('#0', width=60)

        all_group_members_list = [self.group_info[comm_id]['ownerId']]
        for _id in self.group_info[comm_id]['managerList']:
            if _id not in all_group_members_list:
                all_group_members_list.append(_id)
        if self.user_id not in all_group_members_list:
            all_group_members_list.append(self.user_id)
        for _info in group_user_list_res['data']:
            if _info['userId'] not in all_group_members_list:
                all_group_members_list.append(_info['userId'])

        try:
            self.im_user.get_user_detail_by_multi(all_group_members_list)
        except Exception as _e:
            messagebox.showerror('error', _e, parent=parent_top)
        img_obj_dict = {}
        for _user_id in all_group_members_list:
            identity = ''
            if _user_id == group_detail_res['ownerId']:
                identity = '[群主] '
            elif _user_id in group_detail_res['managerList']:
                identity = '[管理员] '
            try:
                group_member_img_head = self.im_user.get_user_head_photo_bytes(_user_id)
                if group_member_img_head:
                    tk_img = self.img_to_tk_img(group_member_img_head, 25)
                    img_obj_dict[_user_id] = tk_img
            except Exception as _e:
                group_user_list_tree.insert('', 'end', values=(_user_id, identity+self.im_user.get_nickname(_user_id)))
            else:
                if _user_id in img_obj_dict and img_obj_dict[_user_id]:
                    group_user_list_tree.insert('', 'end', image=img_obj_dict[_user_id], values=(_user_id, identity+self.im_user.get_nickname(_user_id)))
                else:
                    group_user_list_tree.insert('', 'end', values=(_user_id, identity+self.im_user.get_nickname(_user_id)))

        group_user_list_tree.grid()
        if flag:
            menu_bar = tkinter.Menu(group_user_list_top)
            menu_bar.add_command(label="新增成员",
                                 command=lambda: group_user_operation(all_group_members_list, group_user_list_top,
                                                                      comm_id, group_user_list_tree, 1,
                                                                      after_menu=menu_bar))
            menu_bar.add_command(label="删除成员",
                                 command=lambda: group_user_operation(all_group_members_list, group_user_list_top,
                                                                      comm_id, group_user_list_tree, 0))
            if flag == 1:   # 1是群主，2是管理员
                menu_bar.add_command(label="转让群主",
                                     command=lambda: group_user_operation(all_group_members_list, group_user_list_top,
                                                                          comm_id, group_user_list_tree, 2))
                menu_bar.add_command(label="管理员设置",
                                     command=lambda: group_user_operation(all_group_members_list, group_user_list_top,
                                                                          comm_id, group_user_list_tree, 3))
            menu_bar.add_command(label="黑名单设置",
                                 command=lambda: group_user_operation(all_group_members_list, group_user_list_top,
                                                                      comm_id, group_user_list_tree, 4))
            menu_bar.add_command(label="禁言设置",
                                 command=lambda: group_user_operation(all_group_members_list, group_user_list_top,
                                                                      comm_id, group_user_list_tree, 5))
            group_user_list_top.config(menu=menu_bar)
        else:
            menu_bar = tkinter.Menu(group_user_list_top)
            menu_bar.add_command(label="邀请好友",
                                 command=lambda: group_user_operation(all_group_members_list, group_user_list_top,
                                                                      comm_id, group_user_list_tree, 1,
                                                                      after_menu=menu_bar))
            group_user_list_top.config(menu=menu_bar)
        scrollbar = tkinter.Scrollbar(group_user_list_top)
        scrollbar.grid(row=1, column=1, sticky=tkinter.E + tkinter.N + tkinter.S)
        scrollbar.config(command=group_user_list_tree.yview)  # 绑定拖动

        group_user_list_tree.config(yscrollcommand=scrollbar.set)  # 绑定设置滚动条
        # group_user_list_tree.tag_configure('add', background='orange')

        group_user_list_tree.bind("<Button-3>", lambda event: self.group_member_operation(event, group_user_list_top,
                                                                                          group_user_list_tree))

        group_user_list_top_obj.show()

    def show_qrcode(self, _top):
        self.debug('[show_qrcode]')
        if not self.im_user:
            messagebox.showwarning('warning', '当前未登录')
            return
        json_str = '{' + '"action":"addFriend","appId":"{}","userId":"{}"'.format(self.app_id, self.user_id) + '}'
        b64_json_str_bin = base64.b64encode(json_str.encode('utf-8'))

        qr = qrcode.QRCode(
            version=4,
            box_size=4,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            border=4
        )

        qr.add_data(b64_json_str_bin.decode('utf-8'))  # 自定义字符串

        img = qr.make_image()  # 生成img对象
        img = img.convert('RGBA')
        try:
            bytes_head_photo = self.im_user.get_user_head_photo_bytes()
        except Exception as _e:
            messagebox.showerror('error', _e, parent=_top)
        else:
            sub_top_obj = SubTop('我的二维码', _top)
            top = sub_top_obj.get_handle()
            # 有头像就显示头像在二维码中间
            if bytes_head_photo:
                try:
                    icon = Image.open(BytesIO(bytes_head_photo))  # 待添加图片
                except Exception as _e:
                    messagebox.showerror('error', _e, parent=_top)
                else:
                    icon = icon.resize((100, 100))  # 重新定义尺寸
                    icon = icon.convert('RGBA')
                    img_w, img_h = img.size
                    icon_w, icon_h = icon.size
                    place_w, place_h = int((img_w - icon_w) / 2), int((img_h - icon_h) / 2)
                    img.paste(icon, (place_w, place_h), icon)  # 将icon放置在二维码中心

            tk_image = ImageTk.PhotoImage(image=img.resize((250, 250)))
            l2 = tkinter.Label(top, image=tk_image)
            l2.grid()
            sub_top_obj.show()

    def show_group_share_file(self, group_id, window_top, identity):
        PAGE_SIZE = 20
        sub_top_obj = SubTop('', window_top)
        sub_top = sub_top_obj.get_handle()

        file_info_list = []
        res = self.im_user.get_group_share_file_list(group_id, count=PAGE_SIZE)
        assert res['code'] == '0'
        file_info_list.extend(res['data']['fileList'])
        
        fd = open('test.log', 'w+')
        
        fd.write(str(res['data']['fileList']))
        fd.write('\r\n')
        
        while len(res['data']['fileList']) == PAGE_SIZE:
            cursor = res['data']['cursor']
            res = self.im_user.get_group_share_file_list(group_id, count=PAGE_SIZE, create_time=cursor)
            assert res['code'] == '0'
            file_info_list.extend(res['data']['fileList'])
            fd.write(str(cursor)+'---'+str(res['data']['leftCount']))
            fd.write('\r\n')
            fd.write(str(res['data']['fileList']))
            fd.write('\r\n')

        col = ['upload_user', 'file_name', 'file_id', 'file_uri']
        tree = ttk.Treeview(sub_top, columns=col, height=12)
        tree.heading("upload_user", text="上传用户")  # 设置表头
        tree.heading("file_name", text="文件名")  # 设置表头
        tree.heading("file_id", text="文件ID")  # 设置表头
        tree.heading("file_uri", text="链接")
        tree.column("#0", width=80)  # 设置列宽等属性
        vsb = ttk.Scrollbar(sub_top, orient="vertical", command=tree.yview)

        tree.grid(column=0, row=0)
        tree.config(yscrollcommand=vsb.set)  # 绑定设置滚动条
        vsb.grid(column=1, row=0, sticky=tkinter.NS)

        all_size = 0
        for info in file_info_list:
            if info['uploadUserId'] not in self.head_imgs:
                head_img = self.im_user.get_user_head_photo_bytes(info['uploadUserId'])
                if head_img:
                    self.head_imgs[info['uploadUserId']] = img_to_tk_img(head_img, 25)
                else:
                    self.head_imgs[info['uploadUserId']] = None
            all_size += info['fileSize']
            if self.head_imgs[info['uploadUserId']]:
                tree.insert('', 'end', image=self.head_imgs[info['uploadUserId']], values=(self.im_user.get_nickname(info['uploadUserId']), info['fileName'], info['fileID'], info['fileUri']))
            else:
                tree.insert('', 'end', values=(self.im_user.get_nickname(info['uploadUserId']), info['fileName'], info['fileID'], info['fileUri']))

        all_size_mb = round(all_size/1024/1024, 2)

        sub_top.title(f'群共享文件 - {len(file_info_list)} - {all_size_mb}MB - {all_size}B')
        sub_top_obj.show()

    def show_group_list(self):
        self.debug('[show_group_list]')

        def exit_group(comm_id, top_tree, remove_flag=None):
            try:
                if remove_flag:
                    _res = self.im_user.remove_group(comm_id)
                else:
                    _res = self.im_user.exit_group(comm_id)
            except Exception as error:
                messagebox.showerror('error', error, parent=top)
            else:
                if _res['code'] == '0':
                    tree_children_list = top_tree.get_children()  # 获取行对象
                    for item in tree_children_list:
                        _id = tree.item(item, "values")[0]
                        if _id == comm_id:
                            top_tree.delete(item)
                            break
                    messagebox.showinfo('info', _res, parent=top)
                else:
                    messagebox.showwarning('warning', _res, parent=top)

        def delete_all_group():
            """
            退出所有群聊
            """
            ans = messagebox.askyesno('警告', '是否退出所有群聊')
            # print(ans)
            group_list_res = self.im_user.get_group_list()
            # print(group_list_res)
            for group_info in group_list_res['data']:
                if group_info['ownerId'] == self.user_id:
                    self.im_user.remove_group(group_info['communicationId'])
                else:
                    self.im_user.exit_group(group_info['communicationId'])

        def create_group(sub_top, _tree, top_tree):
            user_id_list = []
            selected_item_list = _tree.selection()  # 返回的是选中的id list
            for _item in selected_item_list:
                user_id = _tree.item(_item, 'values')[0]
                user_id_list.append(user_id)
            # if len(user_id_list) >= 2:
            try:
                _im_user = getattr(self, 'im_user')
                _res = _im_user.create_group(user_id_list)
            except Exception as error:
                messagebox.showerror('error', error, parent=sub_top)
            else:
                if _res['code'] == '0':
                    data = _res['data']
                    # resp = requests.get(data['avatar'])
                    # group_head_img = resp.content if resp.status_code == 200 else None
                    self.im_user.get_group_detail(data['communicationId'])
                    group_head_img = self.im_user.get_group_head_photo_bytes(data['communicationId'])
                    if group_head_img:
                        tk_img = self.img_to_tk_img(group_head_img, 50)
                        self.head_imgs[data['communicationId']] = tk_img
                        top_tree.insert('', 0, image=self.head_imgs[data['communicationId']], values=(data['communicationId'], data['name'], self.user_id, 2))
                    else:
                        top_tree.insert('', 0, values=(data['communicationId'], data['name'], self.user_id, 2))
                messagebox.showinfo('info', _res, parent=sub_top)
            # sub_top.destroy()

        def create_group_communication(parent_top, parent_tree):

            def show_create_group_menu(event, _sub_top, _tree, _parent_tree):
                menu = tkinter.Menu(_sub_top, tearoff=0)
                selected_item_list = _tree.selection()
                menu.add_command(label='当前选中{}个好友'.format(len(selected_item_list)))
                menu.add_separator()
                menu.add_command(label="创建群聊", command=lambda: create_group(_sub_top, _tree, _parent_tree))  # 增加菜单栏
                menu.post(event.x_root, event.y_root)

            sub_top_obj = SubTop('新建群聊', parent_top)
            sub_top = sub_top_obj.get_handle()
            try:
                _im_user = getattr(self, 'im_user')
                _res = _im_user.get_friend_list()
            except Exception as error:
                messagebox.showerror('error', error, parent=sub_top)
                return

            _col = ['user_id', 'nickname']
            _tree = ttk.Treeview(sub_top, columns=_col, height=18, show="headings")
            _tree.heading("user_id", text="用户ID")  # 设置表头
            _tree.heading("nickname", text="用户昵称")  # 设置表头
            _vsb = ttk.Scrollbar(sub_top, orient="vertical", command=_tree.yview)
            _tree.bind("<Button-3>", lambda event: show_create_group_menu(event, sub_top, _tree, parent_tree))
            _tree.config(yscrollcommand=_vsb.set)  # 绑定设置滚动条

            for _info in _res['data']:
                _val = list()
                _val.append(_info['userId'])
                _nickname = self.im_user.get_nickname(_info['userId'])
                _tree.insert('', 0, values=(_val, _nickname))
            _tree.grid(column=0, row=0)
            _vsb.grid(column=1, row=0, sticky=tkinter.NS)
            sub_top.resizable(0, 0)
            sub_top_obj.show()

        def close_group_list_window(father):
            self.show_group = True
            father.destroy()

        def popupmenu(parent_top, parent_tree, event):
            menu = tkinter.Menu(parent_tree, tearoff=0)
            text_menu = tkinter.Menu(parent_tree, tearoff=0)
            file_menu = tkinter.Menu(parent_tree, tearoff=0)
            img_menu = tkinter.Menu(parent_tree, tearoff=0)
            video_menu = tkinter.Menu(parent_tree, tearoff=0)
            audio_menu = tkinter.Menu(parent_tree, tearoff=0)
            location_menu = tkinter.Menu(parent_tree, tearoff=0)
            read_destroy_menu = tkinter.Menu(parent_tree, tearoff=0)
            emoji_menu = tkinter.Menu(parent_tree, tearoff=0)
            red_packet_menu = tkinter.Menu(parent_tree, tearoff=0)
            card_menu = tkinter.Menu(parent_tree, tearoff=0)

            selected_item_list = parent_tree.selection()
            selected_item_list_len = len(selected_item_list)
            if selected_item_list_len == 1:
                cur_item = parent_tree.focus()
                if cur_item != '':
                    _info = parent_tree.item(cur_item, option='values')
                    name = _info[1]
                    # if type(name) == int:
                    #     name = str(name)
                    new_name = name
                    if len(new_name) > 23:
                        new_name = name[0:21] + '...'
                    menu.add_command(label=new_name)
                    menu.add_separator()
                    _comm_id, _to_id, _owner_id, _comm_type = _info
                    if type(_owner_id) == int:
                        _owner_id = str(_owner_id)

                    for _menu, msg_type, menu_content in zip((text_menu, file_menu, img_menu, video_menu, audio_menu, location_menu, read_destroy_menu, emoji_menu), (1, 3, 4, 6, 5, 7, -1, 2), ('文本消息', '文件消息', '图片消息', '视频消息', '语音消息', '位置消息', '阅后即焚消息', '表情消息')):
                        _menu.add_command(label=menu_content)
                        _menu.add_separator()
                        for i in (1, 10, 50, 200, 500, 1000, 2000, 5000, 10000):
                            _menu.add_command(label=f"发送{i}条消息", command=lambda to_id=_to_id, comm_id=_comm_id, comm_type=_comm_type, msg_type=msg_type, times=i: self.send_msg(to_id, comm_id, comm_type, msg_type, times))  # 增加菜单栏
                    text_menu.add_command(label="发送自定义消息", command=lambda to_id=_to_id, comm_id=_comm_id, comm_type=_comm_type: self.send_customize_msg(parent_top, to_id, comm_id, comm_type, 1, 1))
                    red_packet_menu.add_command(label='红包消息')
                    red_packet_menu.add_separator()
                    red_packet_menu.add_command(
                        label="发送1个红包",
                        command=lambda to_id=_to_id, comm_id=_comm_id, comm_type=_comm_type: self.send_redpacket(
                            parent_top, 1.0, comm_id, comm_type, 1, None, 1)
                    )  # 增加菜单栏

                    card_menu.add_command(label='名片消息')
                    card_menu.add_separator()
                    for i in (1, 10, 50, 200, 500, 1000, 2000, 5000, 10000):
                        card_menu.add_command(
                            label=f"发送{i}条消息",
                            command=lambda to_id=None, comm_id=_comm_id, comm_type=_comm_type, times=i: self.send_custom_msg(to_id, comm_id, comm_type, 'card', times)
                        )  # 增加菜单栏clear

                    menu.add_cascade(label='发送文本消息', menu=text_menu)
                    menu.add_cascade(label='发送图片消息', menu=img_menu)
                    menu.add_cascade(label='发送附件消息', menu=file_menu)
                    menu.add_cascade(label='发送视频消息', menu=video_menu)
                    menu.add_cascade(label='发送语音消息', menu=audio_menu)
                    menu.add_cascade(label='发送位置消息', menu=location_menu)
                    menu.add_cascade(label='发送阅后即焚消息', menu=read_destroy_menu)
                    menu.add_cascade(label='发送表情消息', menu=emoji_menu)
                    menu.add_cascade(label='发送名片消息', menu=card_menu)
                    menu.add_cascade(label='发送红包消息', menu=red_packet_menu)

                    group_detail_res = self.im_user.get_group_detail(_comm_id)  # 查询群详情
                    self.group_info[_comm_id] = group_detail_res['data']    # 更新缓存
                    if self.user_id == group_detail_res['data']['ownerId'] or self.user_id in group_detail_res['data']['managerList']:
                        if self.user_id == group_detail_res['data']['ownerId']:
                            menu.add_command(label='解散群聊', command=lambda: exit_group(_comm_id, tree, 1))
                            menu.add_command(label='群成员管理',
                                             command=lambda: self.group_manager(_comm_id, parent_top, parent_tree, 1))
                            menu.add_command(label='群公告', command=lambda: self.show_group_announcement(parent_top, _comm_id, 1))
                        else:
                            menu.add_command(label='退出群聊', command=lambda: exit_group(_comm_id, tree, 0))
                            menu.add_command(label='群成员管理',
                                             command=lambda: self.group_manager(_comm_id, parent_top, parent_tree, 2))
                            menu.add_command(label='群公告', command=lambda: self.show_group_announcement(parent_top, _comm_id, 2))
                        menu.add_command(label='更多设置',
                                         command=lambda: self.show_group_detail_setting(None, _comm_id, parent_top,
                                                                                        parent_tree, 1))
                        menu.add_command(label='群共享文件',
                                         command=lambda: self.show_group_share_file(_comm_id, parent_top, 1))
                    else:
                        menu.add_command(label='退出群聊', command=lambda: exit_group(_comm_id, tree))
                        menu.add_command(label='群公告', command=lambda: self.show_group_announcement(parent_top, _comm_id, 0))
                        menu.add_command(label='查看群成员',
                                         command=lambda: self.group_manager(_comm_id, parent_top, parent_tree, 0))
                        menu.add_command(label='群共享文件',
                                         command=lambda: self.show_group_share_file(_comm_id, parent_top, 0))
            elif selected_item_list_len > 1:
                work_name_list = []
                for _item in selected_item_list:
                    _vals = parent_tree.item(_item, 'values')
                    work_name_list.append(_vals[0])  # work name
                menu.add_command(label='当前选中{}个对象'.format(selected_item_list_len))

                menu.add_separator()
                text_menu.add_command(label="发送1条消息", command=lambda: self.send_msg_multi(tree, 1, 'group'))
                text_menu.add_command(label="发送10条消息", command=lambda: self.send_msg_multi(tree, 10, 'group'))
                text_menu.add_command(label="发送50条消息", command=lambda: self.send_msg_multi(tree, 50, 'group'))
                text_menu.add_command(label="发送200条消息", command=lambda: self.send_msg_multi(tree, 200, 'group'))
                text_menu.add_command(label="发送500条消息", command=lambda: self.send_msg_multi(tree, 500, 'group'))
                text_menu.add_command(label="发送1000条消息", command=lambda: self.send_msg_multi(tree, 1000, 'group'))
                text_menu.add_command(label="发送2000条消息", command=lambda: self.send_msg_multi(tree, 2000, 'group'))
                text_menu.add_command(label="发送5000条消息", command=lambda: self.send_msg_multi(tree, 5000, 'group'))
                text_menu.add_command(label="发送10000条消息", command=lambda: self.send_msg_multi(tree, 10000, 'group'))
                menu.add_cascade(label='发送文本消息', menu=text_menu)
            menu.post(event.x_root, event.y_root)

        if self.im_user is None:
            messagebox.showwarning('warning', '当前未登录')
            return
        if self.show_group is False:
            try:
                hwnd = win32gui.FindWindow(None, '群列表')
                win32gui.SetForegroundWindow(hwnd)
            except Exception as e:
                messagebox.showerror('error', e)
            return
        try:
            im_user = getattr(self, 'im_user')
            # res = im_user.get_group_list()
        except Exception as e:
            messagebox.showerror('error', e)
        else:
            self.show_group = False
            top_obj = SubTop('群列表', self.root)
            top = top_obj.get_handle()
            col = ['comm_id', 'comm_name', 'owner_id', 'comm_type']
            ttk.Style().configure('friend_list.Treeview', rowheight=55)
            tree = ttk.Treeview(top, columns=col, height=12, style='friend_list.Treeview')
            tree.heading("comm_id", text="群ID")  # 设置表头
            tree.heading("comm_name", text="群名称")  # 设置表头
            tree.heading("owner_id", text="群主")  # 设置表头
            tree.heading("comm_type", text="会话类型")
            tree.column("comm_type", width=60)  # 设置列宽等属性
            tree.column("#0", width=80)  # 设置列宽等属性
            vsb = ttk.Scrollbar(top, orient="vertical", command=tree.yview)
            tree.bind("<Button-3>", lambda event: popupmenu(top, tree, event))
            tree.grid(column=0, row=0)
            tree.config(yscrollcommand=vsb.set)  # 绑定设置滚动条
            vsb.grid(column=1, row=0, sticky=tkinter.NS)

            menu_bar = tkinter.Menu(top)
            menu_bar.add_command(label="新建群聊", command=lambda: create_group_communication(top, tree))
            menu_bar.add_command(label="退出所有群聊", command=delete_all_group)
            top.config(menu=menu_bar)
            img_obj_dict = {}
            for _i in im_user.group_id_list:
                val = (
                    _i,
                    im_user.group_info[_i]['name'],
                    im_user.group_info[_i]['ownerId'],
                    2
                )
                group_img_head = self.im_user.get_group_head_photo_bytes(_i)
                if group_img_head:
                    img0 = self.img_to_tk_img(group_img_head, 50)
                    img_obj_dict[_i] = img0
                    tree.insert('', 0, image=img_obj_dict[_i], values=val)
                else:
                    tree.insert('', 0, values=val)

            top.protocol("WM_DELETE_WINDOW", lambda: close_group_list_window(top))
            top.resizable(0, 0)
            top_obj.show()

    def create_chat_room(self, window, window_tree):
        try:
            res = self.im_user.create_chat_room()
        except Exception as _e:
            messagebox.showerror('error', _e, parent=window)
        else:
            if res['code'] == '0':
                chat_room_info = res['data']
                messagebox.showinfo('info', res, parent=window)
                communication_id = chat_room_info['communicationId']
                chat_room_avatar = self.im_user.get_chat_room_head_photo_bytes(communication_id)
                self.head_imgs[communication_id] = img_to_tk_img(chat_room_avatar, 15)
                window_tree.insert('', 0, image=self.head_imgs[communication_id], values=(chat_room_info['name'], communication_id, chat_room_info['roomId']))
            else:
                messagebox.showwarning('warning', res, parent=window)

    def show_chat_room_list(self):

        def dynamic_update_chat_room_list(window, window_tree, chat_room_list_type):
            if len(window_tree.get_children()) == 0:
                return
            if window_tree.yview()[1] == 1.0:
                last_item = window_tree.get_children()[-1]
                last_item_room_comm_id = window_tree.item(last_item, 'values')[1]
                room_info = self.im_user.chat_room_info[last_item_room_comm_id]
                self.debug('[dynamic_update_chat_room_list]', '到底部了', chat_room_list_type, room_info)
                create_time = room_info['createTime']
                try:
                    res = self.im_user.get_chat_room_list_by_type(chat_room_list_type, create_time=create_time)
                except Exception as _e:
                    messagebox.showerror('error', _e, parent=window)
                else:
                    # self.debug('[dynamic_update_chat_room_list]', res)
                    if res['code'] == '0':
                        if 'chatRoomList' in res['data']:
                            chat_room_info_list = res['data']['chatRoomList']
                        else:
                            chat_room_info_list = res['data']
                        if len(chat_room_info_list) == 0:
                            window_tree.unbind('<MouseWheel>')
                            self.debug('[dynamic_update_chat_room_list]', '没有更多数据了')
                            return
                        chat_room_id_list = []
                        for chat_room_info in chat_room_info_list:
                            self.im_user.chat_room_info[chat_room_info['communicationId']] = chat_room_info
                            chat_room_id_list.append(chat_room_info['communicationId'])
                        self.im_user.get_chat_room_head_photo_bytes_multi(chat_room_id_list)
                        for chat_room_info in chat_room_info_list:
                            # self.im_user.chat_room_info[chat_room_info['communicationId']] = chat_room_info
                            chat_room_head_img = self.im_user.get_chat_room_head_photo_bytes(
                                chat_room_info['communicationId'])
                            if chat_room_head_img:
                                tk_img = self.img_to_tk_img(chat_room_head_img, 15)
                                self.head_imgs[chat_room_info['communicationId']] = tk_img
                                window_tree.insert('', 'end', image=self.head_imgs[chat_room_info['communicationId']],
                                                   values=(chat_room_info['name'], chat_room_info['communicationId'],
                                                           chat_room_info['roomId']))
                            else:
                                window_tree.insert('', 'end', values=(
                                    chat_room_info['name'], chat_room_info['communicationId'],
                                    chat_room_info['roomId']))
                    else:
                        messagebox.showwarning('warning', res, parent=window)

        def show_chat_room_list_by_type(chat_room_list_type, window, window_tree):
            window_tree.unbind('<MouseWheel>')
            if chat_room_list_type == 0:
                window_tree.bind('<MouseWheel>', lambda event: dynamic_update_chat_room_list(window, window_tree, chat_room_list_type))
            try:
                res = self.im_user.get_chat_room_list_by_type(chat_room_list_type)
            except Exception as _e:
                messagebox.showerror('error', _e, parent=window)
            else:
                # self.debug('[show_chat_room_list_by_type]', res)
                if chat_room_list_type == 1:
                    self.debug('[show_chat_room_list_by_type]', [_['communicationId'] for _ in res['data']])
                if res['code'] == '0':
                    x = window_tree.get_children()
                    for item in x:
                        window_tree.delete(item)
                    if 'chatRoomList' in res['data']:
                        chat_room_info_list = res['data']['chatRoomList']
                    else:
                        chat_room_info_list = res['data']
                    chat_room_id_list = []
                    for chat_room_info in chat_room_info_list:
                        self.im_user.chat_room_info[chat_room_info['communicationId']] = chat_room_info
                        chat_room_id_list.append(chat_room_info['communicationId'])
                    self.im_user.get_chat_room_head_photo_bytes_multi(chat_room_id_list)
                    for chat_room_info in chat_room_info_list:
                        # self.im_user.chat_room_info[chat_room_info['communicationId']] = chat_room_info
                        chat_room_head_img = self.im_user.get_chat_room_head_photo_bytes(
                            chat_room_info['communicationId'])
                        if chat_room_head_img:
                            tk_img = self.img_to_tk_img(chat_room_head_img, 15)
                            self.head_imgs[chat_room_info['communicationId']] = tk_img
                            window_tree.insert('', 'end', image=self.head_imgs[chat_room_info['communicationId']],
                                               values=(chat_room_info['name'], chat_room_info['communicationId'],
                                                       chat_room_info['roomId']))
                        else:
                            window_tree.insert('', 'end', values=(
                            chat_room_info['name'], chat_room_info['communicationId'], chat_room_info['roomId']))
                else:
                    messagebox.showwarning('warning', res, parent=window)

        if self.im_user is None:
            messagebox.showwarning('warning', '当前未登录', parent=self.root)
            return

        sub_top_obj = SubTop('聊天室', self.root)
        top = sub_top_obj.get_handle()

        column = ('name', 'communication_id', 'room_id')
        tree = ttk.Treeview(top, columns=column, height=15)
        tree.heading("name", text="名称")  # 设置表头
        tree.heading("communication_id", text="会话id")  # 设置表头
        tree.heading("room_id", text="聊天室id")  # 设置表头
        tree.column('#0', width=45)
        tree.bind("<Double-Button-1>", lambda event: self.enter_chat_room(tree))

        vsb = ttk.Scrollbar(top, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)

        menu_bar = tkinter.Menu(top)
        menu_bar.add_command(label="创建聊天室", command=lambda: self.create_chat_room(top, tree))
        top.config(menu=menu_bar)  # 设置菜单

        invite_val = tkinter.IntVar()
        invite_man_radio = tkinter.Radiobutton(top, value=0, text="公开聊天室", variable=invite_val, command=lambda: show_chat_room_list_by_type(0, top, tree))
        invite_woman_radio = tkinter.Radiobutton(top, value=1, text="个人聊天室", variable=invite_val, command=lambda: show_chat_room_list_by_type(1, top, tree))
        invite_man_radio.grid(row=0, column=0)
        invite_woman_radio.grid(row=0, column=1)
        tree.grid(row=1, column=0, columnspan=2)
        vsb.grid(row=1, column=2, sticky=tkinter.NS)
        invite_val.set(0)

        show_chat_room_list_by_type(0, top, tree)
        sub_top_obj.show()

    def show_chat_room_list_by_type(self, chat_room_list_type, window, window_tree):
        """
        展示公开/个人聊天室列表
        :param chat_room_list_type:
        :param window:
        :param window_tree:
        :return:
        """
        try:
            res = self.im_user.get_chat_room_list_by_type(chat_room_list_type)
        except Exception as _e:
            messagebox.showerror('error', _e, parent=window)
        else:
            if res['code'] == '0':
                x = window_tree.get_children()
                for item in x:
                    window_tree.delete(item)
                if 'chatRoomList' in res['data']:
                    chat_room_info_list = res['data']['chatRoomList']
                else:
                    chat_room_info_list = res['data']
                chat_room_id_list = []
                for chat_room_info in chat_room_info_list:
                    self.im_user.chat_room_info[chat_room_info['communicationId']] = chat_room_info
                    chat_room_id_list.append(chat_room_info['communicationId'])
                self.im_user.get_chat_room_head_photo_bytes_multi(chat_room_id_list)
                for chat_room_info in chat_room_info_list:
                    # self.im_user.chat_room_info[chat_room_info['communicationId']] = chat_room_info
                    chat_room_head_img = self.im_user.get_chat_room_head_photo_bytes(chat_room_info['communicationId'])
                    if chat_room_head_img:
                        tk_img = self.img_to_tk_img(chat_room_head_img, 15)
                        self.head_imgs[chat_room_info['communicationId']] = tk_img
                        window_tree.insert('', 'end', image=self.head_imgs[chat_room_info['communicationId']], values=(chat_room_info['name'], chat_room_info['communicationId'], chat_room_info['roomId']))
                    else:
                        window_tree.insert('', 'end', values=(chat_room_info['name'], chat_room_info['communicationId'], chat_room_info['roomId']))
            else:
                messagebox.showwarning('warning', res, parent=window)

    # def show_chat_room_member_list(self, chat_room_id, window):
    #     res = self.im_user.get_chat_room_member_list(chat_room_id)
    #     sub_top_obj = SubTop('聊天室成员列表', window)
    #     top = sub_top_obj.get_handle()
    #     tree = ttk.Treeview(top, columns=('name', 'id'))
    #     tree.column('#0', width=45)
    #     for user in res['data']['userList']:
    #         if user['userId'] in self.head_imgs:
    #             tree.insert('', 'end', image=self.head_imgs[user['userId']], values=(self.im_user.get_nickname(user['userId']), user['userId']))
    #         else:
    #             head_img = self.im_user.get_user_head_photo_bytes(user['userId'])
    #             if head_img:
    #                 tk_img = img_to_tk_img(head_img, 15)
    #                 self.head_imgs[user['userId']] = tk_img
    #                 tree.insert('', 'end', image=self.head_imgs[user['userId']], values=(self.im_user.get_nickname(user['userId']), user['userId']))
    #             else:
    #                 tree.insert('', 'end', values=(self.im_user.get_nickname(user['userId']), user['userId']))
    #     tree.grid()
    #     sub_top_obj.show()

    def recall_msg(self, window, communication_id, msg_id, tree, item, msg_index=None):
        """

        :param window:
        :param communication_id:
        :param msg_id:
        :param tree:
        :param item:
        :param msg_index: 该消息在im_user的communication_msg[communication_id]中的下标
        :return:
        """
        try:
            res = self.im_user.recall_msg(communication_id, msg_id)
        except Exception as _e:
            messagebox.showerror('error', _e, parent=window)
        else:
            messagebox.showinfo('info', res, parent=window)
            if 'code' in res and res['code'] == '0':
                tree.delete(item)
                if msg_index is not None:
                    self.im_user.communication_msg[communication_id][msg_index]['message_main_type'] = 100
                    self.im_user.communication_msg[communication_id][msg_index]['message_type'] = 100
                    self.im_user.communication_msg[communication_id][msg_index]['content'] = '你撤回了一条消息'

    def show_chat_room_msg_detail(self, event, window, tree, chat_room_id):
        self.debug('[show_chat_room_msg_detail]')
        items = tree.selection()
        if len(items) != 1:
            return
        values = tree.item(items[0], 'values')
        if values == '':
            return
        # print(values, type(values))
        tag = values[-1]
        msg = self.im_user.chat_room_msg[chat_room_id][tag]
        menu = tkinter.Menu(window, tearoff=0)

        def show_msg():
            sub_top_obj = SubTop('消息详情', window)
            sub_top = sub_top_obj.get_handle()
            text = tkinter.Text(sub_top)
            json_str = json.dumps(msg, indent=4, ensure_ascii=False)
            text.insert('end', json_str)
            text.grid()
            sub_top_obj.show()

        menu.add_command(label="查看详情", command=show_msg)  # 增加菜单栏
        if 'message_id' in msg and msg['message_main_type'] == 1 and 'from_user_id' in msg and msg['from_user_id'] == self.user_id and 1000*time() - int(msg['send_time']) <= 120000:
            menu.add_command(label="撤回", command=lambda: self.recall_msg(window, chat_room_id, msg['message_id'], tree, items[0]))  # 增加菜单栏
        menu.post(event.x_root, event.y_root)
        # pprint.pprint(msg)

    def chat_room_member_list_operation_by_type(self, window, window_tree, chat_room_id, member_list_type, operation, before_menu_bar, before_user_list):
        window_tree.unbind('<MouseWheel>')
        member_list_type_to_method = {
            0: self.im_user.set_chat_room_member,
            1: self.im_user.set_chat_room_manager,
            2: self.im_user.set_chat_room_black_list,
            3: self.im_user.set_chat_room_white_list,
            4: self.im_user.set_chat_room_mute
        }
        children_items = window_tree.get_children()
        current_user_list = []
        selection_user_list = []
        selected_item_list = window_tree.selection()
        for item in selected_item_list:
            selection_user_list.append(window_tree.item(item, 'values')[1])
        # print(selection_user_list)
        if len(selection_user_list) > 0:
            method = member_list_type_to_method[member_list_type]
            try:
                res = method(chat_room_id, ','.join(selection_user_list), operation)
            except Exception as _e:
                messagebox.showerror('error', _e, parent=window)
                return
            else:
                if 'code' in res and res['code'] == '0':
                    messagebox.showinfo('info', res, parent=window)
                    for item in children_items:
                        current_user_list.append(window_tree.item(item, 'values')[1])
                        window_tree.delete(item)
                    if operation == 'add':
                        tmp = before_user_list[:]
                        tmp.extend(selection_user_list)
                    elif operation == 'remove':
                        tmp = [i for i in before_user_list if i not in selection_user_list]
                    else:
                        raise Exception(f'unknow operation {operation}')
                    for user_id in tmp:
                        window_tree.insert('', 'end', values=(self.im_user.get_nickname(user_id), user_id))
                else:
                    messagebox.showwarning('warning', res, parent=window)
                    return
                    # for user_id in before_user_list:
                    #     window_tree.insert('', 'end', values=(self.im_user.get_nickname(user_id), user_id))
        else:
            if operation == 'add':
                for item in children_items:
                    window_tree.delete(item)
                for user_id in before_user_list:
                    window_tree.insert('', 'end', values=(self.im_user.get_nickname(user_id), user_id))
        window.config(menu=before_menu_bar)

    def update_chat_room_members_list_by_type(self, _top, _tree, chat_room_id, member_list_type, operation, before_menu_bar):
        self.debug('[update_chat_room_members_list_by_type]')

        current_page = 1

        def dynamic_update_chat_room_member_list(top, tree, before_user_list):
            nonlocal current_page
            if tree.yview()[1] == 1.0:
                current_page += 1
                _res = self.im_user.get_chat_room_member_list(chat_room_id, cur_page=current_page)
                # print(current_page, _res)
                _user_info_list = _res['data']['userList']

                if len(_user_info_list) == 0 or _res['data']['curPage'] < current_page:
                    tree.unbind('<MouseWheel>')
                    return
                self.im_user.get_user_detail_by_multi([user['userId'] for user in _user_info_list])
                for user in _user_info_list:
                    if user['userId'] in before_user_list:
                        continue
                    if user['userId'] in self.head_imgs:
                        tree.insert('', 'end', image=self.head_imgs[user['userId']], values=(self.im_user.get_nickname(user['userId']), user['userId']))
                    else:
                        _head_img = self.im_user.get_user_head_photo_bytes(user['userId'])
                        if _head_img:
                            _tk_img = img_to_tk_img(_head_img, 15)
                            self.head_imgs[user['userId']] = _tk_img
                            tree.insert('', 'end', image=self.head_imgs[user['userId']], values=(self.im_user.get_nickname(user['userId']), user['userId']))
                        else:
                            tree.insert('', 'end', values=(self.im_user.get_nickname(user['userId']), user['userId']))

        current_user_list = []
        children_items = _tree.get_children()
        for item in children_items:
            current_user_list.append(_tree.item(item, 'values')[1])
        new_menu_bar = tkinter.Menu(_top)
        new_menu_bar.add_command(label="完成", command=lambda: self.chat_room_member_list_operation_by_type(_top, _tree, chat_room_id, member_list_type, operation, before_menu_bar, current_user_list))
        new_menu_bar.add_command(label="重新选择", command=lambda: clean_selection(_tree))
        _top.config(menu=new_menu_bar)
        if operation == 'add':
            res = self.im_user.get_chat_room_member_list(chat_room_id)
            user_info_list = res['data']['userList']
            new_user_list = [user['userId'] for user in user_info_list if user['userId'] not in current_user_list]
            for item in children_items:
                _tree.delete(item)
            for user_id in new_user_list:
                _tree.insert('', 'end', values=(self.im_user.get_nickname(user_id), user_id))
            _tree.bind('<MouseWheel>', lambda event: dynamic_update_chat_room_member_list(_top, _tree, current_user_list))
        elif operation == 'remove':
            pass

    def show_chat_room_member_list_by_type(self, chat_room_id, window, member_list_type, user_identity):
        """

        :param chat_room_id:
        :param window: 父窗口
        :param member_list_type: 展示的列表类型
        :param user_identity: 用户身份标识
        :return:
        """
        current_page = 1

        def dynamic_update_chat_room_member_list(_top, _tree):
            nonlocal current_page
            if _tree.yview()[1] == 1.0:
                current_page += 1
                _res = self.im_user.get_chat_room_member_list(chat_room_id, cur_page=current_page)
                # print(current_page, _res)
                _user_info_list = _res['data']['userList']

                if len(_user_info_list) == 0 or _res['data']['curPage'] < current_page:
                    _tree.unbind('<MouseWheel>')
                    return
                self.im_user.get_user_detail_by_multi([user['userId'] for user in _user_info_list])
                for user in _user_info_list:
                    if user['userId'] in self.head_imgs:
                        _tree.insert('', 'end', image=self.head_imgs[user['userId']], values=(self.im_user.get_nickname(user['userId']), user['userId']))
                    else:
                        _head_img = self.im_user.get_user_head_photo_bytes(user['userId'])
                        if _head_img:
                            _tk_img = img_to_tk_img(_head_img, 15)
                            self.head_imgs[user['userId']] = _tk_img
                            _tree.insert('', 'end', image=self.head_imgs[user['userId']], values=(self.im_user.get_nickname(user['userId']), user['userId']))
                        else:
                            _tree.insert('', 'end', values=(self.im_user.get_nickname(user['userId']), user['userId']))

        member_list_type_info = {
            0: '成员',
            1: '管理员',
            2: '黑名单',
            3: '白名单',
            4: '禁言'
        }
        if member_list_type == 0:
            res = self.im_user.get_chat_room_member_list(chat_room_id)
        elif member_list_type == 1:
            res = self.im_user.get_chat_room_manager_list(chat_room_id)
        elif member_list_type == 2:
            res = self.im_user.get_chat_room_black_list(chat_room_id)
        elif member_list_type == 3:
            res = self.im_user.get_chat_room_white_list(chat_room_id)
        elif member_list_type == 4:
            res = self.im_user.get_chat_room_mute_list(chat_room_id)
        else:
            raise Exception(f'unknow member_list_type {member_list_type}')

        if res['code'] != '0':
            messagebox.showerror('error', res, parent=window)
            return

        sub_top_obj = SubTop(f'聊天室{member_list_type_info[member_list_type]}列表', window)
        top = sub_top_obj.get_handle()
        tree = ttk.Treeview(top, columns=('name', 'id'), height=20)
        tree.column('#0', width=45)

        menu = tkinter.Menu(top)

        if user_identity != 'normal':
            if member_list_type == 0:
                menu.add_command(label='删除', command=lambda: self.update_chat_room_members_list_by_type(top, tree, chat_room_id, member_list_type, 'remove',  menu))
            elif member_list_type == 1 and user_identity == 'manager':
                pass
            else:
                menu.add_command(label='增加', command=lambda: self.update_chat_room_members_list_by_type(top, tree, chat_room_id, member_list_type, 'add', menu))
                menu.add_command(label='删除', command=lambda: self.update_chat_room_members_list_by_type(top, tree, chat_room_id, member_list_type, 'remove',  menu))

        top.config(menu=menu)

        if member_list_type == 0:
            user_info_list = res['data']['userList']
        else:
            user_info_list = res['data']

        self.im_user.get_user_detail_by_multi([user['userId'] for user in user_info_list])

        for user in user_info_list:
            if user['userId'] in self.head_imgs:
                tree.insert('', 'end', image=self.head_imgs[user['userId']], values=(self.im_user.get_nickname(user['userId']), user['userId']))
            else:
                head_img = self.im_user.get_user_head_photo_bytes(user['userId'])
                if head_img:
                    tk_img = img_to_tk_img(head_img, 15)
                    self.head_imgs[user['userId']] = tk_img
                    tree.insert('', 'end', image=self.head_imgs[user['userId']], values=(self.im_user.get_nickname(user['userId']), user['userId']))
                else:
                    tree.insert('', 'end', values=(self.im_user.get_nickname(user['userId']), user['userId']))
        tree.grid(row=0, column=0)

        vsb = ttk.Scrollbar(top, orient="vertical", command=tree.yview)

        tree.configure(yscrollcommand=vsb.set)
        vsb.grid(row=0, column=1, sticky=tkinter.NS)

        if member_list_type == 0:
            tree.bind('<MouseWheel>', lambda event: dynamic_update_chat_room_member_list(top, tree))

        tree.bind('<Button-3>', lambda event: show_tree_selection_count(event, tree))

        sub_top_obj.show()

    def remove_chat_room(self, chat_room_comm_id, top):
        try:
            res = self.im_user.remove_chat_room(chat_room_comm_id)
        except Exception as _e:
            messagebox.showerror('error', _e, parent=top)
        else:
            messagebox.showinfo('info', res, parent=top)
            if 'code' in res and res['code'] == '0':
                self.exit_chat_room(top, chat_room_comm_id)

    def exit_chat_room(self, window, chat_room_comm_id):
        try:
            res = self.im_user.exit_chat_room(chat_room_comm_id)
        except Exception as _e:
            messagebox.showerror('error', _e, parent=window)
        finally:
            if chat_room_comm_id in self.chat_room_pages:
                del self.chat_room_pages[chat_room_comm_id]
            window.destroy()

    def enter_chat_room(self, window_tree):
        _item = window_tree.focus()  # 返回的是选中行的id号，字符串类
        if _item == '':
            return
        chat_room_name, chat_room_comm_id, chat_room_id = window_tree.item(_item, 'values')
        chat_room_info = self.im_user.chat_room_info[chat_room_comm_id]
        try:
            res = self.im_user.enter_chat_room(chat_room_comm_id)
        except Exception as _e:
            messagebox.showerror('error', _e, parent=self.root)
            return
        else:
            if res['code'] != '0':
                messagebox.showwarning('warning', res, parent=self.root)
                return
        sub_top_obj = SubTop(f'[聊天室 - {chat_room_name}] [ID - {chat_room_id}]', self.root)
        top = sub_top_obj.get_handle()

        menu_bar = tkinter.Menu(top, tearoff=0)

        send_msg_menu = tkinter.Menu(top, tearoff=0)

        chat_room_mamage_menu = tkinter.Menu(top, tearoff=0)

        if self.user_id == chat_room_info['ownerId']:
            user_identity = 'admin'
        elif self.user_id in chat_room_info['managerList']:
            user_identity = 'manager'
        else:
            user_identity = 'normal'
        # 身份对应展示菜单项目内容
        identity_to_label = {
            'admin': ('成员列表', '管理员列表', '黑名单', '白名单', '禁言列表', '名称', '公告', '描述', '全员禁言', '解散聊天室'),
            'manager': ('成员列表', '管理员列表', '黑名单', '白名单', '禁言列表', '名称', '公告', '描述', '全员禁言'),
            'normal': ('成员列表', '管理员列表', '公告', '描述')
        }

        operation_to_method = {
            '成员列表': lambda: self.show_chat_room_member_list_by_type(chat_room_comm_id, top, 0, user_identity),
            '管理员列表': lambda: self.show_chat_room_member_list_by_type(chat_room_comm_id, top, 1, user_identity),
            '黑名单': lambda: self.show_chat_room_member_list_by_type(chat_room_comm_id, top, 2, user_identity),
            '白名单': lambda: self.show_chat_room_member_list_by_type(chat_room_comm_id, top, 3, user_identity),
            '禁言列表': lambda: self.show_chat_room_member_list_by_type(chat_room_comm_id, top, 4, user_identity),
            '解散聊天室': lambda: self.remove_chat_room(chat_room_comm_id, top),
            '公告': lambda: self.show_chat_room_announcement(top, chat_room_comm_id, user_identity),
            '描述': lambda: self.show_chat_room_description(top, chat_room_comm_id, user_identity),
            '名称': lambda: self.show_chat_room_name(top, chat_room_comm_id),
            '全员禁言': lambda: self.show_chat_room_all_mute(top, chat_room_comm_id)
        }

        for _text in identity_to_label[user_identity]:
            if _text in operation_to_method:
                chat_room_mamage_menu.add_command(label=_text, command=operation_to_method[_text])
            else:
                chat_room_mamage_menu.add_command(label=_text)

        text_menu = tkinter.Menu(top, tearoff=0)
        file_menu = tkinter.Menu(top, tearoff=0)
        img_menu = tkinter.Menu(top, tearoff=0)
        video_menu = tkinter.Menu(top, tearoff=0)
        audio_menu = tkinter.Menu(top, tearoff=0)
        location_menu = tkinter.Menu(top, tearoff=0)
        emoji_menu = tkinter.Menu(top, tearoff=0)
        card_menu = tkinter.Menu(top, tearoff=0)

        for _menu, msg_type, menu_content in zip(
                (text_menu, file_menu, img_menu, video_menu, audio_menu, location_menu, emoji_menu),
                (1, 3, 4, 6, 5, 7, 2), ('文本消息', '文件消息', '图片消息', '视频消息', '语音消息', '位置消息', '表情消息')):
            _menu.add_command(label=menu_content)
            _menu.add_separator()
            for i in (1, 10, 50, 100, 1000, 2000, 5000, 10000):
                _menu.add_command(label=f"发送{i}条消息",
                                  command=lambda to_id=None, comm_id=chat_room_comm_id, comm_type=3,
                                                 msg_type=msg_type, times=i: self.send_msg(to_id, comm_id, comm_type,
                                                                                           msg_type, times))  # 增加菜单栏
        card_menu.add_command(label='名片消息')
        card_menu.add_separator()
        for i in (1, 10, 50, 100, 1000, 2000, 5000, 10000):
            card_menu.add_command(label=f"发送{i}条消息", command=lambda to_id=None, comm_id=chat_room_comm_id, comm_type=3, times=i: self.send_custom_msg(to_id, comm_id, comm_type, 'card', times))  # 增加菜单栏

        send_msg_menu.add_cascade(label='发送文本消息', menu=text_menu)
        send_msg_menu.add_cascade(label='发送图片消息', menu=img_menu)
        send_msg_menu.add_cascade(label='发送附件消息', menu=file_menu)
        send_msg_menu.add_cascade(label='发送视频消息', menu=video_menu)
        send_msg_menu.add_cascade(label='发送语音消息', menu=audio_menu)
        send_msg_menu.add_cascade(label='发送位置消息', menu=location_menu)
        send_msg_menu.add_cascade(label='发送表情消息', menu=emoji_menu)
        send_msg_menu.add_cascade(label='发送名片消息', menu=card_menu)

        # menu_bar.add_command(label="发送消息", command=lambda: self.send_msg(None, chat_room_comm_id, 3, 1, 1))

        column = ('user_info', 'msg_type', 'content')
        tree = ttk.Treeview(top, columns=column, height=20)
        tree.heading('user_info', text='用户信息')
        tree.heading('content', text='内容')
        tree.heading('msg_type', text='消息类型')
        tree.column('#0', width=45)
        tree.column('user_info', width=200)
        tree.column('content', width=420)
        tree.tag_configure('self', background='#d9ead3')
        tree.grid(row=0, column=0)

        vsb = ttk.Scrollbar(top, orient="vertical", command=tree.yview)
        vsb.grid(row=0, column=1, sticky=tkinter.NS)
        tree.configure(yscrollcommand=vsb.set)

        tree.bind('<Button-3>', lambda event: self.show_chat_room_msg_detail(event, top, tree, chat_room_comm_id))

        menu_bar.add_cascade(label="发送消息", menu=send_msg_menu)
        menu_bar.add_cascade(label="聊天室详情", menu=chat_room_mamage_menu)
        menu_bar.add_command(label="清空消息", command=lambda: delete_tree_all_items(tree))

        top.config(menu=menu_bar)  # 设置菜单

        self.chat_room_pages[chat_room_comm_id] = tree

        top.protocol("WM_DELETE_WINDOW", lambda: self.exit_chat_room(top, chat_room_comm_id))  # 绑定函数,触发窗口关闭会执行close_window
        sub_top_obj.show()

    def popupmenu(self, father, event):
        self.debug('[popupmenu]')
        menu = tkinter.Menu(father, tearoff=0)
        selected_item_list = father.selection()
        selected_item_list_len = len(selected_item_list)
        if selected_item_list_len > 1:
            work_name_list = []
            for _item in selected_item_list:
                item = father.item(_item)
                work_name_list.append(item['values'][0])  # work name
            menu.add_command(label='当前选中{}个对象'.format(selected_item_list_len))
            menu.add_separator()
            menu.post(event.x_root, event.y_root)
        elif selected_item_list_len == 1:
            val = father.item(selected_item_list[0], 'values')
            comm_id = val[1]
            comm_name = val[0]
            if val[2] == '2':
                group_detail_res = self.im_user.get_group_detail(comm_id)  # 查询群详情
                self.group_info[comm_id] = group_detail_res['data']  # 更新缓存
                menu.add_command(label=comm_name)
                menu.add_separator()
                # menu.add_command(label='发送消息', command=lambda: self.send_msg('', comm_id, 2, 1, 1))
                if self.im_user.group_info[comm_id]['ownerId'] == self.user_id:
                    flag = 1
                elif self.user_id in self.im_user.group_info[comm_id]['managerList']:
                    flag = 2
                else:
                    flag = 0
                _label = '群成员管理' if flag else '查看群成员'
                menu.add_command(label=_label, command=lambda: self.group_manager(comm_id, self.root, father, flag))
                if flag:
                    menu.add_command(label='更多设置',
                                     command=lambda: self.show_group_detail_setting(None, comm_id, self.root, father,
                                                                                    0))
            elif val[2] == '1':
                menu.add_command(label=comm_name)
                # menu.add_separator()
                # to_user_id = val[3]
                # menu.add_command(label='发送消息', command=lambda: self.send_msg(to_user_id, comm_id, 1, 1, 10))
            menu.post(event.x_root, event.y_root)

    def analysis_msg_cost(self):
        if self.im_user is not None:
            self.im_user.analysis_msg_cost()

    def main(self):
        self.load_from_cfg()
        self.root.mainloop()
        self.debug('[main] exit')


if __name__ == '__main__':
    a = Gui()
    a.main()

