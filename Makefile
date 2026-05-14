.PHONY: all clean validate run

all: run validate

run:
	uv run python3 pipeline.py

validate:
	uv run python3 validate.py

clean:
	rm -rf data/ specs/ ledgers/ metrics.json critiques.json report.md \
	       comparative_brief.md llm_calls.jsonl data_manifest.json \
	       walk_forward.json parameter_sensitivity.json adversarial_scenarios.json
