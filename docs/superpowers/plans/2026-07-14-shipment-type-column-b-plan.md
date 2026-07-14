# B 列发货方式实施计划

> **供执行代理使用：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐项执行本计划。步骤使用复选框跟踪。

**Goal:** 让成品表 B 列根据两种原始表中的发货方式写入 `A` 或 `0`，无法识别时留空并标红。

**Architecture:** 在 `converter.py` 增加一个纯函数，基于来源字段中的关键词返回发货方式代码和异常状态。一件代发表读取可选“运输方式”列，黑猫新版表读取可选“备注”列；转换循环统一写入并标记 B 列。

**Tech Stack:** Python、`unittest`、`openpyxl`。

## Global Constraints

- B 列为模板既有列 `送り状種類`，不得调整模板表头或列位置。
- `A` 代表黑猫投函，`0` 代表黑猫宅急便。
- 一件代发表读取“运输方式”，黑猫新版表读取“备注”。
- 字段为空、关键词无法识别或同时出现两种方式时，B 列留空并使用红色标记，订单继续生成。
- 货架排序、地址拆分、SKU 数量分配和其他输出列不得改变。

---

### Task 1: 建立 B 列映射回归测试

**Files:**
- Modify: `tests/test_file_paste_converter.py`

**Interfaces:**
- Consumes: `UploadConverter.convert(source_path, output_dir)`。
- Produces: 对 B2 的文字值和填充色断言。

- [ ] **Step 1: 写入一件代发表宅急便的失败测试**

```python
def test_one_piece_writes_zero_for_takkyubin(self):
    _, values, _ = self.convert_and_load_one_piece([
        self.one_piece_row("TAK", "sku-a", 1, "1-1", shipping_method="宅急便"),
    ])

    self.assertEqual(values[1][1], "0")
```

- [ ] **Step 2: 写入黑猫新版表投函和备注为空的失败测试**

```python
def test_blackcat_writes_a_for_toukan_remark(self):
    _, values, fills = self.convert_and_load_blackcat({"备注": "7.15黑猫投函"})
    self.assertEqual(values[1][1], "A")
    self.assertNotEqual(fills["B2"], color_suffix(MARK_SHIPMENT_TYPE_ISSUE))

def test_blackcat_marks_blank_shipment_type(self):
    _, values, fills = self.convert_and_load_blackcat({"备注": ""})
    self.assertIsNone(values[1][1])
    self.assertEqual(fills["B2"], color_suffix(MARK_SHIPMENT_TYPE_ISSUE))
```

- [ ] **Step 3: 运行新增测试，确认当前代码失败**

Run: `python -m unittest tests.test_file_paste_converter.UploadConverterTest.test_one_piece_writes_zero_for_takkyubin tests.test_file_paste_converter.UploadConverterTest.test_blackcat_writes_a_for_toukan_remark tests.test_file_paste_converter.UploadConverterTest.test_blackcat_marks_blank_shipment_type -v`

Expected: FAIL because the current converter does not write B 列。

### Task 2: 实现发货方式解析和 B 列标记

**Files:**
- Modify: `modules/file_paste/converter.py`

**Interfaces:**
- Produces: `resolve_shipment_type(value) -> tuple[str, str | None]`。
- Reads: `record["shipping_method"]` for 一件代发表 and `record["remark"]` for 黑猫新版表。

- [ ] **Step 1: 添加发货方式解析函数**

```python
def resolve_shipment_type(value):
    text = norm(value)
    has_toukan = "投函" in text
    has_takkyubin = "宅急便" in text
    if has_toukan == has_takkyubin:
        return "", "发货方式无法唯一识别"
    return ("A", None) if has_toukan else ("0", None)
```

- [ ] **Step 2: 读取可选来源字段并写入 B 列**

```python
shipment_type, shipment_type_issue = resolve_shipment_type(
    record["shipping_method"] if source_type == "一件代发表格" else record["remark"]
)
values = {"B": shipment_type}
if shipment_type_issue:
    output_sheet[f"B{output_row}"].fill = MARK_SHIPMENT_TYPE_ISSUE
```

- [ ] **Step 3: 运行新增测试，确认通过**

Run: `python -m unittest tests.test_file_paste_converter.UploadConverterTest.test_one_piece_writes_zero_for_takkyubin tests.test_file_paste_converter.UploadConverterTest.test_blackcat_writes_a_for_toukan_remark tests.test_file_paste_converter.UploadConverterTest.test_blackcat_marks_blank_shipment_type -v`

Expected: PASS.

### Task 3: 记录并完整验证

**Files:**
- Modify: `data/changelog.json`
- Modify: `docs/CHANGELOG_FULL.md`
- Modify: `docs/superpowers/specs/2026-07-14-shipment-type-column-b-design.md`
- Modify: `docs/superpowers/plans/2026-07-14-shipment-type-column-b-plan.md`

- [ ] **Step 1: 在 V4.4.1 改进项补充 B 列发货方式映射说明**

- [ ] **Step 2: 运行全部转换器测试和编译检查**

Run: `python -m unittest tests.test_file_paste_converter -v` and `python -m py_compile modules/file_paste/converter.py tests/test_file_paste_converter.py`.

Expected: 所有测试通过，两个 Python 文件均能编译。

- [ ] **Step 3: 检查一件代发表和黑猫新版表的代表性输出**

Run: `python -m unittest tests.test_file_paste_converter -v`.

Expected: B 列的 `A`、`0`、留空标红测试均通过，已有地址、SKU、货架规则仍通过。

- [ ] **Step 4: 提交变更**

Run: `git add -- modules/file_paste/converter.py tests/test_file_paste_converter.py data/changelog.json docs/CHANGELOG_FULL.md docs/superpowers/specs/2026-07-14-shipment-type-column-b-design.md docs/superpowers/plans/2026-07-14-shipment-type-column-b-plan.md` then `git commit -m "feat: map shipment type to column b"`.
