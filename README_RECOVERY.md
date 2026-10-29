# CAD OCR 应急稳定版（暂时停用 PaddleOCR）

原因：云端日志出现 PaddlePaddle C++ `FatalError: Segmentation fault`，这类原生崩溃不能由 Python try/except 捕获。为了先恢复应用，本版从界面移除 PaddleOCR 选项，并在代码中对 PaddleOCR 调用增加保护，避免进入崩溃推理路径。EasyOCR 和 Tesseract 仍可选择，DXF 转换代码保持不变。

## 更新步骤
1. 下载并解压。
2. 只把包里的 `app.py` 上传到 GitHub 仓库根目录，覆盖旧的 `app.py` 并 Commit changes。
3. 不要替换 requirements.txt；Python 3.11 保持不变。
4. 等 Streamlit 更新后刷新网页，先用 EasyOCR 测试。
5. 上传 DXF 后检查“下载转换后的 DXF”按钮并验证导出文件。

这只是应急恢复方案，不是 PaddleOCR 最终修复。待应用稳定后，再单独固定兼容的 PaddlePaddle/PaddleOCR 版本并重新启用。
