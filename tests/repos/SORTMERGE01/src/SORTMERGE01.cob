       IDENTIFICATION DIVISION.
       PROGRAM-ID. SORTMERGE01.
       
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT INFILE ASSIGN TO "input.txt"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT OUTFILE ASSIGN TO "output.txt"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT SORTWORK ASSIGN TO "sortwork.tmp".

       DATA DIVISION.
       FILE SECTION.
       FD  INFILE.
       01  IN-REC.
           05  IN-NAME PIC X(10).
           05  IN-AGE  PIC 9(2).
           
       FD  OUTFILE.
       01  OUT-REC.
           05  OUT-NAME PIC X(10).
           05  OUT-AGE  PIC 9(2).
           
       SD  SORTWORK.
       01  WORK-REC.
           05  WORK-NAME PIC X(10).
           05  WORK-AGE  PIC 9(2).

       PROCEDURE DIVISION.
       MAIN-PARA.
           SORT SORTWORK ON ASCENDING KEY WORK-AGE
               USING INFILE GIVING OUTFILE.
           GOBACK.
