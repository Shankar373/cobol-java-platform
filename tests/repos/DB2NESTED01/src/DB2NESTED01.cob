       IDENTIFICATION DIVISION.
       PROGRAM-ID. DB2NST01.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  SQLCA-VARIABLES.
           05  SQLCODE    PIC S9(9) COMP.
           05  SQLSTATE   PIC X(5).
       01  WS-CUSTOMER.
           05  WS-CUST-ID   PIC S9(9) COMP VALUE 101.
           05  WS-CUST-NAME PIC X(20).
       PROCEDURE DIVISION.
           IF WS-CUST-ID = 101
               EXEC SQL
                   SELECT CUST_NAME
                   INTO :WS-CUST-NAME
                   FROM CUSTOMER
                   WHERE CUST_ID = :WS-CUST-ID
               END-EXEC
               DISPLAY "NESTED SELECT SQLCODE: " SQLCODE
           END-IF.
           GOBACK.
