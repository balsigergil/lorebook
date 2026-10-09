#!/usr/bin/bash

uv run ruff check --force-exclude --fix --select I,F401 "$1"
uv run ruff format --force-exclude "$1"
