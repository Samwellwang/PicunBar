# PicunBar 🎧

> **品存（Picun）F8 Ultra 蓝牙耳机 macOS 状态栏控制器**  
> 基于 BLE 通信协议逆向工程，让第三方蓝牙耳机在 Mac 上也能拥有类似 AirPods 的原生降噪切换体验。

[![macOS](https://img.shields.io/badge/macOS-12.0+-black?style=flat&logo=apple)](https://www.apple.com/macos/)
[![Architecture](https://img.shields.io/badge/Arch-Universal%20(Intel%20%2B%20Apple%20Silicon)-blue)](https://github.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📖 项目背景

macOS 系统顶部的“声音 / 控制中心”菜单原生物理仅支持 Apple / Beats 系列耳机的降噪调节（如 AirPods Pro、AirPods Max）。第三方蓝牙耳机虽然有手机配套 App，但在 Mac 电脑上通常“无 App 可用”，只能靠摸耳机盲按切换降噪。

本项目通过对品存官方 Android 安装包进行逆向分析，提取出了完整的低功耗蓝牙（BLE GATT）控制协议与 CRC8 校验算法，开发了这款常驻在 macOS 顶部菜单栏的轻量控制工具。

---

## ✨ 核心特性

- 🎛️ **一键降噪切换**：常驻顶部状态栏，随手在 **深度降噪 (ANC)**、**通透模式 (环境音)** 和 **普通模式 (关闭降噪)** 之间切换。
- 🔋 **实时真实电量**：精准解码官方多字节电量报文，准确显示耳机电量百分比。
- 🚀 **扩展功能控制**：
  - 低延迟游戏模式 开 / 关
  - 低音增强 (Bass Boost) 开 / 关
  - 防风降噪 (Windproof) 开 / 关
  - 空间音频 开 / 关
- ⚡️ **极速重连与缓存**：自动扫描并缓存耳机的 BLE UUID，下次连接仅需 **0.3 秒瞬间直连**。
- 🔄 **开机自动启动**：菜单内一键启用/关闭 LaunchAgent 自启动服务。
- 🌐 **双模支持**：除 Python 原生状态栏应用外，项目内还包含一份免安装的 **Web Bluetooth 单文件网页控制器**。

---

## 🖥️ 截图预览

```text
  [顶部菜单栏] 🎧 降噪
  ──────────────────────────────────────
  🎧 Picun F8 Ultra: 已连接
  🔋 电量: 85%
  ──────────────────────────────────────
     关闭降噪 (普通模式)
  ✓ 开启降噪 (ANC 深度)
     开启通透 (环境音透传)
  ──────────────────────────────────────
     低音增强 (Bass Boost)
     防风降噪 (Windproof)
  ✓ 低延迟游戏模式
     空间音频
  ──────────────────────────────────────
  重新扫描连接
  开机自动启动
  退出
```

---

## 📥 安装与使用

### 方式一：下载预编译 DMG 安装包（推荐）

1. 在 [Releases](https://github.com/) 页面下载 `PicunBar-Installer.dmg`。
2. 双击打开，将 **`PicunBar.app`** 拖拽到 **`Applications`（应用程序）** 文件夹。
3. 打开运行即可在屏幕右上角看到耳机图标 `🎧`。

> [!NOTE]  
> **首次运行提示拦截处理**：  
> 由于个人开源项目未购买苹果年费签名证书，首次打开如果提示“未受信任的开发者”，请在访达中对着 `PicunBar.app` **按住 Control 键并右键点击 -> 选择“打开”**，或在系统设置的“隐私与安全性”中点击“仍要打开”。并在弹窗中允许访问蓝牙。

---

### 方式二：从源码直接运行

需要 Python 3.10+ 环境：

```bash
# 1. 克隆仓库
git clone https://github.com/your-username/PicunBar.git
cd PicunBar

# 2. 安装依赖
pip3 install -r requirements.txt

# 3. 运行状态栏小工具
python3 src/picun_menubar.py
```

---

### 方式三：免安装 Web Bluetooth 网页版

如果您在未安装 Python 的电脑上临时需要调节：
1. 切换到 `web/` 目录，启动本地静态服务：
   ```bash
   node web/server.js
   ```
2. 浏览器打开 `http://127.0.0.1:4567`，在 Chrome / Edge 中点击“连接耳机”即可在网页上直接控制！

---

## 🔍 协议逆向全解析 (BLE Protocol Specification)

经分析，品存 F8 Ultra 采用 **珠海杰理（Zhuhai JieLi Technology，Vendor ID: `0x05D6`）** 蓝牙芯片，其 BLE GATT 控制架构如下：

### 1. GATT 服务与特征值

| 类型 | UUID | 作用 |
| :--- | :--- | :--- |
| **Primary Service** | `0000ecd0-22ed-ccdb-79c7-71482b33c801` | 私有音频控制主服务 |
| **Write Characteristic** | `0000ecd2-22ed-ccdb-79c7-71482b33c801` | 接收主机发来的控制指令 |
| **Notify Characteristic** | `0000ecd1-22ed-ccdb-79c7-71482b33c801` | 向上报耳机当前状态变更 |

### 2. 报文帧封装结构

所有指令包均按此格式封装：

```text
[ 0xFC, 0xFA, 载荷长度, 指令码, 载荷数据..., CRC8-Maxim校验码 ]
```

* **帧头**：固定为 `0xFC, 0xFA`（2 字节）
* **载荷长度**：1 字节（后续 `Payload` 字节数）
* **指令码（Cmd）**：1 字节（如 `0x76` 为降噪）
* **载荷（Payload）**：N 字节参数
* **CRC 校验**：1 字节 **CRC8-Maxim**（计算范围为前面所有字节）

### 3. 核心功能 Hex 指令对照表

| 功能 | 指令码 | 载荷参数 | 完整发送报文 (Hex) |
| :--- | :--- | :--- | :--- |
| **关闭降噪（普通模式）** | `0x76` | `[0, 0, 0]` | `FC FA 03 76 00 00 00 13` |
| **开启深度降噪（ANC）** | `0x76` | `[1, 0, 14]` | `FC FA 03 76 01 00 0E A7` |
| **开启通透模式（环境音）** | `0x76` | `[2, 0, 14]` | `FC FA 03 76 02 00 0E 43` |
| **查询当前降噪状态** | `0x76` | `[]` | `FC FA 00 76 A1` |
| **查询电量** | `0x74` | `[]` | `FC FA 00 74 1D` |
| **低延迟游戏模式** | `0x78` | 开: `[1]` / 关: `[0]` | 开: `FC FA 01 78 01 D8` / 关: `FC FA 01 78 00 42` |
| **低音增强 (Bass Boost)** | `0x97` | 开: `[1]` / 关: `[0]` | 开: `FC FA 01 97 01 B5` / 关: `FC FA 01 97 00 EB` |
| **防风噪 (Windproof)** | `0x9A` | 开: `[1]` / 关: `[0]` | 开: `FC FA 01 9A 01 3C` / 关: `FC FA 01 9A 00 62` |
| **空间音频** | `0x79` | 开: `[1]` / 关: `[0]` | 开: `FC FA 01 79 01 1C` / 关: `FC FA 01 79 00 42` |

### 4. 电量解析规则说明

耳机返回的电量报文（`0x74`）为多字节结构：
```text
FC FA 06 74 [01] [24] [00] [00] [00] [00] [52]
             ↑    ↑    ↑    ↑
            b0   b1   b2   b3
```
- `b0`：左耳/主耳在线标记（布尔值，1 表示在线）
- `b1`：左耳/主耳电量百分比（十六进制 `0x24` = 十进制 **36%**）
- `b2` / `b3`：右耳/副耳在线标记与电量（分体耳机有效）

---

## 🛠️ 自行打包构建

如果您修改了代码，只需执行根目录下的自动化打包脚本：

```bash
chmod +x build_app.sh
./build_app.sh
```

脚本将自动执行依赖打包、架构规整、`Info.plist`（LSUIElement 纯状态栏声明）配置与签名，并在项目根目录生成 `PicunBar-Installer.dmg`。

---

## 📂 项目结构

```text
PicunBar/
├── README.md               # 项目主说明文档
├── LICENSE                 # MIT 开源许可证
├── requirements.txt        # Python 依赖清单
├── .gitignore              # Git 忽略配置
├── build_app.sh            # 一键构建 .app 与 .dmg 脚本
├── src/
│   ├── protocol.py         # 核心协议层 (CRC8、报文构建与解码)
│   └── picun_menubar.py    # macOS 状态栏应用主体
└── web/
    ├── index.html          # Web Bluetooth 单文件控制器
    └── server.js           # 本地 Web 服务
```

---

## 🤝 贡献与声明

- 本项目仅供技术研究与个人设备交互使用，耳机的协议版权归原始制造商所有。
- 欢迎提交 Issue 反馈问题或 PR 增加其他杰理方案耳机的适配！

## 📄 License

本项目基于 [MIT 许可证](LICENSE) 开源。
