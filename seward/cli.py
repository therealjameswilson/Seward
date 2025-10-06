import argparse, sys, io, re
from lxml import etree
from .parser import extract_pages, build_document_div
from .tei import wrap_as_tei, append_to_volume
from .validate import validate_with_schemas

def main():
    ap = argparse.ArgumentParser(prog="seward", description="Seward — FRUS TEI Converter")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_convert = sub.add_parser("convert", help="Convert a PDF into standalone TEI")
    ap_convert.add_argument("--pdf", required=True, help="Path to input PDF")
    ap_convert.add_argument("--volume-id", default="frus1981-88v03", help="Volume xml:id (default: frus1981-88v03)")
    ap_convert.add_argument("--doc-id", default="dAUTO", help="Document xml:id (default: dAUTO)")
    ap_convert.add_argument("--doc-number", default="AUTO", help="Document number (default: AUTO)")
    ap_convert.add_argument("--out", required=True, help="Path to output XML")
    ap_convert.add_argument("--rng", help="Optional path to frus.rng")
    ap_convert.add_argument("--sch", help="Optional path to frus.sch")

    ap_append = sub.add_parser("append", help="Append a PDF-converted doc to an existing volume (auto-increment ids)")
    ap_append.add_argument("--pdf", required=True, help="Path to input PDF")
    ap_append.add_argument("--volume", required=True, help="Path to existing FRUS volume XML to append into")
    ap_append.add_argument("--out", required=True, help="Path to output (updated) volume XML")
    ap_append.add_argument("--rng", help="Optional path to frus.rng")
    ap_append.add_argument("--sch", help="Optional path to frus.sch")

    args = ap.parse_args()

    if args.cmd == "convert":
        pages = extract_pages(args.pdf)
        div = build_document_div(pages, args.volume_id, args.doc_id, args.doc_number)
        tei = wrap_as_tei(div, args.volume_id)
        data = etree.tostring(tei, pretty_print=True, xml_declaration=True, encoding="utf-8")
        open(args.out, "wb").write(data)
        report = validate_with_schemas(data,
            open(args.rng, "rb").read() if args.rng else None,
            open(args.sch, "rb").read() if args.sch else None)
        print(report)
        return 0

    if args.cmd == "append":
        pages = extract_pages(args.pdf)
        div = build_document_div(pages, "frus-volume", "dAUTO", "AUTO")  # placeholders overridden in append
        volume_bytes = open(args.volume, "rb").read()
        updated = append_to_volume(volume_bytes, etree.fromstring(etree.tostring(div)))
        open(args.out, "wb").write(updated)
        report = validate_with_schemas(updated,
            open(args.rng, "rb").read() if args.rng else None,
            open(args.sch, "rb").read() if args.sch else None)
        print(report)
        return 0

if __name__ == "__main__":
    sys.exit(main())
