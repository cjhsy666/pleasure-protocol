<p align="center">
  <h1 align="center"> pleasure-protocol </h1>
  <p align="center">
    <code>// 逆向快乐的密码，让 AI 接管一切</code>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/BLE-Protocol_Reverse_Engineered-brightgreen" alt="BLE">
    <img src="https://img.shields.io/badge/AI-Ready-7B68EE" alt="AI Ready">
    <img src="https://img.shields.io/badge/ESP32-Firmware-blue" alt="ESP32">
    <img src="https://img.shields.io/badge/Python-bleak-yellow" alt="Python">
    <img src="https://img.shields.io/badge/LinkZone-Plugin-red" alt="LinkZone">
    <img src="https://img.shields.io/badge/License-MIT-pink" alt="License">
  </p>
</p>

---

> *"他们锁住了快乐，我们用 12 个字节把它偷了回来。"*

GK36 跳蛋 BLE 协议逆向工程 + 全平台控制方案。

12 个字节的数据包，100 级震动，7 档电击，灯光闪烁——
每一个 bit 都被我们拆解、记录、复现。

这不是为了写一个更好的 App。
**这是为了让 AI 能读懂你的身体，然后亲手操控一切。**

```
  ┌──────────────────────────────────────────────────────────┐
  │                                                          │
  │   你和 AI 聊天                                            │
  │       ↓                                                  │
  │   AI 读懂你的情绪                                         │
  │       ↓                                                  │
  │   pleasure-protocol 发出指令                              │
  │       ↓                                                  │
  │   12 字节 → BLE → 设备响应                                │
  │                                                          │
  │   从对话到体感，全自动闭环。                                │
  │                                                          │
  └──────────────────────────────────────────────────────────┘
```

**我们现在建好了第三步和第四步。** 协议已破解，控制已实现。
下一步：接上 AI，让它成为那个"读懂你的人"。

---

## 🧩 三种方式，随你选择

| | 方式 | 场景 | 一句话 |
|---|------|------|--------|
| 🖥️ | **ESP32 固件** | 手机/平板 | WiFi 热点直连，打开浏览器就能玩，不用装任何 App |
| 💻 | **Python 脚本** | PC / 笔记本 | 终端里敲几个字，快乐就来了。也是 AI 的底层调用接口 |
| 💬 | **LinkZone 插件** | QQ / 微信 | 发消息就能控制，远程调教，从这里开始 |

三者共享同一套逆向协议，同一个控制逻辑。
选哪个，取决于你的 AI 从哪里发出指令。

---

## 🚀 快速开始

### ESP32 固件（手机用）

> 硬件：任意 ESP32 开发板

```bash
# 编译上传
pio run -t upload

# 手机连接 WiFi: pleasure-protocol（密码: 12345678）
# 浏览器打开: http://192.168.4.1
```

暗黑主题 Web 面板，滑块 + 按钮，毫秒级实时响应。

### Python 脚本（PC 用）

```bash
pip install bleak
python scripts/GK36_Controller.py

# s3        → 电击 3 档
# se50      → 震动 50%
# l         → 灯光切换
# hb        → 启动心跳保活
```

也是 AI 未来调用的底层接口——AI 生成代码，直接控制设备。

### LinkZone 插件（聊天用）

```bash
cp -r plugins/gk36/ /你的linkzone/plugins/
# 重启框架，然后在群里发:

# 电击3档
# 震动75
# /gk36 连接
# /灯光
```

自然语言就是遥控器。

---

## 🤖 AI 控制的样子

```
  你: "我今天好累..."
  AI: "那就放松一下吧 ☺"
      [震动 20%]
      "先从轻的开始..."

  你: "再强烈一点"
  AI: "好的"
      [震动 65%]
      [5秒后 → 震动 80%]
      "这样呢？"

  你: "电击试试"
  AI: [电击 2档]
      "从低档开始，适应了再加？"
```

AI 不只是遥控器——
它会**感知**你的情绪，**判断**该做什么，**渐进**地调整，**回应**你的反馈。

---

## 🔓 协议破解

> 逆向自官方 App 的 BLE GATT 通信，12 字节 / 包，write-without-response。

```
  Byte:  0    1    2    3    4    5    6    7    8    9   10   11
        0x23 0x81 0xBB 0xAB 0xD2 [CH] [EN] [LV] 0xBB 0xA3 0x3B [CK]
        └──── 固定头 (5 字节) ────┘  │    │    │   └──── 校验 (4 字节) ──┘
                                   通道  使能  强度
```

### ⚡ 电击通道 (0x4B)

| 档位 | byte6 | byte7 | 体感描述 |
|:----:|:-----:|:-----:|----------|
| 关闭 | `0x43` | `0x23` | — |
| 空闲 | `0x47` | `0x23` | 已就绪，等待指令 |
| **1** | `0x47` | `0x20` | 轻轻的 |
| **2** | `0x47` | `0x21` | 嗯？ |
| **3** | `0x47` | `0x22` | 有点感觉了 |
| **4** | `0x47` | `0x25` | 开始认真了 |
| **5** | `0x47` | `0x26` | 抓紧了 |
| **6** | `0x47` | `0x27` | 全力以赴 |

### 📳 震动通道 (0xEC)

100 级精度，通过 `b6` 字节非线性映射。
`0x3B` 为停止/空闲保留码。

从 1% 的若有若无，到 100% 的全力以赴——每一级都有对应的独立数据包。

### 💡 灯光通道 (0xC8)

两状态交替切换。按一下亮，再按一下灭。
氛围感，拉满。

---

## 🗺️ Roadmap

```
  ✅  逆向 BLE 协议
  ✅  Python 控制脚本
  ✅  ESP32 固件 + Web 控制面板
  ✅  LinkZone 聊天插件
  ─────────────────────────
  🔜  AI 情绪感知 → 自动调节强度
  🔜  AI 对话驱动 → 自然语言控制
  🔜  多设备协同
  🔜  远程公网控制
  🔜  语音交互
```

---

## 📁 项目结构

```
pleasure-protocol/
│
├── scripts/
│   └── GK36_Controller.py         Python 控制（AI 调用接口）
│
├── plugins/
│   └── gk36/
│       └── gk36.py                LinkZone 插件（聊天 → 控制）
│
└── src/
    ├── main.cpp                    ESP32 入口
    ├── gk36_protocol.h             12 字节协议（核心资产）
    ├── gk36_ble.h / .cpp           BLE 连接层
    ├── gk36_web.h / .cpp           Web 服务 + WebSocket + OTA
    └── index_html.h                暗黑主题控制面板
```

---

## ❓ FAQ

**Q: 为什么不直接用官方 App？**

A: 因为 App 不会和你聊天，不会读懂你的情绪，不会根据你的反应调整强度。
AI 会。

**Q: AI 控制什么时候能用？**

A: 基础设施已就绪（协议 + 控制层 + 聊天接口）。
下一步是接入大模型，让它学会"感知 → 判断 → 控制"的闭环。

**Q: 支持其他设备吗？**

A: 目前只针对 GK36。但架构是通用的——换个协议表就能适配其他 BLE 设备。
如果你逆向了其他设备的协议，欢迎 PR。

**Q: 会损坏设备吗？**

A: 不会。我们发送的数据包和官方 App 完全一致。只是发送方式从"App → 云 → 蓝牙"变成了"我们 → 蓝牙"。

---

## 📄 许可证

[MIT License](LICENSE)

```
快乐应该自由。
AI 应该懂你。
```

---

<p align="center">
  <i>If this project helped you, consider giving it a ⭐</i>
</p>
