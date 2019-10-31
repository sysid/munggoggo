#!/bin/bash
# pytest test_agent.py -k test_agent_basic -v -s
set -x

package=munggoggo

pipenv run python -m pytest --cov=$package munggoggo/tests
