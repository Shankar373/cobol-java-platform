       IDENTIFICATION DIVISION.
       PROGRAM-ID. DB2ERRC.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  SQLCA-VARIABLES.
           05  SQLCODE    PIC S9(9) COMP.
           05  SQLSTATE   PIC X(5).
       PROCEDURE DIVISION.
           *> Insert first time (should succeed)
           EXEC SQL
               INSERT INTO CUSTOMER (CUST_ID, CUST_NAME) VALUES (101, 'TEST')
           END-EXEC.
           *> Insert second time (should violate primary key constraint)
           EXEC SQL
               INSERT INTO CUSTOMER (CUST_ID, CUST_NAME) VALUES (101, 'TEST')
           END-EXEC.
           DISPLAY "SQLCODE: " SQLCODE.
           GOBACK.
