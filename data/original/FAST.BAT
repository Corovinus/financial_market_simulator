keyrus.com
nolfb
@echo off
:ONC
stend.EXE
if errorlevel 17 goto 17_
if errorlevel 16 goto 16_
if errorlevel 15 goto 15_
if errorlevel 14 goto 14_
if errorlevel 13 goto 13_
if errorlevel 12 goto 12_
if errorlevel 11 goto 11_
if errorlevel 10 goto 10_
if errorlevel 9 goto 9_
if errorlevel 8 goto 8_
if errorlevel 7 goto 7_
if errorlevel 6 goto 6_
if errorlevel 5 goto 5_
if errorlevel 4 goto 4_
if errorlevel 3 goto 3_
if errorlevel 2 goto 2_
if errorlevel 1 goto 1_
if errorlevel 0 goto QUIT
:17_
Head 43
rem Re3
goto ONC
:16_
Head 42
rem Re2
goto ONC
:15_
Head 41
rem Re1
goto ONC
:14_
Head 30
rem TutOp
goto ONC
:13_
Head 33
rem OP3
goto ONC
:12_
Head 32
rem OP2
goto ONC
:11_
Head 31
rem OP1
goto ONC
:10_
Head 20
rem TUTCA
goto ONC
:9_
Head 23
rem CA3
goto ONC
:8_
Head 22
rem CA2
goto ONC
:7_
Head 21
rem CA1
goto ONC
:6_
Head 10
rem TUTBO
goto ONC
:5_
Head 14
rem B04
goto ONC
:4_
Head 13
rem B03
goto ONC
:3_
Head 12
rem B02
goto ONC
:2_
Head 11
rem B01
goto ONC
:1_
Head 0
rem demo fts_tut
goto ONC

:QUIT
