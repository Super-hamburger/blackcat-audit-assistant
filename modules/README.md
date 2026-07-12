# 模块开发规范

V4.1.0 起，业务功能优先放在 `modules/<module_id>/` 下，主程序只负责界面、参数收集、进度展示和调用模块。

## 目录格式

每个模块必须包含：

```text
modules/<module_id>/
  module.json
  module.py
  __init__.py
```

复杂功能可以继续拆文件，例如：

```text
modules/file_paste/
  module.py
  converter.py
  address_splitter.py
```

```text
modules/label_compress/
  module.py
  processor.py
  pdf_engine.py
  recognizer.py
  zip_engine.py
```

## module.json

`module.json` 用于注册模块：

```json
{
  "id": "module_id",
  "name_key": "module.module_id.name",
  "description_key": "module.module_id.description",
  "version": "4.1.0",
  "enabled": true,
  "category": "business"
}
```

`id` 必须与文件夹名一致。删除功能时，优先把 `enabled` 改为 `false`；确认不再使用后再删除目录。

## module.py

`module.py` 必须提供统一入口：

```python
from core.modules.module_contract import ModuleResult


def run(context):
    context = context or {}
    return ModuleResult(ok=True, message="Done", data={})
```

规范：

- `context` 是唯一输入，类型为 `dict`。
- 返回值必须是 `ModuleResult`，或者能被 `ModuleRegistry` 转换的 `dict`。
- 业务逻辑放在模块目录内部，不放到 `ui/`。
- `ui/` 只做文件选择、表单校验、日志展示、调用 `ModuleRegistry.run()`。
- 可复用基础能力可以放在 `core/`，但不能把具体业务流程放回 `core/`。

## 当前模块边界

`file_paste` 负责：

- Excel 格式识别。
- 地址拆分。
- 输出 Excel 的颜色标记。
- 输出文件生成。

`label_compress` 负责：

- PDF 拆分。
- 单号识别。
- 重复检测。
- ZIP 生成。

## 兼容策略

`core/upload_converter.py`、`core/processor.py`、`core/pdf_engine.py`、`core/recognizer.py`、`core/zip_engine.py`、`core/address_splitter.py` 只保留兼容导入。新功能不要继续在这些文件中增加业务逻辑。
