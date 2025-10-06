import re
from datetime import datetime
import pdfplumber
from lxml import etree

XMLNS = "http://www.w3.org/XML/1998/namespace"
TEINS = "{http://www.tei-c.org/ns/1.0}"

MONTHS = r"(January|February|March|April|May|June|July|August|September|October|November|December)"
DATE_RE = re.compile(rf"{MONTHS}\s+\d{{1,2}},\s*\d{{4}}", re.IGNORECASE)
CLASS_RE = re.compile(r"\b(SENSITIVE|SECRET|TOP SECRET|CONFIDENTIAL|UNCLASSIFIED|NOFORN|OADR|E\.O\.\s*12[0-9]{{3}}|EO\s*12[0-9]{{3}})\b", re.IGNORECASE)
PARA_CLASS_RE = re.compile(r"^\s*\((TS|S|C|U)\)\s*")
UPPER_HEAD_RE = re.compile(r"^[A-Z0-9 ,\-\.\'&:;\/\(\)]+$")
LETTER_HEAD_RE = re.compile(r"^\s*([A-Z])\.\s+(.*)")
NUMBER_POINT_RE = re.compile(r"^\s*(\d+)\.\s+(.*)")

def extract_pages(pdf_path):
    pages=[]
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            txt = page.extract_text() or ""
            lines=[ln.rstrip() for ln in txt.splitlines()]
            pages.append({"n":i,"text":txt,"lines":lines})
    return pages

def coalesce_blocks(lines):
    blocks=[]; cur=[]
    for ln in lines:
        if ln.strip(): cur.append(ln)
        else:
            if cur: blocks.append("\n".join(cur).strip()); cur=[]
    if cur: blocks.append("\n".join(cur).strip())
    return blocks

def find_date(pages):
    for idx in [0,1,-1]:
        if abs(idx) <= len(pages):
            m = DATE_RE.search(pages[idx]["text"])
            if m:
                try:
                    return m.group(0), datetime.strptime(m.group(0), "%B %d, %Y").date().isoformat()
                except Exception:
                    return m.group(0), None
    return None, None

def find_place(first_page_lines):
    for ln in first_page_lines[:25]:
        if "WASHINGTON" in ln.upper():
            return "Washington"
    return "Washington"

def find_doc_title(pages):
    for ln in pages[0]["lines"][:100]:
        if re.search(r"U\.?S\.?\s+RELATIONS\s+WITH\s+THE\s+U\.?S\.?S\.?R\.?", ln, re.IGNORECASE):
            return "U.S. Relations with the USSR"
        if re.search(r"NATIONAL SECURITY DECISION DIRECTIVE\s+75", ln, re.IGNORECASE):
            return "National Security Decision Directive 75: U.S. Relations with the USSR"
    for ln in pages[0]["lines"][:40]:
        s=ln.strip()
        if len(s)>10 and UPPER_HEAD_RE.match(s) and not s.startswith("THE WHITE HOUSE"):
            return s.title()
    return "NSDD (auto-extracted)"

def collect_doc_classes(pages):
    seen=set()
    for p in pages:
        cand=(p["lines"][:8]+p["lines"][-8:]) if p["lines"] else []
        for ln in cand:
            for m in CLASS_RE.findall(ln or ""):
                seen.add(re.sub(r"\s+"," ", m.upper().strip()))
    return sorted(seen)

def extract_addressees(pages):
    addrs=[]
    for p in pages[:2]:
        lines=p["lines"]
        for i, ln in enumerate(lines):
            if re.search(r"^\s*MEMORANDUM\s+FOR", ln, re.IGNORECASE):
                j=i; buf=[]
                after=re.split(r":", ln, maxsplit=1)
                if len(after)==2 and after[1].strip(): buf.append(after[1].strip())
                j+=1
                while j<len(lines) and lines[j].strip():
                    buf.append(lines[j].strip()); j+=1
                text_block=" ".join(buf)
                items=re.split(r";|\s{2,}|,\s(?=[A-Z])", text_block)
                for it in items:
                    s=it.strip(" ;,")
                    if s and len(s)>2: addrs.append(s)
                return addrs
    return addrs

def extract_signer(pages):
    for p in pages:
        for i, ln in enumerate(p["lines"]):
            if re.search(r"FOR\s+THE\s+PRESIDENT", ln, re.IGNORECASE):
                nearby=" ".join(p["lines"][i:i+3])
                m=re.search(r"FOR\s+THE\s+PRESIDENT[:\s\-]*([A-Z][A-Za-z\.\s\-']{2,})", nearby, re.IGNORECASE)
                if m:
                    return re.sub(r"\s{2,}"," ", m.group(1)).strip()
    return None

def looks_like_head(text):
    raw=" ".join([ln.strip() for ln in text.splitlines()])
    if raw.lower().startswith("memorandum for"): return False
    if len(raw)<=110 and UPPER_HEAD_RE.match(raw) and sum(c.isupper() for c in raw) >= 0.6*len(re.sub(r"[^A-Za-z]","",raw) or "A"):
        return True
    if raw.endswith(":") and sum(c.isupper() for c in raw) > 0.5*len(re.sub(r"[^A-Za-z]","",raw) or "A"):
        return True
    return False

def annotate_para_classification(text):
    m=PARA_CLASS_RE.search(text)
    if m:
        cls=m.group(1)
        new_text=PARA_CLASS_RE.sub("", text, count=1).strip()
        return new_text, cls
    return text, None

def build_document_div(pages, volume_id, doc_xml_id, doc_number):
    from .tei import build_doc_div
    return build_doc_div(pages, volume_id, doc_xml_id, doc_number)
