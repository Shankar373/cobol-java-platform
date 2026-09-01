       IDENTIFICATION DIVISION.
       PROGRAM-ID. ADVERSARIAL01.
       
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-STATUS        PIC X VALUE 'O'.
           88 STATUS-OPEN   VALUE 'O'.
           88 STATUS-CLOSED VALUE 'C'.
       01  WS-CODE          PIC 9 VALUE 1.
       01  WS-I             PIC 9 VALUE 1.
       01  WS-LIMIT         PIC 9 VALUE 3.
       01  WS-TARGET-1      PIC 9 VALUE 0.
       01  WS-TARGET-2      PIC 9 VALUE 0.
       01  WS-ARRAY-ITEMS.
           05 ITEM-VAL      PIC 99V99 OCCURS 5.
       
       PROCEDURE DIVISION.
           DISPLAY "START" WS-STATUS
           
           EVALUATE WS-STATUS
               WHEN "O"
                   DISPLAY "OPENED"
               WHEN OTHER
                   DISPLAY "OTHER-STATUS"
           END-EVALUATE
           
           IF STATUS-OPEN
               DISPLAY "IS-OPEN"
           END-IF
           
           MOVE 10 TO WS-TARGET-1 WS-TARGET-2
           DISPLAY "MULTI-MOVE: " WS-TARGET-1 WS-TARGET-2
           
           PERFORM VARYING WS-I FROM 1 BY 1 UNTIL WS-I > WS-LIMIT
               MOVE 2.50 TO ITEM-VAL(WS-I)
               DISPLAY "ARRAY_ITEM(" WS-I ")=" ITEM-VAL(WS-I)
           END-PERFORM
           
           DISPLAY "END"
           STOP RUN.
