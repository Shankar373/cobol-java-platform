# SYSTEMAOPS UNIVERSALITY AUDIT

Repository: https://github.com/Shankar373/cobol-java-modernization.git
Commit: 2c86b1f74f8fe64481fc7d18f1c095d92402caf0

COBOL DISCOVERY:
DYNAMIC (Successfully walked and discovered INVOICE01.cob, TAXCALC99.cob, and INVREC01.cpy)

COBOL → JAVA:
HARDCODED (Compiles via Opensource COBOL 4J Docker container but has direct compile-time/runtime dependencies on libcobj.jar)

SEMANTIC ANALYSIS:
DYNAMIC (Parser correctly generated generic AST and Semantic IR models)

DEPENDENCY ANALYSIS:
DYNAMIC (Dependencies engine resolved static CALL to TAXCALC99 and copybook INVREC01)

NATIVE JAVA:
NOT VERIFIED (Generated Java imports jp.osscons.* wrappers and cannot compile or execute without libcobj.jar)

SPRING BOOT:
PARTIAL (Scaffolds Spring structure, but compilation fails due to hardcoded seeding of Policy domain classes)

SPRING BATCH:
PARTIAL (Item reader layout is hardcoded to standard benchmark templates)

JPA:
PARTIAL (Entities are generated but seed configurations assume benchmark-specific tables)

REST:
PARTIAL (REST endpoint routes are configured exclusively to query seeded databases)

EQUIVALENCE:
VERIFIED (Passed for GnuCOBOL vs transpiled Java, but fails to execute on modernized refactored Spring Boot code)

OVERALL GENERICITY:
NOT VERIFIED

FIRST GENERICITY FAILURE:

Stage: refactor
File: cobol_migrate.py
Function: stage_refactor / write_data_seed_runner
Line: 5582
Reason: Hardcoded seeding logic checks entrypoint string names. If "BCMAIN" is absent, it assumes Claims PAS shape and attempts to seed com.systema.modernized.domain.Policy entities, failing compilation on generic repository runs where Policy is not defined.
