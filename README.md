# BlackCat Audit Assistant

黑猫审单助手是一个本地 Windows 工具，用于文件粘贴生成上传表、面单压缩、处理记录、数据统计和版本更新记录维护。

## Current Release

- Version: 4.2.0
- Installer: https://github.com/Super-hamburger/blackcat-audit-assistant/releases/download/v4.2.0/BlackCatAuditAssistant_Setup_4.2.0.zip
- Update manifest: https://super-hamburger.github.io/blackcat-audit-assistant/update_manifest.json

## 4.2.0 Highlights

- 将 4.1.7-test 转为正式发布版。
- 增强黑猫/Yamato 面单识别候选评分和置信度策略。
- 低置信度页面停止任务并输出待检查文件，避免错误命名。
- 生成 recognition_report.csv 便于人工复查。
- 保留 GitHub Pages update_manifest.json 远程更新发现能力。

## Safety

公开仓库不包含本机 logs、output、临时项目、临时安装目录或用户数据。发布包通过 GitHub Release 分发，其他电脑通过 update_manifest.json 检查新版本。
