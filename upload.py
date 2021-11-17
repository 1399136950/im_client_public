import cv2
import os
import sys

import sdk_api


def get_pic_url(_token, img_path):
    res = sdk_api.upload_file(_token, img_path)
    return res['data'][0]['fileUrl']


def upload_video(_token, video_path):
    video = cv2.VideoCapture(video_path)
    video_width = int(video.get(3))
    video_hight = int(video.get(4))
    frame = video.get(5)
    frame_count = video.get(7)
    file_duration = int(frame_count/frame)
    res = sdk_api.upload_file(_token, video_path)
    print(res['data'][0])
    _, first_img = video.read()
    cv2.imwrite('_tmp.png', first_img)
    img_url = get_pic_url(_token, '_tmp.png')
    
    data = {'file_name': res['data'][0]['fileName'], 'file_pic': img_url, 'file_size': res['data'][0]['fileSize'], 'file_uri': res['data'][0]['fileUrl'], 'file_suffix': video_path.split('.')[-1], 'file_duration': file_duration, 'image_width': video_width, 'image_height': video_hight, 'file_md5': res['data'][0]['fileMd5']}
    video.release()
    os.remove('_tmp.png')
    return data
    
    
def upload_image(_token, image_path):
    file_suffix = image_path.split('.')[-1]
    if file_suffix == 'gif':
        image = cv2.VideoCapture(image_path)
        image_width = int(image.get(3))
        image_hight = int(image.get(4))
        image.release()
    else:
        image = cv2.imread(image_path)
        image_width, image_hight, *_ = image.shape
    res = sdk_api.upload_file(_token, image_path)
    print(res['data'][0])
    data = {'file_name': res['data'][0]['fileName'], 'file_size': res['data'][0]['fileSize'], 'file_uri': res['data'][0]['fileUrl'], 'file_suffix': file_suffix, 'image_width': image_width, 'image_height': image_hight, 'file_md5': res['data'][0]['fileMd5']}
    return data
    
    
def _upload_file(_token, file_path):
    file_suffix = file_path.split('.')[-1]
    res = sdk_api.upload_file(_token, file_path)
    print(res['data'][0])
    data = {'file_name': res['data'][0]['fileName'], 'file_size': res['data'][0]['fileSize'], 'file_uri': res['data'][0]['fileUrl'], 'file_suffix': file_suffix, 'file_md5': res['data'][0]['fileMd5']}
    return data


if __name__ == '__main__':
    device_info = {
        'platform': 'web',
        'manufacturer': 'apple',
        'os_version': '10',
        'device_id': 'asd98h4rfnsdhiwefh932'
    }
    phone = '18211439620'
    pwd = '123456'
    from demo_api import *
    demo_res = login(phone, pwd)
    # print(demo_res)
    user_info = {
        # "app_id": "5751a0ff7c93eb26eb1ee2d45fe4a185#zhuanliao",
        "app_id": "9eb745a14c44b7f5badbbb92092ee8e9#Jiao-IM-Demo",
        "user_id": demo_res['data']['zxUserId']
    }
    _res = sdk_api.login_by_sdk(user_info, device_info, demo_res['data']['zxSdkLoginToken'])
    _token = _res['data']['access_token']
    
    model = sys.argv[1]
    file_path = sys.argv[2]
    if model == 'video':
        res = upload_video(_token, file_path)
        print(res)
    elif model == 'image':
        res = upload_image(_token, file_path)
        print(res)
    elif model == 'file':
        res = _upload_file(_token, file_path)
        print(res)
