#!/usr/bin/env bash
# ==============================================================================
# PicunBar 一键打包与 DMG 生成脚本
# ==============================================================================

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "🚀 开始打包 PicunBar.app..."

# 检查 Python 环境
PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" &> /dev/null; then
    if [ -f "/usr/local/opt/python@3.10/bin/python3" ]; then
        PYTHON_BIN="/usr/local/opt/python@3.10/bin/python3"
    else
        echo "❌ 未找到 Python 3 环境，请确认已安装 Python。"
        exit 1
    fi
fi

# 安装依赖
echo "📦 检查并安装依赖..."
"$PYTHON_BIN" -m pip install -q -r requirements.txt

# 临时 Shims 规避部分 macOS 环境缺失 CommandLineTools 导致的 lipo/xcrun 错误
SHIM_DIR="/tmp/pyi_shims_$(id -u)"
mkdir -p "$SHIM_DIR"
cat << 'EOF' > "$SHIM_DIR/lipo"
#!/usr/bin/env bash
args=("$@")
for ((i=0; i<${#args[@]}; i++)); do
    if [ "${args[i]}" = "-output" ]; then
        out_file="${args[i+1]}"
        if [ "${args[0]}" = "-thin" ]; then
            in_file="${args[2]}"
            [ "$in_file" != "$out_file" ] && cp -f "$in_file" "$out_file"
            exit 0
        elif [ "${args[0]}" = "-create" ]; then
            cp -f "${args[3]}" "$out_file"
            exit 0
        fi
    fi
done
exit 0
EOF
chmod +x "$SHIM_DIR/lipo"

cat << 'EOF' > "$SHIM_DIR/install_name_tool"
#!/usr/bin/env bash
exit 0
EOF
chmod +x "$SHIM_DIR/install_name_tool"

cat << 'EOF' > "$SHIM_DIR/xcrun"
#!/usr/bin/env bash
exit 0
EOF
chmod +x "$SHIM_DIR/xcrun"

export PATH="$SHIM_DIR:$PATH"

# 清理旧构建
rm -rf build dist PicunBar.spec PicunBar-Installer.dmg

# 使用 PyInstaller 构建 App
echo "🔨 正在编译应用 Bundle..."
"$PYTHON_BIN" -m PyInstaller \
  --noconfirm \
  --windowed \
  --name "PicunBar" \
  --osx-bundle-identifier "com.samwell.picunbar" \
  --hidden-import "rumps" \
  --hidden-import "bleak" \
  --hidden-import "bleak.backends.corebluetooth" \
  --collect-all "bleak" \
  --collect-all "rumps" \
  --collect-all "pyobjc_framework_corebluetooth" \
  --collect-all "pyobjc_framework_Cocoa" \
  --collect-all "pyobjc_framework_libdispatch" \
  src/picun_menubar.py

# 写入 Info.plist 权限与纯状态栏属性
echo "⚙️ 配置 Info.plist (LSUIElement / Bluetooth 权限)..."
"$PYTHON_BIN" -c "
import plistlib
from pathlib import Path

plist_path = Path('dist/PicunBar.app/Contents/Info.plist')
if plist_path.exists():
    data = plistlib.loads(plist_path.read_bytes())
    data['LSUIElement'] = True
    data['NSBluetoothAlwaysUsageDescription'] = '用于连接品存 F8 Ultra 蓝牙耳机并控制降噪模式与音效'
    data['NSBluetoothPeripheralUsageDescription'] = '用于连接品存 F8 Ultra 蓝牙耳机并控制降噪模式与音效'
    data['CFBundleName'] = 'PicunBar'
    data['CFBundleDisplayName'] = 'Picun F8 Ultra'
    plist_path.write_bytes(plistlib.dumps(data, fmt=plistlib.FMT_XML))
"

# 代码重签名 (Ad-hoc)
echo "🔏 执行 Ad-hoc 签名..."
codesign --force --deep --sign - dist/PicunBar.app

# 生成 DMG
echo "💿 正在生成 DMG 安装包..."
DMG_STAGING="/tmp/picun_dmg_staging"
rm -rf "$DMG_STAGING"
mkdir -p "$DMG_STAGING"
cp -R dist/PicunBar.app "$DMG_STAGING/"
ln -s /Applications "$DMG_STAGING/Applications"

hdiutil create -volname "PicunBar" -srcfolder "$DMG_STAGING" -ov -format UDZO PicunBar-Installer.dmg
rm -rf "$DMG_STAGING" "$SHIM_DIR"

echo "✅ 构建完成！"
echo "👉 安装包位于: $DIR/PicunBar-Installer.dmg"
