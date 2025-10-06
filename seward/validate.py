from lxml import etree

def validate_with_schemas(tei_bytes, rng_bytes=None, sch_bytes=None):
    report=[]
    try:
        doc=etree.fromstring(tei_bytes)
    except Exception as e:
        return f"XML parse error: {e}"

    if rng_bytes:
        try:
            relaxng = etree.RelaxNG(etree.fromstring(rng_bytes))
            ok = relaxng.validate(doc)
            report.append("Relax NG: PASS" if ok else f"Relax NG: FAIL — {relaxng.error_log.last_error}")
        except Exception as e:
            report.append(f"Relax NG error: {e}")
    else:
        report.append("Relax NG: skipped (no schema provided)")
    if sch_bytes:
        try:
            schematron = etree.Schematron(etree.fromstring(sch_bytes))
            ok = schematron.validate(doc)
            report.append("Schematron: PASS" if ok else "Schematron: FAIL — see schema rules")
        except Exception as e:
            report.append(f"Schematron error: {e}")
    else:
        report.append("Schematron: skipped (no schema provided)")
    return "\n".join(report)
