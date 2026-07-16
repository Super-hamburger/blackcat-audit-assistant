# 文件粘贴分组拆分输出 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 文件粘贴按单 SKU 与多 SKU 输出独立 Excel，每份最多 999 条，并统一放入清晰命名的本次生成文件夹。

**Architecture:** 转换器在完成读取和既有排序后，按 SKU 个数将记录分类、按 999 条分块；每个分块独立加载模板并生成一个 Excel。转换结果返回输出文件夹与全部文件清单，界面显示文件夹、文件数和各文件名称，完成后打开文件夹。

**Tech Stack:** Python 3、openpyxl、PySide6、unittest。

## 全局约束

- 每份成品表最多 999 条数据，表头不计入数据条数。
- 单 SKU 与多 SKU 绝不混在同一份 Excel；先分类、后按 999 条拆分。
- 单 SKU 中 `*1` 与 `*N` 同类输出，保留现有 `*1`、`*N`、货架排序规则。
- 数量格式异常数据不丢弃，继续使用原红色标记，按 SKU 个数归类。
- 每次任务生成唯一文件夹 `黑猫上传表_YYYYMMDD_HHMMSS`；文件名含顺序、分类、份数和条数。
- 任务取消、异常或保存失败时，清理本次已经生成和未完成的所有 Excel 与空批次文件夹。
- 功能变化同步更新 `data/changelog.json` 与 `docs/CHANGELOG_FULL.md`。

---

## 文件结构

- `modules/file_paste/converter.py`：记录分类、999 条分块、多文件生成、批次清理和返回文件清单。
- `ui/main_window.py`：展示输出文件夹和多文件清单，自动打开文件夹。
- `tests/test_file_paste_converter.py`：分类、999 条边界、命名、成品内容与取消清理测试。
- `data/changelog.json`、`docs/CHANGELOG_FULL.md`：用户可见更新说明。

### Task 1: 分类、分块和批次输出接口

**Files:**

- Modify: `modules/file_paste/converter.py:15-421`
- Test: `tests/test_file_paste_converter.py`

**Interfaces:**

- Produces: `MAX_OUTPUT_ROWS = 999`、`split_records_by_sku_kind(records)`、`chunk_records(records, size=MAX_OUTPUT_ROWS)`。
- Produces: `UploadConverter.convert(...)` 返回 `output_dir`、`output_paths`、`file_count`、聚合异常统计；取消时抛出 `ConversionCancelled` 且没有本次批次文件夹。

- [ ] **Step 1: 写入失败测试**

```python
def test_chunk_records_keeps_999_row_limit(self):
    chunks = chunk_records(list(range(1200)), 999)
    self.assertEqual([len(chunk) for chunk in chunks], [999, 201])

def test_split_records_separates_single_and_multi_sku(self):
    single, multi = split_records_by_sku_kind([
        {"sku": "A", "quantity": 1},
        {"sku": "B", "quantity": 3},
        {"sku": "C,D", "quantity": "*1+*1"},
    ])
    self.assertEqual([record["sku"] for record in single], ["A", "B"])
    self.assertEqual([record["sku"] for record in multi], ["C,D"])
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `D:\Python\python.exe -m unittest tests.test_file_paste_converter.UploadConverterTest.test_chunk_records_keeps_999_row_limit tests.test_file_paste_converter.UploadConverterTest.test_split_records_separates_single_and_multi_sku -v`

Expected: FAIL，提示分块或分类函数尚不存在。

- [ ] **Step 3: 最小实现分类、分块和多文件返回值**

```python
MAX_OUTPUT_ROWS = 999

def split_records_by_sku_kind(records):
    single = [record for record in records if len(split_skus(record["sku"])) == 1]
    multi = [record for record in records if len(split_skus(record["sku"])) != 1]
    return single, multi

def chunk_records(records, size=MAX_OUTPUT_ROWS):
    return [records[index:index + size] for index in range(0, len(records), size)]
```

将现有逐条写表代码提取为“写入一个记录分块”的私有方法；每个分块加载新模板。为每次转换创建批次文件夹；按“单 SKU 的所有份数、再多 SKU 的所有份数”依次生成 `01_单SKU_第1份_999条.xlsx` 等文件。保存前后执行 `control.checkpoint()`；任何取消或异常都删除本次已保存文件与批次文件夹。

- [ ] **Step 4: 运行转换器测试，确认通过**

Run: `D:\Python\python.exe -m unittest tests.test_file_paste_converter -v`

Expected: PASS。

- [ ] **Step 5: 提交**

Run: `git add modules/file_paste/converter.py tests/test_file_paste_converter.py; git commit -m "feat: split file paste outputs by sku kind"`

### Task 2: 多文件成品、命名和清理回归

**Files:**

- Modify: `tests/test_file_paste_converter.py`
- Modify: `modules/file_paste/converter.py:224-421`

**Interfaces:**

- Consumes: `split_records_by_sku_kind`、`chunk_records` 和多文件转换结果。
- Produces: 每个输出文件保留模板表头、分类内容和原有标记；`output_paths` 按文件名顺序排列。

- [ ] **Step 1: 写入失败测试**

```python
def test_converter_creates_separate_single_and_multi_sku_files(self):
    with patch("modules.file_paste.converter.MAX_OUTPUT_ROWS", 3):
        result = UploadConverter().convert(source_path, output_dir, open_after=False)
    self.assertEqual([Path(path).name for path in result["output_paths"]], [
        "01_单SKU_第1份_3条.xlsx",
        "02_单SKU_第2份_1条.xlsx",
        "03_多SKU_第1份_2条.xlsx",
    ])
    self.assertEqual(read_references(result["output_paths"][0]), ["ONE-1", "ONE-2", "ONE-3"])
    self.assertEqual(read_references(result["output_paths"][2]), ["MULTI-1", "MULTI-2"])
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `D:\Python\python.exe -m unittest tests.test_file_paste_converter.UploadConverterTest.test_converter_creates_separate_single_and_multi_sku_files -v`

Expected: FAIL，当前转换器只生成单个 Excel，也不返回 `output_paths`。

- [ ] **Step 3: 最小实现文件命名和整批清理**

```python
def output_file_name(sequence, label, part, count):
    return f"{sequence:02d}_{label}_第{part}份_{count}条.xlsx"

def cleanup_batch_output(batch_dir, paths):
    for path in paths:
        if path.exists():
            path.unlink()
    if batch_dir.exists() and not any(batch_dir.iterdir()):
        batch_dir.rmdir()
```

保存每个分块后记录路径；仅在所有分类和分块保存完毕时标记批次成功。取消测试必须在第一份文件保存后触发，验证文件夹和其中 Excel 都被删除。

- [ ] **Step 4: 运行转换器测试，确认通过**

Run: `D:\Python\python.exe -m unittest tests.test_file_paste_converter -v`

Expected: PASS。

- [ ] **Step 5: 提交**

Run: `git add modules/file_paste/converter.py tests/test_file_paste_converter.py; git commit -m "test: cover split file paste batch outputs"`

### Task 3: 界面结果和更新记录

**Files:**

- Modify: `ui/main_window.py:2243-2272`
- Modify: `data/changelog.json`
- Modify: `docs/CHANGELOG_FULL.md`
- Test: `tests/test_file_paste_progress.py`

**Interfaces:**

- Consumes: 转换器返回的 `output_dir`、`output_paths` 与 `file_count`。
- Produces: 成功提示展示输出文件夹、文件数量和文件清单；打开输出文件夹而非单个 Excel。

- [ ] **Step 1: 写入失败测试**

```python
def test_success_message_describes_output_folder_and_file_count(self):
    message = main_window.file_paste_success_message({
        "output_dir": "C:/temp/黑猫上传表_20260716_120000",
        "output_paths": ["a.xlsx", "b.xlsx"],
        "file_count": 2,
        "row_count": 1200,
        "source_type": "一件代发表格",
    })
    self.assertIn("生成文件：2 份", message)
    self.assertIn("输出文件夹：C:/temp/黑猫上传表_20260716_120000", message)
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `$env:QT_QPA_PLATFORM='offscreen'; D:\Python\python.exe -m unittest tests.test_file_paste_progress.FilePasteProgressTest.test_success_message_describes_output_folder_and_file_count -v`

Expected: FAIL，提示结果文字构造函数尚不存在。

- [ ] **Step 3: 最小实现界面展示与更新记录**

```python
def file_paste_success_message(result):
    names = "\n".join(f"- {Path(path).name}" for path in result["output_paths"])
    return f"黑猫上传表生成完成。\n生成文件：{result['file_count']} 份\n输出文件夹：{result['output_dir']}\n{names}"
```

成功后将结果框和处理记录保存为 `output_dir`，日志逐行列出文件名，提示说明“已打开输出文件夹”。在更新记录中写明 999 条上限、单/多 SKU 分文件和批次文件夹。

- [ ] **Step 4: 运行界面与更新记录测试，确认通过**

Run: `$env:QT_QPA_PLATFORM='offscreen'; D:\Python\python.exe -m unittest tests.test_file_paste_progress -v; D:\Python\python.exe -m py_compile ui/main_window.py`

Expected: PASS，编译退出码为 0。

- [ ] **Step 5: 提交**

Run: `git add ui/main_window.py tests/test_file_paste_progress.py data/changelog.json docs/CHANGELOG_FULL.md; git commit -m "feat: report split file paste outputs"`

### Task 4: 完整验证与打包自检

**Files:**

- Test: `tests/test_file_paste_converter.py`

- [ ] **Step 1: 运行完整测试和源码自检**

Run: `$env:QT_QPA_PLATFORM='offscreen'; D:\Python\python.exe -m unittest discover -s tests -v; D:\Python\python.exe app.py --self-test`

Expected: 全部通过，且没有半成品批次文件夹。

- [ ] **Step 2: 打包并运行 EXE 自检**

Run: `D:\Python\python.exe -m PyInstaller --noconfirm --clean --distpath dist\BlackCatAuditAssistant_SplitOutputTest --workpath build\SplitOutputTest BlackCatAuditAssistant.spec; dist\BlackCatAuditAssistant_SplitOutputTest\BlackCatAuditAssistant\BlackCatAuditAssistant.exe --self-test`

Expected: PyInstaller 和 EXE 自检退出码均为 0。

- [ ] **Step 3: 提交验证相关改动（若有）**

Run: `git status --short`

Expected: 没有未提交的源码、测试或更新记录改动。
