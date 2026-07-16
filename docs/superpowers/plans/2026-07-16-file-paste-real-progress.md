# 文件粘贴真实进度与可控任务 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让文件粘贴功能在大表处理时显示真实进度、支持暂停和结束，并减少重复样式复制造成的开销。

**Architecture:** 转换器提供线程安全控制对象与结构化进度事件，作为唯一的真实进度来源。模块负责透传，界面工作线程将事件转成 Qt 信号，弹窗根据阶段切换确定/忙碌进度条并控制暂停、继续和结束。输出文件只在成功保存后保留。

**Tech Stack:** Python 3、openpyxl、PySide6、unittest、threading。

## 全局约束

- 所有新增面向用户的文字、计划和更新说明使用简体中文；代码标识符使用英文。
- 保持既有 SKU 分组、货架排序、地址拆分、字段映射和异常标记结果不变。
- 读取和写入阶段必须按实际行数发进度事件；打开、排序、保存阶段不得伪装成固定百分比。
- 取消后不允许产生新的 `.xlsx` 半成品。
- 每次生产代码修改前先写对应失败测试，并在实现后运行测试。
- 功能变化同步更新 `data/changelog.json` 与 `docs/CHANGELOG_FULL.md`。

---

## 文件结构

- `modules/file_paste/converter.py`：转换控制、取消异常、真实进度事件、只读源表和模板样式复用。
- `modules/file_paste/module.py`：将任务控制和进度回调传递给转换器。
- `ui/main_window.py`：工作线程进度信号和带暂停/继续/结束按钮的真实进度弹窗。
- `tests/test_file_paste_converter.py`：转换器进度、暂停、取消、样式与输出清理回归测试。
- `tests/test_file_paste_progress.py`：工作线程进度转发和界面进度状态测试。
- `data/changelog.json`、`docs/CHANGELOG_FULL.md`：本次功能更新记录。

### Task 1: 转换器真实进度与控制对象

**Files:**

- Modify: `modules/file_paste/converter.py:1-312`
- Test: `tests/test_file_paste_converter.py`

**Interfaces:**

- Produces: `ConversionControl.pause()`、`resume()`、`cancel()`、`checkpoint()`；`ConversionCancelled`；`UploadConverter.convert(source_path, output_dir, open_after=True, progress_callback=None, control=None)`。
- Produces: 进度事件字典，字段为 `phase`、`message`、`current`、`total`、`indeterminate`。

- [ ] **Step 1: 写入失败测试**

```python
def test_converter_reports_actual_read_and_write_row_progress(self):
    events = []
    result = UploadConverter().convert(source_path, temp_dir, False, events.append)
    reading = [event for event in events if event["phase"] == "reading"]
    writing = [event for event in events if event["phase"] == "writing"]
    self.assertEqual(reading[-1]["current"], 3)
    self.assertEqual(reading[-1]["total"], 3)
    self.assertEqual(writing[-1]["current"], result["row_count"])
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `$env:QT_QPA_PLATFORM='offscreen'; D:\Python\python.exe -m unittest tests.test_file_paste_converter.UploadConverterTest.test_converter_reports_actual_read_and_write_row_progress -v`

Expected: FAIL，提示 `convert()` 尚不接受进度回调。

- [ ] **Step 3: 最小实现**

```python
class ConversionCancelled(Exception):
    pass

class ConversionControl:
    def checkpoint(self):
        while self._paused.is_set():
            if self._cancelled.is_set():
                raise ConversionCancelled()
            time.sleep(0.03)
        if self._cancelled.is_set():
            raise ConversionCancelled()
```

实现进度事件、循环检查、只读源表及取消清理；模板行复用不可变样式，仍允许异常格单独标色。

- [ ] **Step 4: 运行转换器测试，确认通过**

Run: `D:\Python\python.exe -m unittest tests.test_file_paste_converter -v`

Expected: PASS。

- [ ] **Step 5: 提交**

Run: `git add modules/file_paste/converter.py tests/test_file_paste_converter.py; git commit -m "feat: add controllable file conversion progress"`

### Task 2: 模块和工作线程的进度转发

**Files:**

- Modify: `modules/file_paste/module.py:1-13`
- Modify: `ui/main_window.py:62-87`
- Test: `tests/test_file_paste_progress.py`

**Interfaces:**

- Consumes: `ConversionControl` 与转换器的 `progress_callback`。
- Produces: `ExcelConversionWorker.progress` Qt 信号，向主线程发送进度事件。

- [ ] **Step 1: 写入失败测试**

```python
def test_background_worker_forwards_conversion_progress(self):
    worker = main_window.ExcelConversionWorker(Registry(), {"source_path": "source.xlsx"})
    received = []
    worker.progress.connect(received.append)
    worker.run()
    self.assertEqual(received, [{"phase": "reading", "current": 1, "total": 1}])
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `$env:QT_QPA_PLATFORM='offscreen'; D:\Python\python.exe -m unittest tests.test_file_paste_progress.FilePasteProgressTest.test_background_worker_forwards_conversion_progress -v`

Expected: FAIL，提示工作线程没有 `progress` 信号。

- [ ] **Step 3: 最小实现**

```python
class ExcelConversionWorker(QObject):
    progress = Signal(object)

    def run(self):
        context = {**self.context, "progress_callback": self.progress.emit}
        module_result = self.module_registry.run("file_paste", context)
```

模块将回调与 `conversion_control` 传给 `UploadConverter`。

- [ ] **Step 4: 运行工作线程测试，确认通过**

Run: `$env:QT_QPA_PLATFORM='offscreen'; D:\Python\python.exe -m unittest tests.test_file_paste_progress -v`

Expected: PASS。

- [ ] **Step 5: 提交**

Run: `git add modules/file_paste/module.py ui/main_window.py tests/test_file_paste_progress.py; git commit -m "feat: forward file conversion progress"`

### Task 3: 真实进度弹窗、暂停和结束操作

**Files:**

- Modify: `ui/main_window.py:175-193,2050-2165`
- Test: `tests/test_file_paste_progress.py`

**Interfaces:**

- Consumes: 进度事件、`ConversionControl`、`ExcelConversionWorker.progress`。
- Produces: `on_excel_conversion_progress(event)`、`toggle_excel_conversion_pause()`、`cancel_excel_conversion()`。

- [ ] **Step 1: 写入失败测试**

```python
def test_real_progress_uses_rows_and_busy_bar_for_save(self):
    window = make_window()
    window.show_excel_progress_dialog()
    window.on_excel_conversion_progress({"phase": "writing", "message": "正在写入上传表", "current": 12, "total": 60})
    self.assertEqual(window.excel_progress_bar.maximum(), 60)
    self.assertEqual(window.excel_progress_bar.value(), 12)
    window.on_excel_conversion_progress({"phase": "saving", "message": "正在保存", "indeterminate": True})
    self.assertEqual(window.excel_progress_bar.maximum(), 0)
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `$env:QT_QPA_PLATFORM='offscreen'; D:\Python\python.exe -m unittest tests.test_file_paste_progress.FilePasteProgressTest.test_real_progress_uses_rows_and_busy_bar_for_save -v`

Expected: FAIL，提示缺少真实进度处理方法。

- [ ] **Step 3: 最小实现**

```python
def on_excel_conversion_progress(self, event):
    if event.get("indeterminate"):
        self.excel_progress_bar.setRange(0, 0)
    else:
        self.excel_progress_bar.setRange(0, max(1, event["total"]))
        self.excel_progress_bar.setValue(event["current"])
    self.excel_progress_status.setText(event["message"])
```

创建同一个 `ConversionControl` 并放入 context；连接 `worker.progress`；移除模拟进度计时器和最短展示延迟；对话框加入暂停/继续、结束任务按钮。取消时显示等待当前行结束，收到取消结果后报告“任务已结束，未生成文件”。

- [ ] **Step 4: 运行界面进度测试，确认通过**

Run: `$env:QT_QPA_PLATFORM='offscreen'; D:\Python\python.exe -m unittest tests.test_file_paste_progress -v`

Expected: PASS。

- [ ] **Step 5: 提交**

Run: `git add ui/main_window.py tests/test_file_paste_progress.py; git commit -m "feat: add pause and cancel file conversion"`

### Task 4: 大表回归、更新记录与完整验证

**Files:**

- Modify: `tests/test_file_paste_converter.py`
- Modify: `data/changelog.json`
- Modify: `docs/CHANGELOG_FULL.md`

- [ ] **Step 1: 写入失败测试**

```python
def test_converter_handles_six_thousand_rows_with_monotonic_write_progress(self):
    events = []
    UploadConverter().convert(source_path_with_6000_rows, temp_dir, False, events.append)
    values = [event["current"] for event in events if event["phase"] == "writing"]
    self.assertEqual(values[-1], 6000)
    self.assertEqual(values, sorted(values))
```

- [ ] **Step 2: 运行测试，确认失败或暴露性能回归**

Run: `D:\Python\python.exe -m unittest tests.test_file_paste_converter.UploadConverterTest.test_converter_handles_six_thousand_rows_with_monotonic_write_progress -v`

Expected: 首次因缺少大表进度保证或性能实现而失败；实现完成后重新运行至 PASS。

- [ ] **Step 3: 完善批量进度与更新记录**

进度事件以首行、末行和固定小批次发送，避免 6000 次跨线程 UI 更新拖慢转换；更新两个更新记录文件。

- [ ] **Step 4: 运行完整验证**

Run: `$env:QT_QPA_PLATFORM='offscreen'; D:\Python\python.exe -m unittest discover -s tests -v; D:\Python\python.exe -m py_compile modules/file_paste/converter.py modules/file_paste/module.py ui/main_window.py`

Expected: 全部 PASS，编译命令退出码为 0。

- [ ] **Step 5: 提交**

Run: `git add tests/test_file_paste_converter.py data/changelog.json docs/CHANGELOG_FULL.md; git commit -m "docs: record controllable file paste progress"`
