       IDENTIFICATION DIVISION.
       PROGRAM-ID. ACCTPROG.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT SOURCE-FILE ASSIGN TO "data/raw-source-data.bin"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT RESULT-FILE ASSIGN TO "data/final-result-report.txt"
               ORGANIZATION IS LINE SEQUENTIAL.
       DATA DIVISION.
       FILE SECTION.
       FD SOURCE-FILE.
       COPY ACTREC.
       FD RESULT-FILE.
       COPY ACTREP.
       WORKING-STORAGE SECTION.
       01 WS-EOF              PIC X VALUE 'N'.
       COPY ACTLNK.
       PROCEDURE DIVISION.
       MAIN-LOGIC.
           OPEN INPUT SOURCE-FILE
           OPEN OUTPUT RESULT-FILE
           PERFORM UNTIL WS-EOF = 'Y'
               READ SOURCE-FILE
                   AT END
                       MOVE 'Y' TO WS-EOF
                   NOT AT END
                       PERFORM PROCESS-RECORD
               END-READ
           END-PERFORM
           CLOSE SOURCE-FILE
           CLOSE RESULT-FILE
           GOBACK.
       PROCESS-RECORD.
           MOVE SRC-BALANCE TO LNK-BALANCE
           MOVE SRC-TX-TYPE TO LNK-TX-TYPE
           MOVE SRC-TX-AMOUNT TO LNK-TX-AMOUNT
           CALL "ACCTCALC" USING LNK-CALC-AREA
           MOVE SRC-ACCOUNT-ID TO REP-ACCOUNT-ID
           MOVE LNK-NEW-BALANCE TO REP-NEW-BALANCE
           IF LNK-NEW-BALANCE < 0
               MOVE "OVERDRAWN" TO REP-STATUS
           ELSE
               MOVE "ACTIVE" TO REP-STATUS
           END-IF
           WRITE REP-RECORD.
