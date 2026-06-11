"""
Annotator — YOLO label generation from synthetic PDFs
For each PDF produced by pdf_generator.py:
  1. Convert each page to PNG image
  2. Extract real table coordinates via pymupdf
  3. Map tables to zone types (contract/identity/amount/signature)
  4. Write YOLO label files (class_id cx cy w h normalized)

Output structure:
  data/annotations/
  ├── images/   ← PNG pages
  └── labels/   ← YOLO .txt label files
"""

import fitz  # pymupdf
import random
import numpy as np
import cv2
from PIL import Image as PILImage
from pathlib import Path
from dataclasses import dataclass
import sys
sys.path.insert(0, str(Path(__file__).parent))
from pdf_generator import GeneratedDoc, ZoneCoords, PAGE_W, PAGE_H

# ─────────────────────────────────────────
# Constants
# ─────────────────────────────────────────
ANNOTATIONS_DIR = Path(__file__).parent.parent / "data" / "annotations"
IMAGES_DIR  = ANNOTATIONS_DIR / "images"
LABELS_DIR  = ANNOTATIONS_DIR / "labels"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
LABELS_DIR.mkdir(parents=True, exist_ok=True)

# YOLO class mapping
CLASS_MAP = {
    "contract_block":  0,
    "identity_block":  1,
    "amount_block":    2,
    "signature_block": 3,
}

# PNG render resolution
DPI = 150
ZOOM = DPI / 72  # pymupdf uses 72 dpi base

# Minimum table area to consider (points²) — filters noise
MIN_TABLE_AREA = 20 * 20

def _clean_dir(path: Path) -> None:
    if path.exists():
        for f in path.iterdir():
            if f.is_file():
                f.unlink()


# ─────────────────────────────────────────
# Data class
# ─────────────────────────────────────────
@dataclass
class AnnotatedPage:
    image_path: Path
    label_path: Path
    page: int
    zones: list[ZoneCoords]


# ─────────────────────────────────────────
# Core helpers
# ─────────────────────────────────────────
def _normalize(x: float, y: float, w: float, h: float,
               page_w: float, page_h: float) -> tuple[float, float, float, float]:
    """Convert absolute coords to YOLO normalized (cx, cy, w, h)."""
    cx = (x + w / 2) / page_w
    cy = (y + h / 2) / page_h
    nw = w / page_w
    nh = h / page_h
    # Clamp to [0, 1]
    cx = max(0.0, min(1.0, cx))
    cy = max(0.0, min(1.0, cy))
    nw = max(0.0, min(1.0, nw))
    nh = max(0.0, min(1.0, nh))
    return cx, cy, nw, nh


def _extract_tables(page: fitz.Page) -> list[fitz.Rect]:
    """
    Extract table bounding boxes from a rendered PDF page.
    Uses pymupdf's find_tables() when available,
    falls back to drawing rect detection for older versions.
    """
    tables = []
    try:
        # pymupdf >= 1.23 — native table detection
        tab_finder = page.find_tables()
        for tab in tab_finder.tables:
            rect = tab.bbox
            tables.append(fitz.Rect(rect))
    except AttributeError:
        # Fallback — detect filled rectangles from drawings
        for drawing in page.get_drawings():
            rect = drawing.get("rect")
            if rect is None:
                continue
            r = fitz.Rect(rect)
            if r.width * r.height >= MIN_TABLE_AREA:
                tables.append(r)
    return tables


def _map_tables_to_zones(
    tables: list[fitz.Rect],
    heuristic_zones: list[ZoneCoords],
    page_idx: int,
) -> list[ZoneCoords]:
    page_zones = [z for z in heuristic_zones if z.page == page_idx]
    if not tables or not page_zones:
        return []

    # Sort tables top → bottom by y0
    sorted_tables = sorted(tables, key=lambda r: r.y0)

    # Sort heuristic zones top → bottom
    sorted_hints = sorted(page_zones, key=lambda z: z.y)

    result = []
    for i, table in enumerate(sorted_tables):
        if i >= len(sorted_hints):
            break
        zone_type = sorted_hints[i].zone_type
        result.append(ZoneCoords(
            zone_type=zone_type,
            page=page_idx,
            x=table.x0,
            y=table.y0,
            w=table.width,
            h=table.height,
        ))
    return result


def _write_label(label_path: Path, zones: list[ZoneCoords],
                 page_w: float, page_h: float) -> None:
    """Write YOLO label file — one line per zone."""
    lines = []
    for z in zones:
        cls = CLASS_MAP.get(z.zone_type)
        if cls is None:
            continue
        cx, cy, nw, nh = _normalize(z.x, z.y, z.w, z.h, page_w, page_h)
        lines.append(f"{cls} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")

    with open(label_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def _deskew(img_np: np.ndarray) -> np.ndarray:
    """
    Détecte et corrige l'inclinaison d'une image via Hough transform.
    Retourne l'image redressée.
    """
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=100,
                             minLineLength=100, maxLineGap=10)
    if lines is None:
        return img_np

    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if x2 - x1 != 0:
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            if -10 < angle < 10:
                angles.append(angle)

    if not angles:
        return img_np

    median_angle = float(np.median(angles))
    h, w = img_np.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    corrected = cv2.warpAffine(img_np, M, (w, h),
                                flags=cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_REPLICATE)
    return corrected


def _augment(img_np: np.ndarray) -> np.ndarray:
    """
    Augmentation aléatoire de l'image :
    - 30% : rotation simulée ±5° puis deskewing
    - 70% : bruit gaussien + variation luminosité ±15%
    Les deux peuvent se cumuler.
    """
    # Rotation simulée + deskewing — 30% des images
    # if random.random() < 0.30:
    #     angle = random.uniform(-5.0, 5.0)
    #     h, w = img_np.shape[:2]
    #     center = (w // 2, h // 2)
    #     M = cv2.getRotationMatrix2D(center, angle, 1.0)
    #     img_np = cv2.warpAffine(img_np, M, (w, h),
    #                              flags=cv2.INTER_LINEAR,
    #                              borderMode=cv2.BORDER_REPLICATE)
    #     img_np = _deskew(img_np)

    # Bruit gaussien + luminosité — 70% des images
    if random.random() < 0.70:
        # Bruit gaussien
        noise = np.random.normal(0, random.uniform(3, 10), img_np.shape).astype(np.float32)
        img_np = np.clip(img_np.astype(np.float32) + noise, 0, 255).astype(np.uint8)
        # Variation luminosité
        factor = random.uniform(0.85, 1.15)
        img_np = np.clip(img_np.astype(np.float32) * factor, 0, 255).astype(np.uint8)

    return img_np

# ─────────────────────────────────────────
# Page processor
# ─────────────────────────────────────────
def _process_page(
    pdf_doc: fitz.Document,
    page_idx: int,
    stem: str,
    heuristic_zones: list[ZoneCoords],
) -> AnnotatedPage | None:
    """Process a single PDF page — render PNG + generate label."""
    try:
        page = pdf_doc[page_idx]
        page_w = page.rect.width
        page_h = page.rect.height

        # 1. Render page to PNG
        mat = fitz.Matrix(ZOOM, ZOOM)
        pix = page.get_pixmap(matrix=mat)
        img_name = f"{stem}_p{page_idx:02d}.png"
        img_path = IMAGES_DIR / img_name
        pix.save(str(img_path))

        # Augmentation image
        img_np = np.array(PILImage.open(str(img_path)).convert("RGB"))
        # img_np = _augment(img_np)
        PILImage.fromarray(img_np).save(str(img_path))

        # 2. Extract real table coords
        tables = _extract_tables(page)

        # 3. Map to zone types
        if tables:
            zones = _map_tables_to_zones(tables, heuristic_zones, page_idx)
        else:
            # Fallback to heuristic zones if no tables detected
            zones = [z for z in heuristic_zones if z.page == page_idx]

        # 4. Write YOLO label
        lbl_name = f"{stem}_p{page_idx:02d}.txt"
        lbl_path = LABELS_DIR / lbl_name
        _write_label(lbl_path, zones, page_w, page_h)

        return AnnotatedPage(
            image_path=img_path,
            label_path=lbl_path,
            page=page_idx,
            zones=zones,
        )

    except Exception as e:
        print(f"  [WARN] Page {page_idx} of {stem} failed: {e}")
        return None


# ─────────────────────────────────────────
# Public API
# ─────────────────────────────────────────
def annotate_batch(docs: list[GeneratedDoc]) -> list[AnnotatedPage]:
    """
    Annotate all PDFs from a GeneratedDoc batch.
    Returns list of AnnotatedPage with image + label paths.
    """
    all_pages: list[AnnotatedPage] = []
    total = len(docs)

    for i, doc in enumerate(docs):
        if not doc.filepath.exists():
            print(f"  [WARN] PDF not found: {doc.filepath}")
            continue

        stem = doc.filepath.stem
        try:
            pdf = fitz.open(str(doc.filepath))
            for p in range(len(pdf)):
                result = _process_page(pdf, p, stem, doc.zones)
                if result:
                    all_pages.append(result)
            pdf.close()
        except Exception as e:
            print(f"  [WARN] Failed to open {doc.filepath.name}: {e}")

        if (i + 1) % 50 == 0 or (i + 1) == total:
            print(f"[annotator] {i + 1}/{total} PDFs annotated")

    print(f"[annotator] Done — {len(all_pages)} pages annotated")
    print(f"  Images : {IMAGES_DIR}")
    print(f"  Labels : {LABELS_DIR}")
    return all_pages


def annotate_single(doc: GeneratedDoc) -> list[AnnotatedPage]:
    """Annotate a single GeneratedDoc — useful for testing."""
    return annotate_batch([doc])


# ─────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────
if __name__ == "__main__":
    import json
    from collections import defaultdict

    zones_path = Path(__file__).parent.parent / "data" / "annotations" / "zones.json"
    if not zones_path.exists():
        print("[annotator] zones.json introuvable — lance pdf_generator.py d'abord")
        sys.exit(1)

    print("[annotator] Nettoyage images/ et labels/...")
    _clean_dir(IMAGES_DIR)
    _clean_dir(LABELS_DIR)

    with open(zones_path, encoding="utf-8") as f:
        raw = json.load(f)

    grouped = defaultdict(list)
    meta = {}
    for entry in raw:
        fp = entry["filepath"]
        grouped[fp].append(ZoneCoords(
            zone_type=entry["zone_type"],
            page=entry["page"],
            x=entry["x"],
            y=entry["y"],
            w=entry["w"],
            h=entry["h"],
        ))
        meta[fp] = (entry["doc_type"], entry["lang"], entry["pages"])

    docs = []
    for fp, zones in grouped.items():
        dt, lang, pages = meta[fp]
        docs.append(GeneratedDoc(
            filepath=Path(fp),
            doc_type=dt,
            lang=lang,
            pages=pages,
            zones=zones,
        ))

    print(f"[annotator] {len(docs)} PDFs chargés depuis zones.json")
    pages_out = annotate_batch(docs)
    print(f"\nSample output:")
    for pg in pages_out[:5]:
        print(f"  {pg.image_path.name} — {len(pg.zones)} zones")