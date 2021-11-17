ENV_MODEL = 'produce'

TIMEOUT = (10, 10)    # 接口超时时间

DEVICE_MODEL = 'android'  # 设备类型: android/ios/pc

if ENV_MODEL == 'dev':
    """
    外网测试服务器地址
    """
    HOST = ''                 # rest api 服务器地址
    LOGIN_HOST = ''           # 登录服务器地址
    REDPACKET_HOST = ''       # 红包服务地址
    IM_SERVER_ADDRESS = ()  # im 服务器地址
    DEMO_HOST = ''            # demo 服务地址
    AES_KEY = ''
elif ENV_MODEL == 'produce':
    """
    生产服务器地址
    """
    HOST = ''                 # rest api 服务器地址
    LOGIN_HOST = ''           # 登录服务器地址
    REDPACKET_HOST = ''       # 红包服务地址
    IM_SERVER_ADDRESS = ()  # im 服务器地址
    DEMO_HOST = ''            # demo 服务地址
    AES_KEY = ''
elif ENV_MODEL == 'jun':
    """
    君君测试服务器地址
    """
    HOST = ''                 # rest api 服务器地址
    LOGIN_HOST = ''           # 登录服务器地址
    REDPACKET_HOST = ''       # 红包服务地址
    IM_SERVER_ADDRESS = ()  # im 服务器地址
    DEMO_HOST = ''            # demo 服务地址
    AES_KEY = ''
