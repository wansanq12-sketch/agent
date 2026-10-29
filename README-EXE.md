# 夜璃 Windows 安装版

## 安装和更新

1. 在 GitHub Actions 的 **Build Windows Installer** 构建完成后，下载 **Yeli-Windows-Installer**。
2. 下载内容中的 `Yeli-Setup-1.1.0-x64.exe` 是安装程序。双击安装，不需要安装 Python。
3. 安装后从开始菜单「夜璃」启动，也可以在安装时选择创建桌面快捷方式。
4. 后续下载新版本的 `Yeli-Setup-版本号-x64.exe` 直接覆盖安装，无需先卸载；安装器沿用原安装目录。更新时请先退出夜璃。
5. 程序默认安装到 `%LOCALAPPDATA%\Programs\Yeli`。Windows「已安装的应用」中可查看版本和卸载。

## 配置会保留

个人数据固定保存在 `%LOCALAPPDATA%\Yeli\data`，与安装目录和版本号无关。API 密钥、角色设置、提醒、声音选择、聊天记录、记忆、导入的技能和游戏陪玩配置均沿用原文件。

之前独立 EXE 版本也使用同一个数据目录；在同一个 Windows 用户下安装后可直接读取。源码版位于源码目录的 data 不会自动搬迁，请先保留旧数据并使用备份恢复功能。切换电脑或 Windows 账户时也需要迁移数据。

第一次启动新版时，会在 `data/upgrade-backups` 中备份旧数据库与配置，再写入版本记录。备份包含本机密钥，请妥善保管；软件不会将其上传。新增配置使用默认值，已有配置不会重置。未来若数据格式升级，会检查数据版本，阻止旧程序写入较新的数据格式。

卸载只移除程序和快捷方式，保留个人数据；重新安装后可以继续使用。设置页显示当前软件版本，滚动条隐藏后仍可用滚轮或触控板滚动。

## 声音和游戏陪玩

声音页提供晓晓、晓伊、晓臻、晓雨四种女声，支持试听、选择和保存。在线朗读需允许将待朗读文字发送至微软，音频不落盘，无需语音密钥。试听只发送固定示例。游戏模式只播放声音，不弹回复气泡。

AI 聊天仍使用你配置的 API，游戏陪玩需支持图片输入的模型。安装目录的 `skills/hex-aram` 可通过技能管理导入。Windows 游戏捕获、桌面交互与独占全屏显示仍需实机验证。

启动失败可查看 `%LOCALAPPDATA%\Yeli\data\startup-error.log` 和 `launch.log`。

## 构建和版本管理

`VERSION` 是版本号唯一来源（主版本.次版本.修订号）。发布新版本时修改它，并更新 CHANGELOG.md。Windows EXE 的文件属性、安装器、设置页和发布清单统一读取此版本。

构建步骤：

```text
python -m pip install -r requirements-windows.txt "pyinstaller>=6.17,<7"
python tools/windows_version.py
python -m PyInstaller --noconfirm --clean Yeli-Windows.spec
ISCC.exe /DAppVersion=1.1.0 installer/Yeli.iss
```

构建必须在 Windows 上进行。GitHub Actions 会构建安装器，测试旧版安装 → 新版覆盖安装 → 卸载，校验用户数据不变，并运行安装后的 EXE 检查内置 OCR、素材与本机 API。检查不读取或发送真实屏幕。

最终产物为版本化安装器、release.json 和 SHA256SUMS.txt；不会上传个人数据，也不会自动发布 GitHub Release。安装器尚未配置代码签名。
