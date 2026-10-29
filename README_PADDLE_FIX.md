# CAD OCR PaddleOCR 版本兼容修复包

## 修复内容
- 恢复界面中的 PaddleOCR 选项。
- requirements.txt 固定 PaddlePaddle CPU 3.2.0 + PaddleOCR 3.5.0，避免依赖自动升级导致运行时组合漂移。官方 PaddleOCR 3.x 文档建议 PaddlePaddle 3.0+，安装文档提供 3.2.0 CPU 安装命令。
- 设置 CPU-only 和保守线程/禁用 oneDNN 环境变量，降低 Streamlit Cloud CPU 原生推理崩溃风险。
- 保留 EasyOCR、Tesseract 和 DXF 导出代码。
- 将 PaddleOCR 可捕获的 Python 异常显示到页面，方便继续诊断。

## 更新方法
1. 在 GitHub 仓库根目录，分别用本包里的 `app.py` 和 `requirements.txt` 覆盖原文件。
2. 提交 Commit changes。
3. Streamlit Cloud 会重新安装依赖。因为 requirements.txt 有 PaddlePaddle 新依赖，首次构建可能需要几分钟。
4. 等构建完成后，先刷新应用，先测试 EasyOCR，再测试 PaddleOCR。
5. 如果 PaddleOCR 仍然引发 `FatalError: Segmentation fault`，请不要反复调用它；收集新的构建日志和 Python/Paddle 版本，进一步定位底层环境。Segmentation fault 是原生进程崩溃，不能由 Python try/except 捕获。

## 版本核对
- Python: 3.11（Streamlit 设置中保持 3.11）
- PaddlePaddle: 3.2.0 CPU
- PaddleOCR: 3.5.0
