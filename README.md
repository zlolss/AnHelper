# 此版本因重构废稿，功能不全
# 说明
用于android设备远程实时控制的工具整合包。
- 封装了[minicap](https://github.com/bbsvip/minicap_minitouch_prebuilt/tree/main) 、 [minicap_sdk32](https://github.com/UrielCh/minicap-prebuilt)、 [minitouch](https://github.com/bbsvip/minicap_minitouch_prebuilt/tree/main) 、[ADBKeyboard](https://github.com/senzhk/ADBKeyBoard) 的预编译包
- 支持多线程（threading）中资源自动分配，但应避免在多进程（multiprocessing）中使用
- 支持多设备连接
- 支持安卓设备的实时截图(延迟约30~40ms)
- 支持修改分辨率
- 支持监听屏幕旋转
- 支持监听输入框弹出
- 内置触控点坐标变换
- 支持中文输入
- 包含一个远程控制demo
- 支持安卓系统版本android<=12, sdk<=32
- 使用server-client结构，支持从多个程序控制同一个设备，不会造成明显的性能降低

# 适用场景
- 有一定实时性要求的安卓游戏自动控制项目
- 需要从不同线程控制、获取屏幕内容的多线程项目

# 安装

```shell
pip install anhelper
```


# 已知问题
- 实体机上可能存在输入设备写入权限问题，导致minitouch无法运行。需要adb获取root权限。
- 部分机器需要手动在设置中开启ADBKeyboard并且手动切换输入法才可用。

# 用于安卓控制的同类开源项目推荐
- [uiautomator2](https://github.com/openatx/uiautomator2)
- [scrcpy](https://github.com/Genymobile/scrcpy)
- [QtScrcpy](https://github.com/barry-ran/QtScrcpy)
- [minidevice](https://github.com/NakanoSanku/minidevice/tree/dev)


# 在python项目中使用
```python
# 服务单独启动（自动检测，系统中只会有一个服务运行）
python -m anhelper.server
```

```python
from anhelper import client
# 创建客户端，默认选择第一个adb连接的安卓设备，添加形如devicename='emulator-5562'的参数来连接其他设备
# 设备名称见adb devices
c = client.Client(ensure=True)

# 获取截图（cv2格式的bgr矩阵）
im = c.cap()

## 在notebook中显示截图 
from PIL import Image
img = Image.fromarray(c.frame[:,:,[2,1,0]])
display(img)

# 在文本框中输入文本
c.imesend('hello')

# 点击相对坐标位置
c.touch(0.1,0.1)
```

# 包含开源项目许可声明

[minicap](https://github.com/DeviceFarmer/minicap/blob/master/LICENSE)

[minitouch](https://github.com/DeviceFarmer/minitouch/blob/master/LICENSE)

[ADBKeyBoard](https://github.com/senzhk/ADBKeyBoard/blob/master/LICENSE)

[vue](https://github.com/vuejs/core/blob/main/LICENSE)

[pure.css](https://github.com/pure-css/pure/blob/master/LICENSE)

[fontawesome](https://fontawesome.com/license/free)