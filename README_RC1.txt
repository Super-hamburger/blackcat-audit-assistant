黑猫审单助手 RC1 完整项目稳定版

这个包保留 v3.0 / Alpha19 完整项目功能，并增加 RC1 跨电脑稳定修复。

RC1重点：
1. 不再写死 C:\Users\Admin
2. 默认输出到当前用户桌面：
   Desktop\BlackCatAuditAssistant\output
3. 运行数据写到用户可写目录
4. 兼容不同Windows用户名、日文系统、OneDrive桌面
5. 修复朋友电脑 WinError 5 Access Denied

运行：
1. 第一次运行 install_dependencies.bat
2. 双击 run.bat

打包EXE：
双击 build_portable_rc1.bat
输出位置：
dist\BlackCatAuditAssistant

发送给朋友：
只发送 dist\BlackCatAuditAssistant 整个文件夹的压缩包。
不要只发送 exe。
