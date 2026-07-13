# 文件粘贴功能重建 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** 从两种原始 Excel 表稳定生成与“改1”样表完全同表头的黑猫上传表，并正确处理日本地址、SKU 数量和一件代发货架排序。

**Architecture:** 在 modules/file_paste 内拆出模板加载、地址拆分、数量解析和转换写入四个职责。界面仍通过既有模块入口调用转换器，只增加结果汇总和问题提示。成品表从内置的可用样表模板复制，避免在代码中手写或遗漏 98 列表头。

**Tech Stack:** Python 3、openpyxl、PySide6、unittest、PyInstaller。

## Global Constraints

- 以 0713-黑猫宅急便模版（泉南仓库）(100) (改1).xlsx 的表头、列数、列顺序为唯一输出标准。
- 只识别黑猫新版和一件代发两种原始表，按表头判断，不按文件名判断。
- L/M/N/O 地址长度分别为 12/16/25/25 全角字符；地址超长不阻止生成，尾部全部保留在 O 并标记。
- 地址按日本行政区、町名、丁目、番地、号、楼名、房号的自然边界拆分，不能在 3丁目、1-2-3、101号室 或楼名中间强拆。
- 黑猫新版：AB=sku，AD=明细；一件代发：AB=货架，AD 为 SKU 与数量合并结果。
- 一件代发单货架升序排序；多货架订单维持原顺序并置底。
- 保留文件粘贴以外的 4.4.1-test 功能，不发布给其它电脑，不改版本号或远程更新清单。
- 每次功能改动同步更新 data/changelog.json 与 docs/CHANGELOG_FULL.md。

---

### Task 1: 加入黑猫成品模板和模板加载器

**Files:**
- Create: assets/templates/blackcat_upload_template.xlsx
- Create: modules/file_paste/template.py
- Create: tests/test_file_paste_template.py
- Modify: BlackCatAuditAssistant.spec

**Interfaces:**
- Consumes: 已确认的“改1”成品表第一行和固定发件字段。
- Produces: load_upload_template() -> tuple[Workbook, Worksheet]，返回包含精确 98 列表头、列宽和基础样式的可写工作簿。

- [ ] **Step 1: 制作不含客户数据的内置模板**

从用户提供的“改1”成品表复制第一行的 98 列表头、列宽、冻结窗格和基础样式；仅保留第二行中固定发件字段的值和样式，清空订单号、收件人、电话、邮编、L:O 地址、AB 和 AD。保存为 assets/templates/blackcat_upload_template.xlsx。

- [ ] **Step 2: 写出先失败的模板测试**

在 tests/test_file_paste_template.py 写入：

~~~
from modules.file_paste.template import load_upload_template


def test_upload_template_has_the_exact_blackcat_layout():
    workbook, sheet = load_upload_template()

    assert sheet.max_column == 98
    assert sheet["A1"].value == "お客様管理番号(内部ID)"
    assert sheet["AB1"].value == "品名１(明细半角50字符以内)"
    assert sheet["AD1"].value == "品名２(明细超过半角50字符部分放这列，这列也最多50字符)"
    assert sheet.freeze_panes == "A2"
~~~

- [ ] **Step 3: 运行模板测试确认失败**

Run: D:Pythonpython.exe -m unittest tests.test_file_paste_template -v

Expected: FAIL，提示 modules.file_paste.template 尚不存在。

- [ ] **Step 4: 实现模板加载器并让打包包含模板**

在 modules/file_paste/template.py 实现以下接口；打包环境使用 _MEIPASS，源码环境使用项目根目录：

~~~
from pathlib import Path
import sys
from openpyxl import load_workbook


def template_path() -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return root / "assets" / "templates" / "blackcat_upload_template.xlsx"


def load_upload_template():
    workbook = load_workbook(template_path())
    return workbook, workbook.worksheets[0]
~~~

BlackCatAuditAssistant.spec 已收集整个 assets 目录；确认这个逻辑保持不变，使新模板自动进入 EXE。

- [ ] **Step 5: 运行模板测试确认通过**

Run: D:Pythonpython.exe -m unittest tests.test_file_paste_template -v

Expected: PASS，工作表为 98 列且关键表头位置不变。

- [ ] **Step 6: 提交模板任务**

~~~
git add assets/templates/blackcat_upload_template.xlsx modules/file_paste/template.py tests/test_file_paste_template.py BlackCatAuditAssistant.spec
git commit -m "feat: add canonical Black Cat upload template"
~~~

### Task 2: 重写日本地址智能拆分器

**Files:**
- Modify: modules/file_paste/address_splitter.py
- Create: tests/test_file_paste_address_splitter.py

**Interfaces:**
- Consumes: 一条已合并的收件地址字符串。
- Produces: split_japanese_address(address: str) -> dict[str, object]，其中含 L、M、N、O、overflow、was_split。

- [ ] **Step 1: 写出地址语义和超长的失败测试**

~~~
from modules.file_paste.address_splitter import display_width, split_japanese_address


def test_japanese_address_keeps_block_and_room_tokens_intact():
    parts = split_japanese_address(
        "東京都世田谷区北沢二丁目24-5-101 サンライズマンション 101号室"
    )

    all_parts = "".join(parts[key] for key in "LMNO")
    assert "二丁目" in all_parts
    assert "24-5-101" in all_parts
    assert "101号室" in all_parts
    assert display_width(parts["L"]) <= 12
    assert display_width(parts["M"]) <= 16
    assert display_width(parts["N"]) <= 25


def test_address_overflow_is_preserved_in_o_and_marked():
    address = "東京都港区芝公園一丁目1-2-3 " + "VeryLongBuildingName " * 8 + "101号室"
    parts = split_japanese_address(address)

    assert parts["overflow"] is True
    assert parts["O"].endswith("101号室")
~~~

- [ ] **Step 2: 运行地址测试确认失败**

Run: D:Pythonpython.exe -m unittest tests.test_file_paste_address_splitter -v

Expected: FAIL，提示 split_japanese_address 尚不存在。

- [ ] **Step 3: 实现自然边界分词和四列分配**

在 address_splitter.py 用现有的全半角宽度计算，新增：

~~~
ADDRESS_LIMITS = (12, 16, 25, 25)


def split_japanese_address(address: str) -> dict[str, object]:
    tokens = tokenize_japanese_address(compact_spaces(address))
    values = allocate_tokens(tokens, ADDRESS_LIMITS)
    return {
        "L": values[0], "M": values[1], "N": values[2], "O": values[3],
        "overflow": display_width(values[3]) > ADDRESS_LIMITS[3],
        "was_split": any(values[index] for index in range(1, 4)),
    }
~~~

tokenize_japanese_address 必须把都道府县、市区町村、町名、丁目、番地、连字符数字块、号、楼名、号室作为不可从中间切断的优先单元。allocate_tokens 先将完整单元放进当前列；单个楼名大于当前列限制时，仅可在空格、连字符或字符宽度边界处分开；第四列放入所有剩余文本，绝不截断。

- [ ] **Step 4: 运行地址测试确认通过**

Run: D:Pythonpython.exe -m unittest tests.test_file_paste_address_splitter -v

Expected: PASS，L/M/N 未超限，O 能保留全部超长尾部并返回 overflow=True。

- [ ] **Step 5: 提交地址任务**

~~~
git add modules/file_paste/address_splitter.py tests/test_file_paste_address_splitter.py
git commit -m "feat: split Japanese addresses by semantic boundaries"
~~~

### Task 3: 以新规则重建转换器

**Files:**
- Modify: modules/file_paste/converter.py
- Modify: tests/test_file_paste_converter.py

**Interfaces:**
- Consumes: UploadConverter.convert(source_path, output_dir, open_after=False)。
- Produces: 成品路径和包含 row_count、source_type、split_count、address_overflow_count、quantity_issue_count、quantity_issue_orders 的结果字典。

- [ ] **Step 1: 用两类来源和货架排序写出失败测试**

替换旧的“货位别名、旧地址颜色、投函/宅急便”测试。先在 UploadConverterTest 中增加两个测试辅助方法：convert_and_load_one_piece(rows) 使用完整一件代表表头创建临时文件并调用现有 convert_and_load；convert_and_load_blackcat(row) 使用完整黑猫新版表头创建临时文件并调用现有 convert_and_load。新增核心断言：

~~~
def test_one_piece_merges_each_sku_with_its_quantity_and_sorts_shelves():
    result, sheet = convert_and_load_one_piece([
        {"参考单号": "MULTI", "SKU": "sku-a,sku-b", "数量": "*1+*1", "货架": "13-6-3-2"},
        {"参考单号": "EARLY", "SKU": "sku-c", "数量": 1, "货架": "13-3-3-2"},
        {"参考单号": "BOTTOM", "SKU": "sku-d", "数量": 1, "货架": "16-1-1-3,13-6-3-3"},
    ])

    assert [sheet[f"A{row}"].value for row in range(2, 5)] == ["EARLY", "MULTI", "BOTTOM"]
    assert sheet["AB2"].value == "13-3-3-2"
    assert sheet["AD3"].value == "sku-a*1,sku-b*1"
    assert result["quantity_issue_count"] == 0


def test_blackcat_uses_sku_in_ab_detail_in_ad_and_exact_template_header():
    result, sheet = convert_and_load_blackcat({"单号": "NB-1", "sku": "sku-a", "明细": "*3"})

    assert sheet.max_column == 98
    assert sheet["A1"].value == "お客様管理番号(内部ID)"
    assert sheet["A2"].value == "NB-1"
    assert sheet["AB2"].value == "sku-a"
    assert sheet["AD2"].value == "*3"
~~~

再补一个多 SKU 总数无法分配的测试：输出保留该订单行、AD 为空并标红、quantity_issue_orders == ["AMBIGUOUS"]。

- [ ] **Step 2: 运行转换器测试确认失败**

Run: D:Pythonpython.exe -m unittest tests.test_file_paste_converter -v

Expected: FAIL，现有转换器仍只创建 42 列、把一件代发强制写成 SKU*1，且没有新结果字段。

- [ ] **Step 3: 实现来源读取、数量解析、排序和模板写入**

在 converter.py 删除旧的手写 OUTPUT_HEADERS、旧地址分支和旧运输方式映射；只保留通用的表头标准化、文本写入和安全输出目录逻辑。加入：

~~~
def resolve_sku_quantities(sku_text: str, quantity_value) -> tuple[str, str | None]:
    """Return AD text and an optional unresolved-quantity reason."""


def shelf_sort_key(shelf: str) -> tuple:
    """Sort one shelf by hyphen-delimited numeric/letter segments; multi-shelf is last."""


def write_output_row(sheet, row_index: int, record: dict, address: dict, item_text: str) -> None:
    """Overwrite dynamic cells on a copied template row and preserve template defaults."""
~~~

映射必须为：两种来源的订单号写 A、电话写 I、邮编写 K、地址写 L:O、收件人写 P；黑猫新版 sku 写 AB 且 明细 写 AD；一件代表 货架 写 AB 且 SKU/数量合并值写 AD。对一件代表仅排序单货架行，多个货架行按输入顺序追加到底部。对地址 overflow=True 的 O 填红色；对数量无法确定的 AD 填红色并返回问题订单号。所有动态单元格写字符串，防止电话和邮编被转为数字。

- [ ] **Step 4: 运行转换器测试确认通过**

Run: D:Pythonpython.exe -m unittest tests.test_file_paste_converter -v

Expected: PASS，两个来源均生成 98 列模板输出，SKU、数量、货架、地址和排序断言全部通过。

- [ ] **Step 5: 用用户样表做对比验证**

Run: D:Pythonpython.exe -m unittest tests.test_file_paste_template tests.test_file_paste_address_splitter tests.test_file_paste_converter -v

Expected: PASS。随后用 0713-黑猫新版(100).xlsx 和 202607137740一件代发.xlsx 各生成一次输出，检查两份输出均有 98 列、第一行与内置模板一致，且一件代表多货架行位于文件底部。

- [ ] **Step 6: 提交转换器任务**

~~~
git add modules/file_paste/converter.py tests/test_file_paste_converter.py
git commit -m "feat: rebuild Black Cat file paste conversion"
~~~

### Task 4: 更新界面结果、自测和更新日志

**Files:**
- Modify: ui/main_window.py:1930-1972
- Modify: app.py:107-151
- Modify: data/changelog.json
- Modify: docs/CHANGELOG_FULL.md

**Interfaces:**
- Consumes: 转换器新增的 address_overflow_count、quantity_issue_count、quantity_issue_orders。
- Produces: 界面日志、完成弹窗和自测报告中的清晰问题数量。

- [ ] **Step 1: 写出模块返回结果的失败测试**

在 tests/test_file_paste_converter.py 增加：

~~~
def test_converter_reports_address_overflow_and_quantity_issues():
    result, _ = convert_and_load_one_piece([
        {"参考单号": "LONG", "SKU": "sku-long", "数量": 1, "货架": "1-1", "地址": LONG_ADDRESS},
        {"参考单号": "AMBIGUOUS", "SKU": "sku-a,sku-b", "数量": 5, "货架": "1-2"},
    ])

    assert result["address_overflow_count"] == 1
    assert result["quantity_issue_count"] == 1
    assert result["quantity_issue_orders"] == ["AMBIGUOUS"]
~~~

- [ ] **Step 2: 运行结果测试确认失败**

Run: D:Pythonpython.exe -m unittest tests.test_file_paste_converter.UploadConverterTest.test_converter_reports_address_overflow_and_quantity_issues -v

Expected: FAIL，旧结果字典没有新字段。

- [ ] **Step 3: 最小范围更新界面和自测样本**

在 ui/main_window.py 的成功日志和完成弹窗增加两行：地址超长并已放入 O 列：N 行、SKU 数量待确认：N 行；当待确认订单非空时，日志显示订单号列表。不要改动文件选择、输出目录、历史记录或其它页面。

在 app.py 的一件代发自测样本中加入 货架 和 数量 字段，并断言返回结果的 row_count == 1、address_overflow_count == 0、quantity_issue_count == 0。

在两份更新日志的 V4.4.1-test 条目下，替换旧文件粘贴说明为：两种表格重建、98 列模板、日本地址智能拆分和 O 列超长标记、一件代发 SKU/数量和货架排序。保留扫码验单和更新检查的原有 4.4.1 内容。

- [ ] **Step 4: 运行结果和自测前置检查**

Run: D:Pythonpython.exe -m unittest tests.test_file_paste_converter -v

Expected: PASS，新增统计字段准确返回。

Run: D:Pythonpython.exe -m json.tool datachangelog.json > $null

Expected: exit code 0。

- [ ] **Step 5: 提交界面、自测和日志任务**

~~~
git add ui/main_window.py app.py data/changelog.json docs/CHANGELOG_FULL.md tests/test_file_paste_converter.py
git commit -m "feat: report file paste address and quantity issues"
~~~

### Task 5: 打包、完整验证并启动手测版

**Files:**
- Modify: dist/BlackCatAuditAssistant/（仅构建产物，不提交）
- Create: self_test_4_4_1_file_paste_rebuild_exe.json（自测报告，不提交）

**Interfaces:**
- Consumes: 已通过的源码测试和 installer/build_portable.bat。
- Produces: 可运行的便携版 dist/BlackCatAuditAssistant/BlackCatAuditAssistant.exe。

- [ ] **Step 1: 运行完整源码测试和静态检查**

Run: D:Pythonpython.exe -m unittest discover -s tests -v

Expected: PASS。

Run: D:Pythonpython.exe -m compileall -q app.py core modules ui

Expected: exit code 0。

- [ ] **Step 2: 构建便携测试版**

Run: cmd /c installeruild_portable.bat

Expected: exit code 0，并生成 distBlackCatAuditAssistantBlackCatAuditAssistant.exe。assets/templates/blackcat_upload_template.xlsx 必须存在于打包目录中。

- [ ] **Step 3: 运行打包 EXE 自测**

Run: distBlackCatAuditAssistantBlackCatAuditAssistant.exe --self-test --self-test-output self_test_4_4_1_file_paste_rebuild_exe.json

Expected: exit code 0；报告中 import fitz、import pymupdf、import openpyxl、run file_paste sample workbook、run label_compress sample pdf 均为 ok: true。

- [ ] **Step 4: 检查用户样表的打包输出**

用打包 EXE 或对应模块对两份用户样表生成文件，检查：第一行与内置模板完全一致、输出为 98 列、地址超长只标记 O、黑猫新版 AB/AD 映射正确、一件代发 AB/AD 和货架排序正确。

- [ ] **Step 5: 启动软件交付手动测试**

Run: Start-Process -FilePath "$PWDdistBlackCatAuditAssistantBlackCatAuditAssistant.exe" -WorkingDirectory "$PWDdistBlackCatAuditAssistant"

Expected: 软件启动，用户可自行导入两种原始表完成手测。

- [ ] **Step 6: 提交源码和文档变更，不提交构建产物**

~~~
git status --short
git add modules/file_paste ui/main_window.py app.py data/changelog.json docs/CHANGELOG_FULL.md tests BlackCatAuditAssistant.spec
git commit -m "feat: complete rebuilt file paste workflow"
~~~

## 自检结果

- 规格覆盖：模板表头、两种原始表、地址拆分和超长处理、SKU 数量、货架排序、UI 提示、更新日志、源码测试、打包 EXE 自测和手动交付均有对应任务。
- 占位检查：本计划不含未定义的后续工作；每个改动任务均给出了文件、接口、失败测试、实现要求、通过命令和提交范围。
- 接口一致性：Task 2 定义的 split_japanese_address 被 Task 3 消费；Task 3 定义的结果字典字段被 Task 4 消费；Task 5 验证 Task 1 到 Task 4 的全部产物。
