# BlackCat Audit Assistant 5.0.0

发布日期：2026-07-18

## 发布说明

- 面单打印改为仅上传黑猫生成的 PDF；按客户、货架顺序，以及投函/宅急便合并或分开生成打印文件。
- 文件粘贴中，严格 SKU×1 的品名1（AB）写入 `LP[货架/客户编号]`；品名2（AD）保留原商品内容。
- SKU×N 和多 SKU 记录仍会写入完整成品表上传黑猫，但不会生成 LP 标记，打印时自动排除。

## 更新包

下载地址：`https://github.com/Super-hamburger/blackcat-audit-assistant/releases/download/v5.0.0/BlackCatAuditAssistant_Setup_5.0.0.zip`

SHA256：`c8f915a807672094401895c4c73666afb301e24446f5a2562593b895001b1660`

该更新包支持通过远程更新清单自动更新。
