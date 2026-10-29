from __future__ import annotations

import io
import inspect
import json
import math
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import streamlit as st

try:
    import ezdxf
except Exception:
    ezdxf = None

try:
    import pytesseract
    from pytesseract import Output
except Exception:
    pytesseract = None
    Output = None

try:
    import easyocr
except Exception:
    easyocr = None

try:
    from paddleocr import PaddleOCR
except Exception:
    PaddleOCR = None


@dataclass
class TextRegion:
    id: str
    text: str
    confidence: float
    needs_review: bool
    bbox_world: dict
    rotation: float
    source_types: list[str]
    source_entity_handles: list[str]
    source_layer: str
    target_layer: str = "Text_Converted_Layer"
    ocr_engine: str = "pytesseract-offline"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def image_regions(image: np.ndarray, threshold: float = 0.55, engine: str = "Tesseract") -> tuple[list[TextRegion], np.ndarray]:
    """Detect likely text components and OCR them in local/offline mode."""
    if image is None:
        return [], image
    display = image.copy()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Adaptive threshold handles dark CAD backgrounds and uneven scans.
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY_INV, 31, 9)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(bw, 8)
    regions: list[TextRegion] = []
    h, w = gray.shape
    for i in range(1, n):
        x, y, ww, hh, area = stats[i]
        if area < 20 or ww < 8 or hh < 8 or ww > w * 0.9 or hh > h * 0.4:
            continue
        # Merge/ignore long dimension lines; text candidates have bounded aspect.
        aspect = ww / max(hh, 1)
        if aspect > 25 and hh < 14:
            continue
        crop = image[max(0, y-3):min(h, y+hh+3), max(0, x-3):min(w, x+ww+3)]
        text, conf = ocr_crop(crop, engine)
        if not text.strip():
            continue
        c = max(0.0, min(1.0, conf))
        region = TextRegion(
            id=f"text-{len(regions)+1:06d}", text=text.strip(), confidence=c,
            needs_review=c < threshold,
            bbox_world={"min_x": float(x), "min_y": float(h-y-hh), "max_x": float(x+ww), "max_y": float(h-y)},
            rotation=0.0, source_types=["RASTER_COMPONENT"], source_entity_handles=[], source_layer="IMAGE", ocr_engine=engine,
        )
        regions.append(region)
        color = (0, 0, 255) if region.needs_review else (0, 190, 80)
        cv2.rectangle(display, (x, y), (x+ww, y+hh), color, 2)
        cv2.putText(display, region.text[:20], (x, max(18, y-5)), cv2.FONT_HERSHEY_SIMPLEX, .5, color, 1, cv2.LINE_AA)
    return regions, display


@st.cache_resource(show_spinner=False)
def get_easy_reader():
    return easyocr.Reader(["ch_sim", "en"], gpu=False, verbose=False) if easyocr else None

@st.cache_resource(show_spinner=False)
def get_paddle_reader():
    if PaddleOCR is None:
        return None
    parameters = inspect.signature(PaddleOCR).parameters
    options: dict[str, object] = {"lang": "ch"}
    if "use_textline_orientation" in parameters:
        options["use_textline_orientation"] = True
    else:
        options["use_angle_cls"] = True
        if "show_log" in parameters:
            options["show_log"] = False
    return PaddleOCR(**options)

def ocr_crop(crop: np.ndarray, engine: str = "Tesseract") -> tuple[str, float]:
    if engine == "EasyOCR":
        reader = get_easy_reader()
        if reader is None:
            return "[EasyOCR未安装：请检查 requirements.txt 和部署日志]", 0.0
        try:
            # Vector glyphs are rendered as white strokes on a black canvas.
            # EasyOCR works more reliably with dark strokes on a light background.
            work = crop.copy()
            if work.ndim == 2:
                work = cv2.cvtColor(work, cv2.COLOR_GRAY2BGR)
            gray = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)
            # Normalize polarity: use white background with black strokes.
            if float(np.mean(gray)) < 127:
                gray = cv2.bitwise_not(gray)
            # Add generous white padding and enlarge small CAD glyphs.
            gray = cv2.copyMakeBorder(gray, 18, 18, 24, 24, cv2.BORDER_CONSTANT, value=255)
            target_h = max(96, min(256, gray.shape[0] * 4))
            scale = target_h / max(1, gray.shape[0])
            gray = cv2.resize(gray, (max(1, int(gray.shape[1] * scale)), target_h),
                              interpolation=cv2.INTER_CUBIC)
            # EasyOCR accepts a grayscale numpy image. paragraph=False preserves per-box results.
            result = reader.readtext(gray, detail=1, paragraph=False,
                                     text_threshold=0.25, low_text=0.15,
                                     link_threshold=0.2, mag_ratio=2.0)
            texts = [str(x[1]).strip() for x in result if len(x) >= 3 and str(x[1]).strip()]
            scores = [float(x[2]) for x in result if len(x) >= 3 and str(x[1]).strip()]
            return " ".join(texts), float(np.mean(scores)) if scores else 0.0
        except Exception as exc:
            # Keep the reason visible instead of silently turning every failure into an empty result.
            return f"[EasyOCR错误：{type(exc).__name__}: {exc}]", 0.0
    if engine == "PaddleOCR":
        reader = get_paddle_reader()
        if reader is None:
            return "[PaddleOCR未安装：请检查 requirements.txt 和部署日志]", 0.0

        def parse_paddle(result):
            """Normalize PaddleOCR 2.x/3.x result formats to [(text, score_or_none)]."""

            def as_payload(value):
                if callable(value):
                    try:
                        value = value()
                    except Exception:
                        return None
                if isinstance(value, (str, bytes)):
                    try:
                        value = json.loads(value)
                    except Exception:
                        return None
                return value

            def normalize_score(value):
                try:
                    score = float(value)
                except (TypeError, ValueError):
                    return None
                if not np.isfinite(score) or score < 0:
                    return None
                # Some wrappers expose confidence as 0..100 rather than 0..1.
                if 1.0 < score <= 100.0:
                    score /= 100.0
                if 0.0 <= score <= 1.0:
                    return score
                return None

            pairs = []
            pages = result if isinstance(result, (list, tuple)) else [result]
            for page in pages:
                payload = page if isinstance(page, dict) else getattr(page, "json", None)
                payload = as_payload(payload)

                if payload is None and not isinstance(page, (list, tuple, dict)):
                    # Some PaddleOCR result wrappers expose result data as attributes.
                    payload = {}
                    for key in ("res", "rec_texts", "rec_scores", "text", "score"):
                        try:
                            value = getattr(page, key)
                        except Exception:
                            continue
                        if value is not None:
                            payload[key] = value

                if isinstance(payload, dict):
                    payload = payload.get("res", payload)
                    payload = as_payload(payload)
                    if isinstance(payload, dict):
                        texts = payload.get("rec_texts")
                        scores = payload.get("rec_scores")
                        # Support alternative field names used by some wrappers.
                        if texts is None:
                            texts = payload.get("texts", payload.get("text", []))
                        if scores is None:
                            scores = payload.get(
                                "text_rec_score",
                                payload.get("scores", payload.get("score", []))
                            )

                        if hasattr(texts, "tolist"):
                            texts = texts.tolist()
                        if hasattr(scores, "tolist"):
                            scores = scores.tolist()
                        if texts is None:
                            texts = []
                        if not isinstance(texts, (list, tuple)):
                            texts = [texts]
                        if scores is None:
                            scores = []
                        if not isinstance(scores, (list, tuple)):
                            scores = [scores]

                        # A single nested score can arrive as [[0.98]].
                        flattened_scores = []
                        for item in scores:
                            if hasattr(item, "tolist"):
                                item = item.tolist()
                            while isinstance(item, (list, tuple)) and len(item) == 1:
                                item = item[0]
                            flattened_scores.append(item)

                        for i, text in enumerate(texts):
                            text = str(text).strip()
                            if not text:
                                continue
                            score = normalize_score(flattened_scores[i]) if i < len(flattened_scores) else None
                            pairs.append((text, score))
                        continue

                # PaddleOCR 2.x output: [[box, (text, score)], ...]
                if isinstance(page, (list, tuple)):
                    for line in page:
                        if (
                            isinstance(line, (list, tuple)) and len(line) >= 2
                            and isinstance(line[1], (list, tuple)) and len(line[1]) >= 2
                        ):
                            text = str(line[1][0]).strip()
                            if text:
                                pairs.append((text, normalize_score(line[1][1])))
            return pairs

        try:
            # OCR-friendly preprocessing for isolated CAD vector glyphs, e.g. outlined A.
            base = crop.copy()
            if base.ndim == 2:
                base = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)
            gray = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY)
            if float(np.mean(gray)) < 127:
                gray = cv2.bitwise_not(gray)
            gray = cv2.copyMakeBorder(
                gray, 24, 24, 24, 24, cv2.BORDER_CONSTANT, value=255
            )
            target_h = max(128, min(320, gray.shape[0] * 4))
            scale = target_h / max(1, gray.shape[0])
            gray = cv2.resize(
                gray, (max(1, int(gray.shape[1] * scale)), target_h),
                interpolation=cv2.INTER_CUBIC
            )
            variants = [
                gray,
                cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            ]
            best, errors = [], []

            for variant in variants:
                try:
                    if hasattr(reader, "predict"):
                        raw_result = reader.predict(variant)
                    else:
                        raw_result = reader.ocr(
                            cv2.cvtColor(variant, cv2.COLOR_GRAY2BGR), cls=True
                        )
                    pairs = parse_paddle(raw_result)
                    if not pairs:
                        continue

                    valid_scores = [
                        score for _, score in pairs
                        if score is not None and np.isfinite(score)
                        and 0.0 <= score <= 1.0
                    ]
                    best_scores = [
                        score for _, score in best
                        if score is not None and np.isfinite(score)
                        and 0.0 <= score <= 1.0
                    ]

                    # Prefer results with usable confidence scores, otherwise retain text.
                    if (
                        not best
                        or (valid_scores and not best_scores)
                        or (
                            valid_scores and best_scores
                            and float(np.mean(valid_scores)) > float(np.mean(best_scores))
                        )
                    ):
                        best = pairs
                except Exception as exc:
                    errors.append(f"{type(exc).__name__}: {exc}")

            if best:
                recognized_text = " ".join(text for text, _ in best)
                valid_scores = [
                    score for _, score in best
                    if score is not None and np.isfinite(score)
                    and 0.0 <= score <= 1.0
                ]
                # Keep the app's existing numeric API safe. A displayed 0.0 means
                # "no valid score returned" unless the UI separately reports that state.
                confidence = float(np.mean(valid_scores)) if valid_scores else 0.0
                if not valid_scores:
                    # Keep existing return type compatible; tell the user this is missing data,
                    # not a measured confidence of zero.
                    st.caption("PaddleOCR 已返回文字，但当前结果中未读取到有效置信度分数；显示的 0% 不应视为真实模型置信度。")
                return recognized_text, confidence

            if errors:
                return f"[PaddleOCR错误：{errors[0]}]", 0.0
            return "", 0.0
        except Exception as exc:
            return f"[PaddleOCR错误：{type(exc).__name__}: {exc}]", 0.0
    if pytesseract is None:
        return "[Tesseract未安装]", 0.0
    try:
        scale = 3
        up = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)
        data = pytesseract.image_to_data(gray, config="--psm 7", output_type=Output.DICT, lang="eng")
        words, confs = [], []
        for txt, conf in zip(data.get("text", []), data.get("conf", [])):
            if txt.strip() and float(conf) >= 0:
                words.append(txt.strip()); confs.append(float(conf) / 100)
        return " ".join(words), float(np.mean(confs)) if confs else 0.0
    except Exception:
        return "", 0.0


def dxf_regions(raw: bytes, threshold: float = .55, engine: str = "Tesseract") -> tuple[list[TextRegion], object, str]:
    if ezdxf is None:
        raise RuntimeError("未安装 ezdxf，无法处理 DXF。请执行 pip install -r requirements.txt")
    # ezdxf.read expects a text stream for ASCII DXF. UploadedFile returns bytes,
    # so decode explicitly and keep a tolerant fallback for legacy encodings.
    try:
        text_stream = io.StringIO(raw.decode("utf-8-sig"))
    except UnicodeDecodeError:
        text_stream = io.StringIO(raw.decode("gb18030", errors="replace"))
    doc = ezdxf.read(text_stream)
    msp = doc.modelspace()
    regions: list[TextRegion] = []
    # Extract existing standard text for traceability.
    for entity in msp:
        typ = entity.dxftype()
        if typ not in {"TEXT", "MTEXT"}:
            continue
        text = entity.dxf.text if typ == "TEXT" else entity.text
        ins = entity.dxf.insert
        h = float(getattr(entity.dxf, "height", 2.5))
        width = max(h * max(len(text), 1) * .6, h)
        region = TextRegion(
            id=f"text-{len(regions)+1:06d}", text=text, confidence=1.0, needs_review=False,
            bbox_world={"min_x": float(ins.x), "min_y": float(ins.y), "max_x": float(ins.x+width), "max_y": float(ins.y+h)},
            rotation=float(getattr(entity.dxf, "rotation", 0.0)), source_types=[typ],
            source_entity_handles=[entity.dxf.handle], source_layer=entity.dxf.layer,
        )
        regions.append(region)
    # Detect non-standard vector text made from lines/arcs/polylines.
    regions.extend(vector_dxf_regions(msp, threshold, engine))
    return regions, doc, f"DXF已处理：包含标准TEXT/MTEXT与图形化线段文字识别（{engine}）。"


def vector_dxf_regions(msp, threshold: float = .55, engine: str = "Tesseract") -> list[TextRegion]:
    """Rasterize connected vector glyph groups, then OCR each group."""
    items = []
    for e in msp:
        typ = e.dxftype()
        if typ in {"TEXT", "MTEXT", "INSERT", "DIMENSION", "HATCH"}:
            continue
        pts = []
        try:
            if typ == "LINE":
                pts = [(float(e.dxf.start.x), float(e.dxf.start.y)), (float(e.dxf.end.x), float(e.dxf.end.y))]
            elif typ == "ARC":
                c, r = e.dxf.center, float(e.dxf.radius)
                a1, a2 = math.radians(float(e.dxf.start_angle)), math.radians(float(e.dxf.end_angle))
                if a2 <= a1: a2 += 2 * math.pi
                pts = [(float(c.x + r*math.cos(a)), float(c.y + r*math.sin(a))) for a in np.linspace(a1, a2, 20)]
            elif typ in {"LWPOLYLINE", "POLYLINE"}:
                pts = [(float(p[0]), float(p[1])) for p in e.get_points()]
        except Exception:
            pts = []
        if len(pts) >= 2:
            xs, ys = zip(*pts); items.append({"entity": e, "pts": pts, "box": (min(xs),min(ys),max(xs),max(ys))})
    if not items: return []
    # Union nearby entities into candidate glyph groups.
    groups = []
    for item in items:
        x1,y1,x2,y2 = item["box"]; placed = False
        for g in groups:
            gx1,gy1,gx2,gy2 = g["box"]; gap = max(1.0, 0.12 * max(x2-x1, y2-y1, gx2-gx1, gy2-gy1))
            if not (x1 > gx2+gap or x2 < gx1-gap or y1 > gy2+gap or y2 < gy1-gap):
                g["items"].append(item); g["box"]=(min(gx1,x1),min(gy1,y1),max(gx2,x2),max(gy2,y2)); placed=True; break
        if not placed: groups.append({"items":[item], "box":item["box"]})
    out=[]
    for g in groups:
        x1,y1,x2,y2=g["box"]; w=max(32,int((x2-x1)*4)); h=max(32,int((y2-y1)*4)); canvas=np.full((h+24,w+24,3),255,np.uint8)
        for item in g["items"]:
            p=item["pts"]
            q=[(int((x-x1)*4+12), int((y2-y)*4+12)) for x,y in p]
            cv2.polylines(canvas,[np.array(q,np.int32)],False,(0,0,0),max(2,int(min(w,h)/45)))
        text, conf = ocr_crop(canvas, engine)
        if not text.strip() or text.startswith("["): continue
        handles=[str(i["entity"].dxf.handle) for i in g["items"]]
        out.append(TextRegion(id=f"text-vector-{len(out)+1:06d}", text=text.strip(), confidence=conf, needs_review=conf<threshold,
            bbox_world={"min_x":x1,"min_y":y1,"max_x":x2,"max_y":y2}, rotation=0.0,
            source_types=sorted({i["entity"].dxftype() for i in g["items"]}), source_entity_handles=handles, source_layer="VECTOR", ocr_engine=engine))
    return out


def add_dxf_text(doc, regions: list[TextRegion], hide_source: bool = False) -> None:
    if "Text_Converted_Layer" not in doc.layers:
        doc.layers.new("Text_Converted_Layer", dxfattribs={"color": 3})
    msp = doc.modelspace()
    for r in regions:
        p = r.bbox_world
        height = max(1.0, (p["max_y"] - p["min_y"]) * .8)
        msp.add_text(r.text, dxfattribs={"layer": "Text_Converted_Layer", "height": height,
                                         "rotation": r.rotation, "insert": (p["min_x"], p["min_y"])})
        if r.needs_review:
            msp.add_lwpolyline([(p["min_x"],p["min_y"]),(p["max_x"],p["min_y"]),(p["max_x"],p["max_y"]),(p["min_x"],p["max_y"]),(p["min_x"],p["min_y"])],
                               dxfattribs={"layer": "Text_Converted_Layer", "color": 1, "closed": True})
    if hide_source:
        for layer in doc.layers:
            if layer.dxf.name != "Text_Converted_Layer":
                layer.dxf.off = True


def regions_json(regions: list[TextRegion]) -> str:
    return json.dumps({"generated_at": utc_now(), "count": len(regions), "regions": [asdict(r) for r in regions]}, ensure_ascii=False, indent=2)


st.set_page_config(page_title="CAD 图形文字智能转换", page_icon="▦", layout="wide", initial_sidebar_state="expanded")
st.markdown("""<style>
:root{--accent:#20c997} .stApp{background:linear-gradient(135deg,#07121f 0%,#0d1f2d 55%,#102a36 100%);color:#eef6f8}
.block-container{max-width:1400px;padding-top:2rem}.hero{padding:24px 30px;border:1px solid #214452;border-radius:20px;background:linear-gradient(105deg,#112d3b,#0b1c28);box-shadow:0 12px 50px #0004;margin-bottom:20px}.hero h1{margin:0;color:#eafff8;font-size:2.2rem}.hero p{color:#a9c7ce;margin:.5rem 0 0}.metric{padding:16px;border-radius:14px;background:#102b38;border:1px solid #1d4d5b}.metric b{font-size:1.8rem;color:#4de1ad}.stButton>button{border-radius:10px;border:1px solid #21bf8d;background:#123d3d;color:#d9fff4;font-weight:600}.stDownloadButton>button{border-radius:10px}
</style>""", unsafe_allow_html=True)
st.markdown("<div class='hero'><h1>▦ CAD 图形化文字智能转换</h1><p>本地离线处理 · 世界坐标追溯 · 低置信度人工复核 · 企业交付工作流</p></div>", unsafe_allow_html=True)

with st.sidebar:
    st.header("处理配置")
    threshold = st.slider("低置信度阈值", 0.0, 1.0, 0.55, 0.05)
    ocr_engine = st.selectbox("OCR 模型", ["EasyOCR", "PaddleOCR", "Tesseract"], index=0, help="用于识别图形化文字渲染图；首次运行可能下载模型。Tesseract 需安装系统程序和语言包。")
    hide_source = st.checkbox("转换后隐藏原始图层", value=False)
    st.caption("本地运行时在本机处理；部署到云端时文件会发送到托管服务器。请勿上传涉密图纸。")
    status = {"Tesseract": pytesseract is not None, "EasyOCR": easyocr is not None, "PaddleOCR": PaddleOCR is not None}
    st.caption("模型状态：" + " · ".join(f"{k} {'✓' if v else '未安装'}" for k,v in status.items()))

uploaded = st.file_uploader("上传工图纸", type=["dxf", "png", "jpg", "jpeg", "bmp", "webp", "tif", "tiff"], help="重点支持 DXF 中由 LINE/ARC/LWPOLYLINE 等实体构成的图形化文字；也支持 PNG/JPG 等截图 OCR")
if not uploaded:
    st.info("请上传一张 DXF 工程图或图纸图片，系统将自动识别并生成结果。")
    st.stop()

raw = uploaded.getvalue(); suffix = Path(uploaded.name).suffix.lower()
start = time.perf_counter(); regions: list[TextRegion] = []; preview = None; doc = None; note = ""
try:
    if suffix == ".dxf":
        regions, doc, note = dxf_regions(raw, threshold, ocr_engine)
    else:
        arr = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        if arr is None:
            raise ValueError("图片解码失败。请将文件另存为 PNG/JPG 后重试。")
        regions, preview = image_regions(arr, threshold, ocr_engine)
        note = f"图片模式：使用 {ocr_engine}；坐标以图像像素映射为世界坐标；如需写回 CAD，请上传 DXF。"
except Exception as exc:
    st.error(f"处理失败：{exc}"); st.stop()
elapsed = time.perf_counter() - start

c1,c2,c3,c4 = st.columns(4)
for col, title, val in [(c1,"识别区域",len(regions)),(c2,"需人工复核",sum(r.needs_review for r in regions)),(c3,"平均置信度",f"{np.mean([r.confidence for r in regions])*100:.1f}%" if regions else "0%"),(c4,"处理耗时",f"{elapsed:.2f}s")]:
    col.markdown(f"<div class='metric'><span>{title}</span><br><b>{val}</b></div>", unsafe_allow_html=True)
st.caption(note)
if ocr_engine == "EasyOCR" and not regions:
    st.warning("EasyOCR 没有返回可用文字。请检查下方诊断：标准 TEXT/MTEXT 会直接提取；图形化字形会先聚类、渲染，再由 EasyOCR 识别。单个线段字形（例如 A 或 工）本身也可能不符合 OCR 模型的训练特征。")
    st.caption(f"EasyOCR 导入状态：{'已导入' if easyocr is not None else '未导入'}；若未导入，请检查云端构建日志。")

if ocr_engine == "PaddleOCR" and not regions:
    st.warning("PaddleOCR 没有返回可用文字。检查图形字形是否被聚类为候选区域；如发生内部异常，页面会显示错误信息。")
    st.caption(f"PaddleOCR 导入状态：{'已导入' if PaddleOCR is not None else '未导入'}。")

left, right = st.columns([1.15, 1])
with left:
    st.subheader("识别结果预览")
    if preview is not None:
        st.image(cv2.cvtColor(preview, cv2.COLOR_BGR2RGB), use_container_width=True)
    else:
        st.info("DXF 已解析。下载转换后的 DXF，在 CAD 中查看写回结果。")
with right:
    st.subheader("文字识别清单")
    df = pd.DataFrame([{"编号":r.id,"文本":r.text,"置信度":f"{r.confidence:.1%}","复核": "是" if r.needs_review else "否", "坐标":json.dumps(r.bbox_world, ensure_ascii=False)} for r in regions])
    st.dataframe(df, use_container_width=True, hide_index=True)

st.divider(); st.subheader("导出与交付")
json_bytes = regions_json(regions).encode("utf-8")
csv_bytes = df.to_csv(index=False).encode("utf-8-sig") if not df.empty else "编号,文本,置信度,复核,坐标\n".encode()
b1,b2,b3 = st.columns(3)
b1.download_button("下载 JSON 识别报告", json_bytes, f"{uploaded.name}.json", "application/json")
b2.download_button("下载 CSV 清单", csv_bytes, f"{uploaded.name}.csv", "text/csv")
if suffix == ".dxf" and doc is not None:
    # Always show the DXF download after a successful DXF parse.
    add_dxf_text(doc, regions, hide_source)
    out = io.StringIO()
    doc.write(out)
    converted_data = out.getvalue().encode("utf-8")
    b3.download_button("下载转换后的 DXF", converted_data,
                       f"{Path(uploaded.name).stem}_converted.dxf", "application/dxf")
    st.caption("DXF 转换文件已生成。请在 CAD 中检查 Text_Converted_Layer、文字位置和原始图形。")
else:
    b3.download_button("下载 TXT 清单", "\\n".join(f"{r.id}\\t{r.text}\\t{r.confidence:.3f}" for r in regions), f"{uploaded.name}.txt", "text/plain")

with st.expander("处理说明与企业验收提示"):
    st.markdown("""- 低置信度区域用红色框标记，建议人工复核。\n- DXF 模式会创建 `Text_Converted_Layer` 并写入 TEXT 对象。\n- DWG 需要企业部署已授权的 CAD/ODA 转换服务，再接入同一适配器接口。\n- 准确率、误报率和 5 秒性能指标必须使用甲方标注测试集实测，不以演示数据代替。""")
