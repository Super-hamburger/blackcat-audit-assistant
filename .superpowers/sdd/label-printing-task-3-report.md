# 面单打印任务 3 报告

## 完成内容

- 添加 `label_printing` 模块清单和注册入口。
- 入口会校验 `source_path`、`finished_path`、`pdf_paths` 与 `output_dir` 四类必填输入。
- 源码自测新增真实的一行原始表、一行成品表与一页 PDF 样例；仅在生成一页 `全部客户_合并_货架排序.pdf` 时通过。
- 保留既有文件粘贴与面单压缩自测逻辑不变。

## 验证结果

- `py -3.14 -m unittest tests.test_label_printing_processor tests.test_packaging_config -v`：16 项通过。
- `py -3.14 app.py --self-test --self-test-output self_test_label_printing_source.json`：通过；报告的所有检查均为 `ok: true`，包含 `run label_printing sample pdf`。
- 已删除临时自测 JSON 产物。
