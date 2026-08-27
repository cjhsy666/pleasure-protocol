"""
GK36 BLE Controller - LinkZone 插件

通过聊天消息控制 GK36 设备（蓝牙直连）。

命令：
  /gk36 连接 [地址]    扫描并连接设备（不指定地址则自动扫描）
  /gk36 断开           断开连接
  /gk36 状态           查看当前连接状态

  /电击 关闭            关闭电击
  /电击 0-6             设置电击强度（0=空闲, 1-6=强度档位）

  /震动 关闭            关闭震动
  /震动 0-100           设置震动强度百分比

  /灯光                 切换灯光

自然语言触发：
  电击X档 / 电击X / shock X    电击强度
  震动X / vib X                震动百分比
  开灯 / 关灯                  灯光控制
"""

import asyncio
import threading

# bleack 在 on_start 中延迟导入，避免未安装时插件加载报错
bleak_available = False
try:
    from bleak import BleakClient, BleakScanner
    bleak_available = True
except ImportError:
    pass

# ============================================================
# 协议数据（与 gk36_protocol.h 完全一致）
# ============================================================

PACKET_SIZE = 12

SHOCK_PACKETS = {
    0: bytes.fromhex("2381bbabd24b4323bba33b31"),  # off
    1: bytes.fromhex("2381bbabd24b4723bba33b45"),  # idle
    2: bytes.fromhex("2381bbabd24b47202ba33b46"),  # level 1
    3: bytes.fromhex("2381bbabd24b47213ba33b47"),  # level 2
    4: bytes.fromhex("2381bbabd24b472233a33b44"),  # level 3
    5: bytes.fromhex("2381bbabd24b47253ba33b3b"),  # level 4
    6: bytes.fromhex("2381bbabd24b472633a33b48"),  # level 5
    7: bytes.fromhex("2381bbabd24b4727bba33b49"),  # level 6
}

SHOCK_LABELS = ["关闭", "空闲", "1档", "2档", "3档", "4档", "5档", "6档"]

VIBRATION_IDLE = bytes.fromhex("2381bbabd2ec3b23bba33b90")

VIBRATION_BY_POSITION = [
    0x39, 0x3A, 0x37, 0x38, 0x35, 0x36, 0x33, 0x34, 0x31, 0x32,
    0x2F, 0x30, 0x2D, 0x2E, 0x4B, 0x4C, 0x49, 0x4A, 0x47, 0x48,
    0x45, 0x46, 0x43, 0x44, 0x41, 0x42, 0x3F, 0x40, 0x3D, 0x3E,
    0x1B, 0x1C, 0x19, 0x1A, 0x17, 0x18, 0x15, 0x16, 0x13, 0x14,
    0x11, 0x12, 0x0F, 0x10, 0x0D, 0x0E, 0x2B, 0x2C, 0x29, 0x2A,
    0x27, 0x28, 0x25, 0x26, 0x23, 0x24, 0x21, 0x22, 0x1F, 0x20,
    0x1D, 0x1E, 0x7B, 0x7C, 0x79, 0x7A, 0x77, 0x78, 0x75, 0x76,
    0x73, 0x74, 0x71, 0x72, 0x6F, 0x70, 0x6D, 0x6E, 0x8B, 0x8C,
    0x89, 0x8A, 0x87, 0x88, 0x85, 0x86, 0x83, 0x84, 0x81, 0x82,
    0x7F, 0x80, 0x7D, 0x7E, 0x5B, 0x5C, 0x59, 0x5A, 0x57, 0x3C,
]

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

LIGHT_STATE_A = bytes.fromhex("2381bbabd2c83b23bba33bc4")
LIGHT_STATE_B = bytes.fromhex("2381bbabd2c83c33bba33bc7")


def vibration_position_to_b6(percent):
    """1-100 百分比 -> b6 值"""
    pos = max(1, min(100, percent))
    return VIBRATION_BY_POSITION[pos - 1]


def vibration_get_packet(b6):
    """b6 值 -> 数据包"""
    if b6 == 0x3B:
        return VIBRATION_IDLE
    return VIBRATION_PACKETS.get(b6)


# ============================================================
# LinkZone 插件
# ============================================================

class GK36Plugin(Plugin):
    def __init__(self):
        super().__init__({
            "name": "gk36",
            "version": "1.0.0",
            "description": "GK36 BLE 设备控制器",
            "author": "pleasure-protocol",
            "triggers": [
                {"type": 0, "pattern": "/gk36"},
                {"type": 0, "pattern": "/电击"},
                {"type": 0, "pattern": "/震动"},
                {"type": 0, "pattern": "/灯光"},
                {"type": 2, "pattern": r"^电击\s*\d+\s*档?$"},
                {"type": 2, "pattern": r"^电击\s*(关闭|关|off)$"},
                {"type": 2, "pattern": r"^震动\s*\d+\s*%?$"},
                {"type": 2, "pattern": r"^震动\s*(关闭|关|off)$"},
                {"type": 2, "pattern": r"^(开灯|关灯|灯光)$"},
            ],
            "event_types": ["message"],
            "is_service": True,
            "permission_level": 5,
            "cooldown": 1,
        })

        self._client = None
        self._write_char = None
        self._connected = False
        self._device_name = ""
        self._device_address = ""
        self._last_shock = SHOCK_PACKETS[0]
        self._last_vibration = VIBRATION_IDLE
        self._lock = threading.Lock()
        self._heartbeat_running = False

    # ---- 生命周期 ----

    def on_start(self):
        self.db = LZDB("gk36")

        # 恢复上次的设备地址
        saved_addr = self.db.get("config", "device_address")
        if saved_addr:
            self._device_address = saved_addr
            LinkZone.logger.info("gk36", f"已保存设备地址: {saved_addr}")

        if not bleak_available:
            LinkZone.logger.warning("gk36", "bleak 未安装，请运行: pip install bleak")

    def on_stop(self):
        self._disconnect_sync()
        LinkZone.logger.info("gk36", "插件已停止")

    # ---- 消息处理 ----

    def handle_event(self, sender):
        text = sender.get_message().strip()

        # /gk36 子命令
        if text.startswith("/gk36"):
            self._handle_gk36_cmd(sender, text)
            return

        # /电击 X
        if text.startswith("/电击"):
            arg = text.replace("/电击", "").strip()
            self._handle_shock(sender, arg)
            return

        # /震动 X
        if text.startswith("/震动"):
            arg = text.replace("/震动", "").strip()
            self._handle_vibration(sender, arg)
            return

        # /灯光
        if text.startswith("/灯光"):
            self._handle_light(sender)
            return

        # 自然语言匹配
        import re

        m = re.match(r"^电击\s*(\d+)\s*档?$", text)
        if m:
            self._handle_shock(sender, m.group(1))
            return

        if re.match(r"^电击\s*(关闭|关|off)$", text, re.I):
            self._handle_shock(sender, "关闭")
            return

        m = re.match(r"^震动\s*(\d+)\s*%?$", text)
        if m:
            self._handle_vibration(sender, m.group(1))
            return

        if re.match(r"^震动\s*(关闭|关|off)$", text, re.I):
            self._handle_vibration(sender, "关闭")
            return

        if re.match(r"^(开灯|关灯|灯光)$", text):
            self._handle_light(sender)
            return

    # ---- /gk36 子命令 ----

    def _handle_gk36_cmd(self, sender, text):
        parts = text.split(maxsplit=1)
        sub = parts[1].strip() if len(parts) > 1 else ""

        if sub.startswith("连接") or sub.startswith("connect"):
            addr = sub.replace("连接", "").replace("connect", "").strip()
            self._cmd_connect(sender, addr)
        elif sub.startswith("断开") or sub.startswith("disconnect"):
            self._cmd_disconnect(sender)
        elif sub.startswith("状态") or sub.startswith("status"):
            self._cmd_status(sender)
        elif sub.startswith("扫描") or sub.startswith("scan"):
            self._cmd_scan(sender)
        else:
            sender.reply(
                "GK36 控制命令：\n"
                "/gk36 连接 [地址] - 扫描并连接\n"
                "/gk36 断开 - 断开连接\n"
                "/gk36 状态 - 查看状态\n"
                "/gk36 扫描 - 扫描设备\n"
                "\n"
                "/电击 0-6 - 设置强度\n"
                "/震动 0-100 - 设置强度\n"
                "/灯光 - 切换灯光\n"
                "\n"
                "也可以直接发：电击3档、震动50、开灯"
            )

    def _cmd_scan(self, sender):
        if not bleak_available:
            sender.reply("bleak 未安装，请运行: pip install bleak")
            return

        sender.reply("正在扫描 BLE 设备（10秒）...")
        LinkZone.logger.info("gk36", "开始扫描")

        def do_scan():
            try:
                loop = asyncio.new_event_loop()
                devices = loop.run_until_complete(
                    BleakScanner.discover(timeout=10.0, return_adv=True)
                )
                loop.close()

                results = []
                for addr, (dev, adv) in devices.items():
                    name = dev.name or adv.local_name or ""
                    if "GK36" in name.upper() or name:
                        results.append((addr, name, adv.rssi))

                if not results:
                    sender.reply("未发现设备")
                    return

                lines = ["发现设备："]
                for i, (addr, name, rssi) in enumerate(results[:10]):
                    marker = " [GK36]" if "GK36" in name.upper() else ""
                    lines.append(f"  {i+1}. {name or '未知'} ({addr}) RSSI:{rssi}{marker}")
                lines.append("\n发送 /gk36 连接 <地址> 连接")
                sender.reply("\n".join(lines))
            except Exception as e:
                sender.reply(f"扫描失败: {e}")
                LinkZone.logger.error("gk36", f"扫描错误: {e}")

        threading.Thread(target=do_scan, daemon=True).start()

    def _cmd_connect(self, sender, address):
        if not bleak_available:
            sender.reply("bleak 未安装，请运行: pip install bleak")
            return

        if self._connected:
            sender.reply(f"已连接 {self._device_name} ({self._device_address})")
            return

        def do_connect():
            try:
                target = address or self._device_address
                if not target:
                    sender.reply("请先扫描: /gk36 扫描\n或指定地址: /gk36 连接 AA:BB:CC:DD:EE:FF")
                    return

                sender.reply(f"正在连接 {target}...")
                loop = asyncio.new_event_loop()

                async def connect():
                    client = BleakClient(target)
                    await client.connect()
                    return client

                client = loop.run_until_complete(connect())

                # 找到可写特征
                write_char = None
                for service in client.services:
                    for char in service.characteristics:
                        if "write" in char.properties or "write-without-response" in char.properties:
                            write_char = char
                            break
                    if write_char:
                        break

                if not write_char:
                    sender.reply("连接成功但未找到可写特征")
                    client.disconnect()
                    loop.close()
                    return

                with self._lock:
                    self._client = client
                    self._write_char = write_char
                    self._connected = True
                    self._device_address = target
                    self._device_name = target

                # 保存地址
                self.db.set("config", "device_address", target)

                sender.reply(f"已连接 {target}")

                # 启动心跳
                self._start_heartbeat()

            except Exception as e:
                sender.reply(f"连接失败: {e}")
                LinkZone.logger.error("gk36", f"连接错误: {e}")

        threading.Thread(target=do_connect, daemon=True).start()

    def _cmd_disconnect(self, sender):
        if not self._connected:
            sender.reply("当前未连接")
            return

        self._disconnect_sync()
        sender.reply(f"已断开 {self._device_name}")

    def _cmd_status(self, sender):
        if self._connected:
            hb = "运行中" if self._heartbeat_running else "已停止"
            sender.reply(
                f"已连接: {self._device_name}\n"
                f"地址: {self._device_address}\n"
                f"心跳: {hb}"
            )
        else:
            saved = self._device_address or "无"
            sender.reply(f"未连接\n已保存地址: {saved}")

    # ---- 电击 ----

    def _handle_shock(self, sender, arg):
        if not self._ensure_connected(sender):
            return

        arg = arg.strip().lower()
        if arg in ("关闭", "关", "off", "0"):
            level = 0
        else:
            try:
                level = int(arg)
            except ValueError:
                sender.reply("用法: /电击 0-6 或 电击3档")
                return

        level = max(0, min(7, level))
        pkt = SHOCK_PACKETS[level]
        self._last_shock = pkt
        self._send(pkt)
        sender.reply(f"电击 -> {SHOCK_LABELS[level]}")

    # ---- 震动 ----

    def _handle_vibration(self, sender, arg):
        if not self._ensure_connected(sender):
            return

        arg = arg.strip().lower()
        if arg in ("关闭", "关", "off"):
            self._last_vibration = VIBRATION_IDLE
            self._send(VIBRATION_IDLE)
            sender.reply("震动 -> 关闭")
            return

        try:
            percent = int(arg)
        except ValueError:
            sender.reply("用法: /震动 0-100 或 震动50")
            return

        percent = max(0, min(100, percent))
        if percent == 0:
            self._last_vibration = VIBRATION_IDLE
            self._send(VIBRATION_IDLE)
            sender.reply("震动 -> 关闭")
            return

        b6 = vibration_position_to_b6(percent)
        pkt = vibration_get_packet(b6)
        if pkt:
            self._last_vibration = pkt
            self._send(pkt)
            sender.reply(f"震动 -> {percent}% (b6=0x{b6:02X})")
        else:
            sender.reply(f"震动映射失败 (b6=0x{b6:02X})")

    # ---- 灯光 ----

    def _handle_light(self, sender):
        if not self._ensure_connected(sender):
            return

        pkt = LIGHT_STATE_B  # 简单交替
        self._send(pkt)
        sender.reply("灯光已切换")

    # ---- BLE 底层 ----

    def _ensure_connected(self, sender):
        if not bleak_available:
            sender.reply("bleak 未安装，请运行: pip install bleak")
            return False
        if not self._connected:
            sender.reply("未连接，请先: /gk36 连接")
            return False
        return True

    def _send(self, packet):
        with self._lock:
            if not self._connected or not self._client or not self._write_char:
                return False
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(
                    self._client.write_gatt_char(self._write_char, packet, response=False)
                )
                loop.close()
                return True
            except Exception as e:
                LinkZone.logger.error("gk36", f"发送失败: {e}")
                self._connected = False
                return False

    def _disconnect_sync(self):
        self._stop_heartbeat()
        with self._lock:
            if self._client:
                try:
                    loop = asyncio.new_event_loop()
                    loop.run_until_complete(self._client.disconnect())
                    loop.close()
                except Exception:
                    pass
            self._client = None
            self._write_char = None
            self._connected = False

    # ---- 心跳 ----

    def _start_heartbeat(self):
        if self._heartbeat_running:
            return
        self._heartbeat_running = True

        def heartbeat():
            while self._heartbeat_running and self._connected:
                self._send(self._last_shock)
                sleep(2500)
                self._send(self._last_vibration)
                sleep(2500)

        threading.Thread(target=heartbeat, daemon=True).start()
        LinkZone.logger.info("gk36", "心跳已启动")

    def _stop_heartbeat(self):
        self._heartbeat_running = False
