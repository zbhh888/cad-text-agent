# 修复 `import cv2` 的 ImportError

截图中的 Traceback 明确停在 `app.py` 的 `import cv2`，所以当前首要问题发生在 OpenCV 导入阶段，尚未运行到 PaddleOCR 推理。常见原因是 Streamlit Cloud 缺少 Linux 系统库（例如 libGL/libglib），或同时安装了不兼容/重复的 OpenCV wheel。

本包做两项修改：
- `requirements.txt`：删除 `opencv-python-headless`，改为 `opencv-contrib-python==4.10.0.84`，与 PaddleOCR 3.x/PaddleX 的依赖检查保持一致；固定 `numpy==1.26.4`，避免不必要的 NumPy/OpenCV 版本漂移。
- `packages.txt`：增加 `libgl1` 和 `libglib2.0-0`，供 Streamlit Cloud 安装系统动态库。

## 更新步骤
1. 解压本包。
2. 在 GitHub 仓库根目录，用本包中的 `app.py`、`requirements.txt`、`packages.txt` 分别覆盖同名文件。
3. Commit changes，等待 Streamlit 重新安装依赖。不要只改 app.py；依赖变更必须触发重新构建。
4. 重新打开网页，确认是否仍停在 `import cv2`。
5. 如果还是失败，进入 Manage app -> Logs，复制 ImportError 的完整底层信息（例如 `libGL.so.1`、`numpy.core...` 或 `cv2...`）。

注意：这只能针对当前 `cv2` 导入失败做修复尝试；它不能保证解决之前独立出现的 PaddlePaddle `Segmentation fault`。`cv2` 能导入后，再单独验证 PaddleOCR 推理。
