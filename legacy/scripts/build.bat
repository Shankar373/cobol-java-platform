@echo off
if not exist bin mkdir bin
cobc -x -free -I copybooks -o bin\claims_core.exe src\CCMAIN01.cob src\CCLOAD01.cob src\CCPROC01.cob src\CCREPT01.cob
