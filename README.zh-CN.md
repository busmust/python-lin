# python-lin

通过 BUSMUST 硬件设备进行 LIN（Local Interconnect Network）总线通信的 Python 库。

本软件包提供了类似 [python-can](https://github.com/hardbyte/python-can) 的编程接口，可以方便地使用 Python 控制 LIN 总线、收发 LIN 报文。

## 功能特性

- LIN 主机和从机模式（主机写入 / 主机读取 / 从机写入）
- 经典校验和增强校验和，自动计算 PID 与校验和
- 硬件周期性发送任务（TXTASK），精确控制定时
- 上拉电阻和 LIN 总线 12V 电压控制（输出 / 输入）

## 兼容设备

| 型号 | LIN 通道 | CAN FD | 说明 |
|------|---------|--------|------|
| BM-USB-CAN-L1 | 1 | 1 | 紧凑型单通道 LIN + CAN FD 适配器 |
| BM-USB-CAN-XL2 | 2 | 2 | 双通道 LIN + CAN FD 适配器 |
| BM-USB-CAN-XL4 | 4 | 4 | 四通道 LIN + CAN FD 适配器 |

## 安装

### 1. 安装 BMAPI 运行时库

从 [BMAPI SDK Releases](https://github.com/busmaster/bmapi-sdk/releases) 下载最新的 SDK，将运行时库复制到系统路径：

| 平台 | SDK 中的文件 | 安装方法 |
|------|-------------|---------|
| Windows 64-bit | `bin/win64/BMAPI64.dll` | 复制到 `C:\Windows\System32\`，或将 SDK 的 `bin/win64/` 加入 `PATH` |
| Windows 32-bit | `bin/win32/BMAPI.dll` | 复制到 `C:\Windows\System32\`，或将 SDK 的 `bin/win32/` 加入 `PATH` |
| Linux x86 64-bit | `bin/unix64/release/libbmapi64.so` | `sudo cp libbmapi64.so /usr/local/lib/ && sudo ldconfig` |
| Linux x86 32-bit | `bin/unix32/release/libbmapi.so` | `sudo cp libbmapi.so /usr/local/lib/ && sudo ldconfig` |
| Linux ARM 64-bit | `bin/aarch64-linux-gnu/release/libbmapi64.arm.so` | `sudo cp libbmapi64.arm.so /usr/local/lib/libbmapi64.so && sudo ldconfig` |
| Linux ARM 32-bit | `bin/arm-linux-gnueabihf/libbmapi.arm.so` | `sudo cp libbmapi.arm.so /usr/local/lib/libbmapi.so && sudo ldconfig` |

> **ARM 平台注意：** SO 文件名中的 `.arm` 后缀在复制到系统路径时需要去掉（例如 `libbmapi64.arm.so` → `/usr/local/lib/libbmapi64.so`）。

### 2. 设置 python-lin

```bash
export PYTHONPATH=/path/to/python-lin
```

## 快速开始

```python
from lin.interfaces.bmlin import BmLinBus
from lin.message import Message, LIN_MASTER_WRITE

# 创建 LIN 总线实例（主机模式）
bus = BmLinBus(channel=0, bitrate=19200, is_master=True)

# 发送 LIN 报文（主机写入）
msg = Message(lin_id=0x10, data=[0x01, 0x02, 0x03, 0x04], dlc=4, msgtype=LIN_MASTER_WRITE)
bus.send(msg)

# 接收 LIN 报文
msg = bus.recv(timeout=1.0)
print(f"Received: ID=0x{msg.lin_id:02X}, Data={list(msg.data)}")

bus.shutdown()
```

## 系统要求

- Python 3.7+
- BUSMUST LIN 硬件设备
- BMAPI 运行时库（包含在 [BMAPI SDK](https://github.com/busmaster/bmapi-sdk/releases) 中）

## 例程

参见 `examples/` 目录获取完整的使用示例：

- `bmapi_lin_txrx.py` — LIN 收发示例，支持主机/从机模式

## 使用 PyInstaller 打包

使用 PyInstaller 打包时需要：

1. 将 BMAPI DLL 捆绑到打包目录中
2. 声明 `lin.interfaces.bmlin` 为隐式导入

示例 spec 文件：

```python
from ctypes.util import find_library

# 从系统 PATH 查找 BMAPI DLL（若未找到则回退到本地文件）
dll_path = find_library('bmapi64') or 'BMAPI64.dll'

a = Analysis(
    ['your_app.py'],
    pathex=['/path/to/python-lin'],
    binaries=[(dll_path, '.')],
    hiddenimports=['lin.interfaces.bmlin'],
    # ... 其他 Analysis 选项
)
```

构建命令：

```bash
pyinstaller your_app.spec
```

运行时，DLL 通过打包目录中的 `_MEIPASS` 回退路径自动找到。

> **替代方案：** 如果不捆绑 DLL，则目标机器必须已安装 BMAPI 到系统路径。此时省略 `binaries` 行，运行时通过 `find_library()` 自动查找。

## 相关项目

- [BMAPI SDK](https://github.com/busmaster/bmapi-sdk) — BUSMUST 设备完整 SDK
- [python-can](https://github.com/busmust/python-can) — BUSMUST 的 CAN/CAN FD 接口

## 技术支持

微信搜索"霸码科技"，关注公众号后点击"技术支持"即可与技术人员一对一聊天获得深度技术支持。

## 许可证

详见 [LICENSE](LICENSE)。本软件包仅限与 BUSMUST 硬件设备配合使用。
