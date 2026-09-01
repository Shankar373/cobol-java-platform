       IDENTIFICATION DIVISION.
       PROGRAM-ID. DB2TVS01.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  SQLCA-VARIABLES.
           05  SQLCODE    PIC S9(9) COMP.
           05  SQLSTATE   PIC X(5).
       01  WS-CUSTOMER.
           05  WS-CUST-ID     PIC S9(9) COMP.
           05  WS-CUST-NAME   PIC X(20) VALUE SPACES.
       PROCEDURE DIVISION.
           *> Insert first record and commit
           MOVE 101 TO WS-CUST-ID
           MOVE "COMMIT CUSTOMER    " TO WS-CUST-NAME
           EXEC SQL
               INSERT INTO CUSTOMER (CUST_ID, CUST_NAME)
               VALUES (:WS-CUST-ID, :WS-CUST-NAME)
           END-EXEC
           EXEC SQL COMMIT END-EXEC
           
           *> Select to verify it is committed
           MOVE SPACES TO WS-CUST-NAME
           EXEC SQL
               SELECT CUST_NAME INTO :WS-CUST-NAME
               FROM CUSTOMER WHERE CUST_ID = 101
           END-EXEC
           IF SQLCODE = 0 AND WS-CUST-NAME = "COMMIT CUSTOMER     "
               DISPLAY "COMMITTED: YES"
           ELSE
               DISPLAY "COMMITTED: NO"
           END-IF

           *> Insert second record and rollback
           MOVE 102 TO WS-CUST-ID
           MOVE "ROLLBACK CUSTOMER  " TO WS-CUST-NAME
           EXEC SQL
               INSERT INTO CUSTOMER (CUST_ID, CUST_NAME)
               VALUES (:WS-CUST-ID, :WS-CUST-NAME)
           END-EXEC
           EXEC SQL ROLLBACK END-EXEC

           *> Select to verify it was rolled back
           MOVE SPACES TO WS-CUST-NAME
           EXEC SQL
               SELECT CUST_NAME INTO :WS-CUST-NAME
               FROM CUSTOMER WHERE CUST_ID = 102
           END-EXEC
           IF SQLCODE = 100
               DISPLAY "ROLLED BACK: YES"
           ELSE
               DISPLAY "ROLLED BACK: NO"
           END-IF
           GOBACK.
