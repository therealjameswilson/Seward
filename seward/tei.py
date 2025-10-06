import re, io
from lxml import etree
from .parser import (
    XMLNS, TEINS,
    coalesce_blocks, LETTER_HEAD_RE, NUMBER_POINT_RE,
    find_date, find_place, find_doc_title, collect_doc_classes,
    extract_addressees, extract_signer, annotate_para_classification, looks_like_head
)

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
    import re
    nums=[]
    for d in doc_ids:
        m=re.match(r"d(\d+)$", d or "")
        if m:
            nums.append(int(m.group(1)))
    next_num = max(nums)+1 if nums else 1
    return f"d{next_num}", next_num

def append_to_volume(existing_xml_bytes, new_div):
    import io
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
