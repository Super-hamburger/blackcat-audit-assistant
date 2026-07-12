# 扫码验单未匹配源数据导出实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 仅核验数量为 1 的源数据，并在会话结束后导出完整的未匹配源数据行。

**Architecture:** 导入 Excel 时保留符合条件的完整源行，并为每个订单与 SKU 建立待匹配行索引。一次成功扫码从对应索引中取出一条行标识并标记已匹配，扫码路径不读写磁盘、不遍历全表；导出时才按原始行顺序筛选未匹配行并生成 Excel。

**Tech Stack:** Python、PySide6、OpenPyXL、unittest。

## 全局约束

- 只有数量恰好为 `1` 的行参与扫码、异常导出和未匹配导出。
- 数量大于等于 `2` 的行必须完全忽略。
- 未匹配导出必须保留源 Excel 的全部原始列和值。
- 扫码成功路径必须只进行字典或队列查找及少量状态更新，不读写 Excel。

---

### Task 1: 建立数量过滤与未匹配导出的回归测试

**Files:**
- Modify: `tests/test_scan_check_export.py`

**Interfaces:**
- Consumes: `ScanCheckService.load_excel(path)`、`ScanCheckService.start()`、`ScanCheckService.scan(code)`。
- Produces: `ScanCheckService.export_unmatched_source_rows(output_path)`，返回实际导出的 `.xlsx` 路径。

- [ ] **Step 1: 写入失败测试**

```python
def test_export_unmatched_source_rows_ignores_quantity_two_rows(self):
    # 源表包含数量为 1 的 SKU-01、SKU-03，以及数量为 2 的 SKU-02。
    # 扫描 SKU-01 后，导出文件只保留 SKU-03 的完整原始数据行。
    self.assertEqual(summary["item_count"], 2)
    self.assertEqual(exported_rows, [headers, unmatched_source_row])
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:\Python\python.exe -m unittest tests.test_scan_check_export -v`

Expected: FAIL，因为 `export_unmatched_source_rows` 尚不存在，且当前导入会把数量为 `2` 的行加入扫码数据。

- [ ] **Step 3: 实现最小数据模型变更**

```python
eligible_rows = []
pending_row_indexes_by_key = {}
matched_row_indexes = set()

if quantity != 1:
    continue

row_index = len(eligible_rows)
eligible_rows.append(source_row)
pending_row_indexes_by_key.setdefault((order_key, sku_key), deque()).append(row_index)
```

- [ ] **Step 4: 在成功扫码时标记单条源行**

```python
pending_indexes = self.pending_row_indexes_by_key[(self.current_order, code)]
matched_row_index = pending_indexes.popleft()
self.matched_row_indexes.add(matched_row_index)
```

- [ ] **Step 5: 实现未匹配 Excel 导出**

```python
def export_unmatched_source_rows(self, output_path):
    rows = [row for index, row in enumerate(self.eligible_rows)
            if index not in self.matched_row_indexes]
    return self._export_source_rows(output_path, rows, "未匹配数据")
```

- [ ] **Step 6: 运行测试确认通过**

Run: `D:\Python\python.exe -m unittest tests.test_scan_check_export -v`

Expected: PASS，数量为 `2` 的行不会参与核验或导出，已匹配行不会出现在未匹配文件中。

### Task 2: 接入扫码验单界面的未匹配导出操作

**Files:**
- Modify: `ui/main_window.py`
- Test: `tests/test_scan_check_export.py`

**Interfaces:**
- Consumes: `ScanCheckService.export_unmatched_source_rows(output_path)`。
- Produces: `MainWindow.export_scan_unmatched_source_rows()`，显示导出成功、无未匹配数据和导出失败状态。

- [ ] **Step 1: 写入失败测试**

```python
def test_export_unmatched_source_rows_uses_xlsx_extension(self):
    output = service.export_unmatched_source_rows(Path(temp_dir) / "unmatched.csv")
    self.assertEqual(Path(output).suffix, ".xlsx")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `D:\Python\python.exe -m unittest tests.test_scan_check_export -v`

Expected: FAIL，因为未匹配导出接口尚未实现。

- [ ] **Step 3: 添加界面按钮与保存流程**

```python
unmatched_export_btn = QPushButton("导出未匹配源数据")
unmatched_export_btn.clicked.connect(self.export_scan_unmatched_source_rows)

default_path = Path.home() / "Desktop" / f"扫码验单未匹配_{time.strftime('%Y%m%d_%H%M%S')}.xlsx"
```

- [ ] **Step 4: 运行目标测试确认通过**

Run: `D:\Python\python.exe -m unittest tests.test_scan_check_export -v`

Expected: PASS，未匹配导出始终生成 `.xlsx` 文件。

### Task 3: 完整验证与本地测试版启动

**Files:**
- Verify: `modules/scan_check/module.py`
- Verify: `ui/main_window.py`
- Verify: `tests/test_scan_check_export.py`

- [ ] **Step 1: 运行全部单元测试**

Run: `D:\Python\python.exe -m unittest discover -s tests -v`

Expected: 所有扫码验单与单实例测试通过。

- [ ] **Step 2: 编译与源码自检**

Run: `D:\Python\python.exe -m compileall modules\scan_check\module.py ui\main_window.py tests\test_scan_check_export.py`

Run: `D:\Python\python.exe app.py --self-test --self-test-output self_test_scan_unmatched_source.json`

Expected: 编译命令退出码为 `0`，自检 JSON 的 `ok` 为 `true`。

- [ ] **Step 3: 启动更新后的源码测试版**

Run: `D:\Python\pythonw.exe app.py`

Expected: 打开扫码验单界面，可导入源表并测试“导出未匹配源数据”。
