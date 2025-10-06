# Seward — FRUS TEI Converter (Prototype)

Seward converts declassified government PDFs (e.g., NSDDs, NSC memos) into **FRUS‑flavored TEI P5**, ready for validation and publication on [history.state.gov](https://history.state.gov).

## Features
- PDF → TEI with page breaks, opener (dateline/salute/signed), doc metadata, and paragraph‑level classification markers.
- Heuristics for **lettered sections** (A./B./C.) and **numbered sub‑points**.
- **Addressee parsing** (MEMORANDUM FOR …) into both `<list>` and `<salute>`.
- **Exporter** to append a new document to an **existing FRUS volume**, with **auto‑incremented** `xml:id` (`d###`) and `docNumber`.
- Optional **Relax NG / Schematron** validation (drop `frus.rng` and/or `frus.sch` into `schema/` or upload via UI).

> This is a working prototype meant for historians/compilers; rules are modular and can be tightened per volume and doc type.

---

## Quick Start

```bash
git clone https://github.com/<you>/Seward.git
cd Seward
make setup
make ui
```

Then open the local URL Streamlit prints (usually `http://localhost:8501`) and drop in a PDF.

### CLI
```bash
# Convert a PDF to standalone TEI
python -m seward.cli convert --pdf data/example.pdf --out out/tei.xml

# Append into an existing volume (auto-increment ids and docNumber)
python -m seward.cli append --pdf data/example.pdf --volume examples/frus1981-88v03_with_d260.xml --out out/updated_volume.xml
```

### Validation
Place your schemas under `schema/`:
```
schema/
 ├── frus.rng
 └── frus.sch
```
They’ll be used by both the UI and CLI to run **Relax NG** and **Schematron** checks.

---

## Repository Layout

```
.
├── app.py                     # Streamlit UI (drag-drop PDF -> TEI/volume + validation)
├── seward/
│   ├── __init__.py
│   ├── cli.py                 # CLI entry points (convert/append)
│   ├── parser.py              # PDF parsing + heuristics
│   ├── tei.py                 # TEI builders + exporters
│   └── validate.py            # RNG/Schematron validation
├── schema/                    # (optional) put frus.rng / frus.sch here
│   └── .gitkeep
├── examples/                  # Example outputs and fixtures
│   ├── frus1981-88v03_with_d260.xml
│   └── nsdd75_tei_example.xml
├── tests/
│   └── test_structure.py
├── requirements.txt
├── Makefile
├── LICENSE
├── README.md
├── .gitignore
└── .github/workflows/ci.yml
```

---

## Notes & Roadmap
- Tune regexes/rules in `parser.py` and extend with YAML rule packs per doc type.
- Add facsimile mapping (`<facsimile>`, `<surface>`, `<zone>`) for stamps/redactions.
- Integrate official FRUS ODD/RNG/Schematron once approved.
- Add batch mode (folder of PDFs → many docs appended in one run).

Contributions welcome via PRs.
