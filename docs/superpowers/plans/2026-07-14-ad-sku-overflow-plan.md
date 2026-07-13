# AD 列 SKU 溢出分配实施计划

> **供执行代理使用：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐项执行本计划。步骤使用复选框跟踪。

**目标：** 让一件代发表的 SKU 明细在 AD 列最多保留 50 个半角字符，无法完整放入的 SKU 项移入 AC 列。

**实现方式：** 保留 `resolve_sku_quantities` 的数量解析结果，新增只负责 AD/AC 分配的辅助函数。该函数以完整 `SKU*数量` 项为单位分配，不在字符中间截断。

**技术栈：** Python、`unittest`、`openpyxl`。

## 全局约束

- AD 最多容纳 50 个半角字符。
- SKU 项格式必须保持为完整的 `SKU*数量`，项目之间使用英文逗号。
- AD 按源表顺序尽量容纳完整项目；第一个无法容纳的项目和其后所有项目写入 AC。
- 单个 SKU 项自身超过 50 个半角字符时，AC 写该完整项目，AD 留空。
- 黑猫新版表、货架排序、地址拆分、数量异常标记和成品表表头不得改变。

---

### 任务 1：建立 AD/AC 分配回归测试

**文件：**
- 修改：`tests/test_file_paste_converter.py`

**接口：**
- 使用：`UploadConverter.convert(source_path, output_dir)`。
- 验证：输出工作表的 `AC2`、`AD2` 文本值。

- [ ] **步骤 1：编写三项 SKU 溢出测试**

```python
def test_one_piece_moves_complete_sku_overflow_items_from_ad_to_ac(self):
    sku_one = "a" * 20
    sku_two = "b" * 20
    sku_three = "c" * 20
    _, values, _ = self.convert_and_load_one_piece([
        self.one_piece_row("OVERFLOW", f"{sku_one},{sku_two},{sku_three}", "*1+*1+*1", "1-1"),
    ])

    self.assertEqual(values[1][28], f"{sku_three}*1")
    self.assertEqual(values[1][29], f"{sku_one}*1,{sku_two}*1")
    self.assertLessEqual(len(values[1][29]), 50)
```

- [ ] **步骤 2：运行测试，确认当前实现因 AC 为空、AD 超过 50 而失败**

运行：`D:\Python\python.exe -m unittest tests.test_file_paste_converter.UploadConverterTest.test_one_piece_moves_complete_sku_overflow_items_from_ad_to_ac -v`

预期：测试失败，`AC2` 为空。

### 任务 2：实现完整 SKU 项的 AD/AC 分配

**文件：**
- 修改：`modules/file_paste/converter.py`
- 修改：`tests/test_file_paste_converter.py`

**接口：**
- 新增：`split_item_text_for_ad(item_text, limit=50) -> tuple[str, str]`。
- 修改：一件代发表的 `values`，同时写入 `AC` 和 `AD`。

- [ ] **步骤 1：实现按完整 SKU 项分配的辅助函数**

```python
def split_item_text_for_ad(item_text, limit=50):
    items = split_skus(item_text)
    ad_items = []
    for index, item in enumerate(items):
        candidate = ",".join([*ad_items, item])
        if len(candidate) <= limit:
            ad_items.append(item)
            continue
        return ",".join(ad_items), ",".join(items[index:])
    return ",".join(ad_items), ""
```

- [ ] **步骤 2：仅在一件代发表路径中调用该函数并写入 AC/AD**

```python
if source_type == "一件代发表格":
    item_text, quantity_issue = resolve_sku_quantities(record["sku"], record["quantity"])
    ad_value, ac_value = split_item_text_for_ad(item_text)
else:
    ac_value, ad_value = "", record["detail"]

values = {"AC": ac_value, "AD": ad_value}
```

- [ ] **步骤 3：运行三项 SKU 溢出测试，确认通过**

运行：`D:\Python\python.exe -m unittest tests.test_file_paste_converter.UploadConverterTest.test_one_piece_moves_complete_sku_overflow_items_from_ad_to_ac -v`

预期：测试通过，AD 不超过 50，第三个 SKU 项完整进入 AC。

- [ ] **步骤 4：补充单项超长测试并运行转换器测试文件**

```python
def test_one_piece_moves_a_single_overlong_sku_item_to_ac(self):
    long_sku = "x" * 51
    _, values, _ = self.convert_and_load_one_piece([
        self.one_piece_row("LONG-SKU", long_sku, 1, "1-1"),
    ])

    self.assertEqual(values[1][28], f"{long_sku}*1")
    self.assertIsNone(values[1][29])
```

运行：`D:\Python\python.exe -m unittest tests.test_file_paste_converter -v`

预期：所有转换器测试通过。

### 任务 3：记录、验证与提交

**文件：**
- 修改：`data/changelog.json`
- 修改：`docs/CHANGELOG_FULL.md`

- [ ] **步骤 1：记录 AD 50 字符上限和 AC 溢出规则**
- [ ] **步骤 2：运行完整测试、编译检查和 JSON 校验**

运行：`D:\Python\python.exe -m unittest discover -s tests -v`、`D:\Python\python.exe -m compileall modules\file_paste tests`、`D:\Python\python.exe -c "import json; json.load(open('data/changelog.json', encoding='utf-8')); print('JSON OK')"`。

- [ ] **步骤 3：提交变更**

运行：`git add -- modules/file_paste/converter.py tests/test_file_paste_converter.py data/changelog.json docs/CHANGELOG_FULL.md docs/superpowers/plans/2026-07-14-ad-sku-overflow-plan.md`，随后执行 `git commit -m "fix: split AD SKU overflow into AC"`。
