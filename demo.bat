@echo off
cls
call .venv\scripts\activate.bat

:: Crawl *all* meetings from SA4
tdoc-crawler crawl-meetings -s S4
tdoc-crawler crawl-meetings -s SP

:: crawl all tdocs metadata from 2016 on onwards
tdoc-crawler crawl --start-date 2016

:: query tdocs from atias agenda items from 2018 on onwards
tdoc-crawler query --agenda "*atias*" --start-date 2018
