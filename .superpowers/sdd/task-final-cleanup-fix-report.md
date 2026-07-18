# PDF-only 清理异常安全修复报告

## 范围

仅在试验副本修复 `modules/label_printing/processor.py` 的 `_remove_created_files`：单个已创建输出文件删除失败时，继续尝试删除剩余文件，并避免覆盖处理器原始异常。

## TDD 证据

- 红：新增 `test_cleanup_continues_after_one_created_file_cannot_be_deleted`，将第一个 `Path.unlink` 设为抛出 `OSError`。修复前定向测试以该 `OSError` 失败，第二个路径未被调用。
- 绿：每次 `unlink` 单独捕获 `OSError` 后，运行 `py -3.14 -m unittest tests.test_label_printing_processor -v`，13 项测试全部通过。

## 变更与检查

- `_remove_created_files` 对每个路径独立处理删除异常，保留调用方的原始处理异常重抛流程。
- 已运行 `git diff --check -- modules/label_printing/processor.py tests/test_label_printing_processor.py .superpowers/sdd/task-final-cleanup-fix-report.md`，未报告空白错误。

## 顾虑

删除失败的文件仍可能留在磁盘；这是刻意保留的最佳努力清理行为，不能让清理失败掩盖原始的 PDF 处理异常。
