10 REM PC-BASIC test 
20 REM INPUT from console
30 INPUT "a,b", a, b$
40 PRINT A, B$
1000 ' dump screen
1010 DEF SEG=&HB800
1020 OPEN "dump"+N$+".dat" FOR OUTPUT AS 2
1030 FOR Y = 0 TO 24
1040 FOR X = 0 TO 79
1050 PRINT #2, CHR$(PEEK(2*(Y*80+X)));
1060 NEXT
1065 PRINT #2, ""
1070 NEXT
1080 CLOSE 2

