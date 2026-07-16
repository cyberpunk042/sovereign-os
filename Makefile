# sovereign-os — operator Makefile.
# Common operator verbs as 'make <target>'. Mirrors CI exactly so
# devs can run identical commands locally.

SHELL := /bin/bash
PROFILE ?= sain-01

.PHONY: help setup dev-deps validate lint unit l3 l3-fast test smoke dry-run \
        preflight ci all clean clean-pyc dashboards-lint install install-units uninstall uninstall-units bins panel bootstrap \
        operator-sudo operator-sudo-uninstall man man-check demo-capture demo-preflight cockpit-wasm cockpit-wasm-all _require-pytest

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

dev-deps:  ## Install the Python test/lint deps (pytest pyyaml jsonschema) from requirements-dev.txt
	python3 -m pip install -r requirements-dev.txt

panel:  ## Start the operator panels (build configurator :8100 + runtime dashboard :8443) — no sudo
	scripts/operator/panel.sh

bootstrap:  ## One command: enable apt components + install ALL build-host deps (zfs, mkosi, qemu…). Self-sudo.
	scripts/install/bootstrap-host.sh

dev-setup:  ## Dev workstation: node + Claude Code + Claude VS Code extension + ~/.claude (GUI-aware)
	scripts/install/dev-workstation.sh

provision:  ## Resume setup in ONE command: bootstrap + dev tools + selfdef(build+enable) + operator-deps (idempotent)
	scripts/install/provision.sh

operator-sudo:  ## Install the SCOPED NOPASSWD sudoers drop-in (preview first: scripts/operator/operator-sudoers.sh --print)
	sudo scripts/operator/operator-sudoers.sh

operator-sudo-uninstall:  ## Remove the operator NOPASSWD sudoers drop-in
	sudo scripts/operator/operator-sudoers.sh --uninstall

validate:  ## Validate all profiles against schema + mixin merger
	scripts/validate-profiles.sh

_require-pytest:  # internal: fail with a friendly hint if pytest isn't installed
	@python3 -c 'import pytest' 2>/dev/null || { \
	  echo "pytest is not installed — run 'make dev-deps' (installs pytest pyyaml jsonschema from requirements-dev.txt)"; \
	  exit 1; }

lint: _require-pytest  ## Run all Layer 1 lint suites
	python3 -m pytest tests/schema tests/lint -v

unit: _require-pytest  ## Run all Layer 2 unit tests
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

dashboards-lint: _require-pytest  ## Verify Grafana dashboard JSONs + metric lockstep
	python3 -m pytest tests/lint/test_dashboard_json_valid.py tests/lint/test_dashboard_metrics_lockstep.py -v

demo-preflight:  ## Webapp increment preflight (branch-vs-main + app-shell sync + doc lints)
	bash scripts/webapp/preflight.sh

controls-audit:  ## Phase 3 read-only audit: which panel actions are exec-rail-wired vs copy-only
	python3 scripts/webapp/controls-audit.py $(if $(JSON),--json,)

cockpit-wasm:  ## Rebuild the committed cockpit wasm DEMO artifact (banner-only). Needs wasm32 target + wasm-bindgen 0.2.100. SMOKE=1 executes it in node
	bash cockpit-wasm/build.sh $(if $(SMOKE),--smoke,)

cockpit-wasm-all:  ## Build + verify the FULL cockpit bridge (all ~398 crates, --features bridges) in a temp dir; commits nothing (F-2026-001)
	bash cockpit-wasm/build.sh --verify-all

demo-capture:  ## Capture + verify DEMO-mode panels (needs a browser; NODE_PATH to playwright). PANELS=a,b or SDD=SDD-124; OUT=dir
	NODE_PATH=$${NODE_PATH:-/opt/node22/lib/node_modules} node scripts/webapp/demo-capture.mjs \
	  $(if $(PANELS),--panels $(PANELS),$(if $(SDD),--sdd $(SDD),--all)) $(if $(OUT),--out $(OUT),)

test: lint unit l3-fast  ## Standard test bundle: lint + unit + L3 fast (mirrors pre-commit hook)

ci: lint unit l3  ## Full CI bundle: lint + unit + ALL L3 (mirrors GitHub Actions)

dry-run:  ## Validate the build plan without executing any step
	SOVEREIGN_OS_PROFILE=$(PROFILE) scripts/build/orchestrate.sh run --dry-run

preflight:  ## Run pre-install hooks against the active profile
	SOVEREIGN_OS_PROFILE=$(PROFILE) scripts/build/orchestrate.sh preflight

smoke: validate l3-fast dry-run  ## Combined smoke: validate + L3 fast + orchestrator dry-run

all: setup test smoke  ## Full operator-side bootstrap-and-test loop

clean: clean-pyc  ## Remove build state + temporary files (incl. __pycache__)
	@rm -rf ~/.sovereign-os/build-state ~/.sovereign-os/log
	@rm -rf .sovereign-os/
	@echo "cleaned local sovereign-os state"

clean-pyc:  ## Remove Python bytecode cruft (__pycache__ dirs + *.pyc) from the tree
	@find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name '*.pyc' -delete 2>/dev/null || true
	@echo "cleaned __pycache__ + *.pyc"

PREFIX ?= /usr/local
SOVEREIGN_OS_LIB ?= $(PREFIX)/lib/sovereign-os
# Fish resolves vendor completions from its build-time data root, not PREFIX.
# Keep this platform path overrideable and DESTDIR-stageable.
FISH_COMPLETION_DIR ?= /usr/share/fish/vendor_completions.d

man:  ## Regenerate the committed sovereign-osctl(1) roff artifact (requires pandoc)
	bash scripts/docs/build-sovereign-osctl-manpage.sh build

man-check:  ## Verify the committed roff artifact matches the Markdown source
	bash scripts/docs/build-sovereign-osctl-manpage.sh check

install:  ## Install sovereign-osctl + manpages + command discovery to PREFIX (default: /usr/local)
	@echo "Installing to PREFIX=$(PREFIX)"
	@install -d "$(DESTDIR)$(PREFIX)/bin" \
	            "$(DESTDIR)$(SOVEREIGN_OS_LIB)/lib" \
	            "$(DESTDIR)$(SOVEREIGN_OS_LIB)/operator" \
	            "$(DESTDIR)$(SOVEREIGN_OS_LIB)/osctl.d" \
	            "$(DESTDIR)$(SOVEREIGN_OS_LIB)/share" \
	            "$(DESTDIR)$(SOVEREIGN_OS_LIB)/hooks" \
	            "$(DESTDIR)$(SOVEREIGN_OS_LIB)/whitelabel" \
	            "$(DESTDIR)$(SOVEREIGN_OS_LIB)/profiles" \
	            "$(DESTDIR)$(SOVEREIGN_OS_LIB)/inference" \
	            "$(DESTDIR)$(PREFIX)/share/man/man1" \
	            "$(DESTDIR)$(PREFIX)/share/bash-completion/completions" \
	            "$(DESTDIR)$(PREFIX)/share/zsh/site-functions" \
	            "$(DESTDIR)$(FISH_COMPLETION_DIR)"
	@install -m 755 scripts/sovereign-osctl "$(DESTDIR)$(PREFIX)/bin/sovereign-osctl"
	@install -m 644 VERSION "$(DESTDIR)$(SOVEREIGN_OS_LIB)/VERSION"
	@install -m 755 scripts/operator/command-discovery.py "$(DESTDIR)$(SOVEREIGN_OS_LIB)/operator/command-discovery.py"
	@install -m 644 scripts/osctl.d/*.sh "$(DESTDIR)$(SOVEREIGN_OS_LIB)/osctl.d/"
	@install -m 644 docs/man/sovereign-osctl-command-topics.json "$(DESTDIR)$(SOVEREIGN_OS_LIB)/share/sovereign-osctl-command-topics.json"
	@install -m 644 scripts/build/lib/common.sh "$(DESTDIR)$(SOVEREIGN_OS_LIB)/lib/common.sh"
	@install -m 644 scripts/build/lib/observability.sh "$(DESTDIR)$(SOVEREIGN_OS_LIB)/lib/observability.sh"
	@install -m 644 scripts/build/lib/state.sh "$(DESTDIR)$(SOVEREIGN_OS_LIB)/lib/state.sh"
	@install -m 644 scripts/build/lib/logging.sh "$(DESTDIR)$(SOVEREIGN_OS_LIB)/lib/logging.sh"
	@cp -r scripts/hooks/* "$(DESTDIR)$(SOVEREIGN_OS_LIB)/hooks/"
	@cp -r scripts/whitelabel "$(DESTDIR)$(SOVEREIGN_OS_LIB)/"
	@cp -r scripts/inference "$(DESTDIR)$(SOVEREIGN_OS_LIB)/"
	@cp -r profiles/* "$(DESTDIR)$(SOVEREIGN_OS_LIB)/profiles/"
	@cp -r whitelabel "$(DESTDIR)$(SOVEREIGN_OS_LIB)/"
	@install -m 644 docs/man/sovereign-osctl*.1 "$(DESTDIR)$(PREFIX)/share/man/man1/"
	@python3 scripts/operator/command-discovery.py --registry docs/man/sovereign-osctl-command-topics.json completion bash > "$(DESTDIR)$(PREFIX)/share/bash-completion/completions/sovereign-osctl"
	@python3 scripts/operator/command-discovery.py --registry docs/man/sovereign-osctl-command-topics.json completion zsh > "$(DESTDIR)$(PREFIX)/share/zsh/site-functions/_sovereign-osctl"
	@python3 scripts/operator/command-discovery.py --registry docs/man/sovereign-osctl-command-topics.json completion fish > "$(DESTDIR)$(FISH_COMPLETION_DIR)/sovereign-osctl.fish"
	@echo "Installed:"
	@echo "  $(DESTDIR)$(PREFIX)/bin/sovereign-osctl"
	@echo "  $(DESTDIR)$(SOVEREIGN_OS_LIB)/  (lib + hooks + profiles + inference + whitelabel)"
	@echo "  $(DESTDIR)$(PREFIX)/share/man/man1/sovereign-osctl*.1"
	@echo "  Bash/Zsh completions under $(DESTDIR)$(PREFIX)/share/; Fish under $(DESTDIR)$(FISH_COMPLETION_DIR)/"
	@echo "Note: this installs the shared libs + osctl. The systemd fleet (111 units)"
	@echo "      + the script trees the units reference is installed by 'make install-units'."

# Absolute install roots the systemd units reference in their ExecStart lines.
# These are FIXED, not PREFIX-relative: the shipped unit files hardcode them, so
# install-units stages the script trees at exactly these paths (honoring DESTDIR
# for staged / packaged installs). The two-prefix doctrine (operator-API scripts
# under /usr/local/lib; hook/inference/hardware scripts under the /opt vendor tree)
# is documented in systemd/system/README.md and enforced by
# tests/lint/test_systemd_install_coverage.py (every unit ExecStart must stay
# within this set, and its script must exist in-repo).
SOVEREIGN_OS_OPT   ?= /opt/sovereign-os
SOVEREIGN_OS_OPLIB ?= /usr/local/lib/sovereign-os
SYSTEMD_UNIT_DIR   ?= /etc/systemd/system

install-units:  ## Install the full systemd unit fleet + the script trees the units reference (DESTDIR-stageable; run daemon-reload + enable after)
	@echo "Installing systemd fleet to $(DESTDIR)$(SYSTEMD_UNIT_DIR)"
	@echo "  operator-API scripts -> $(DESTDIR)$(SOVEREIGN_OS_OPLIB)/scripts/operator"
	@echo "  hook/inference/hardware scripts -> $(DESTDIR)$(SOVEREIGN_OS_OPT)/scripts/{hooks,inference,hardware}"
	@install -d "$(DESTDIR)$(SYSTEMD_UNIT_DIR)"
	@install -m 644 systemd/system/*.service systemd/system/*.timer systemd/system/*.target "$(DESTDIR)$(SYSTEMD_UNIT_DIR)/"
	@install -d "$(DESTDIR)$(SOVEREIGN_OS_OPLIB)/scripts/operator" \
	            "$(DESTDIR)$(SOVEREIGN_OS_OPT)/scripts/hooks" \
	            "$(DESTDIR)$(SOVEREIGN_OS_OPT)/scripts/inference" \
	            "$(DESTDIR)$(SOVEREIGN_OS_OPT)/scripts/hardware"
	@cp -r scripts/operator/*  "$(DESTDIR)$(SOVEREIGN_OS_OPLIB)/scripts/operator/"
	@cp -r scripts/hooks/*     "$(DESTDIR)$(SOVEREIGN_OS_OPT)/scripts/hooks/"
	@cp -r scripts/inference/* "$(DESTDIR)$(SOVEREIGN_OS_OPT)/scripts/inference/"
	@cp -r scripts/hardware/*  "$(DESTDIR)$(SOVEREIGN_OS_OPT)/scripts/hardware/"
	@echo "Installed $(words $(wildcard systemd/system/*.service)) service + $(words $(wildcard systemd/system/*.timer)) timer + $(words $(wildcard systemd/system/*.target)) target units + their script trees."
	@echo "Activate as root, selectively per profile:"
	@echo "  sudo systemctl daemon-reload"
	@echo "  sudo systemctl enable --now <unit>   # e.g. sovereign-gatewayd.service"

# SDD-043 Phase 1: the Rust binaries compile for the active profile's CPU
# ISA (VNNI/BF16/popcnt/… derived from hardware.cpu.features by
# scripts/build/cpu-features.py), so the inference crates actually exploit
# the declared hardware. Set SOVEREIGN_OS_BINS_TUNE=0 for a portable build
# (e.g. cross-host CI, or a build host that isn't the target CPU).
SOVEREIGN_OS_BINS_TUNE ?= 1

bins:  ## Build + install the Rust binaries (CPU-tuned for PROFILE) to PREFIX/bin
	@if [ "$(SOVEREIGN_OS_BINS_TUNE)" = "1" ]; then \
	   tune="$$(scripts/build/cpu-features.py --profile $(PROFILE) --verify)"; \
	   echo "Building Rust binaries (release) — CPU-tuned for $(PROFILE):"; \
	   echo "  RUSTFLAGS += $$tune"; \
	 else tune=""; echo "Building Rust binaries (release) — portable (SOVEREIGN_OS_BINS_TUNE=0)"; fi; \
	 RUSTFLAGS="$${RUSTFLAGS:+$$RUSTFLAGS }$$tune" \
	   cargo build --release -p sovereign-telemetry -p sovereign-resource-control -p sovereign-gatewayd
	@install -d "$(DESTDIR)$(PREFIX)/bin"
	@install -m 755 target/release/sovereign-telemetry "$(DESTDIR)$(PREFIX)/bin/sovereign-telemetry"
	@install -m 755 target/release/sovereign-resource-control "$(DESTDIR)$(PREFIX)/bin/sovereign-resource-control"
	@install -m 755 target/release/sovereign-gatewayd "$(DESTDIR)$(PREFIX)/bin/sovereign-gatewayd"
	@echo "Installed:"
	@echo "  $(DESTDIR)$(PREFIX)/bin/sovereign-telemetry        (sovereign-telemetry-textfile.timer)"
	@echo "  $(DESTDIR)$(PREFIX)/bin/sovereign-resource-control"
	@echo "  $(DESTDIR)$(PREFIX)/bin/sovereign-gatewayd         (sovereign-gatewayd.service)"

uninstall:  ## Remove sovereign-osctl + manpages + completions + the `bins` binaries from PREFIX
	@rm -f  "$(DESTDIR)$(PREFIX)/bin/sovereign-osctl"
	@rm -f  "$(DESTDIR)$(PREFIX)/share/man/man1/sovereign-osctl"*.1
	@rm -f  "$(DESTDIR)$(PREFIX)/share/bash-completion/completions/sovereign-osctl"
	@rm -f  "$(DESTDIR)$(PREFIX)/share/zsh/site-functions/_sovereign-osctl"
	@rm -f  "$(DESTDIR)$(FISH_COMPLETION_DIR)/sovereign-osctl.fish"
	@rm -rf "$(DESTDIR)$(SOVEREIGN_OS_LIB)"
	@rm -f  "$(DESTDIR)$(PREFIX)/bin/sovereign-telemetry"
	@rm -f  "$(DESTDIR)$(PREFIX)/bin/sovereign-resource-control"
	@rm -f  "$(DESTDIR)$(PREFIX)/bin/sovereign-gatewayd"
	@echo "Uninstalled sovereign-osctl + lib + manpage + bins from PREFIX=$(PREFIX)"

uninstall-units:  ## Remove the systemd unit files + the install-units script trees (disable first: systemctl disable --now <unit>)
	@for u in systemd/system/*.service systemd/system/*.timer systemd/system/*.target; do \
	  rm -f "$(DESTDIR)$(SYSTEMD_UNIT_DIR)/$$(basename $$u)"; \
	done
	@rm -rf "$(DESTDIR)$(SOVEREIGN_OS_OPLIB)/scripts/operator" \
	        "$(DESTDIR)$(SOVEREIGN_OS_OPT)/scripts/hooks" \
	        "$(DESTDIR)$(SOVEREIGN_OS_OPT)/scripts/inference" \
	        "$(DESTDIR)$(SOVEREIGN_OS_OPT)/scripts/hardware"
	@echo "Removed the systemd fleet unit files + install-units script trees (run 'systemctl daemon-reload')."
