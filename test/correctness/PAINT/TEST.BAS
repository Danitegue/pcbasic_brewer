10 REM PC-BASIC test 
20 REM PAINT
30 SCREEN 1
35 OPEN "OUTPUT.TXT" FOR OUTPUT AS 1
40 ON ERROR GOTO 10000
50 PAINT 
60 PAINT (100,100)
65 PAINT STEP (1,1),2
70 PAINT (100,100), 1
75 PAINT (100,100),
80 PAINT (100,100), -1
90 PAINT (100,100), 256
95 PAINT (100,100), "TILE"
100 PAINT (100,100), 32768
110 PAINT (100,100), "TILE",
120 PAINT (100,100), 32768,
130 PAINT (100,100), "TILE", 1
140 PAINT (100,100), 1, 1
150 PAINT (100,100),,1
160 PAINT (100,100),,
170 PAINT (100,100), "TILE", 256
180 PAINT (100,100), 1, 256
190 PAINT (100,100), "TILE", -1
200 PAINT (100,100), 1, -1
210 PAINT (100,100), "TILE", 1, "TWO"
220 PAINT (100,100), "TILE", 1, "TILE"
230 PAINT (100,100), "TILE", 1, "TILE2"
240 SCREEN 9
250 PAINT (100,100), "TILE", 1, "TWO"
260 PAINT (100,100), "TILE", 1, "TILE"
270 PAINT (100,100), "TILE", 1, "TILE2"
9999 END
10000 PRINT#1, ERR, ERL
10010 RESUME NEXT
