V4.0.2 Sound API Fix

修复原因：
V4.0.1 为了解决启动初期无声音问题，替换了 SoundEngine。
但原 UI 仍然调用旧方法 play_click / play_complete / play_error。
因此点击主要功能按钮时发生 AttributeError，导致文件粘贴和面单压缩无法继续。

本版修复：
- SoundEngine 同时支持旧接口和新接口
- 恢复 play_click / play_complete / play_error
- 预热声音时只缓存，不触发业务错误
- 保留 V4.0.1 的更新日志修复

本次检测到 UI 使用的 sound_engine 方法：
['play_click', 'play_done', 'play_error', 'play_import', 'preload']

运行：
run_v4.bat

打包：
build_portable_v4.bat
