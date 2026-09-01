#!/usr/bin/env bash
set -e
mkdir -p bin
cobc -x -free -I copybooks -o bin/claims_core src/CCMAIN01.cob src/CCLOAD01.cob src/CCPROC01.cob src/CCREPT01.cob
echo "ClaimsCore build successful."
