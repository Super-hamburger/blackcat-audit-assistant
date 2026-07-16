# 扫码异常声音与英文输入实施计划

**目标：** 扫码异常强制播放已确认的专用警示音；扫码输入框默认偏好英文小写输入。

**范围：** 仅改临时测试项目，不改扫码匹配、异常导出、版本号或发布清单。

## 任务 1：编写失败测试

**文件：**
- 修改：tests/test_scan_input_compatibility.py
- 新建：tests/test_scan_feedback.py

- [ ] 新增测试：scan_error.wav 存在、是单声道 PCM WAV 且可读取。
- [ ] 新增测试：扫码异常声音播放方法不依赖统一 UI 音效开关。
- [ ] 新增测试：扫码输入框具有仅拉丁字符和偏好小写的输入法提示。
- [ ] 运行 D:\Python\python.exe -m unittest tests.test_scan_feedback -v，确认专用声音与方法尚未存在而失败。
- [ ] 提交失败测试：test: cover scanner feedback。

## 任务 2：接入专用声音和英文输入

**文件：**
- 重命名：assets/sounds/scan_error_preview.wav 为 assets/sounds/scan_error.wav。
- 修改：ui/main_window.py。

- [ ] 在扫码异常分支调用 play_scan_error_sound，而不是受开关控制的 play_error_sound。
- [ ] 新增 play_scan_error_sound，直接播放 scan_error.wav，不检查统一 UI 音效开关。
- [ ] 在扫码输入框设置 Qt 的仅拉丁字符和偏好小写输入法提示。
- [ ] 在 Windows 中安全尝试激活英文键盘布局；操作失败时不阻断扫码。
- [ ] 运行扫码输入兼容与扫码反馈测试，确认全部通过。
- [ ] 提交实现：feat: improve scanner feedback。

## 任务 3：更新记录与验证

**文件：**
- 修改：data/changelog.json。
- 修改：docs/CHANGELOG_FULL.md。
- 新建：docs/superpowers/plans/2026-07-16-scan-error-sound-and-input.md。

- [ ] 在两份更新日志记录：扫码异常使用强制警示音，扫码输入默认英文小写。
- [ ] 运行全部自动化测试、ui/main_window.py 静态编译、JSON 校验和源码自测。
- [ ] 打包独立测试包并运行打包 EXE 自测。
- [ ] 提交更新记录：docs: record scanner feedback improvements。

