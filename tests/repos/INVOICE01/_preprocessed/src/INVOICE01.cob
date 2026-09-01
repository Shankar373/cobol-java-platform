       IDENTIFICATION DIVISION.
       PROGRAM-ID. INVOICE01.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT IN-FILE ASSIGN TO "data/in/invoice-input.dat"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT OUT-FILE ASSIGN TO "data/out/invoice-output.dat"
               ORGANIZATION IS LINE SEQUENTIAL.
       DATA DIVISION.
       FILE SECTION.
       FD IN-FILE.
       01 IN-REC.
          05 IN-ID        PIC X(10).
          05 IN-DATE      PIC X(8).
          05 IN-CUSTOMER  PIC X(10).
          05 IN-AMOUNT    PIC 9(8)V99.
       FD OUT-FILE.
       01 OUT-REC.
          05 OUT-ID       PIC X(10).
          05 OUT-DATE     PIC X(8).
          05 OUT-CUSTOMER PIC X(10).
          05 OUT-AMOUNT   PIC 9(8)V99.
          05 OUT-TAX      PIC 9(8)V99.
          05 OUT-STATUS   PIC X(10).
       WORKING-STORAGE SECTION.
       01 WS-EOF          PIC X VALUE 'N'.
       01 WS-COUNT        PIC 9(5) VALUE ZERO.
       01 WS-TAX-RATE     PIC 9V99 VALUE 0.15.
       PROCEDURE DIVISION.
       MAIN-LOGIC.
           OPEN INPUT IN-FILE
           OPEN OUTPUT OUT-FILE
           DISPLAY "INVOICE PROCESSING STARTED"
           PERFORM UNTIL WS-EOF = 'Y'
               READ IN-FILE
                   AT END
                       MOVE 'Y' TO WS-EOF
                   NOT AT END
                       PERFORM PROCESS-RECORD
               END-READ
           END-PERFORM
           CLOSE IN-FILE
           CLOSE OUT-FILE
           DISPLAY "INVOICES PROCESSED: " WS-COUNT
           DISPLAY "INVOICE PROCESSING COMPLETED"
           GOBACK.
       PROCESS-RECORD.
           ADD 1 TO WS-COUNT
           MOVE IN-ID TO OUT-ID
           MOVE IN-DATE TO OUT-DATE
           MOVE IN-CUSTOMER TO OUT-CUSTOMER
           MOVE IN-AMOUNT TO OUT-AMOUNT
           MULTIPLY IN-AMOUNT BY WS-TAX-RATE GIVING OUT-TAX
           IF IN-AMOUNT > 1000.00
               MOVE "PREMIUM" TO OUT-STATUS
           ELSE
               MOVE "STANDARD" TO OUT-STATUS
           END-IF
           WRITE OUT-REC.
