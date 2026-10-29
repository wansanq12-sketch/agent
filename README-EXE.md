# 夜璃 EXE 版

此说明适用于 Windows 构建成功后生成的 Yeli.exe；源码目录本身不包含已构建 EXE。

## 使用者

- 解压成品 ZIP，双击 Yeli.exe，不需要安装 Python 或运行依赖安装命令。
- 首次启动会解压内置运行环境，可能需要等待；后续仍需网络调用你配置的 AI。
- 设置中填写自己的 API；游戏陪玩必须使用支持图片输入的模型。
- 同包 hex-aram 文件夹可以直接通过技能管理导入，再启用。
- 聊天、密钥、记忆与配置保存在 `%LOCALAPPDATA%\Yeli\data`，不会放在 EXE 的临时解压目录。替换 EXE 不会覆盖这些数据。
- 旧源码版的数据不会自动迁移，请保留旧 data 文件夹；不要把含密钥的数据目录发给别人。
- Windows 版游戏捕获、透明窗口与独占全屏显示仍需要实机确认。没有匹配版本统计资料时，游戏建议只按机制推理。
- 若启动报错，查看 `%LOCALAPPDATA%\Yeli\data\startup-error.log` 和 `launch.log`。

## 构建者（不是最终使用者）

PyInstaller 必须在 Windows 上构建 Windows EXE。当前 macOS 开发机不能直接产出已验证的 Windows 成品。

方式一：在自己的 Windows 构建环境安装 Python 3.12 64 位，安装 requirements-windows.txt 和 PyInstaller 6.17+，运行：

```
python -m pip install -r requirements-windows.txt "pyinstaller>=6.17,<7"
python -m PyInstaller --noconfirm --clean Yeli-Windows.spec
```

成品是 `dist/Yeli.exe`，Python、Qt WebEngine、OCR 模型与依赖、人物素材均随程序打包。不要分发源码 data 文件夹。未配置代码签名证书，因此不是签名发行版；不要为了运行它关闭系统保护。

方式二：把不含个人数据的源码放到你自己的 GitHub 仓库，包含 `.github/workflows/windows-exe.yml`。在 Actions → Build Windows EXE → Run workflow 手动启动。构建成功后下载 Yeli-Windows-EXE artifact。此流程只读仓库、生成构建产物，不自动发布或部署。

自动检查会实际运行打包后的 EXE，验证内置 OCR 原生库/模型、人物图片和本机 API，不会读取或发送你的屏幕。它不等同于真人游戏与桌面交互测试。未经运行成功，不应把构建配置当作已交付的 EXE。

## 交互与声音更新

输入框发送后保持打开，点击外部收起。右键精简为设置、隐藏、游戏模式和退出；隐藏后通过托盘显示。声音设置位于设置面板的声音页，游戏模式使用系统中文语音并隐藏回复气泡。Windows 需已安装中文语音包，可以先试听；没有可用声音时设置页会显示原因，不额外调用语音 API。更新只替换 EXE，保留用户数据目录。
