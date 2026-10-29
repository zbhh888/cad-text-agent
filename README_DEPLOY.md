# CAD 图形化文字识别（按项目示例定向版）

## 本版本针对的目标
项目示例强调的不是只识别截图上的普通打印文字，而是识别 DXF 中由 `LINE`、`ARC`、`LWPOLYLINE`、`POLYLINE` 等图形实体拼成的字形，例如线段组成的英文字母 A、线段组成的中文字符。程序会把邻近实体聚类、渲染为位图，再交给 OCR 引擎识别，最后把结果写入 `Text_Converted_Layer`。

## 启动
```bash
python -m pip install -r requirements.txt
streamlit run app.py --server.port 8502
```
浏览器打开 `http://127.0.0.1:8502`。

## 试运行样例
上传 `sample_vector_glyphs.dxf`：
- 英文 A：由 3 条 LINE 实体组成；
- 中文“工”：由 3 条 LINE 实体组成；
- `STANDARD TEXT: A12`：标准 TEXT 对照项；
- 矩形轮廓：干扰项，用于观察是否误检为文字。

注意：此样例用来验证完整流程与候选区域，不保证启发式聚类会在所有图纸上准确把字符分开。识别效果取决于线段间距、图层、比例、字体和 OCR 模型。若图形文字识别为空或误识别，应查看检测结果和日志，再调整聚类阈值/渲染分辨率。

## 在线部署
1. 把此目录中的所有文件和文件夹上传到 GitHub 仓库根目录（保留 `.streamlit/config.toml`）。
2. 登录 https://share.streamlit.io/，选择仓库和 `app.py` 进行部署。
3. 只有部署成功后，平台才会提供真实的 `*.streamlit.app` 网址。

## 重要限制
- 此包没有被部署到公网，因此目前没有可直接访问的在线应用网址。
- PaddleOCR / PaddlePaddle 依赖较大，云端可能构建失败。若失败，先移除 requirements 中 `paddleocr`、`paddlepaddle`，使用 EasyOCR 或 RapidOCR。
- 云端部署会把图纸上传至托管服务器处理，请勿上传涉密图纸。
- 字符准确率、综合直通率、误报率和 5 秒性能指标必须用有标准答案的测试集实际测量。
- DWG 原生读取仍需额外配置有授权的 CAD 转换器。
