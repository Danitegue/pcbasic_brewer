10 REM PC-BASIC test
20 REM CHR$ function
30 OPEN "OUTPUT.TXT" FOR OUTPUT AS 1
40 ON ERROR GOTO 10000
50 PRINT#1, CHR$
60 PRINT#1, CHR$(
70 PRINT#1, CHR$("ABC"
80 PRINT#1, CHR$(1
90 PRINT#1, CHR$(1.5
100 PRINT#1, CHR$(-1)
110 PRINT#1, CHR$(1)
120 PRINT#1, CHR$(-1.5)
130 PRINT#1, CHR$(1.5)
140 PRINT#1, CHR$(-1.5D2)
150 PRINT#1, CHR$(1.5D2)
160 PRINT#1, CHR$("ABC")
200 PRINT#1, CHR$(0)
210 PRINT#1, CHR$(256)
220 PRINT#1, CHR$(32768)
230 PRINT#1, CHR$(65536)
240 PRINT#1, CHR$(1.701412E+38)
250 PRINT#1, CHR$(1.701411834604692D+38)
9999 END
10000 PRINT#1, ERR, ERL
10010 RESUME NEXT
