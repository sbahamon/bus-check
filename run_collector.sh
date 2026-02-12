#!/usr/bin/env bash
cd /Users/steffanybahamon/Desktop/projects/bus-check
export PYTHONPATH=src
exec .venv/bin/python -u -m bus_check.collector.headway_collector
