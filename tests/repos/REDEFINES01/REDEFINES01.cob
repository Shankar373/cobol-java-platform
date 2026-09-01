       IDENTIFICATION DIVISION.
       PROGRAM-ID. REDEFINES01.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT OUT-FILE ASSIGN TO "WS-FILE-OUT"
               FILE STATUS IS WS-FS.
       DATA DIVISION.
       FILE SECTION.
       FD  OUT-FILE.
       01  OUT-REC PIC X(10).
       WORKING-STORAGE SECTION.
       01  WS-FS PIC XX.
       01  WS-BUF-X PIC X(10).
       01  WS-BUF-9 REDEFINES WS-BUF-X PIC 9(10).
       01  WS-DISPLAY PIC X(20).
       PROCEDURE DIVISION.
       MAIN-PARA.
      * View 1: write alphanumeric value via WS-BUF-X
           MOVE 'HELLO1234' TO WS-BUF-X
      * View 2: same storage read as numeric via the REDEFINES
           DISPLAY 'WS-BUF-9 as numeric: ' WS-BUF-9
           MOVE WS-BUF-9 TO WS-DISPLAY
           DISPLAY 'WS-DISPLAY (buf redefines view): ' WS-DISPLAY
      * Verify the overlap: writing via one view is visible via the other
           MOVE '9999999999' TO WS-BUF-9
           DISPLAY 'After MOVE 9999999999 to WS-BUF-9:'
           DISPLAY 'WS-BUF-X: ' WS-BUF-X
           DISPLAY 'WS-BUF-9: ' WS-BUF-9
      * Write the redefined contents to the output file
           MOVE WS-BUF-X TO OUT-REC
           OPEN OUTPUT OUT-FILE
           WRITE OUT-REC
           CLOSE OUT-FILE
           STOP RUN.
