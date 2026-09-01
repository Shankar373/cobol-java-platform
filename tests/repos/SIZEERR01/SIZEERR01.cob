       IDENTIFICATION DIVISION.
       PROGRAM-ID. SIZEERR01.
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       SPECIAL-NAMES.
           .
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-SMALL PIC 9(2) VALUE 0.
       01 WS-OVERFLOW PIC X VALUE 'N'.
       PROCEDURE DIVISION.
       MAIN-PARA.
      * Test 1: ADD that overflows a 2-digit field -> ON SIZE ERROR
           DISPLAY 'Before ADD: WS-SMALL = ' WS-SMALL
           ADD 1000 TO WS-SMALL ON SIZE ERROR
               MOVE 'Y' TO WS-OVERFLOW
               DISPLAY 'ON SIZE ERROR triggered'
           END-ADD
           DISPLAY 'After ADD: WS-SMALL = ' WS-SMALL
           DISPLAY 'WS-OVERFLOW = ' WS-OVERFLOW
      * Test 2: SUBTRACT that underflows a 2-digit field -> ON SIZE ERROR
           MOVE 'N' TO WS-OVERFLOW
           SUBTRACT 100 FROM WS-SMALL ON SIZE ERROR
               MOVE 'Y' TO WS-OVERFLOW
               DISPLAY 'ON SIZE ERROR underflow triggered'
           END-SUBTRACT
           DISPLAY 'After SUBTRACT: WS-SMALL = ' WS-SMALL
           DISPLAY 'WS-OVERFLOW = ' WS-OVERFLOW
           STOP RUN.
