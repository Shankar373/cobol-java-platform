#!/usr/bin/env bash
set -e
rm -f data/work/policy.dat data/work/customer.dat data/out/claim-audit.dat data/out/claim-exceptions.dat data/out/eod-claims-report.txt
./bin/claims_core
cat data/out/eod-claims-report.txt
