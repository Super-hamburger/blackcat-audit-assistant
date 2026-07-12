RC1资源修复版

修复内容：
1. 修复EXE打包后头像不显示/变成小图标的问题
2. 修复EXE打包后声音没有的问题
3. 新增 PyInstaller spec，打包时自动包含：
   assets
   data
   locales
   plugins
   updater
4. ResourceManager 支持 PyInstaller 的 sys._MEIPASS 资源路径

打包方式：
双击 build_portable_rc1.bat

生成后发送：
压缩 dist\BlackCatAuditAssistant 整个文件夹，不要只发exe。
