.PHONY: setup ui test lint convert append

setup:
	python -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -r requirements.txt

ui:
	streamlit run app.py

test:
	pytest -q

lint:
	python -m compileall seward

convert:
	python -m seward.cli convert --pdf data/example.pdf --out out/tei.xml

append:
	python -m seward.cli append --pdf data/example.pdf --volume examples/frus1981-88v03_with_d260.xml --out out/updated_volume.xml
