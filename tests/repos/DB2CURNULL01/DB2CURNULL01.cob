IDENTIFICATION DIVISION.
       PROGRAM-ID. DB2CURNULL01.
       
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       SPECIAL-NAMES.
           .                                                        
       
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-DBNAME PIC X(30) VALUE "modernization_db".
       01 WS-USERNAME PIC X(30) VALUE "modernize".
       01 WS-PASSWD PIC X(30) VALUE "modernize".
       
       * SQLCA is injected by the ocesql preprocessor
       * EXEC SQL INCLUDE SQLCA END-EXEC.  -- injected
       
       01 WS-EMPTABLE OCCURS 10 TIMES.
           05 WS-EMPNO PIC 9(4).
           05 WS-EMPNAME PIC X(20).
           05 WS-SALARY PIC 9(5)V99 COMP-3.
           05 WS-COMM PIC 9(3) VALUE 0.
           05 WS-NULL-INDICATOR PIC S9(4) COMP VALUE 0.  -- NULL indicator col
       
       01 WS-ROW-NUM PIC 9(2) VALUE 1.
       01 WS-DISPLAY-LINE PIC X(80) VALUE SPACES.
       01 WS-NULL-COUNT PIC 9(2) VALUE 0.
       
       * Cursor declaration
       EXEC SQL DECLARE EMP_CURSOR CURSOR FOR
           SELECT EMPNO, EMPNAME, SALARY, COMM, :WS-NULL-INDICATOR AS NULL_IND
           FROM STAFF.EMPTABLE
           FOR READ ONLY
       END-EXEC.
       
       EXEC SQL WHENEVER NOT FOUND STOP RUN END-EXEC.
       
       PROCEDURE DIVISION.
       MAIN-SECTION.
           * Connect to the database
           EXEC SQL CONNECT TO :WS-DBNAME IDENTIFIED BY :WS-USERNAME
               USING :WS-DBNAME END-EXEC.
           
           * Insert test rows with some NULL values in COMM
           EXEC SQL WHENEVER NOT FOUND GO TO end-program END-EXEC.
           
           EXEC SQL INSERT INTO STAFF.EMPTABLE
               (EMPNO, EMPNAME, SALARY, COMM, NULL_IND)
               VALUES (1001, 'JONES', 30000, 100, 0)
           END-EXEC.
           
           EXEC SQL INSERT INTO STAFF.EMPTABLE
               (EMPNO, EMPNAME, SALARY, COMM, NULL_IND)
               VALUES (1002, 'SMITH', 25000, NULL, -1)  -- NULL indicator -1
           END-EXEC.
           
           EXEC SQL INSERT INTO STAFF.EMPTABLE
               (EMPNO, EMPNAME, SALARY, COMM, NULL_IND)
               VALUES (1003, 'ALLEN', 30000, 500, 0)
           END-EXEC.
           
           * Open the cursor
           EXEC SQL OPEN EMP_CURSOR END-EXEC.
           
           DISPLAY 'Cursor opened. Fetching rows...'
           
           * Fetch rows
           EXEC SQL FETCH EMP_CURSOR INTO :WS-EMPNO, :WS-EMPNAME, :WS-SALARY, :WS-COMM, :WS-NULL-INDICATOR END-EXEC.
           
           PERFORM
               WHILE SQLCODE > -999
                   DISPLAY 'Row ' WS-ROW-NUM ': EMPNO=' WS-EMPNO ' EMPNAME=' WS-EMPNAME 
                        ' SALARY=' WS-SALARY ' COMM=' WS-COMM 
                        ' NULL-IND=' WS-NULL-INDICATOR
                   
                   IF WS-NULL-INDICATOR = -1
                       DISPLAY '  *** NULL detected in COMM column ***'
                       ADD 1 TO WS-NULL-COUNT
                   END-IF
                   
                   ADD 1 TO WS-ROW-NUM
                   EXEC SQL FETCH EMP_CURSOR INTO :WS-EMPNO, :WS-EMPNAME, :WS-SALARY, :WS-COMM, :WS-NULL-INDICATOR END-EXEC.
               END-PERFORM
           
           DISPLAY 'Total NULL columns found: ' WS-NULL-COUNT
           
       end-program:
           * Close cursor and disconnect
           EXEC SQL CLOSE EMP_CURSOR END-EXEC.
           EXEC SQL COMMIT END-EXEC.
           EXEC SQL COMMIT WORK END-EXEC.
           EXEC SQL DISCONNECT ALL END-EXEC.
           STOP RUN.