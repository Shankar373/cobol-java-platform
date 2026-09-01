        IDENTIFICATION DIVISION.
        PROGRAM-ID. SQLBASE1.
        DATA DIVISION.
        WORKING-STORAGE SECTION.
        01  SQLCA-VARIABLES.
            05  SQLCODE    PIC S9(9) COMP.
            05  SQLSTATE   PIC X(5).
        
        EXEC SQL BEGIN DECLARE SECTION END-EXEC.
        01  WS-CUST-ID     PIC S9(9) COMP.
        01  WS-CUST-NAME   PIC X(20).
        01  WS-NEW-NAME    PIC X(20) VALUE "UPDATED NAME        ".
        EXEC SQL END DECLARE SECTION END-EXEC.

        PROCEDURE DIVISION.
        MAIN-PARA.
            EXEC SQL
                DECLARE C1 CURSOR FOR
                SELECT CUST_ID, CUST_NAME
                FROM CUSTOMER
                ORDER BY CUST_ID
            END-EXEC.

            DISPLAY "--- SELECT INTO ---"
            MOVE 101 TO WS-CUST-ID
            EXEC SQL
                SELECT CUST_NAME
                INTO :WS-CUST-NAME
                FROM CUSTOMER
                WHERE CUST_ID = :WS-CUST-ID
            END-EXEC
            DISPLAY "SELECT SQLCODE: " SQLCODE
            DISPLAY "CUST-NAME: " WS-CUST-NAME

            DISPLAY "--- INSERT ---"
            MOVE 102 TO WS-CUST-ID
            MOVE "NEW CUSTOMER        " TO WS-CUST-NAME
            EXEC SQL
                INSERT INTO CUSTOMER (CUST_ID, CUST_NAME)
                VALUES (:WS-CUST-ID, :WS-CUST-NAME)
            END-EXEC
            DISPLAY "INSERT SQLCODE: " SQLCODE

            DISPLAY "--- UPDATE ---"
            EXEC SQL
                UPDATE CUSTOMER
                SET CUST_NAME = :WS-NEW-NAME
                WHERE CUST_ID = 101
            END-EXEC
            DISPLAY "UPDATE SQLCODE: " SQLCODE

            DISPLAY "--- CURSOR FETCH ---"
            EXEC SQL OPEN C1 END-EXEC
            DISPLAY "OPEN SQLCODE: " SQLCODE
            
            PERFORM UNTIL SQLCODE NOT = 0
                EXEC SQL
                    FETCH C1 INTO :WS-CUST-ID, :WS-CUST-NAME
                END-EXEC
                IF SQLCODE = 0
                    DISPLAY "FETCH CUST: " WS-CUST-ID " | " WS-CUST-NAME
                END-IF
            END-PERFORM
            
            EXEC SQL CLOSE C1 END-EXEC
            DISPLAY "CLOSE SQLCODE: " SQLCODE

            DISPLAY "--- DELETE ---"
            EXEC SQL
                DELETE FROM CUSTOMER
                WHERE CUST_ID = 102
            END-EXEC
            DISPLAY "DELETE SQLCODE: " SQLCODE
            GOBACK.
