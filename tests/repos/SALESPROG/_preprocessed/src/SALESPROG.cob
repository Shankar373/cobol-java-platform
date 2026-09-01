       IDENTIFICATION DIVISION.
       PROGRAM-ID. SALESPROG.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT SLS-FILE ASSIGN TO "data/in/sales-input.dat"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT RPT-FILE ASSIGN TO "data/out/sales-report.dat"
               ORGANIZATION IS LINE SEQUENTIAL.
       DATA DIVISION.
       FILE SECTION.
       FD SLS-FILE.
       COPY SLSREC.
       FD RPT-FILE.
       01 RPT-REC.
          05 RPT-REP-ID   PIC X(8).
          05 RPT-PRODUCT  PIC X(12).
          05 RPT-TOTAL    PIC 9(9)V99.
          05 RPT-TIER     PIC X(10).
       WORKING-STORAGE SECTION.
       01 WS-EOF          PIC X VALUE 'N'.
       01 WS-COUNT        PIC 9(5) VALUE ZERO.
       01 WS-CALC-AREA.
          05 WS-QTY        PIC 9(5).
          05 WS-UNIT-PRICE PIC 9(7)V99.
          05 WS-DISCOUNT   PIC 9V99.
          05 WS-TOTAL      PIC 9(9)V99.
          05 WS-TIER       PIC X(10).
       PROCEDURE DIVISION.
       MAIN-SECTION.
           OPEN INPUT SLS-FILE
           OPEN OUTPUT RPT-FILE
           DISPLAY "SALES PROCESSING STARTED"
           PERFORM UNTIL WS-EOF = 'Y'
               READ SLS-FILE
                   AT END
                       MOVE 'Y' TO WS-EOF
                   NOT AT END
                       PERFORM PROCESS-SALE
               END-READ
           END-PERFORM
           CLOSE SLS-FILE
           CLOSE RPT-FILE
           DISPLAY "SALES RECORDS PROCESSED: " WS-COUNT
           DISPLAY "SALES PROCESSING COMPLETED"
           GOBACK.
       PROCESS-SALE.
           ADD 1 TO WS-COUNT
           MOVE SLS-QTY       TO WS-QTY
           MOVE SLS-UNIT-PRICE TO WS-UNIT-PRICE
           MOVE ZERO          TO WS-DISCOUNT
           CALL "SALESCALC" USING WS-CALC-AREA
           MOVE SLS-REP-ID    TO RPT-REP-ID
           MOVE SLS-PRODUCT   TO RPT-PRODUCT
           MOVE WS-TOTAL      TO RPT-TOTAL
           MOVE WS-TIER       TO RPT-TIER
           WRITE RPT-REC.
