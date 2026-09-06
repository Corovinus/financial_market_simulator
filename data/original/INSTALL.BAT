@echo off
rem ========================================================= Файл INSTALL.BAT
echo -----------------------------------------------------------------------------
echo -----------------------  Программный продукт FAST  --------------------------
echo -----------------------  Установка на жесткий диск --------------------------
echo -----------------------------------------------------------------------------
echo  
if %1.==. goto TYPEHELP
if %2.==. goto TYPEPAR
if %3.==. goto TYPEPAR
if not exist %2%3\NUL goto MAKEDIR
echo  
echo ВНИМАНИЕ! Каталог "%3" уже существует!
echo   Если Вы хотите произвести установку в этот каталог, нажмите пробел,
echo   иначе нажмите {Ctrl-Break} и измените имя каталога в команде INSTALL.
echo  
pause>nul
goto COPYTEST
:MAKEDIR
if not exist %2\NUL goto TYPEDRIVE
%2
md %3
if not exist %2%3\NUL goto TYPEDIR
:COPYTEST
if not exist %1install.bat goto TYPEDEST
echo Установка на диск "%2" в каталог "%3" с дисковода "%1"
echo  
echo Чтобы начать установку, нажмите пробел, 
echo иначе нажмите {Ctrl-Break} и повторите команду INSTALL с правильными параметрами
pause>nul
%1
echo  
echo         Начался процесс установки ...
%2
cd %3
copy %1*.*
del install.bat>nul
echo  
echo         Программа FAST установлена на диск "%2" в каталог "%3"
echo  
echo   Для запуска наберите команду:
echo  
echo     FAST
goto END
:TYPEHELP
echo Для установки программного продукта FAST на жесткий диск наберите команду:
echo     INSTALL {имя_дисковода_с_дискетой} {имя_диска} {имя_каталога}
echo   например:
echo     INSTALL A: D: \FAST - установка на диск "D:" в каталог "\FAST" с дискеты,
echo       помещенной в дисковод "A:";
echo     INSTALL B: C: \USER\FAST - установка на диск "C:" в подкаталог "FAST"
echo       УЖЕ СУЩЕСТВУЮЩЕГО каталога "USER" с дискеты, помещенной в дисковод "B:".
echo  
echo Для запуска программы после установки наберите команду:
echo     FAST
echo   Для установки полного комплекта на жестком диске необходимо около 1.4 Мбайт
goto END
:TYPEPAR
echo ОШИБКА! Неверное число параметров
goto STOP
:TYPEDEST
echo  
echo ОШИБКА! "%1" - неверное имя дисковода с установочной дискетой
echo   Измените имя дисковода в команде INSTALL.
goto STOP
:TYPEDRIVE
echo  
echo ОШИБКА! "%2" - неверное имя диска.
echo   Измените имя диска в команде INSTALL.
goto STOP
:TYPEDIR
echo  
echo ОШИБКА! "%3" - неверное имя каталога.
echo   Измените имя каталога в команде INSTALL.
goto STOP
:STOP
echo Использование:
echo     INSTALL {имя_дисковода_с_дискетой} {имя_диска} {имя_каталога}
echo   например:
echo     INSTALL A: D: \FAST - установка на диск "D:" в каталог "\FAST" с дискеты,
echo       помещенной в дисковод "A:";
echo     INSTALL B: C: \USER\FAST - установка на диск "C:" в подкаталог "FAST"
echo       УЖЕ СУЩЕСТВУЮЩЕГО каталога "USER" с дискеты, помещенной в дисковод "B:".
:END
