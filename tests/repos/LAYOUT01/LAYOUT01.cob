       IDENTIFICATION DIVISION.
       PROGRAM-ID. LAYOUT01.
       
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-RECORD.
           05  WS-TEXT          PIC X(4) VALUE "AAAA".
           05  WS-NUM REDEFINES WS-TEXT PIC 9(4).
       
       01  WS-COUNT             PIC 9 VALUE 3.
       01  WS-ITEMS.
           05  ITEM-VAL         PIC X(3) OCCURS 1 TO 5 DEPENDING ON WS-COUNT.
           
       PROCEDURE DIVISION.
           DISPLAY "INITIAL TEXT: " WS-TEXT
           
           MOVE 1234 TO WS-NUM
           DISPLAY "AFTER NUM MOVE TEXT: " WS-TEXT
           DISPLAY "AFTER NUM MOVE NUM: " WS-NUM
           
           MOVE "XYZ" TO ITEM-VAL(1)
           MOVE "ABC" TO ITEM-VAL(2)
           MOVE "DEF" TO ITEM-VAL(3)
           DISPLAY "ITEM 1: " ITEM-VAL(1)
           DISPLAY "ITEM 2: " ITEM-VAL(2)
           DISPLAY "ITEM 3: " ITEM-VAL(3)
           
           STOP RUN.
