# 扫码枪兼容输入实施计划

**目标：** 扫码验单同时支持回车、Tab 和无结束键扫码枪；同一条码只能提交一次，慢速人工输入保持回车确认。

**架构：** 在主窗口增加独立的扫码输入控制器，负责监听输入速度、150ms 自动提交计时器以及 Tab 键。原有 handle_scan_input 继续负责调用验单服务、更新界面、提示音与异常弹窗。

**技术：** Python、PySide6、unittest、openpyxl。

## 全局约束

- 仅修改临时测试项目。
- 不修改 Excel 匹配、多电脑统计、异常导出和发布版本信息。
- 代码使用英文；说明和更新日志使用简体中文。
- 修改功能时同步更新 data/changelog.json 与 docs/CHANGELOG_FULL.md。

---

### 任务 1：编写输入兼容的失败测试

**文件：**
- 新建：tests/test_scan_input_compatibility.py
- 修改：ui/main_window.py

**接口：**
- 新增 ScanInputController(input_widget, submit_callback)。
- 控制器接收输入框编辑事件和 Tab 键；满足规则时调用 submit_callback 一次。

- [ ] 新建 Qt 应用测试夹具，并为每个测试创建 QLineEdit、记录提交内容的回调与 ScanInputController。
- [ ] 编写测试：模拟 Tab 键后，当前条码立即提交且 Tab 不改变焦点。
- [ ] 编写测试：快速写入至少 4 个字符，等待 150ms 后自动提交一次。
- [ ] 编写测试：超过 1 秒的慢速输入不自动提交。
- [ ] 编写测试：回车提交后，自动提交计时器不再重复调用。
- [ ] 运行 D:\Python\python.exe -m unittest tests.test_scan_input_compatibility -v，确认因控制器尚不存在而失败。
- [ ] 提交失败测试：test: cover scanner input compatibility。

### 任务 2：实现统一扫码提交入口

**文件：**
- 修改：ui/main_window.py 的 QtCore 导入、MainWindow 初始化、扫码输入框创建和 handle_scan_input 附近。

**接口：**
- ScanInputController 使用 150ms 单次 QTimer。
- 仅当输入长度至少为 4 且从首字符到最后字符不超过 1 秒时自动提交。
- submit_callback 停止计时器、读取并清空输入框、调用既有 ScanCheckService，再恢复输入框焦点。

- [ ] 新增 ScanInputController：输入编辑时记录首字符时间并重启单次计时器；Tab 事件拦截后立即请求提交；回车通过同一个请求提交方法。
- [ ] 将现有 handle_scan_input 改为统一提交入口，并在每次提交开始前停止自动计时器，避免重复扫码。
- [ ] 在扫码输入框创建时安装控制器；保留当前的回车流程。
- [ ] 运行 D:\Python\python.exe -m unittest tests.test_scan_input_compatibility -v，确认四项兼容测试通过。
- [ ] 运行 D:\Python\python.exe -m unittest tests.test_scan_check_export -v，确认验单导出未受影响。
- [ ] 提交实现：feat: support scanner input terminators。

### 任务 3：记录优化并完成验证

**文件：**
- 修改：data/changelog.json 当前版本的 improved 列表。
- 修改：docs/CHANGELOG_FULL.md 当前版本的 Improved 区域。

- [ ] 在两份更新日志加入：扫码验单兼容回车、Tab 和无结束键扫码枪；快速扫码停顿后自动提交，其他电脑无需配置结束键。
- [ ] 运行 D:\Python\python.exe -m unittest discover -s tests -v。
- [ ] 运行 D:\Python\python.exe -m compileall ui/main_window.py。
- [ ] 运行 D:\Python\python.exe -c "import json; json.load(open('data/changelog.json', encoding='utf-8'))"。
- [ ] 运行 D:\Python\python.exe app.py --self-test。
- [ ] 提交更新记录：docs: record scanner input compatibility。

