IDENTIFICATION DIVISION.
       PROGRAM-ID. OCCURS01.
       
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       SPECIAL-NAMES.
           .                                                        
       
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-DAY-OF-WEEK PIC 9(1).
       01 WS-DAYS-ARRAY OCCURS 5 TIMES PIC 9(2).
           10 WS-DAY-NAMES PIC X(10) OCCURS 5 TIMES VALUE
               "SUN" "MON" "TUE" "WED" "THU" "FRI" "SAT".
       01 WS-INDEX PIC 9(2) VALUE 1.
       01 WS-DISPLAY-ARRAY PIC 9(2) VALUE 0.
       01 WS-SUM PIC 9(3) VALUE 0.
       
       PROCEDURE DIVISION.
       MAIN-SECTION.
           * Initialize and loop over the OCCURS array
           PERFORM VARYING WS-INDEX FROM 1 BY 1 UNTIL WS-INDEX > 5
               MOVE WS-INDEX TO WS-DAYS-ARRAY(WS-INDEX)
               MOVE WS-DAY-NAMES(WS-INDEX) TO WS-DISPLAY
               DISPLAY 'Day ' WS-INDEX ': ' WS-DAY-NAMES(WS-INDEX) ' is day number ' WS-DAYS-ARRAY(WS-INDEX)
               ADD WS-DAYS-ARRAY(WS-INDEX) TO WS-SUM
           END-PERFORM
           
           DISPLAY '---'
           DISPLAY 'Sum of all days: ' WS-SUM
           
           * Display the array via the alternative view
           DISPLAY '---Array via WS-DISPLAY-ARRAY---'
           MOVE WS-DAYS-ARRAY TO WS-DISPLAY-ARRAY
           DISPLAY 'WS-DISPLAY-ARRAY value: ' WS-DISPLAY-ARRAY
           
           STOP RUN.