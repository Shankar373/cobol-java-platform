       IDENTIFICATION DIVISION.
       PROGRAM-ID. CALLCHAIN01.
       
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT REPORT-FILE ASSIGN TO "data/out/chain-report.dat"
               ORGANIZATION IS LINE SEQUENTIAL.
               
       DATA DIVISION.
       FILE SECTION.
       FD  REPORT-FILE.
       01  REPORT-REC          PIC X(80).
       
       WORKING-STORAGE SECTION.
       COPY "CHNDATA.cpy".
       01  WS-SUBPROG-NAME     PIC X(8) VALUE "SUBPROG2".
       01  WS-DISPLAY-RES      PIC ZZZZZ9.
       01  WS-OUT-LINE         PIC X(80) VALUE SPACES.
       
       01  WS-SUB                      PIC 9(4) COMP VALUE ZERO.
       PROCEDURE DIVISION.
           OPEN OUTPUT REPORT-FILE
           
           MOVE 10 TO CHN-NUM-1
           MOVE 5 TO CHN-NUM-2
           CALL "SUBPROG1" USING CHN-RECORD
           
           MOVE CHN-RESULT TO WS-DISPLAY-RES
           STRING "STATIC CALL RESULT: " DELIMITED BY SIZE
                  WS-DISPLAY-RES DELIMITED BY SIZE
                  " MSG: " DELIMITED BY SIZE
                  CHN-MSG DELIMITED BY SIZE
                  INTO WS-OUT-LINE
           WRITE REPORT-REC FROM WS-OUT-LINE
           
           MOVE 10 TO CHN-NUM-1
           MOVE 5 TO CHN-NUM-2
           CALL WS-SUBPROG-NAME USING CHN-RECORD
           
           MOVE SPACES TO WS-OUT-LINE
           MOVE CHN-RESULT TO WS-DISPLAY-RES
           STRING "DYNAMIC CALL RESULT: " DELIMITED BY SIZE
                  WS-DISPLAY-RES DELIMITED BY SIZE
                  " MSG: " DELIMITED BY SIZE
                  CHN-MSG DELIMITED BY SIZE
                  INTO WS-OUT-LINE
           WRITE REPORT-REC FROM WS-OUT-LINE
           
           CLOSE REPORT-FILE
           STOP RUN.
