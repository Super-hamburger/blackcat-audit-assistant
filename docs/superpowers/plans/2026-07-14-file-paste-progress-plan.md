# 文件粘贴生成进度实施计划

> **供执行代理使用：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐项执行本计划。步骤使用复选框跟踪。

**目标：** 文件粘贴生成成品表时显示至少两秒的进度动画，且生成过程不阻塞主窗口。

**实现方式：** 在 `ui/main_window.py` 定义 `ExcelConversionWorker`，并将其移动到独立 `QThread`。主窗口显示非阻塞模态进度窗口，以 `QTimer` 更新进度，并在工作线程回传成功或失败结果后补足最少展示时间。

**技术栈：** Python、PySide6、`unittest`、`QThread`、`QTimer`。

## 全局约束

- 进度动画从开始显示到结束不得少于 2000 毫秒。
- 后台任务未完成前，进度条不得显示 100 或成功状态。
- 生成期间不允许重复点击“生成上传表”。
- 成功后保留现有日志、处理记录、自动打开 Excel 和完成提示。
- 不得改变 Excel 转换、地址拆分、SKU、货架、B 列发货方式和模板表头规则。

---

### 任务 1：建立进度时长回归测试

**文件：**
- 新建：`tests/test_file_paste_progress.py`

**接口：**
- 使用：`ui.main_window.minimum_remaining_progress_ms(started_at, now, minimum_ms=2000)`。
- 使用：`ui.main_window.EXCEL_PROGRESS_MINIMUM_MS`。

- [ ] **步骤 1：写入失败测试**

```python
def test_minimum_progress_delay_fills_the_remaining_time(self):
    remaining = getattr(main_window, "minimum_remaining_progress_ms", lambda *_: -1)
    self.assertEqual(remaining(0.5, 2.0), 500)

def test_minimum_progress_delay_is_zero_after_two_seconds(self):
    remaining = getattr(main_window, "minimum_remaining_progress_ms", lambda *_: -1)
    self.assertEqual(remaining(0.0, 2.5), 0)
```

- [ ] **步骤 2：运行测试，确认当前代码失败**

Run: `D:\Python\python.exe -m unittest tests.test_file_paste_progress -v`

Expected: FAIL because the duration helper does not exist.

### 任务 2：实现后台生成和进度窗口

**文件：**
- 修改：`ui/main_window.py`

**接口：**
- 新增：`EXCEL_PROGRESS_MINIMUM_MS = 2000`。
- 新增：`minimum_remaining_progress_ms(started_at, now, minimum_ms=2000) -> int`。
- 新增：`ExcelConversionWorker(module_registry, context)`，发出 `finished(dict)` 或 `failed(str)` 信号。

- [ ] **步骤 1：定义最少展示时间计算函数和后台工作对象**

```python
def minimum_remaining_progress_ms(started_at, now, minimum_ms=2000):
    elapsed_ms = int((now - started_at) * 1000)
    return max(0, minimum_ms - elapsed_ms)
```

- [ ] **步骤 2：为文件粘贴页保存生成按钮引用，并新增进度窗口和动画计时器**

- [ ] **步骤 3：将 `convert_upload_excel` 改为启动工作线程；任务结束后补足展示时间并在主线程处理结果**

- [ ] **步骤 4：运行进度测试，确认通过**

Run: `D:\Python\python.exe -m unittest tests.test_file_paste_progress -v`

Expected: PASS.

### 任务 3：整体验证、记录和测试版打包

**文件：**
- 修改：`data/changelog.json`
- 修改：`docs/CHANGELOG_FULL.md`

- [ ] **步骤 1：记录文件粘贴后台生成和两秒进度动画**

- [ ] **步骤 2：运行全部测试、静态检查、JSON 校验和打包 EXE 自测**

Run: `D:\Python\python.exe -m unittest discover -s tests -v`、`D:\Python\python.exe -m py_compile ui\main_window.py`、`D:\Python\python.exe -c "import json; json.load(open('data/changelog.json', encoding='utf-8')); print('JSON OK')"`、`dist\BlackCatAuditAssistant\BlackCatAuditAssistant.exe --self-test`。

Expected: 测试与编译成功，JSON 有效，打包 EXE 自测通过。

- [ ] **步骤 3：提交变更并打开测试版程序**

Run: `git add -- ui/main_window.py tests/test_file_paste_progress.py data/changelog.json docs/CHANGELOG_FULL.md docs/superpowers/specs/2026-07-14-file-paste-progress-design.md docs/superpowers/plans/2026-07-14-file-paste-progress-plan.md` then `git commit -m "feat: show file paste progress"`。
