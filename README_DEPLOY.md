# CAD 图形化文字识别 - PaddleOCR 与 DXF 转换修复版

此版本针对：
1. PaddleOCR 漏掉线段构成的独立字母 A：增加反色/灰度归一化、留白、放大和阈值化的多版本识别尝试，并显示内部异常。能改善识别机会，但不保证所有图形字形均识别正确。
2. 页面没有 DXF 下载按钮：当 `.dxf` 文件解析成功时，始终显示“下载转换后的 DXF”按钮。

## 更新方法
只需将此包中的 `app.py` 上传到 GitHub 仓库根目录覆盖原文件并 Commit changes。保留当前已经成功部署的 `requirements.txt`，本次不要更改依赖。等待 Streamlit 自动重启后重新上传 `sample_vector_glyphs.dxf`。

## 验收
- 选择 PaddleOCR，检查是否识别 A 和“工”。
- DXF 解析成功后应出现“下载转换后的 DXF”。
- 下载后用 CAD 打开，检查 `Text_Converted_Layer` 和标准 `TEXT/MTEXT` 实体。
- 按钮出现不等于转换验收通过，必须实际检查 DXF 文件。
