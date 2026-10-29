# CAD OCR 恢复版

此版本恢复到此前 EasyOCR 已识别出 A 和“工”、PaddleOCR 可识别“工”的单次 PaddleOCR 推理流程，撤销最近加入的多种图像变体连续推理逻辑，以排查 Paddle C++ Segmentation fault。保留 EasyOCR 的反色、留白和放大预处理，并确保 DXF 输入时显示“下载转换后的 DXF”按钮。

## 更新
只上传此包中的 app.py 到 GitHub 仓库根目录，覆盖现有 app.py 并提交。不要修改 requirements.txt 和 Python 3.11 设置。等待 Streamlit 自动重启。

## 测试顺序
1. 先选择 EasyOCR 测试 A 和“工”。
2. 再选择 PaddleOCR 测试，确认应用是否仍然崩溃。
3. 检查 DXF 上传后是否显示下载转换后的 DXF。
4. 下载后在 CAD 中检查 Text_Converted_Layer 和标准 TEXT/MTEXT 实体。

如果 PaddleOCR 仍出现 C++ Segmentation fault，说明可能是 PaddlePaddle/PaddleOCR 的二进制运行时兼容或底层推理问题，需要进一步固定兼容版本；不要在同一进程里继续尝试多次推理，因为原生段错误无法由 Python try/except 捕获。
