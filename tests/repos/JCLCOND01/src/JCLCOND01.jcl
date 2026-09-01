//JCLCOND01 JOB (ACCT),'COND_TEST'
//* Step 1: Sets RC=4
//STEP1    EXEC PGM=COBPROG1
//* Step 2: COND=(4,EQ,STEP1) -> (4 EQ 4 is true -> BYPASS)
//STEP2    EXEC PGM=COBPROG2,COND=(4,EQ,STEP1)
//* Step 3: COND=(0,NE,STEP1) -> (0 NE 4 is true -> BYPASS)
//STEP3    EXEC PGM=COBPROG2,COND=(0,NE,STEP1)
//* Step 4: COND=(4,GT,STEP1) -> (4 GT 4 is false -> EXECUTE, sets RC=8/ABEND)
//STEP4    EXEC PGM=COBPROG2,COND=(4,GT,STEP1)
//* Step 5: Normal step after abend without EVEN -> BYPASSED due to abend
//STEP5    EXEC PGM=COBPROG3
//* Step 6: Step with EVEN -> EXECUTES even after abend
//STEP6    EXEC PGM=COBPROG3,COND=EVEN
//* Step 7: Step with ONLY -> EXECUTES only after abend
//STEP7    EXEC PGM=COBPROG3,COND=ONLY
