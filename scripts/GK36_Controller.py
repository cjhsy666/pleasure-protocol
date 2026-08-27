"""
BLE Device Control Client
基于逆向分析的协议实现

依赖: pip install bleak
"""

import asyncio
import sys
from dataclasses import dataclass
from typing import Optional

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.characteristic import BleakGATTCharacteristic


# ============================================================
# 电击通道 (0x4b): byte6=使能, byte7=强度, byte8=模式
#   byte6=0x43 -> 关闭   byte6=0x47 -> 开启
#   byte7=0x23 = 默认/空闲 (无输出)
#   byte7=0x20~0x22, 0x25~0x27 = 6档有效强度 (0x24跳过)
#   byte7 越小 = 强度越低
#   byte8=模式 (循环: 2B,3B,33,BB)
# ============================================================

# byte7 值 -> 档位 (0=默认无输出, 1=最低, 6=最高)
SHOCK_BYTE7_MAP = [0x23, 0x20, 0x21, 0x22, 0x25, 0x26, 0x27]

SHOCK_PACKETS = {
    "off":     bytes.fromhex("2381bbabd24b4323bba33b31"),
    "level_0": bytes.fromhex("2381bbabd24b4723bba33b45"),  # byte7=0x23 (使能开启但空闲)
    "level_1": bytes.fromhex("2381bbabd24b47202ba33b46"),  # byte7=0x20 (最低强度)
    "level_2": bytes.fromhex("2381bbabd24b47213ba33b47"),
    "level_3": bytes.fromhex("2381bbabd24b472233a33b44"),
    "level_4": bytes.fromhex("2381bbabd24b47253ba33b3b"),
    "level_5": bytes.fromhex("2381bbabd24b472633a33b48"),
    "level_6": bytes.fromhex("2381bbabd24b4727bba33b49"),  # byte7=0x27 (最高强度)
}


# ============================================================
# 震动通道 (0xec): byte6=b6强度值
#   b6=0x3B 是"停止/空闲"保留码
#   滑条位置 1(最低) -> 100(最高) 的 b6 映射见 VIBRATION_BY_POSITION
# ============================================================

VIBRATION_IDLE = bytes.fromhex("2381bbabd2ec3b23bba33b90")  # b6=0x3B

# 按 b6 值索引的包字典
VIBRATION_PACKETS = {
    0x0D: bytes.fromhex("2381bbabd2ec0dc3bba33bfe"),
    0x0E: bytes.fromhex("2381bbabd2ec0ec3bba33b01"),
    0x0F: bytes.fromhex("2381bbabd2ec0f23bba33bfc"),
    0x10: bytes.fromhex("2381bbabd2ec1033bba33bff"),
    0x11: bytes.fromhex("2381bbabd2ec11c3bba33bfa"),
    0x12: bytes.fromhex("2381bbabd2ec12c3bba33bfd"),
    0x13: bytes.fromhex("2381bbabd2ec13c3bba33b08"),
    0x14: bytes.fromhex("2381bbabd2ec1433bba33bfb"),
    0x15: bytes.fromhex("2381bbabd2ec15c3bba33b06"),
    0x16: bytes.fromhex("2381bbabd2ec16c3bba33b09"),
    0x17: bytes.fromhex("2381bbabd2ec1723bba33b04"),
    0x18: bytes.fromhex("2381bbabd2ec1833bba33b07"),
    0x19: bytes.fromhex("2381bbabd2ec19c3bba33b02"),
    0x1A: bytes.fromhex("2381bbabd2ec1ac3bba33b05"),
    0x1B: bytes.fromhex("2381bbabd2ec1b23bba33bf0"),
    0x1C: bytes.fromhex("2381bbabd2ec1c33bba33b03"),
    0x1D: bytes.fromhex("2381bbabd2ec1dc3bba33bce"),
    0x1E: bytes.fromhex("2381bbabd2ec1ec3bba33bd1"),
    0x1F: bytes.fromhex("2381bbabd2ec1f23bba33bcc"),
    0x20: bytes.fromhex("2381bbabd2ec2033bba33bcf"),
    0x21: bytes.fromhex("2381bbabd2ec21c3bba33bca"),
    0x22: bytes.fromhex("2381bbabd2ec22c3bba33bcd"),
    0x23: bytes.fromhex("2381bbabd2ec2323bba33bd8"),
    0x24: bytes.fromhex("2381bbabd2ec2433bba33bcb"),
    0x25: bytes.fromhex("2381bbabd2ec25c3bba33bd6"),
    0x26: bytes.fromhex("2381bbabd2ec26c3bba33bd9"),
    0x27: bytes.fromhex("2381bbabd2ec2723bba33bd4"),
    0x28: bytes.fromhex("2381bbabd2ec2833bba33bd7"),
    0x29: bytes.fromhex("2381bbabd2ec29c3bba33bd2"),
    0x2A: bytes.fromhex("2381bbabd2ec2ac3bba33bd5"),
    0x2B: bytes.fromhex("2381bbabd2ec2b23bba33b00"),
    0x2C: bytes.fromhex("2381bbabd2ec2c33bba33bd3"),
    0x2D: bytes.fromhex("2381bbabd2ec2dc3bba33b9e"),
    0x2E: bytes.fromhex("2381bbabd2ec2ec3bba33ba1"),
    0x2F: bytes.fromhex("2381bbabd2ec2f23bba33b9c"),
    0x30: bytes.fromhex("2381bbabd2ec3033bba33b9f"),
    0x31: bytes.fromhex("2381bbabd2ec31c3bba33b9a"),
    0x32: bytes.fromhex("2381bbabd2ec32c3bba33b9d"),
    0x33: bytes.fromhex("2381bbabd2ec3323bba33ba8"),
    0x34: bytes.fromhex("2381bbabd2ec3433bba33b9b"),
    0x35: bytes.fromhex("2381bbabd2ec35c3bba33ba6"),
    0x36: bytes.fromhex("2381bbabd2ec36c3bba33ba9"),
    0x37: bytes.fromhex("2381bbabd2ec3723bba33ba4"),
    0x38: bytes.fromhex("2381bbabd2ec3833bba33ba7"),
    0x39: bytes.fromhex("2381bbabd2ec39c3bba33ba2"),
    0x3A: bytes.fromhex("2381bbabd2ec3ac3bba33ba5"),
    # 0x3B 是停止保留码, 见 VIBRATION_IDLE
    0x3C: bytes.fromhex("2381bbabd2ec3c33bba33ba3"),
    0x3D: bytes.fromhex("2381bbabd2ec3dc3bba33bee"),
    0x3E: bytes.fromhex("2381bbabd2ec3ec3bba33bf1"),
    0x3F: bytes.fromhex("2381bbabd2ec3f23bba33bec"),
    0x40: bytes.fromhex("2381bbabd2ec4033bba33bef"),
    0x41: bytes.fromhex("2381bbabd2ec41c3bba33bea"),
    0x42: bytes.fromhex("2381bbabd2ec42c3bba33bed"),
    0x43: bytes.fromhex("2381bbabd2ec4323bba33bf8"),
    0x44: bytes.fromhex("2381bbabd2ec4433bba33beb"),
    0x45: bytes.fromhex("2381bbabd2ec45c3bba33bf6"),
    0x46: bytes.fromhex("2381bbabd2ec46c3bba33bf9"),
    0x47: bytes.fromhex("2381bbabd2ec4723bba33bf4"),
    0x48: bytes.fromhex("2381bbabd2ec4833bba33bf7"),
    0x49: bytes.fromhex("2381bbabd2ec49c3bba33bf2"),
    0x4A: bytes.fromhex("2381bbabd2ec4ac3bba33bf5"),
    0x4B: bytes.fromhex("2381bbabd2ec4b23bba33ba0"),
    0x4C: bytes.fromhex("2381bbabd2ec4c33bba33bf3"),
    0x57: bytes.fromhex("2381bbabd2ec5723bba33b44"),
    0x59: bytes.fromhex("2381bbabd2ec59c3bba33b42"),
    0x5A: bytes.fromhex("2381bbabd2ec5ac3bba33b45"),
    0x5B: bytes.fromhex("2381bbabd2ec5b23bba33b30"),
    0x5C: bytes.fromhex("2381bbabd2ec5c33bba33b43"),
    0x6D: bytes.fromhex("2381bbabd2ec6dc3bba33bde"),
    0x6E: bytes.fromhex("2381bbabd2ec6ec3bba33be1"),
    0x6F: bytes.fromhex("2381bbabd2ec6f23bba33bdc"),
    0x70: bytes.fromhex("2381bbabd2ec7033bba33bdf"),
    0x71: bytes.fromhex("2381bbabd2ec71c3bba33bda"),
    0x72: bytes.fromhex("2381bbabd2ec72c3bba33bdd"),
    0x73: bytes.fromhex("2381bbabd2ec7323bba33be8"),
    0x74: bytes.fromhex("2381bbabd2ec7433bba33bdb"),
    0x75: bytes.fromhex("2381bbabd2ec75c3bba33be6"),
    0x76: bytes.fromhex("2381bbabd2ec76c3bba33be9"),
    0x77: bytes.fromhex("2381bbabd2ec7723bba33be4"),
    0x78: bytes.fromhex("2381bbabd2ec7833bba33be7"),
    0x79: bytes.fromhex("2381bbabd2ec79c3bba33be2"),
    0x7A: bytes.fromhex("2381bbabd2ec7ac3bba33be5"),
    0x7B: bytes.fromhex("2381bbabd2ec7b23bba33bd0"),
    0x7C: bytes.fromhex("2381bbabd2ec7c33bba33be3"),
    0x7D: bytes.fromhex("2381bbabd2ec7dc3bba33b2e"),
    0x7E: bytes.fromhex("2381bbabd2ec7ec3bba33b31"),
    0x7F: bytes.fromhex("2381bbabd2ec7f23bba33b2c"),
    0x80: bytes.fromhex("2381bbabd2ec8033bba33b2f"),
    0x81: bytes.fromhex("2381bbabd2ec81c3bba33b2a"),
    0x82: bytes.fromhex("2381bbabd2ec82c3bba33b2d"),
    0x83: bytes.fromhex("2381bbabd2ec8323bba33b38"),
    0x84: bytes.fromhex("2381bbabd2ec8433bba33b2b"),
    0x85: bytes.fromhex("2381bbabd2ec85c3bba33b36"),
    0x86: bytes.fromhex("2381bbabd2ec86c3bba33b39"),
    0x87: bytes.fromhex("2381bbabd2ec8723bba33b34"),
    0x88: bytes.fromhex("2381bbabd2ec8833bba33b37"),
    0x89: bytes.fromhex("2381bbabd2ec89c3bba33b32"),
    0x8A: bytes.fromhex("2381bbabd2ec8ac3bba33b35"),
    0x8B: bytes.fromhex("2381bbabd2ec8b23bba33be0"),
    0x8C: bytes.fromhex("2381bbabd2ec8c33bba33b33"),
}

# 按滑条位置排序的 b6 列表 (位置1=最低, 位置100=最高)
VIBRATION_BY_POSITION = [
    0x39, 0x3A, 0x37, 0x38, 0x35, 0x36, 0x33, 0x34, 0x31, 0x32,  # pos  1-10
    0x2F, 0x30, 0x2D, 0x2E, 0x4B, 0x4C, 0x49, 0x4A, 0x47, 0x48,  # pos 11-20
    0x45, 0x46, 0x43, 0x44, 0x41, 0x42, 0x3F, 0x40, 0x3D, 0x3E,  # pos 21-30
    0x1B, 0x1C, 0x19, 0x1A, 0x17, 0x18, 0x15, 0x16, 0x13, 0x14,  # pos 31-40
    0x11, 0x12, 0x0F, 0x10, 0x0D, 0x0E, 0x2B, 0x2C, 0x29, 0x2A,  # pos 41-50
    0x27, 0x28, 0x25, 0x26, 0x23, 0x24, 0x21, 0x22, 0x1F, 0x20,  # pos 51-60
    0x1D, 0x1E, 0x7B, 0x7C, 0x79, 0x7A, 0x77, 0x78, 0x75, 0x76,  # pos 61-70
    0x73, 0x74, 0x71, 0x72, 0x6F, 0x70, 0x6D, 0x6E, 0x8B, 0x8C,  # pos 71-80
    0x89, 0x8A, 0x87, 0x88, 0x85, 0x86, 0x83, 0x84, 0x81, 0x82,  # pos 81-90
    0x7F, 0x80, 0x7D, 0x7E, 0x5B, 0x5C, 0x59, 0x5A, 0x57, 0x3C,  # pos 91-100
]

# 启动自检: 确保位置表里的每个 b6 都能在包字典里查到
assert len(VIBRATION_BY_POSITION) == 100, "VIBRATION_BY_POSITION must have 100 entries"
_missing = [b6 for b6 in VIBRATION_BY_POSITION if b6 not in VIBRATION_PACKETS]
assert not _missing, f"VIBRATION_PACKETS missing: {[hex(x) for x in _missing]}"


# ============================================================
# 灯光通道 (0xc8): 两状态交替
# ============================================================

LIGHT_PACKETS = {
    "state_a": bytes.fromhex("2381bbabd2c83b23bba33bc4"),
    "state_b": bytes.fromhex("2381bbabd2c83c33bba33bc7"),
}


# ============================================================
# BLE 客户端
# ============================================================

@dataclass
class DeviceEndpoint:
    write_char: BleakGATTCharacteristic
    notify_char: Optional[BleakGATTCharacteristic] = None


class DeviceClient:
    def __init__(self, address: str):
        self.address = address
        self.client: Optional[BleakClient] = None
        self.endpoint: Optional[DeviceEndpoint] = None
        self._light_state = 0
        self._send_lock = asyncio.Lock()

        # 心跳会重发这两个"最后一次用户设置"的状态包
        # 默认都是关闭/空闲, 保证未主动开启前心跳不会误触发输出
        self._last_shock: bytes = SHOCK_PACKETS["off"]
        self._last_vibration: bytes = VIBRATION_IDLE

    async def connect(self) -> None:
        print(f"[*] Connecting to {self.address} ...")
        self.client = BleakClient(
            self.address,
            disconnected_callback=self._on_disconnected,
        )
        await self.client.connect()
        print(f"[+] Connected. MTU={self.client.mtu_size}")

        write_char = None
        notify_char = None
        for service in self.client.services:
            for char in service.characteristics:
                props = char.properties
                if ("write" in props or "write-without-response" in props) and write_char is None:
                    write_char = char
                if "notify" in props and notify_char is None:
                    notify_char = char

        if write_char is None:
            raise RuntimeError("No writable characteristic found")

        self.endpoint = DeviceEndpoint(write_char, notify_char)
        print(f"[+] Write char : {write_char.uuid}")
        if notify_char:
            print(f"[+] Notify char: {notify_char.uuid}")
            await self.client.start_notify(notify_char, self._on_notify)

    async def disconnect(self) -> None:
        if self.client and self.client.is_connected:
            await self.client.disconnect()
            print("[*] Disconnected")

    @property
    def is_connected(self) -> bool:
        return bool(self.client and self.client.is_connected)

    def _on_disconnected(self, _client: BleakClient) -> None:
        print("[!] Device disconnected")

    def _on_notify(self, _char: BleakGATTCharacteristic, data: bytearray) -> None:
        print(f"[<] notify: {data.hex()}")

    async def send(self, packet: bytes, verbose: bool = True) -> None:
        if not self.endpoint or not self.is_connected:
            raise RuntimeError("Not connected")
        if len(packet) != 12:
            raise ValueError(f"Packet must be 12 bytes, got {len(packet)}")
        async with self._send_lock:
            await self.client.write_gatt_char(
                self.endpoint.write_char, packet, response=False
            )
        if verbose:
            print(f"[>] {packet.hex()}")

    # ---------- 电击 (0x4b) ----------

    async def shock_stop(self) -> None:
        """关闭电击"""
        self._last_shock = SHOCK_PACKETS["off"]
        await self.send(self._last_shock)

    async def shock_level(self, level: int) -> None:
        """电击强度 0-6 (0=使能空闲, 1=最低, 6=最高)"""
        level = max(0, min(6, level))
        self._last_shock = SHOCK_PACKETS[f"level_{level}"]
        await self.send(self._last_shock)

    # ---------- 震动 (0xec) ----------

    async def vibration_off(self) -> None:
        """关闭震动"""
        self._last_vibration = VIBRATION_IDLE
        await self.send(self._last_vibration)

    async def vibration_level(self, percent: int) -> Optional[int]:
        """
        震动强度 0-100
        percent=0 等同于关闭震动 (发 idle 保留码)
        1-100 按滑条位置映射 (位置1=最低, 位置100=最高)
        返回实际发送的 b6 值, 关闭时返回 None
        """
        percent = max(0, min(100, percent))
        if percent == 0:
            await self.vibration_off()
            return None

        # 1-100 映射到 VIBRATION_BY_POSITION 的 0..99 索引
        idx = percent - 1
        b6 = VIBRATION_BY_POSITION[idx]
        self._last_vibration = VIBRATION_PACKETS[b6]
        await self.send(self._last_vibration)
        return b6

    async def vibration_raw(self, b6: int) -> None:
        """直接按 b6 值发送震动包"""
        if b6 == 0x3B:
            self._last_vibration = VIBRATION_IDLE
            await self.send(self._last_vibration)
            return
        if b6 in VIBRATION_PACKETS:
            self._last_vibration = VIBRATION_PACKETS[b6]
            await self.send(self._last_vibration)
        else:
            all_b6 = sorted(VIBRATION_PACKETS.keys())
            closest = min(all_b6, key=lambda k: abs(k - b6))
            print(f"[!] b6=0x{b6:02X} 未收录, 用最近值 0x{closest:02X}")
            self._last_vibration = VIBRATION_PACKETS[closest]
            await self.send(self._last_vibration)

    # ---------- 灯光 (0xc8) ----------

    async def light_toggle(self) -> None:
        key = "state_a" if self._light_state == 0 else "state_b"
        await self.send(LIGHT_PACKETS[key])
        self._light_state ^= 1

    # ---------- 心跳 ----------

    async def heartbeat_loop(self, interval: float = 5.0) -> None:
        """
        保持连接活跃, 重发"最后一次用户设置"的状态
        - 用户未开启任何输出时, 缓存默认是 off/idle, 心跳等价于保活
        - 用户开启后, 心跳周期重发当前状态, 不会打断持续输出
        """
        try:
            while self.is_connected:
                await self.send(self._last_shock, verbose=False)
                await asyncio.sleep(interval / 2)
                await self.send(self._last_vibration, verbose=False)
                await asyncio.sleep(interval / 2)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[!] Heartbeat stopped: {e}")


# ============================================================
# 设备扫描
# ============================================================

async def scan_and_pick() -> Optional[BLEDevice]:
    print("[*] Scanning for 10 seconds ...")
    devices = await BleakScanner.discover(timeout=10.0, return_adv=True)

    entries = list(devices.items())
    if not entries:
        print("[!] No devices found")
        return None

    print("\nFound devices:")
    for i, (addr, (dev, adv)) in enumerate(entries):
        name = dev.name or adv.local_name or "<unknown>"
        rssi = adv.rssi
        print(f"  [{i}] {addr}  {name}  (RSSI {rssi})")

    choice = input("\nSelect device index (or Enter to cancel): ").strip()
    if not choice:
        return None
    try:
        idx = int(choice)
        return entries[idx][1][0]
    except (ValueError, IndexError):
        print("[!] Invalid selection")
        return None


# ============================================================
# 交互式 CLI
# ============================================================

HELP = """
Commands:
  s0 .. s6        电击强度 0-6
                   s0=使能空闲 s1=最低 ... s6=最高
  so              电击关闭
  ss              震动关闭
  se0 .. se100    震动强度百分比 (se0 等同 ss)
  sr <hex>        震动直发 b6 值 (如 sr 3c)
  l               灯光切换
  raw <hex>       发送任意 12 字节 hex 包
  hb [sec]        启动心跳循环 (默认 5 秒, 重发当前状态)
  stop            停止心跳循环
  q               退出
"""

async def repl(client: DeviceClient) -> None:
    print(HELP)
    hb_task: Optional[asyncio.Task] = None
    loop = asyncio.get_running_loop()

    while True:
        line = await loop.run_in_executor(None, input, "> ")
        line = line.strip()
        if not line:
            continue

        parts = line.split()
        cmd = parts[0].lower()

        try:
            if cmd == "q":
                break
            elif cmd == "so":
                await client.shock_stop()
                print("[+] 电击关闭")
            elif cmd.startswith("s") and len(cmd) == 2 and cmd[1].isdigit():
                lv = int(cmd[1])
                await client.shock_level(lv)
                b7 = SHOCK_BYTE7_MAP[lv]
                print(f"[+] 电击强度 -> {lv} (byte7=0x{b7:02X})")
            elif cmd == "ss":
                await client.vibration_off()
                print("[+] 震动关闭")
            elif cmd.startswith("se") and len(cmd) > 2 and cmd[2:].isdigit():
                pct = int(cmd[2:])
                b6 = await client.vibration_level(pct)
                if b6 is None:
                    print(f"[+] 震动关闭 (se{pct})")
                else:
                    print(f"[+] 震动强度 -> {pct}% (b6=0x{b6:02X})")
            elif cmd == "sr" and len(parts) == 2:
                b6 = int(parts[1], 16)
                await client.vibration_raw(b6)
            elif cmd == "l":
                await client.light_toggle()
                print("[+] 灯光切换")
            elif cmd == "raw" and len(parts) == 2:
                await client.send(bytes.fromhex(parts[1]))
            elif cmd == "hb":
                interval = float(parts[1]) if len(parts) > 1 else 5.0
                if hb_task and not hb_task.done():
                    print("[!] Heartbeat already running")
                else:
                    hb_task = asyncio.create_task(client.heartbeat_loop(interval))
                    print(f"[+] Heartbeat every {interval}s (重发当前状态)")
            elif cmd == "stop":
                if hb_task:
                    hb_task.cancel()
                    hb_task = None
                    print("[+] Heartbeat stopped")
            elif cmd in ("h", "?", "help"):
                print(HELP)
            else:
                print("[?] Unknown command; type 'h' for help")
        except Exception as e:
            print(f"[!] Error: {e}")

    if hb_task:
        hb_task.cancel()
        try:
            await hb_task
        except (asyncio.CancelledError, Exception):
            pass


# ============================================================
# 主入口
# ============================================================

async def main() -> None:
    address: Optional[str] = None

    if len(sys.argv) > 1:
        address = sys.argv[1]
    else:
        dev = await scan_and_pick()
        if dev is None:
            return
        address = dev.address

    client = DeviceClient(address)
    try:
        await client.connect()
        await asyncio.sleep(0.3)
        await repl(client)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[*] Interrupted")
