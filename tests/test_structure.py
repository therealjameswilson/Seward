from lxml import etree

def test_has_doc_div():
    xml = open('examples/nsdd75_tei_example.xml','rb').read()
    doc = etree.fromstring(xml)
    ns = {"tei":"http://www.tei-c.org/ns/1.0"}
    divs = doc.xpath("//tei:div[@type='document']", namespaces=ns)
    assert divs, "No document div found"
    heads = doc.xpath("//tei:div[@type='document']/tei:head", namespaces=ns)
    assert heads and heads[0].text, "Head missing or empty"
