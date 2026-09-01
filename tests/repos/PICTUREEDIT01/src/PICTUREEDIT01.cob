       IDENTIFICATION DIVISION.
       PROGRAM-ID. PICTUREEDIT01.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-VAL-NUM          PIC S9(5)V99 VALUE 12345.67.
       01  WS-VAL-NEG          PIC S9(5)V99 VALUE -12345.67.
       01  WS-VAL-ZERO         PIC S9(5)V99 VALUE 0.
       01  WS-VAL-OVERFLOW     PIC S9(7)V99 VALUE 1234567.89.

       01  WS-EDITED-CURR      PIC $$$,$$9.99.
       01  WS-EDITED-PLUS      PIC ++++,++9.99.
       01  WS-EDITED-MINUS     PIC ----,--9.99.
       01  WS-EDITED-ZSUPP     PIC ZZ,ZZ9.99.
       01  WS-EDITED-AST       PIC **,**9.99.
       01  WS-EDITED-CR        PIC ZZ,ZZ9.99CR.
       01  WS-EDITED-DB        PIC ZZ,ZZ9.99DB.
       01  WS-EDITED-OVERFLOW  PIC ZZ9.99.

       PROCEDURE DIVISION.
       MAIN-PARA.
      *> Positive currency formatting
           MOVE WS-VAL-NUM TO WS-EDITED-CURR
           DISPLAY "POS CURR: " WS-EDITED-CURR

      *> Negative currency formatting
           MOVE WS-VAL-NEG TO WS-EDITED-CURR
           DISPLAY "NEG CURR: " WS-EDITED-CURR

      *> Zero currency formatting
           MOVE WS-VAL-ZERO TO WS-EDITED-CURR
           DISPLAY "ZERO CURR: " WS-EDITED-CURR

      *> Positive sign formatting
           MOVE WS-VAL-NUM TO WS-EDITED-PLUS
           DISPLAY "POS PLUS: " WS-EDITED-PLUS

      *> Negative sign formatting
           MOVE WS-VAL-NEG TO WS-EDITED-PLUS
           DISPLAY "NEG PLUS: " WS-EDITED-PLUS

      *> Positive minus sign formatting (suppressed sign)
           MOVE WS-VAL-NUM TO WS-EDITED-MINUS
           DISPLAY "POS MINUS: " WS-EDITED-MINUS

      *> Negative minus sign formatting
           MOVE WS-VAL-NEG TO WS-EDITED-MINUS
           DISPLAY "NEG MINUS: " WS-EDITED-MINUS

      *> Zero suppression formatting
           MOVE WS-VAL-NUM TO WS-EDITED-ZSUPP
           DISPLAY "POS ZSUPP: " WS-EDITED-ZSUPP
           MOVE WS-VAL-ZERO TO WS-EDITED-ZSUPP
           DISPLAY "ZERO ZSUPP: " WS-EDITED-ZSUPP

      *> Asterisk fill formatting
           MOVE WS-VAL-NUM TO WS-EDITED-AST
           DISPLAY "POS AST: " WS-EDITED-AST
           MOVE 0.12 TO WS-VAL-ZERO
           MOVE WS-VAL-ZERO TO WS-EDITED-AST
           DISPLAY "ZERO AST: " WS-EDITED-AST

      *> CR/DB formatting
           MOVE WS-VAL-NUM TO WS-EDITED-CR
           DISPLAY "POS CR: " WS-EDITED-CR
           MOVE WS-VAL-NEG TO WS-EDITED-CR
           DISPLAY "NEG CR: " WS-EDITED-CR

           MOVE WS-VAL-NUM TO WS-EDITED-DB
           DISPLAY "POS DB: " WS-EDITED-DB
           MOVE WS-VAL-NEG TO WS-EDITED-DB
           DISPLAY "NEG DB: " WS-EDITED-DB

      *> Overflow formatting
           MOVE WS-VAL-OVERFLOW TO WS-EDITED-OVERFLOW
           DISPLAY "OVERFLOW: " WS-EDITED-OVERFLOW

           GOBACK.
