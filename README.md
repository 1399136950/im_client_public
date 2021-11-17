### 运行

在脚本根目录创建一个`cfg`文件夹，然后新建`config.json`文件，格式如下:

````json
{
    "app_id": "9eb745a14c44b7f5badbbb92092ee8e9#Jiao-IM-Demo",
    "phone": "12618400077",
    "pwd": "123456",
    "msg_sleep_time": 0.016,
    "auto_login": true
}
````

保存后，运行`agui.py`即可

另外，也可以不创建json文件，直接运行`agui.py`,然后在`本地设置`中设置相关参数并保存:

- appid: 应用id
- phone: 手机号
- pwd: 用户密码
- msg_sleep_time: 发送消息间隔
- auto login: 每次运行脚本是否自动登录
- gui_debug: gui相关debug打印
- im_user_debug: gim_user相关debug打印

### 服务器地址配置

`config.py`中设置服务器地址信息

````python
HOST = ''                 # rest api 服务器地址
LOGIN_HOST = ''           # 登录服务器地址
REDPACKET_HOST = ''       # 红包服务地址
IM_SERVER_ADDRESS = ()  # im 服务器地址
DEMO_HOST = ''            # demo 服务地址
````

### 第三方扩展

该脚本使用了一些第三方库如

```
win32gui
qrcode
requests
protobuf
pycryptodome(windows)/pycrypto(linux)
PythonMagick
```

具体见`requirements.txt`

### 临时文件

`runtime`文件夹存放脚本运行需要的临时文件,比如用户最近一次登录的id和时间戳信息.

### 打包

执行`unpack.sh`，自动将相关文件打包成exe可执行文件