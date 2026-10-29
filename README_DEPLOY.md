# CAD 图形化文字识别系统 - 云端依赖修复版

## 修复说明
此版本移除了默认安装的 `easyocr`、`paddleocr` 和 `paddlepaddle`，以降低 Streamlit Cloud 构建时的依赖冲突和超时风险。默认 OCR 引擎为 Tesseract，系统包包括英文和简体中文语言包。

## 上传步骤
把此包中的文件更新到现有 GitHub 仓库根目录，覆盖 `app.py`、`requirements.txt`、`packages.txt`，保留 `.streamlit/config.toml` 和 `sample_vector_glyphs.dxf`。如果你想全量替换，可上传整个文件夹内容并覆盖同名文件。

## 部署
Streamlit Cloud 会检测仓库变更并重新构建。也可在 Manage app 中选择 Reboot app。

## 测试
部署成功后上传 `sample_vector_glyphs.dxf`，OCR 引擎选择 Tesseract，检查线段字形候选、置信度、复核标记以及转换 DXF 的 `Text_Converted_Layer`。

## 限制
这次修复优先让应用构建起来，并不保证所有图形化中文识别准确率达到项目验收指标。图形分组、渲染和 OCR 效果仍需使用真实标注图纸测试。云端上传文件会发送到托管服务器处理。
