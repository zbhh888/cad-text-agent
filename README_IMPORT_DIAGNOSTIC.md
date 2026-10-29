# PaddleOCR 导入诊断版

当前网页显示“PaddleOCR未安装”，但代码原本会吞掉导入异常，所以这可能是包缺失，也可能是依赖冲突/动态库加载错误。此版本在侧栏显示实际导入异常与 PaddlePaddle 版本。

## 更新
1. 在 GitHub 仓库根目录只覆盖 app.py（本包中的 app.py）。
2. Commit changes，等待 Streamlit 更新。
3. 打开网页左侧模型状态区域，复制 PaddleOCR 导入失败下方的完整错误文字发给助手。
4. 同时在仓库 requirements.txt 确认存在以下三行：

```text
numpy>=1.24,<2.0
--extra-index-url https://www.paddlepaddle.org.cn/packages/stable/cpu/
paddlepaddle==3.2.0
paddleocr==3.5.0
```

不要只根据“Updated app!”判断依赖安装成功。若 requirements 已有这些行，先不要盲目更换版本；先拿到具体导入异常再定点修复。
