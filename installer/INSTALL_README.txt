黑猫审单助手安装说明

1. 把整个 BlackCatAuditAssistant 文件夹复制到目标电脑。
2. 双击 BlackCatAuditAssistant.exe 启动软件。
3. 不需要在目标电脑安装 Python。
4. 输出文件、日志和用户数据会自动写入当前用户可写目录。
5. 后续升级时，在软件“设置”页点击“检查更新”查看新版本下载地址。

升级维护说明：
- 发布新版本时更新 updater/update_manifest.example.json 或远程 update_manifest.json。
- 远程清单的 manifest_url 一旦配置，其他电脑会通过它检查最新版本。
