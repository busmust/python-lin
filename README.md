# python-lin

A Python library for LIN (Local Interconnect Network) bus communication via BUSMUST hardware devices.

This package provides a programming interface similar to [python-can](https://github.com/hardbyte/python-can), making it easy to control LIN buses and send/receive LIN messages using Python.

## Features

- LIN Master and Slave mode (Master Write / Master Read / Slave Write)
- Classic and Enhanced checksum support with auto-calculation
- Hardware-periodic transmit tasks (TXTASK) with precise timing
- Pull-up resistor and LIN bus 12V voltage control (output / input)

## Supported Devices

| Model | LIN Channels | CAN FD | Notes |
|-------|-------------|--------|-------|
| BM-USB-CAN-L1 | 1 | 1 | Compact single-channel LIN + CAN FD adapter |
| BM-USB-CAN-XL2 | 2 | 2 | Dual-channel LIN + CAN FD adapter |
| BM-USB-CAN-XL4 | 4 | 4 | Quad-channel LIN + CAN FD adapter |

## Installation

### 1. Install BMAPI Runtime Library

Download the latest [BMAPI SDK](https://github.com/busmaster/bmapi-sdk/releases) and copy the runtime library to a system path:

| Platform | SDK File | Install Command |
|----------|----------|----------------|
| Windows 64-bit | `bin/win64/BMAPI64.dll` | Copy to `C:\Windows\System32\` or add SDK `bin/win64/` to `PATH` |
| Windows 32-bit | `bin/win32/BMAPI.dll` | Copy to `C:\Windows\System32\` or add SDK `bin/win32/` to `PATH` |
| Linux x86 64-bit | `bin/unix64/release/libbmapi64.so` | `sudo cp libbmapi64.so /usr/local/lib/ && sudo ldconfig` |
| Linux x86 32-bit | `bin/unix32/release/libbmapi.so` | `sudo cp libbmapi.so /usr/local/lib/ && sudo ldconfig` |
| Linux ARM 64-bit | `bin/aarch64-linux-gnu/release/libbmapi64.arm.so` | `sudo cp libbmapi64.arm.so /usr/local/lib/libbmapi64.so && sudo ldconfig` |
| Linux ARM 32-bit | `bin/arm-linux-gnueabihf/libbmapi.arm.so` | `sudo cp libbmapi.arm.so /usr/local/lib/libbmapi.so && sudo ldconfig` |

> **Note for ARM platforms:** The `.arm` suffix in the SO filename must be removed when copying to system paths (e.g., `libbmapi64.arm.so` → `/usr/local/lib/libbmapi64.so`).

### 2. Set Up python-lin

```bash
export PYTHONPATH=/path/to/python-lin
```

## Quick Start

```python
from lin.interfaces.bmlin import BmLinBus
from lin.message import Message, LIN_MASTER_WRITE

# Create a LIN bus instance (master mode)
bus = BmLinBus(channel=0, bitrate=19200, is_master=True)

# Send a LIN message (master write)
msg = Message(lin_id=0x10, data=[0x01, 0x02, 0x03, 0x04], dlc=4, msgtype=LIN_MASTER_WRITE)
bus.send(msg)

# Receive a LIN message
msg = bus.recv(timeout=1.0)
print(f"Received: ID=0x{msg.lin_id:02X}, Data={list(msg.data)}")

bus.shutdown()
```

## Requirements

- Python 3.7+
- BUSMUST hardware device with LIN support
- BMAPI runtime library (included in [BMAPI SDK](https://github.com/busmaster/bmapi-sdk/releases))

## Examples

See the `examples/` directory for complete usage examples:

- `bmapi_lin_txrx.py` — LIN transmit and receive with master/slave mode selection

## Packaging with PyInstaller

To bundle your application with PyInstaller, you need to:

1. Include the BMAPI DLL in the package
2. Declare `lin.interfaces.bmlin` as a hidden import

Example spec file:

```python
from ctypes.util import find_library

# Locate BMAPI DLL from system PATH (or fallback to local file)
dll_path = find_library('bmapi64') or 'BMAPI64.dll'

a = Analysis(
    ['your_app.py'],
    pathex=['/path/to/python-lin'],
    binaries=[(dll_path, '.')],
    hiddenimports=['lin.interfaces.bmlin'],
    # ... other Analysis options
)
```

Build with:

```bash
pyinstaller your_app.spec
```

At runtime, the DLL is found via the `_MEIPASS` fallback path inside the bundle.

> **Alternative:** If you don't bundle the DLL, the target machine must have BMAPI installed in the system PATH. In that case, omit the `binaries` line and rely on `find_library()` at runtime.

## Related Projects

- [BMAPI SDK](https://github.com/busmaster/bmapi-sdk) — Complete SDK for BUSMUST devices
- [python-can](https://github.com/busmust/python-can) — BUSMUST interface for CAN/CAN FD

## Support

For technical support, search for "霸码科技" on WeChat, follow our official account, and click "技术支持" to chat directly with our engineers.

## License

See [LICENSE](LICENSE) for details. This library is licensed for use exclusively with BUSMUST hardware devices.
