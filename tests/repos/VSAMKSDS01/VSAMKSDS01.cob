       IDENTIFICATION DIVISION.
       PROGRAM-ID. VSAMKSDS01.
       
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT KSDS-FILE ASSIGN TO "data/work/ksds.dat"
               ORGANIZATION IS INDEXED
               ACCESS MODE IS DYNAMIC
               RECORD KEY IS KSDS-KEY
               ALTERNATE RECORD KEY IS KSDS-ALT1
               ALTERNATE RECORD KEY IS KSDS-ALT2 WITH DUPLICATES
               FILE STATUS IS KSDS-STATUS.
               
       DATA DIVISION.
       FILE SECTION.
       FD  KSDS-FILE.
       01  KSDS-REC.
           05  KSDS-KEY         PIC X(4).
           05  KSDS-ALT1        PIC X(4).
           05  KSDS-ALT2        PIC X(4).
           05  KSDS-DATA        PIC X(10).
           
       WORKING-STORAGE SECTION.
       01  KSDS-STATUS          PIC X(2).
       
       PROCEDURE DIVISION.
           OPEN OUTPUT KSDS-FILE.
           DISPLAY "OPEN OUTPUT STATUS: " KSDS-STATUS.
           
           MOVE "1000" TO KSDS-KEY.
           MOVE "A001" TO KSDS-ALT1.
           MOVE "B001" TO KSDS-ALT2.
           MOVE "REC ONE   " TO KSDS-DATA.
           WRITE KSDS-REC.
           DISPLAY "WRITE ONE STATUS: " KSDS-STATUS.
           
           MOVE "2000" TO KSDS-KEY.
           MOVE "A002" TO KSDS-ALT1.
           MOVE "B001" TO KSDS-ALT2.
           MOVE "REC TWO   " TO KSDS-DATA.
           WRITE KSDS-REC.
           DISPLAY "WRITE TWO STATUS: " KSDS-STATUS.
           
           MOVE "3000" TO KSDS-KEY.
           MOVE "A001" TO KSDS-ALT1.
           MOVE "B002" TO KSDS-ALT2.
           MOVE "REC THREE " TO KSDS-DATA.
           WRITE KSDS-REC.
           DISPLAY "WRITE DUP ALT1 STATUS: " KSDS-STATUS.
           
           CLOSE KSDS-FILE.
           
           OPEN I-O KSDS-FILE.
           DISPLAY "OPEN I-O STATUS: " KSDS-STATUS.
           
           MOVE "A002" TO KSDS-ALT1.
           READ KSDS-FILE KEY IS KSDS-ALT1.
           DISPLAY "READ ALT1 A002 STATUS: " KSDS-STATUS.
           DISPLAY "READ KEY: " KSDS-KEY " DATA: " KSDS-DATA.
           
           MOVE "B001" TO KSDS-ALT2.
           READ KSDS-FILE KEY IS KSDS-ALT2.
           DISPLAY "READ ALT2 B001 STATUS: " KSDS-STATUS.
           DISPLAY "READ KEY: " KSDS-KEY " DATA: " KSDS-DATA.
           
           MOVE "B001" TO KSDS-ALT2.
           START KSDS-FILE KEY IS >= KSDS-ALT2.
           DISPLAY "START STATUS: " KSDS-STATUS.
           
           READ KSDS-FILE NEXT.
           DISPLAY "READ NEXT 1 STATUS: " KSDS-STATUS.
           DISPLAY "READ KEY: " KSDS-KEY " DATA: " KSDS-DATA.
           
           READ KSDS-FILE NEXT.
           DISPLAY "READ NEXT 2 STATUS: " KSDS-STATUS.
           DISPLAY "READ KEY: " KSDS-KEY " DATA: " KSDS-DATA.
           
           READ KSDS-FILE NEXT.
           DISPLAY "READ NEXT 3 STATUS: " KSDS-STATUS.
           
           READ KSDS-FILE NEXT.
           DISPLAY "READ NEXT 4 STATUS: " KSDS-STATUS.
           
           CLOSE KSDS-FILE.
           STOP RUN.
