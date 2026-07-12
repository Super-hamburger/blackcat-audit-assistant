# BlackCat Audit Assistant v3.0 Stage 3 Architecture

中文名：黑猫审单助手  
版本：3.0.0-architecture-foundation

## 第三阶段内容

### 1. 插件化架构

新增：

```text
core/plugin_manager.py
plugins/examples/
```

插件可以放在 `plugins/插件名/` 下，每个插件包含：

```text
plugin.json
plugin.py
```

### 2. 自动更新架构

新增：

```text
core/update_manager.py
updater/update_manifest.example.json
```

当前是本地更新清单示例。以后可以接服务器地址，实现真正自动检查新版本。

### 3. 多语言架构

新增：

```text
core/i18n_manager.py
locales/zh_CN.json
locales/ja_JP.json
```

当前已准备中文和日文语言包，后续会逐步把所有界面文字接入语言系统。

### 4. 完整安装包基础

新增：

```text
installer/build_portable.bat
installer/build_onefile.bat
installer/README_installer.md
```

可先生成便携版或单文件 EXE。真正安装向导版后续建议使用 Inno Setup。

## 运行

第一次运行：

```bat
install_dependencies.bat
```

启动：

```bat
run.bat
```

## 打包

便携版：

```bat
installer\build_portable.bat
```

单文件 EXE：

```bat
installer\build_onefile.bat
```
