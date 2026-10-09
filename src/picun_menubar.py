#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Picun (品存) F8 Ultra macOS Status Bar App
基于 BLE 协议的 macOS 状态栏耳机控制小工具
"""

import sys
import os
import json
import asyncio
import threading
from pathlib import Path
from typing import Optional

# 确保能正确导入同一目录下的 protocol.py
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

import rumps
from bleak import BleakClient, BleakScanner

from protocol import (
    SERVICE_UUID,
    WRITE_CHAR_UUID,
    NOTIFY_CHAR_UUID,
    CMD_NOISE_MODE,
    CMD_BATTERY,
    CMD_GAME_MODE,
    CMD_SPATIAL_AUDIO,
    CMD_BASS_BOOST,
    CMD_WINDPROOF,
    ANC_MODE_OFF,
    ANC_MODE_ANC,
    ANC_MODE_TRANSPARENCY,
    DEPTH_HIGH,
    build_packet,
    parse_battery
)

CACHE_FILE = Path.home() / ".picun_f8_cache.json"


class PicunStatusBarApp(rumps.App):
    def __init__(self):
        super().__init__("🎧", quit_button=None)
        
        # 菜单结构
        self.item_device = rumps.MenuItem("🎧 Picun F8 Ultra: 正在连接...", callback=self.on_click_connect)
        self.item_battery = rumps.MenuItem("🔋 电量: --")
        
        # 降噪模式
        self.item_mode_off = rumps.MenuItem("关闭降噪 (普通模式)", callback=self.set_mode_off)
        self.item_mode_anc = rumps.MenuItem("开启降噪 (ANC 深度)", callback=self.set_mode_anc)
        self.item_mode_trans = rumps.MenuItem("开启通透 (环境音透传)", callback=self.set_mode_trans)
        
        # 增强功能
        self.item_bass = rumps.MenuItem("低音增强 (Bass Boost)", callback=self.toggle_bass)
        self.item_wind = rumps.MenuItem("防风降噪 (Windproof)", callback=self.toggle_wind)
        self.item_game = rumps.MenuItem("低延迟游戏模式", callback=self.toggle_game)
        self.item_spatial = rumps.MenuItem("空间音频", callback=self.toggle_spatial)
        
        # 系统操作
        self.item_reconnect = rumps.MenuItem("重新扫描连接", callback=self.on_click_connect)
        self.item_autostart = rumps.MenuItem("开机自动启动", callback=self.toggle_autostart)
        self.item_quit = rumps.MenuItem("退出", callback=self.on_quit)

        self.menu = [
            self.item_device,
            self.item_battery,
            None,
            self.item_mode_off,
            self.item_mode_anc,
            self.item_mode_trans,
            None,
            self.item_bass,
            self.item_wind,
            self.item_game,
            self.item_spatial,
            None,
            self.item_reconnect,
            self.item_autostart,
            self.item_quit
        ]
        
        # 状态记录
        self.client: Optional[BleakClient] = None
        self.is_connected = False
        self.current_mode = -1
        self.bass_state = False
        self.wind_state = False
        self.game_state = False
        self.spatial_state = False
        
        # 初始化开机自启状态
        self.update_autostart_ui()

        # 启动后台 Asyncio 线程
        self.loop = asyncio.new_event_loop()
        self.bg_thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.bg_thread.start()

        # 自动执行初次连接
        asyncio.run_coroutine_threadsafe(self.connect_device(), self.loop)

    def _run_async_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def update_autostart_ui(self):
        plist_path = Path.home() / "Library/LaunchAgents/com.samwell.picunbar.plist"
        self.item_autostart.state = 1 if plist_path.exists() else 0

    def toggle_autostart(self, _):
        plist_path = Path.home() / "Library/LaunchAgents/com.samwell.picunbar.plist"
        python_bin = sys.executable
        script_path = str(Path(__file__).resolve())
        
        if plist_path.exists():
            plist_path.unlink()
            rumps.notification("Picun 控制器", "开机自启", "已关闭开机自动启动")
        else:
            plist_path.parent.mkdir(parents=True, exist_ok=True)
            content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.samwell.picunbar</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_bin}</string>
        <string>{script_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
"""
            plist_path.write_text(content)
            rumps.notification("Picun 控制器", "开机自启", "已开启开机自动启动")
        self.update_autostart_ui()

    def on_quit(self, _):
        if self.client and self.client.is_connected:
            asyncio.run_coroutine_threadsafe(self.client.disconnect(), self.loop)
        rumps.quit_application()

    def update_ui_status(self, connected: bool, device_name: str = ""):
        self.is_connected = connected
        if connected:
            self.title = "🎧"
            self.item_device.title = f"🎧 {device_name or 'Picun F8 Ultra'}: 已连接"
        else:
            self.title = "🎧 (离线)"
            self.item_device.title = "🎧 Picun F8: 未连接 (点击连接)"
            self.item_battery.title = "🔋 电量: --"
            self.item_mode_off.state = 0
            self.item_mode_anc.state = 0
            self.item_mode_trans.state = 0

    def update_mode_ui(self, mode: int):
        self.current_mode = mode
        self.item_mode_off.state = 1 if mode == ANC_MODE_OFF else 0
        self.item_mode_anc.state = 1 if mode == ANC_MODE_ANC else 0
        self.item_mode_trans.state = 1 if mode == ANC_MODE_TRANSPARENCY else 0

        mode_names = {
            ANC_MODE_OFF: "普通",
            ANC_MODE_ANC: "降噪",
            ANC_MODE_TRANSPARENCY: "通透"
        }
        if mode in mode_names:
            self.title = f"🎧 {mode_names[mode]}"

    def on_click_connect(self, _):
        if not self.is_connected:
            self.item_device.title = "🎧 正在搜索并连接耳机..."
            asyncio.run_coroutine_threadsafe(self.connect_device(force_scan=True), self.loop)

    async def connect_device(self, force_scan=False):
        cached_address = None
        if not force_scan and CACHE_FILE.exists():
            try:
                data = json.loads(CACHE_FILE.read_text())
                cached_address = data.get("address")
            except Exception:
                pass

        target_device = None

        if cached_address:
            print(f"[BLE] 尝试连接缓存设备: {cached_address}")
            try:
                target_device = await BleakScanner.find_device_by_address(cached_address, timeout=3.0)
            except Exception as e:
                print(f"[BLE] 查找缓存设备失败: {e}")

        if not target_device:
            print("[BLE] 正在扫描周围低功耗蓝牙设备...")
            self.item_device.title = "🎧 正在扫描设备..."
            discovered = await BleakScanner.discover(timeout=4.0, return_adv=True)
            for d, adv in discovered.values():
                name = d.name or ""
                uuids = [u.lower() for u in adv.service_uuids]
                # 匹配逻辑：名称包含 SW', Picun, F8 或含有 0xECD0 服务
                if (
                    name.startswith("SW'")
                    or "Picun" in name
                    or "F8" in name
                    or SERVICE_UUID.lower() in uuids
                ):
                    target_device = d
                    print(f"[BLE] 匹配到设备: {d.name} ({d.address})")
                    break

        if not target_device:
            print("[BLE] 未找到耳机，请确认耳机已开机且手机端未连接")
            self.update_ui_status(False)
            return

        try:
            print(f"[BLE] 正在连接 GATT: {target_device.address}...")
            client = BleakClient(
                target_device,
                disconnected_callback=self._on_ble_disconnected
            )
            await client.connect()
            self.client = client
            self.update_ui_status(True, target_device.name)

            # 保存缓存
            CACHE_FILE.write_text(json.dumps({"address": target_device.address, "name": target_device.name}))

            # 启用通知监听
            await client.start_notify(NOTIFY_CHAR_UUID, self._on_notify_received)
            print("[BLE] 已启动 Notify 监听！")

            # 查询初始状态
            await asyncio.sleep(0.3)
            await self.send_cmd(CMD_NOISE_MODE, [], "查询降噪状态")
            await asyncio.sleep(0.3)
            await self.send_cmd(CMD_BATTERY, [], "查询电量")

        except Exception as e:
            print(f"[BLE] 连接失败: {e}")
            self.update_ui_status(False)

    def _on_ble_disconnected(self, client):
        print("[BLE] 耳机蓝牙已断开")
        self.update_ui_status(False)

    def _on_notify_received(self, sender, data: bytearray):
        # 基础帧验证: [FC, FA, len, cmd, payload..., crc]
        if len(data) >= 4 and data[0] == 0xFC and data[1] == 0xFA:
            length = data[2]
            cmd = data[3]
            payload = data[4:4+length]
            print(f"[RX Notify] cmd={hex(cmd)}, len={length}, payload={list(payload)}")

            # 降噪状态响应
            if cmd == CMD_NOISE_MODE and len(payload) >= 1:
                mode = payload[0]
                self.update_mode_ui(mode)
            # 电量响应
            elif cmd == CMD_BATTERY:
                battery_str = parse_battery(payload)
                print(f"[BLE] 解析电量: {battery_str}")
                self.item_battery.title = f"🔋 电量: {battery_str}"
            # 低延迟游戏模式响应
            elif cmd == CMD_GAME_MODE and len(payload) >= 1:
                self.game_state = (payload[0] == 1)
                self.item_game.state = 1 if self.game_state else 0
            # 空间音频响应
            elif cmd == CMD_SPATIAL_AUDIO and len(payload) >= 1:
                self.spatial_state = (payload[0] == 1)
                self.item_spatial.state = 1 if self.spatial_state else 0
            # 低音增强响应
            elif cmd == CMD_BASS_BOOST and len(payload) >= 1:
                self.bass_state = (payload[0] == 1)
                self.item_bass.state = 1 if self.bass_state else 0
            # 防风降噪响应
            elif cmd in (CMD_WINDPROOF, 0x9A, 0x9a) and len(payload) >= 1:
                self.wind_state = (payload[0] == 1)
                self.item_wind.state = 1 if self.wind_state else 0

    async def send_cmd(self, cmd: int, payload: list = None, desc=""):
        if not self.client or not self.client.is_connected:
            print("[BLE] 发送失败: 未连接")
            return
        pkt = build_packet(cmd, payload)
        try:
            await self.client.write_gatt_char(WRITE_CHAR_UUID, pkt)
            print(f"[TX] ({desc}): {pkt.hex().upper()}")
        except Exception as e:
            print(f"[TX] 发送异常: {e}")

    # 降噪菜单回调
    def set_mode_off(self, _):
        asyncio.run_coroutine_threadsafe(self.send_cmd(CMD_NOISE_MODE, [ANC_MODE_OFF, 0, 0], "关闭降噪"), self.loop)
        self.update_mode_ui(ANC_MODE_OFF)

    def set_mode_anc(self, _):
        asyncio.run_coroutine_threadsafe(self.send_cmd(CMD_NOISE_MODE, [ANC_MODE_ANC, 0, DEPTH_HIGH], "深度降噪"), self.loop)
        self.update_mode_ui(ANC_MODE_ANC)

    def set_mode_trans(self, _):
        asyncio.run_coroutine_threadsafe(self.send_cmd(CMD_NOISE_MODE, [ANC_MODE_TRANSPARENCY, 0, DEPTH_HIGH], "通透模式"), self.loop)
        self.update_mode_ui(ANC_MODE_TRANSPARENCY)

    # 扩展功能开关
    def toggle_bass(self, _):
        self.bass_state = not self.bass_state
        self.item_bass.state = 1 if self.bass_state else 0
        asyncio.run_coroutine_threadsafe(self.send_cmd(CMD_BASS_BOOST, [1 if self.bass_state else 0], "低音增强"), self.loop)

    def toggle_wind(self, _):
        self.wind_state = not self.wind_state
        self.item_wind.state = 1 if self.wind_state else 0
        asyncio.run_coroutine_threadsafe(self.send_cmd(CMD_WINDPROOF, [1 if self.wind_state else 0], "防风降噪"), self.loop)

    def toggle_game(self, _):
        self.game_state = not self.game_state
        self.item_game.state = 1 if self.game_state else 0
        asyncio.run_coroutine_threadsafe(self.send_cmd(CMD_GAME_MODE, [1 if self.game_state else 0], "低延迟游戏模式"), self.loop)

    def toggle_spatial(self, _):
        self.spatial_state = not self.spatial_state
        self.item_spatial.state = 1 if self.spatial_state else 0
        asyncio.run_coroutine_threadsafe(self.send_cmd(CMD_SPATIAL_AUDIO, [1 if self.spatial_state else 0], "空间音频"), self.loop)


def main():
    app = PicunStatusBarApp()
    app.run()


if __name__ == "__main__":
    main()
