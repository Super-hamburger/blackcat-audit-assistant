# Codex 工作准则

1. 采用 Karpathy Principles 编程原则。
2. 代码里面使用英文，解释说明使用中文。
3. 不能泄露、打印、提交或暴露任何密码、密钥、令牌或敏感凭证。需要使用时提前询问。
4. 每次新增、删除或修改功能，都必须同步更新 `data/changelog.json` 和 `docs/CHANGELOG_FULL.md`。
5. 每次发布新版本，都必须同步更新 `version.json`、`APP_VERSION`、`updater/update_manifest.example.json` 和发布包名称。
6. 业务功能优先放在 `modules/`，主界面只负责收集参数、展示结果和调用模块。
7. 默认只做本机测试版更新；只有用户明确说“发布新版本”时，才更新给其他电脑使用的发布包和远程更新清单。
8. 每次打包后必须验证核心依赖和核心功能入口：`fitz`/PyMuPDF、`openpyxl`、`file_paste`、`label_compress`。不能只验证窗口能打开。
9. 每次交给用户测试前，必须先运行源码静态检查、JSON 校验和打包 EXE 的 `--self-test`，确认自测报告通过。
10. 调整功能前先复制临时项目，在临时项目里修改、测试、打包；不要直接影响现成正式软件。
