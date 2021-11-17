import PythonMagick
from PIL import Image, ImageTk
from io import BytesIO


def img2ico(src, dst):
    """
    图片转ico格式
    :param src: 原图片路径
    :param dst: 目的图片路径
    :return: None
    """
    img = PythonMagick.Image(src)
    img.sample('256x256')
    img.write(dst)


def img_to_tk_img(src_img: bytes, size: int):
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


if __name__ == '__main__':
    img2ico('default.jpg', 'default.ico')
