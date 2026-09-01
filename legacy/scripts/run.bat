@echo off
if not exist bin\claims_core.exe exit /b 1
if exist data\work\policy.dat del /q data\work\policy.dat
if exist data\work\customer.dat del /q data\work\customer.dat
if exist data\out\claim-audit.dat del /q data\out\claim-audit.dat
if exist data\out\claim-exceptions.dat del /q data\out\claim-exceptions.dat
if exist data\out\eod-claims-report.txt del /q data\out\eod-claims-report.txt
bin\claims_core.exe
type data\out\eod-claims-report.txt
