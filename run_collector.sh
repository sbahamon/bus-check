#!/usr/bin/env bash
cd "$(dirname "$0")"
export PYTHONPATH=src
exec .venv/bin/python -u -m bus_check.collector.headway_collector
