       IDENTIFICATION DIVISION.
       PROGRAM-ID. COBPROG1.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT IN-FILE ASSIGN TO INPUTDD
             ORGANIZATION IS LINE SEQUENTIAL.
       DATA DIVISION.
       FILE SECTION.
       FD  IN-FILE.
       01  IN-REC PIC X(80).
       WORKING-STORAGE SECTION.
       01  WS-EOF PIC X VALUE 'N'.
       PROCEDURE DIVISION.
           OPEN INPUT IN-FILE.
           PERFORM UNTIL WS-EOF = 'Y'
               READ IN-FILE INTO IN-REC
                   AT END
                       MOVE 'Y' TO WS-EOF
                   NOT AT END
                       DISPLAY IN-REC
               END-READ
           END-PERFORM.
           CLOSE IN-FILE.
           GOBACK.
