# Use project venv when present; override with: make PYTHON=/path/to/python lint
VENV := $(CURDIR)/venv/bin/python
PYTHON := $(if $(wildcard $(VENV)),$(VENV),python3)

# English diagnostics from mypy/basedpyright
export LANG := C.UTF-8
export LC_ALL := C.UTF-8
export LANGUAGE := C

.PHONY: help format lint stubs install install-dev uninstall build native native-rebuild native-fast clean dev run test

help:
	@echo "format          ruff format + isort"
	@echo "lint            mypy + basedpyright + named-args + explicit-types + stub check"
	@echo "stubs           regenerate orcsome3_backend.pyi from the Cython backend"
	@echo "dev             venv + deps + native backend (does not pip-install orcsome3)"
	@echo "run             python -m orcsome3 from this tree (needs: make dev)"
	@echo "test            unittest (X tests skip if DISPLAY cannot be opened)"
	@echo "install         pip install ."
	@echo "install-dev     pip install -e '.[dev]'"
	@echo "uninstall       pip uninstall orcsome3"
	@echo "build           sdist + wheel (needs: pip install build)"
	@echo "native          build Cython backend (static libs)"
	@echo "native-rebuild  wipe cached libs and rebuild native backend"
	@echo "native-fast     re-cythonize/link only (needs a prior native build)"
	@echo "clean           remove build artifacts and caches"

format:
	$(PYTHON) -m ruff check --fix .
	$(PYTHON) -m ruff format .

stubs:
	$(PYTHON) tools/generate_backend_stub.py

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m mypy orcsome3 tools tests
	$(PYTHON) -m basedpyright --pythonpath $(PYTHON) orcsome3 setup.py orcsome3_backend.pyi tools tests
	$(PYTHON) tools/check_named_args.py
	$(PYTHON) tools/check_explicit_types.py
	$(PYTHON) tools/generate_backend_stub.py --check

test:
	$(PYTHON) -m unittest discover -s tests -v

dev:
	@test -x "$(VENV)" || python3 -m venv "$(CURDIR)/venv"
	$(VENV) -m pip install -q dbus-next typing_extensions "Cython>=3.0" mypy basedpyright ruff
	@if [ -d orcsome3_built_libraries ]; then \
		$(MAKE) native-fast PYTHON="$(VENV)"; \
	else \
		$(MAKE) native PYTHON="$(VENV)"; \
	fi
	@echo "Ready. Run: make run"

run:
	$(PYTHON) -m orcsome3 $(ARGS)

install:
	$(PYTHON) -m pip install .

install-dev:
	$(PYTHON) -m pip install -e ".[dev]"

uninstall:
	$(PYTHON) -m pip uninstall -y orcsome3

build:
	$(PYTHON) -m build

native:
	$(PYTHON) -m orcsome3.libs.build --build-dir .

native-rebuild:
	$(PYTHON) -m orcsome3.libs.build --build-dir . --force-rebuild

native-fast:
	$(PYTHON) -m orcsome3.libs.build --build-dir . --skip-build-external-libs

clean:
	rm -rf dist build .eggs *.egg-info orcsome3_built_libraries .mypy_cache .ruff_cache
	rm -f orcsome3_backend*.so
