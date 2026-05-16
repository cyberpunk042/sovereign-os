# sovereign-os — operator Makefile.
# Common operator verbs as 'make <target>'. Mirrors CI exactly so
# devs can run identical commands locally.

SHELL := /bin/bash
PROFILE ?= sain-01

.PHONY: help setup validate lint unit l3 l3-fast test smoke dry-run \
        preflight ci all clean dashboards-lint

.DEFAULT_GOAL := help

help:  ## Show this help
	@echo "sovereign-os operator Makefile"
	@echo
	@echo "Common targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | sort \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo
	@echo "Override the profile: 'make <target> PROFILE=<id>' (default: sain-01)"
	@echo "Available profiles: $$(ls profiles/*.yaml 2>/dev/null | xargs -n1 basename | sed 's/.yaml$$//' | tr '\n' ' ')"

setup:  ## One-command fresh-clone bootstrap (git hooks + deps + smoke)
	scripts/setup.sh

validate:  ## Validate all profiles against schema + mixin merger
	scripts/validate-profiles.sh

lint:  ## Run all Layer 1 lint suites
	python3 -m pytest tests/schema tests/lint -v

unit:  ## Run all Layer 2 unit tests
	python3 -m pytest tests/unit -v

l3:  ## Run all Layer 3 nspawn-style tests (full suite, ~30+ seconds)
	@set -e; for t in tests/nspawn/test_*.sh; do \
	  echo "==> $$(basename $$t)"; \
	  bash "$$t" >/dev/null && echo "    PASS" || { echo "    FAIL"; exit 1; }; \
	done
	@echo "all $(words $(wildcard tests/nspawn/test_*.sh)) L3 tests passed"

l3-fast:  ## Run a fast representative subset of L3 tests (~5 seconds)
	@for t in tests/nspawn/test_common_lib.sh tests/nspawn/test_state_lib.sh \
	          tests/nspawn/test_observability_lib.sh tests/nspawn/test_orchestrator_dry_run.sh; do \
	  echo "==> $$(basename $$t)"; \
	  bash "$$t" >/dev/null && echo "    PASS" || { echo "    FAIL"; exit 1; }; \
	done

dashboards-lint:  ## Verify Grafana dashboard JSONs + metric lockstep
	python3 -m pytest tests/lint/test_dashboard_json_valid.py tests/lint/test_dashboard_metrics_lockstep.py -v

test: lint unit l3-fast  ## Standard test bundle: lint + unit + L3 fast (mirrors pre-commit hook)

ci: lint unit l3  ## Full CI bundle: lint + unit + ALL L3 (mirrors GitHub Actions)

dry-run:  ## Validate the build plan without executing any step
	SOVEREIGN_OS_PROFILE=$(PROFILE) scripts/build/orchestrate.sh run --dry-run

preflight:  ## Run pre-install hooks against the active profile
	SOVEREIGN_OS_PROFILE=$(PROFILE) scripts/build/orchestrate.sh preflight

smoke: validate l3-fast dry-run  ## Combined smoke: validate + L3 fast + orchestrator dry-run

all: setup test smoke  ## Full operator-side bootstrap-and-test loop

clean:  ## Remove build state + temporary files
	@rm -rf ~/.sovereign-os/build-state ~/.sovereign-os/log
	@rm -rf .sovereign-os/
	@echo "cleaned local sovereign-os state"
