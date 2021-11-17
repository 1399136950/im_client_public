import tkinter
from tkinter import ttk, messagebox
import win32gui
import asyncio
from time import time
import os
from threading import Thread

from im_user import GUIIMUser
import agui
from utils.img2ico import img2ico


TREE_ROW_BG = '#d9ead3'  # 浅绿色


class SDKGui(agui.Gui):

    CFG_PATH = 'cfg/sdk_01_config.json'

    RUNTIME_FILE = 'runtime/sdk_01_runtime'

    def __init__(self):
        super().__init__()

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
        username_label = tkinter.Label(self.add_work_frame, text='用户ID', width=25)
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
        # col = ['comm_name', 'commid', 'comm_type', 'name', 'time', 'msg_count', 'msg_id', 'content']
        # ttk.Style().configure('main.Treeview', rowheight=30)
        # self.tree = ttk.Treeview(self.info_frame, columns=col, height=12, style='main.Treeview')
        # self.tree.heading("comm_name", text="会话名")  # 设置表头
        # self.tree.heading("commid", text="会话id")  # 设置表头
        # self.tree.heading("comm_type", text="会话类型")  # 设置表头
        # self.tree.heading("name", text="消息发送方")  # 设置表头
        # self.tree.heading("time", text="时间")
        # self.tree.heading("msg_count", text="新消息数量")
        # self.tree.heading("msg_id", text="消息id")
        # self.tree.heading("content", text="内容")
        # self.tree.column("time", width=160)  # 设置列宽等属性
        # self.tree.column("msg_count", width=70)  # 设置列宽等属性
        # self.tree.column("comm_type", width=60)  # 设置列宽等属性
        # self.tree.column("#0", width=60)  # 设置列宽等属性
        # # self.tree.column("msg_id", width=300)    # 设置列宽等属性
        # vsb = ttk.Scrollbar(self.info_frame, orient="vertical", command=self.tree.yview)
        # self.tree.bind("<Button-3>", lambda event: self.popupmenu(self.tree, event))
        # self.tree.bind("<Double-Button-1>", self.show_communication)
        # self.tree.grid(column=0, row=0)
        # vsb.grid(column=1, row=0, sticky=tkinter.NS)
        # self.tree.configure(yscrollcommand=vsb.set)
        # self.tree.tag_configure('diff', background=agui.TREE_ROW_BG)
        # self.add_work_tree.tag_configure('diff', background=agui.TREE_ROW_BG)
        # self.root.protocol("WM_DELETE_WINDOW", self.close_window)  # 绑定函数,触发窗口关闭会执行close_window

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

    def setting(self):
        self.debug('setting')

        def save_setting():
            old_cfg = agui.load_json_from_file(self.CFG_PATH)
            if old_cfg is None:
                old_cfg = {}
            old_cfg['app_id'] = app_id_entry.get()
            old_cfg['user_id'] = user_id_entry.get()
            old_cfg['pwd'] = pwd_entry.get()
            old_cfg['msg_sleep_time'] = float(msg_sleep_time_entry.get())
            # old_cfg['phone'] = phone_entry.get()
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

            agui.add_json_to_file(old_cfg, self.CFG_PATH)
            close_setting_window(top)

        def close_setting_window(_father):
            self.setting_flag = True
            _father.destroy()

        if self.setting_flag:
            self.setting_flag = False

            cfg = agui.load_json_from_file(self.CFG_PATH)
            self.debug('[setting]', cfg)

            sub_top_obj = agui.SubTop('本地设置', self.root)
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
                if 'user_id' in cfg:
                    user_id = tkinter.StringVar(top, value=cfg['user_id'])
                else:
                    user_id = tkinter.StringVar(top, value=self.user_id)
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
                user_id = tkinter.StringVar(top, value=self.user_id)
                app_id = tkinter.StringVar(top, value=self.app_id)
                pwd = tkinter.StringVar(top, value=self.pwd)
                # phone = tkinter.StringVar(top, value=self.phone)
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

            user_id_label = tkinter.Label(top, width=40, text='userid: ')
            user_id_entry = tkinter.Entry(top, width=40, textvariable=user_id)

            # user_name_label = tkinter.Label(top, width=40, text='user_name: ')
            # user_name_entry = tkinter.Entry(top, width=40, textvariable=user_name)

            # phone_label = tkinter.Label(top, width=40, text='phone: ')
            # phone_entry = tkinter.Entry(top, width=40, textvariable=phone)

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

            user_id_label.grid(row=1, column=0)
            user_id_entry.grid(row=1, column=1, columnspan=2)

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

    def load_from_cfg(self):
        self.debug('[load_from_cfg]')
        cfg_dict = agui.load_json_from_file(self.CFG_PATH)
        # print(cfg_dict)
        if cfg_dict:
            for _k in cfg_dict:
                setattr(self, _k, cfg_dict[_k])
                self.insert_add_tree('[初始化] [{}]\t[{}]'.format(_k, cfg_dict[_k]))
                if _k == 'user_id':
                    self.username_variable.set(cfg_dict[_k])
                elif _k == 'pwd':
                    self.pwd_variable.set(cfg_dict[_k])
            if self.auto_login:
                self.run_user(cfg_dict['user_id'], cfg_dict['pwd'])
        with open(self.RUNTIME_FILE, 'w+') as fd:
            fd.write('1')

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
                    'user_id': user_name
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

    def run_loop_thread(self, user_info):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        im_user = GUIIMUser(user_info, self.chat_room_pages, tree=self.tree)
        im_user.DEBUG = self.IM_USER_DEBUG
        im_user.INFO = self.IM_USER_INFO
        try:
            # im_user.login_demo()
            im_user.login_by_sdk()
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
        self.root.title(self.wdname)
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

if __name__ == '__main__':
    a = SDKGui()
    a.main()
