# 地址 L 列优化实施计划

> **供执行代理使用：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐项执行本计划。步骤使用复选框跟踪。

**目标：** 将文件粘贴功能的地址 L 列上限调整为 13 个全角字，并在保留行政区划优先级的前提下填满 L 列剩余容量。

**实现方式：** 在现有地址词段分配器中，仅为 L 列加入“下一个词段可按宽度截断并继续分配”的规则。M、N、O 列继续沿用现有整词段优先的分配方式和 16/25/25 的长度限制。

**技术栈：** Python、`unittest`、现有 `modules.file_paste.address_splitter`。

## 全局约束

- L、M、N、O 的长度上限必须为 13、16、25、25 个全角字。
- L 优先保留都道府县、市区郡町村，并在有后续内容时尽量填满。
- 全角字符宽度为 1，ASCII/半角字符宽度为 0.5。
- M、N、O 的既有语义拆分和 O 列超长标红行为不得改变。
- 地址字符不得丢失、重排或重复。

---

### 任务 1：为 L 列填满规则建立回归测试

**文件：**
- 修改：`tests/test_file_paste_address_splitter.py`

**接口：**
- 使用：`split_japanese_address(address) -> dict[str, str | bool]`
- 验证：返回结果中的 `L`、`M`、`N`、`O` 和 `overflow`。

- [ ] **步骤 1：编写失败测试**

```python
def test_l_keeps_administrative_prefix_and_fills_to_thirteen_full_width_characters(self):
    parts = split_japanese_address("東京都世田谷区北沢二丁目サンライズマンション101号室")

    self.assertTrue(parts["L"].startswith("東京都世田谷区"))
    self.assertEqual(display_width(parts["L"]), 13)
    self.assertEqual("".join(parts[key] for key in "LMNO"), "東京都世田谷区北沢二丁目サンライズマンション101号室")
    self.assertLessEqual(display_width(parts["M"]), 16)
    self.assertLessEqual(display_width(parts["N"]), 25)
```

- [ ] **步骤 2：运行测试，确认它因当前 L 列只容纳 12 个全角字或不填满而失败**

运行：

```powershell
D:\Python\python.exe -m unittest tests.test_file_paste_address_splitter.JapaneseAddressSplitterTest.test_l_keeps_administrative_prefix_and_fills_to_thirteen_full_width_characters -v
```

预期：测试失败，L 列显示宽度不是 13。

### 任务 2：实现 L 列的容量填充规则

**文件：**
- 修改：`modules/file_paste/address_splitter.py`
- 修改：`tests/test_file_paste_address_splitter.py`

**接口：**
- 修改：`ADDRESS_LIMITS = (13, 16, 25, 25)`。
- 修改：`allocate_tokens(tokens, limits=ADDRESS_LIMITS)`。

- [ ] **步骤 1：将 L 列上限改为 13**

```python
ADDRESS_LIMITS = (13, 16, 25, 25)
```

- [ ] **步骤 2：仅当当前列为 L 且下一个地址词段放不下时，使用 `split_by_display_width` 截取可放入的前缀**

```python
if column == 0 and values[column]:
    remaining_width = limits[column] - display_width(values[column])
    prefix, suffix = split_by_display_width(current, remaining_width)
    if prefix:
        values[column] = _join_address_tokens(values[column], prefix)
        pending.insert(0, suffix)
        column += 1
        continue
```

- [ ] **步骤 3：运行单个回归测试，确认通过**

运行：

```powershell
D:\Python\python.exe -m unittest tests.test_file_paste_address_splitter.JapaneseAddressSplitterTest.test_l_keeps_administrative_prefix_and_fills_to_thirteen_full_width_characters -v
```

预期：测试通过，L 列长度为 13，地址完整保留。

- [ ] **步骤 4：运行地址拆分测试文件，确认既有的 M/N/O 和超长行为未回归**

运行：

```powershell
D:\Python\python.exe -m unittest tests.test_file_paste_address_splitter -v
```

预期：全部测试通过。

### 任务 3：集成验证与提交

**文件：**
- 修改：`data/changelog.json`
- 修改：`docs/CHANGELOG_FULL.md`

- [ ] **步骤 1：记录 L 列地址上限及填充规则变更**

- [ ] **步骤 2：运行完整文件粘贴测试、Python 编译检查和 JSON 校验**

运行：

```powershell
D:\Python\python.exe -m unittest discover -s tests -v
D:\Python\python.exe -m compileall modules\file_paste tests
D:\Python\python.exe -c "import json; json.load(open('data/changelog.json', encoding='utf-8')); print('JSON OK')"
```

预期：所有测试通过，编译成功，输出 `JSON OK`。

- [ ] **步骤 3：提交变更**

```powershell
git add -- modules/file_paste/address_splitter.py tests/test_file_paste_address_splitter.py data/changelog.json docs/CHANGELOG_FULL.md docs/superpowers/plans/2026-07-14-address-l-column-optimization-plan.md
git commit -m "fix: optimize L column address allocation"
```
