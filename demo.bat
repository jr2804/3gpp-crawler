@echo off
cls
call .venv\scripts\activate.bat

:: SET TDC_AI_CONVERT_MD=1
:: SET TDC_AI_VLM=1
SET TDC_AI_EXTRACTION_PROFILE=optimum

:: tdoc-crawler crawl-meetings -s S4
:: tdoc-crawler crawl --start-date 2016
tdoc-crawler query --agenda "*atias*" --start-date 2018

3gpp-crawler workspace deactivate
3gpp-crawler workspace delete atias --force
3gpp-crawler workspace create atias
3gpp-crawler workspace activate atias
:: add tdocs
3gpp-crawler workspace add atias S4-260109 --kind tdoc

:: add specs in different versions/releases
3gpp-crawler workspace add atias 26131 26132 26260 26261 21905 --kind spec
3gpp-crawler workspace add atias 26260 --kind spec
3gpp-crawler workspace add atias 26260 26261 --kind spec
3gpp-crawler workspace add atias 26260 --kind spec
3gpp-crawler workspace members atias
:: 3gpp-crawler workspace process atias
