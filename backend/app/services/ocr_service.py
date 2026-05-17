import io
import re
import unicodedata
from typing import List, Set, Tuple

import pytesseract
from PIL import Image, ImageOps
from pdf2image import convert_from_bytes

from app.core.config import settings
from app.services.workflow_service import WorkflowService

if settings.TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

# Mots déclencheurs du routage automatique (alignés sur workflow_service.ROUTING_RULES + synonymes FR)
_ROUTING_CANONICAL: List[Tuple[str, List[str]]] = []
for _dept, keys in WorkflowService.ROUTING_RULES.items():
    for k in keys:
        _ROUTING_CANONICAL.append((k, [k]))

# Synonymes supplémentaires → libellé canonique déjà présent dans ROUTING_RULES
_EXTRA_ALIASES: List[Tuple[str, List[str]]] = [
    ("loan", ["crédit", "credit", "credits", "crédits", "emprunt", "borrowing"]),
    ("prêt", ["pret", "prets", "préts", "prêts"]),
    ("financement", ["financements", "funding", "financing"]),
    ("projet", ["projets", "project", "projects"]),
    ("analyse", ["analyses", "analytic", "analytics"]),
    ("rapport", ["rapports", "reports", "reporting"]),
    ("étude", ["etude", "etudes", "études", "study", "studies"]),
    ("urgent", ["urgence", "urgents", "priority", "priorité", "priorite"]),
    ("directeur", ["directrice", "dg", "direction", "managing"]),
    ("approbation", ["approve", "approved", "agrément", "agrement", "validation finale"]),
    ("demande", ["demandes", "request", "requests", "requête", "requete", "requisition"]),
    ("contrat", ["contrats", "contracts", "contractuel"]),
    ("facture", ["factures", "invoices", "billing", "facturation"]),
    ("paiement", ["paiements", "payments", "payment", "règlement", "reglement"]),
]

# Mots-clés affichés même sans lien routage (détection métier courante)
_EXTRA_DISPLAY_ONLY: List[str] = [
    "courrier",
    "correspondance",
    "instruction",
    "réclamation",
    "reclamation",
    "mise en demeure",
    "contentieux",
    "garantie",
    "hypothèque",
    "hypotheque",
    "immobilier",
    "compte",
    "virement",
    "titulaire",
    "bénéficiaire",
    "beneficiaire",
    "signature",
    "amendement",
    "avenant",
    "clôture",
    "cloture",
]


def _normalize_match_text(s: str) -> str:
    s = s.replace("œ", "oe").replace("Œ", "OE").replace("æ", "ae").replace("Æ", "AE")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.lower()


def _token_pattern(term: str) -> re.Pattern:
    """Mot ou phrase : frontière sur caractères alphanumériques (texte déjà normalisé)."""
    t = _normalize_match_text(term)
    if not t:
        return re.compile(r"$^")
    parts = [p for p in re.split(r"\s+", t.strip()) if p]
    if not parts:
        return re.compile(r"$^")
    if len(parts) == 1 and len(parts[0]) <= 2:
        return re.compile(rf"(?<![a-z0-9]){re.escape(parts[0])}(?![a-z0-9])")
    inner = r"[^\w]*".join(re.escape(p) for p in parts)
    return re.compile(rf"(?<![a-z0-9]){inner}(?![a-z0-9])")


class OCRService:
    """OCR Tesseract : texte + mots-clés (normalisation, synonymes, frontières de mots)."""

    def __init__(self) -> None:
        self._compiled: List[Tuple[str, re.Pattern]] = []
        seen_sig: set = set()
        for canonical, variants in _ROUTING_CANONICAL + _EXTRA_ALIASES:
            for v in variants:
                sig = (_normalize_match_text(canonical), _normalize_match_text(v))
                if sig in seen_sig:
                    continue
                seen_sig.add(sig)
                self._compiled.append((canonical, _token_pattern(v)))
        for term in _EXTRA_DISPLAY_ONLY:
            sig = ("__extra__", _normalize_match_text(term))
            if sig in seen_sig or not sig[1]:
                continue
            seen_sig.add(sig)
            self._compiled.append((term, _token_pattern(term)))

    def extract_text(self, file_content: bytes, mime_type: str) -> str:
        tess_config = "--oem 3"
        try:
            if mime_type == "application/pdf":
                images = convert_from_bytes(file_content, fmt="png", thread_count=1)
                text_parts: List[str] = []
                for image in images:
                    image = ImageOps.autocontrast(image.convert("RGB"))
                    text = pytesseract.image_to_string(
                        image,
                        lang=settings.OCR_LANGUAGE,
                        config=f"{tess_config} --psm 6",
                    )
                    text_parts.append(text)
                return "\n".join(text_parts)
            if mime_type.startswith("image/"):
                image = Image.open(io.BytesIO(file_content)).convert("RGB")
                image = ImageOps.autocontrast(image)
                return pytesseract.image_to_string(
                    image,
                    lang=settings.OCR_LANGUAGE,
                    config=f"{tess_config} --psm 6",
                )
            raise ValueError(f"Unsupported MIME type for OCR: {mime_type}")
        except Exception as e:
            raise Exception(f"OCR processing failed: {str(e)}") from e

    def detect_keywords(self, text: str) -> List[str]:
        folded = _normalize_match_text(text)
        detected: Set[str] = set()
        for label, pattern in self._compiled:
            if pattern.search(folded):
                detected.add(label)
        return sorted(detected)

    def process_document(self, file_content: bytes, mime_type: str) -> dict:
        text = self.extract_text(file_content, mime_type)
        keywords = self.detect_keywords(text)
        return {
            "text": text,
            "keywords": keywords,
            "word_count": len(text.split()),
        }


ocr_service = OCRService()
