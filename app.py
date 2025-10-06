import io, re
from datetime import datetime
import streamlit as st
from lxml import etree
import pdfplumber

XMLNS = "http://www.w3.org/XML/1998/namespace"
TEINS = "{http://www.tei-c.org/ns/1.0}"

# --- Helpers (same logic as backend) ---
MONTHS = r"(January|February|March|April|May|June|July|August|September|October|November|December)"
DATE_RE = re.compile(rf"{MONTHS}\s+\d{{1,2}},\s*\d{{4}}", re.IGNORECASE)
CLASS_RE = re.compile(r"\b(SENSITIVE|SECRET|TOP SECRET|CONFIDENTIAL|UNCLASSIFIED|NOFORN|OADR|E\.O\.\s*12[0-9]{{3}}|EO\s*12[0-9]{{3}})\b", re.IGNORECASE)
PARA_CLASS_RE = re.compile(r"^\s*\((TS|S|C|U)\)\s*")
UPPER_HEAD_RE = re.compile(r"^[A-Z0-9 ,\-\.\'&:;\/\(\)]+$")
LETTER_HEAD_RE = re.compile(r"^\s*([A-Z])\.\s+(.*)")
NUMBER_POINT_RE = re.compile(r"^\s*(\d+)\.\s+(.*)")

def extract_pages(pdf_bytes):
    pages=[]
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
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

def build_doc_div(pages, volume_id, doc_xml_id, doc_number):
    date_human, date_iso = find_date(pages)
    place = find_place(pages[0]["lines"])
    doc_title = find_doc_title(pages)
    classes = collect_doc_classes(pages)
    addressees = extract_addressees(pages)
    signer = extract_signer(pages)

    div = etree.Element(TEINS + "div", attrib={"type":"document"})
    div.set("{%s}id" % XMLNS, doc_xml_id)

    etree.SubElement(div, TEINS + "head").text = doc_title
    etree.SubElement(div, TEINS + "docNumber").text = str(doc_number)
    etree.SubElement(div, TEINS + "docTitle").text = doc_title
    date_el = etree.SubElement(div, TEINS + "docDate")
    if date_iso: date_el.set("when", date_iso)
    date_el.text = f"{place}, {date_human}" if date_human else place
    etree.SubElement(div, TEINS + "classification").text = "; ".join(classes) if classes else "UNSPECIFIED"

    if addressees:
        lst=etree.SubElement(div, TEINS + "list")
        for it in addressees:
            etree.SubElement(lst, TEINS + "item").text = it

    if signer:
        etree.SubElement(div, TEINS + "signed").text = f"FOR THE PRESIDENT: {signer}"

    opener = etree.Element(TEINS + "opener")
    dl = etree.SubElement(opener, TEINS + "dateline"); dl.text = date_el.text
    if addressees:
        salute = etree.SubElement(opener, TEINS + "salute")
        salute.text = "MEMORANDUM FOR: " + "; ".join(addressees)
    if signer:
        s = etree.SubElement(opener, TEINS + "signed"); s.text = f"FOR THE PRESIDENT: {signer}"
    fixed_order=["head","docNumber","docTitle","docDate","classification","list"]
    idx=0
    for child in list(div):
        if etree.QName(child).localname in fixed_order: idx+=1
        else: break
    div.insert(idx, opener)

    current_section_div=None
    current_list=None
    for p in pages:
        etree.SubElement(div, TEINS + "pb", n=str(p["n"]))
        blocks=coalesce_blocks(p["lines"])
        for block in blocks:
            mL = LETTER_HEAD_RE.match(block)
            if mL and len(mL.group(2))>0 and len(mL.group(2))<140:
                current_section_div = etree.SubElement(div, TEINS + "div", {"type":"section", "n":mL.group(1)})
                etree.SubElement(current_section_div, TEINS + "head", level="3").text = mL.group(2).strip()
                current_list=None
                continue
            mN = NUMBER_POINT_RE.match(block)
            if mN and current_section_div is not None:
                if current_list is None:
                    current_list = etree.SubElement(current_section_div, TEINS + "list", {"type":"ordered"})
                it=etree.SubElement(current_list, TEINS + "item", n=mN.group(1))
                txt, pcl = annotate_para_classification(mN.group(2).strip())
                pel = etree.SubElement(it, TEINS + "p")
                if pcl: pel.set("ana", f"#{pcl}")
                pel.text = txt
                continue
            if looks_like_head(block):
                etree.SubElement(div, TEINS + "head", level="2").text = re.sub(r"\s+"," ", block).strip().rstrip(":")
                current_list=None
                continue
            txt, pcl = annotate_para_classification(block)
            target = current_section_div if current_section_div is not None else div
            pel = etree.SubElement(target, TEINS + "p")
            if pcl: pel.set("ana", f"#{pcl}")
            pel.text = txt

    etree.SubElement(div, TEINS + "note", type="source").text = "Provenance: Ronald Reagan Presidential Library (Matlock Files)."
    return div

def wrap_as_tei(div, volume_id):
    TEI = etree.Element(TEINS + "TEI")
    TEI.set("{%s}id" % XMLNS, volume_id)
    text = etree.SubElement(TEI, TEINS + "text")
    body = etree.SubElement(text, TEINS + "body")
    body.append(div)
    return TEI

def compute_next_doc_id(doc_ids):
    nums=[]
    for d in doc_ids:
        m=re.match(r"d(\d+)$", d or "")
        if m:
            nums.append(int(m.group(1)))
    next_num = max(nums)+1 if nums else 1
    return f"d{next_num}", next_num

def append_to_volume(existing_xml_bytes, new_div):
    parser=etree.XMLParser(remove_blank_text=False)
    vol=etree.parse(io.BytesIO(existing_xml_bytes), parser)
    ns={"tei":"http://www.tei-c.org/ns/1.0"}
    body=vol.xpath("//tei:text/tei:body", namespaces=ns)[0]
    existing_ids=[el.get("{%s}id" % XMLNS) for el in body.xpath(".//tei:div[@type='document']", namespaces=ns)]
    existing_ids=[i for i in existing_ids if i]
    new_id, new_num = compute_next_doc_id(existing_ids)
    new_div.set("{%s}id" % XMLNS, new_id)
    dn = new_div.find(f".//{TEINS}docNumber")
    if dn is not None: dn.text = str(new_num)
    body.append(new_div)
    return etree.tostring(vol, pretty_print=True, xml_declaration=True, encoding="utf-8")

def validate_with_schemas(tei_bytes, rng_bytes=None, sch_bytes=None):
    report=[]
    doc=etree.fromstring(tei_bytes)
    if rng_bytes:
        try:
            relaxng = etree.RelaxNG(etree.fromstring(rng_bytes))
            ok = relaxng.validate(doc)
            report.append("Relax NG: PASS" if ok else f"Relax NG: FAIL — {relaxng.error_log.last_error}")
        except Exception as e:
            report.append(f"Relax NG error: {e}")
    else:
        report.append("Relax NG: skipped (no schema uploaded)")
    if sch_bytes:
        try:
            schematron = etree.Schematron(etree.fromstring(sch_bytes))
            ok = schematron.validate(doc)
            report.append("Schematron: PASS" if ok else "Schematron: FAIL — see schema rules")
        except Exception as e:
            report.append(f"Schematron error: {e}")
    else:
        report.append("Schematron: skipped (no schema uploaded)")
    return "\n".join(report)

# --- UI ---
st.set_page_config(page_title="Seward — FRUS TEI Converter", layout="centered")
st.title("Seward — FRUS TEI Converter (v0.6)")

pdf_file = st.file_uploader("Upload declassified PDF", type=["pdf"])
col1, col2 = st.columns(2)
with col1:
    volume_id = st.text_input("Volume xml:id", value="frus1981-88v03")
    auto_increment = st.checkbox("Auto-increment doc xml:id in existing volume", value=True)
with col2:
    doc_xml_id = st.text_input("Doc xml:id (if not auto)", value="dAUTO")
    doc_number = st.text_input("Doc number (if not auto)", value="AUTO")

existing_volume = st.file_uploader("Optionally upload existing FRUS volume XML to append", type=["xml"])
rng_upload = st.file_uploader("Optionally upload frus.rng (Relax NG)", type=["rng"])
sch_upload = st.file_uploader("Optionally upload frus.sch (Schematron)", type=["sch","xml"])

if st.button("Convert"):
    if not pdf_file:
        st.error("Please upload a PDF.")
    else:
        pages = extract_pages(pdf_file.read())
        div = build_doc_div(pages, volume_id, doc_xml_id, doc_number)
        if existing_volume:
            tei_bytes = append_to_volume(existing_volume.read(), etree.fromstring(etree.tostring(div)))
            st.success("Appended to existing volume.")
            st.download_button("Download updated volume XML", data=tei_bytes, file_name=f"{volume_id}_updated.xml", mime="application/xml")
            report = validate_with_schemas(tei_bytes, rng_upload.read() if rng_upload else None, sch_upload.read() if sch_upload else None)
            st.text_area("Validation report", report, height=150)
        else:
            tei = wrap_as_tei(div, volume_id)
            tei_bytes = etree.tostring(tei, pretty_print=True, xml_declaration=True, encoding="utf-8")
            st.download_button("Download TEI XML", data=tei_bytes, file_name="seward_output.xml", mime="application/xml")
            report = validate_with_schemas(tei_bytes, rng_upload.read() if rng_upload else None, sch_upload.read() if sch_upload else None)
            st.text_area("Validation report", report, height=150)
