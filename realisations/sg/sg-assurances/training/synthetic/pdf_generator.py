"""
PDF Generator — Synthetic SG Assurances documents
Generates multipage PDFs (contrat / formulaire sinistre / avis echeance)
with randomized zone positions for YOLO annotation.
Outputs: PDFs in data/synthetic_pdfs/ + zone coordinates per page
"""

import random
import os
from dataclasses import dataclass, field
from pathlib import Path
from faker import Faker
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

# ─────────────────────────────────────────
# Constants
# ─────────────────────────────────────────
PAGE_W, PAGE_H = A4  # 595.27 x 841.89 points
MARGIN_MIN = 15 * mm
MARGIN_MAX = 25 * mm
LANG_SPLIT = 0.7  # 70% FR / 30% EN

DATA_DIR = Path(__file__).parent.parent / "data" / "synthetic_pdfs"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DOC_TYPES = ["contrat", "formulaire", "echeance"]
PAGES_RANGE = {
    "contrat":    (3, 5),
    "formulaire": (2, 3),
    "echeance":   (1, 2),
}
# Bandes verticales pour placement aléatoire des blocs
BAND_TOP    = (0.10, 0.35)   # 10% à 35% de la hauteur page
BAND_MIDDLE = (0.35, 0.62)   # 35% à 62%
BAND_BOTTOM = (0.62, 0.88)   # 62% à 88%
BANDS = [BAND_TOP, BAND_MIDDLE, BAND_BOTTOM]

def _clean_dir(path: Path) -> None:
    """Remove all files in a directory without removing the directory."""
    if path.exists():
        for f in path.iterdir():
            if f.is_file():
                f.unlink()

# ─────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────
@dataclass
class ZoneCoords:
    """Bounding box of a detected zone in PDF points."""
    zone_type: str   # contract_block | identity_block | amount_block | signature_block
    page: int        # 0-indexed
    x: float         # left edge in points
    y: float         # top edge in points (from top of page)
    w: float         # width in points
    h: float         # height in points

@dataclass
class GeneratedDoc:
    """Output of a single PDF generation."""
    filepath: Path
    doc_type: str
    lang: str
    pages: int
    zones: list[ZoneCoords] = field(default_factory=list)


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────
def _faker(lang: str) -> Faker:
    return Faker("fr_FR" if lang == "fr" else "en_GB")

def _rand_margin() -> float:
    return random.uniform(MARGIN_MIN, MARGIN_MAX)

def _rand_x(w: float) -> float:
    """Random x position keeping zone inside page."""
    lo = MARGIN_MIN
    hi = PAGE_W - MARGIN_MIN - w
    return random.uniform(lo, max(lo, hi))

def _rand_y_in_band(band: tuple, h: float) -> float:
    """Position verticale aléatoire dans une bande donnée."""
    y_min = band[0] * PAGE_H
    y_max = band[1] * PAGE_H - h
    return random.uniform(y_min, max(y_min, y_max))

def _rand_color() -> colors.Color:
    """Light background color for zone variation."""
    opts = [colors.white, colors.HexColor("#f5f5f5"), colors.HexColor("#eef2f7")]
    return random.choice(opts)

def _styles(lang: str) -> dict:
    base = getSampleStyleSheet()
    normal = ParagraphStyle(
        "sg_normal",
        parent=base["Normal"],
        fontSize=random.uniform(8.5, 10.5),
        leading=random.uniform(12, 15),
        spaceAfter=random.uniform(3, 6),
    )
    title = ParagraphStyle(
        "sg_title",
        parent=base["Heading1"],
        fontSize=random.uniform(13, 16),
        spaceAfter=random.uniform(6, 10),
        alignment=random.choice([TA_LEFT, TA_CENTER]),
    )
    label = ParagraphStyle(
        "sg_label",
        parent=base["Normal"],
        fontSize=random.uniform(7.5, 9),
        textColor=colors.HexColor("#555555"),
    )
    return {"normal": normal, "title": title, "label": label}


# ─────────────────────────────────────────
# Zone builders — return (flowable_list, zone_type)
# ─────────────────────────────────────────
def _build_contract_block(fk: Faker, styles: dict) -> list:
    """contract_block: police number + dates."""
    label = "Numéro de police" if fk.locale == "fr_FR" else "Policy Number"
    data = [
        [label, fk.bothify("POL-####-???-####")],
        ["Date d'effet" if fk.locale == "fr_FR" else "Effective date",
         fk.date_this_decade().strftime("%d/%m/%Y")],
        ["Date d'échéance" if fk.locale == "fr_FR" else "Expiry date",
         fk.date_this_decade().strftime("%d/%m/%Y")],
    ]
    t = Table(data, colWidths=[60*mm, 80*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _rand_color()),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("FONTSIZE", (0, 0), (-1, -1), random.uniform(8, 10)),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return [t, Spacer(1, random.uniform(4*mm, 8*mm))]

def _build_identity_block(fk: Faker, styles: dict) -> list:
    """identity_block: insured person identity."""
    label = "Assuré(e)" if fk.locale == "fr_FR" else "Insured"
    data = [
        [label, fk.name()],
        ["Adresse" if fk.locale == "fr_FR" else "Address", fk.address().replace("\n", " ")],
        ["Date de naissance" if fk.locale == "fr_FR" else "Date of birth",
         fk.date_of_birth(minimum_age=18, maximum_age=80).strftime("%d/%m/%Y")],
    ]
    t = Table(data, colWidths=[60*mm, 100*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _rand_color()),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#aaaaaa")),
        ("FONTSIZE", (0, 0), (-1, -1), random.uniform(8, 10)),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return [t, Spacer(1, random.uniform(4*mm, 8*mm))]

def _build_amount_block(fk: Faker, styles: dict) -> list:
    """amount_block: prime / franchise / garantie amounts."""
    label_prime = "Prime annuelle TTC" if fk.locale == "fr_FR" else "Annual premium incl. tax"
    label_franc = "Franchise" if fk.locale == "fr_FR" else "Deductible"
    label_garan = "Plafond de garantie" if fk.locale == "fr_FR" else "Coverage limit"
    data = [
        [label_prime, f"{random.randint(200, 2000)},00 €"],
        [label_franc,  f"{random.choice([150, 300, 500, 1000])},00 €"],
        [label_garan,  f"{random.choice([50000, 100000, 300000])},00 €"],
    ]
    t = Table(data, colWidths=[90*mm, 60*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f0fe")),
        ("BACKGROUND", (0, 1), (-1, -1), _rand_color()),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#3b5998")),
        ("FONTSIZE", (0, 0), (-1, -1), random.uniform(8.5, 10.5)),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return [t, Spacer(1, random.uniform(4*mm, 8*mm))]

def _build_signature_block(fk: Faker, styles: dict) -> list:
    """signature_block: signature area + date."""
    date_lbl = "Fait le" if fk.locale == "fr_FR" else "Signed on"
    sig_lbl  = "Signature de l'assuré(e)" if fk.locale == "fr_FR" else "Insured signature"
    data = [
        [f"{date_lbl} : {fk.date_this_year().strftime('%d/%m/%Y')}", ""],
        [sig_lbl, ""],
        ["", ""],
    ]
    t = Table(data, colWidths=[80*mm, 80*mm], rowHeights=[8*mm, 8*mm, 20*mm])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
        ("FONTSIZE", (0, 0), (-1, -1), random.uniform(8, 9.5)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
    ]))
    return [t, Spacer(1, random.uniform(4*mm, 8*mm))]


# ─────────────────────────────────────────
# Page content builders
# ─────────────────────────────────────────
def _page_contrat(fk: Faker, styles: dict, page_idx: int) -> list:
    """Build flowables for one contrat page."""
    elems = []
    if page_idx == 0:
        title = "CONTRAT D'ASSURANCE" if fk.locale == "fr_FR" else "INSURANCE CONTRACT"
        elems.append(Paragraph(title, styles["title"]))
        elems.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#3b5998")))
        elems.append(Spacer(1, random.uniform(5*mm, 10*mm)))
        blocks = [
            _build_contract_block(fk, styles),
            _build_identity_block(fk, styles),
        ]
        for b in blocks:
            elems += b
    elif page_idx == 1:
        section = "GARANTIES SOUSCRITES" if fk.locale == "fr_FR" else "SUBSCRIBED COVERAGES"
        elems.append(Paragraph(section, styles["title"]))
        elems.append(Spacer(1, random.uniform(3*mm, 6*mm)))
        body = fk.paragraphs(nb=random.randint(3, 5)) or []
        blocks = [
            _build_amount_block(fk, styles),
            [Paragraph(p, styles["normal"]) for p in body],
        ]
        for b in blocks:
            elems += b
    else:
        section = "CONDITIONS PARTICULIÈRES" if fk.locale == "fr_FR" else "PARTICULAR CONDITIONS"
        elems.append(Paragraph(section, styles["title"]))
        elems.append(Spacer(1, random.uniform(3*mm, 6*mm)))
        body = fk.paragraphs(nb=random.randint(4, 7))
        for p in body:
            elems.append(Paragraph(p, styles["normal"]))
        if page_idx == PAGES_RANGE["contrat"][1] - 1:
            elems += _build_signature_block(fk, styles)

    return elems

def _page_formulaire(fk: Faker, styles: dict, page_idx: int) -> list:
    elems = []
    if page_idx == 0:
        title = "DÉCLARATION DE SINISTRE" if fk.locale == "fr_FR" else "CLAIM DECLARATION"
        elems.append(Paragraph(title, styles["title"]))
        elems.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#c0392b")))
        elems.append(Spacer(1, random.uniform(5*mm, 8*mm)))
        lbl = "Nature du sinistre" if fk.locale == "fr_FR" else "Nature of claim"
        nature_block = [
            Paragraph(f"<b>{lbl}</b>", styles["normal"]),
            Paragraph(fk.sentence(nb_words=12), styles["normal"]),
        ]
        blocks = [
            _build_contract_block(fk, styles),
            _build_identity_block(fk, styles),
            nature_block,
        ]
        for b in blocks:
            elems += b
    else:
        body = fk.paragraphs(nb=random.randint(2, 4)) or []
        blocks = [
            _build_amount_block(fk, styles),
            [Paragraph(p, styles["normal"]) for p in body],
            _build_signature_block(fk, styles),
        ]
        for b in blocks:
            elems += b
    return elems

def _page_echeance(fk: Faker, styles: dict, page_idx: int) -> list:
    elems = []
    title = "AVIS D'ÉCHÉANCE" if fk.locale == "fr_FR" else "RENEWAL NOTICE"
    elems.append(Paragraph(title, styles["title"]))
    elems.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#27ae60")))
    elems.append(Spacer(1, random.uniform(5*mm, 8*mm)))
    if page_idx == 0:
        blocks = [
            _build_identity_block(fk, styles),
            _build_amount_block(fk, styles),
        ]
        for b in blocks:
            elems += b
    else:
        body = fk.paragraphs(nb=random.randint(3, 5)) or []
        blocks = [
            [Paragraph(p, styles["normal"]) for p in body],
            _build_signature_block(fk, styles),
        ]
        for b in blocks:
            elems += b
    return elems


# ─────────────────────────────────────────
# Zone coordinate extraction
# ─────────────────────────────────────────
def _extract_zones_from_story(story: list, doc_type: str, page_idx: int) -> list[ZoneCoords]:
    zones = []
    zone_map = {
        "contract_block":  ("contrat", "formulaire", "echeance"),
        "identity_block":  ("contrat", "formulaire", "echeance"),
        "amount_block":    ("contrat", "formulaire", "echeance"),
        "signature_block": ("contrat", "formulaire"),
    }

    table_count = 0
    for flowable in story:
        if isinstance(flowable, Table):
            if table_count == 0:
                if page_idx == 0:
                    present = {"contract_block"}
                else:
                    present = {"amount_block"}
            elif table_count == 1:
                if page_idx == 0:
                    present = {"identity_block"}
                else:
                    present = {"signature_block"}
            else:
                present = set()
            table_count += 1

            y_cursor = random.uniform(60*mm, 100*mm)
            for ztype in present:
                w = random.uniform(120*mm, 160*mm)
                h = random.uniform(20*mm, 35*mm)
                x = _rand_x(w)
                y = y_cursor
                zones.append(ZoneCoords(
                    zone_type=ztype,
                    page=page_idx,
                    x=x,
                    y=y,
                    w=w,
                    h=h,
                ))
                y_cursor += h + random.uniform(8*mm, 15*mm)

    return zones


# ─────────────────────────────────────────
# Document generators
# ─────────────────────────────────────────
def _generate_doc(doc_type: str, lang: str, doc_id: int) -> GeneratedDoc:
    fk = _faker(lang)
    styles = _styles(lang)
    nb_pages = random.randint(*PAGES_RANGE[doc_type])
    fname = DATA_DIR / f"{doc_type}_{lang}_{doc_id:04d}.pdf"

    page_builders = {
        "contrat":    _page_contrat,
        "formulaire": _page_formulaire,
        "echeance":   _page_echeance,
    }
    builder = page_builders[doc_type]

    all_zones: list[ZoneCoords] = []
    all_stories = []

    for p in range(nb_pages):
        story = builder(fk, styles, p)
        zones = _extract_zones_from_story(story, doc_type, p)
        all_zones.extend(zones)
        all_stories.append(story)

    # Build PDF — one SimpleDocTemplate, pages separated by PageBreak
    from reportlab.platypus import PageBreak
    full_story = []
    for i, s in enumerate(all_stories):
        full_story.extend(s)
        if i < len(all_stories) - 1:
            full_story.append(PageBreak())

    margin = _rand_margin()
    doc = SimpleDocTemplate(
        str(fname),
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
    )
    doc.build(full_story)

    return GeneratedDoc(
        filepath=fname,
        doc_type=doc_type,
        lang=lang,
        pages=nb_pages,
        zones=all_zones,
    )


# ─────────────────────────────────────────
# Public API
# ─────────────────────────────────────────
def generate_batch(nb_per_type: int = 200) -> list[GeneratedDoc]:
    """
    Generate nb_per_type PDFs for each doc type (contrat / formulaire / echeance).
    Language split: 70% fr / 30% en.
    Returns list of GeneratedDoc with zone coordinates.
    """
    results = []
    doc_id = 0

    for doc_type in DOC_TYPES:
        print(f"[pdf_generator] Generating {nb_per_type} '{doc_type}' PDFs...")
        for i in range(nb_per_type):
            lang = "fr" if random.random() < LANG_SPLIT else "en"
            try:
                doc = _generate_doc(doc_type, lang, doc_id)
                results.append(doc)
                doc_id += 1
                if (i + 1) % 50 == 0:
                    print(f"  {i + 1}/{nb_per_type} done")
            except Exception as e:
                print(f"  [WARN] Failed doc_id={doc_id} type={doc_type}: {e}")
                doc_id += 1

    print(f"[pdf_generator] Done — {len(results)} PDFs generated in {DATA_DIR}")
    return results


if __name__ == "__main__":
    print("[pdf_generator] Nettoyage synthetic_pdfs/...")
    _clean_dir(DATA_DIR)
    docs = generate_batch(nb_per_type=200)
    print(f"Total PDFs: {len(docs)}")
    print(f"Total zones: {sum(len(d.zones) for d in docs)}")
    import json
    zones_out = []
    for d in docs:
        for z in d.zones:
            zones_out.append({
                "filepath": str(d.filepath),
                "doc_type": d.doc_type,
                "lang": d.lang,
                "pages": d.pages,
                "zone_type": z.zone_type,
                "page": z.page,
                "x": z.x,
                "y": z.y,
                "w": z.w,
                "h": z.h,
            })
    zones_path = DATA_DIR.parent / "annotations" / "zones.json"
    zones_path.parent.mkdir(parents=True, exist_ok=True)
    with open(zones_path, "w", encoding="utf-8") as f:
        json.dump(zones_out, f, ensure_ascii=False, indent=2)
    print(f"[pdf_generator] Zones saved → {zones_path}")

    # Sample output
    if docs:
        sample = docs[0]
        print(f"Sample: {sample.filepath.name} | {sample.pages} pages | {len(sample.zones)} zones")
        for z in sample.zones:
            print(f"  {z.zone_type} p{z.page} x={z.x:.1f} y={z.y:.1f} w={z.w:.1f} h={z.h:.1f}")