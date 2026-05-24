@echo off
cls
call .venv\scripts\activate.bat

SET TDC_WORKSPACE=atias
SET TDC_FIGURES=reference

:: Crawl *all* meetings from SA4
tdoc-crawler crawl-meetings -s S4
tdoc-crawler crawl-meetings -s SP

:: crawl all tdocs metadata from 2016 on onwards
tdoc-crawler crawl --start-date 2016

:: query tdocs from atias agenda items from 2018 on onwards
tdoc-crawler query --agenda "*atias*" --start-date 2018

:: remove and re-create workspace 'atias'
3gpp-crawler workspace deactivate
3gpp-crawler workspace delete atias --force
3gpp-crawler workspace create atias
3gpp-crawler workspace activate atias

:: add single tdoc to workspace ('-w atias' is optional if workspace is active)
3gpp-crawler workspace add SP-251352 SP-241314 SP-190040 --kind tdoc -w atias

:: add all tdocs from agenda items matching '*atias*' (from all meetings)
3gpp-crawler workspace add --agenda "*atias*"
3gpp-crawler workspace add --title "*split render*"
3gpp-crawler workspace add --source "*audio swg*"

:: add specs in different versions/releases
:: ... latest (default; currently 19.1.0)
3gpp-crawler workspace add 26131 26132 26260 26261 21905 --kind spec

:: ... specific releases
3gpp-crawler workspace add 26260 --kind spec --release 18.1
3gpp-crawler workspace add 26260 26261 --kind spec --release 18.0
3gpp-crawler workspace add 26260 --kind spec --release 17

:: duplicates should give a warning
3gpp-crawler workspace add 26260 --kind spec --release 18.1

3gpp-crawler workspace add 26250:26258 --kind spec

:: add other sources
3gpp-crawler workspace add https://www.itu.int/dms_pubrec/itu-r/rec/bs/R-REC-BS.775-1-199407-S!!PDF-E.pdf --kind other
3gpp-crawler workspace add https://www.itu.int/dms_pub/itu-r/opb/rep/r-rep-bs.2159-6-2013-pdf-e.pdf --kind other
3gpp-crawler workspace add https://en.wikipedia.org/wiki/Ambisonics --kind other


:: overview
3gpp-crawler workspace members

:: convert tdocs/specs to PDF/artefacts for AI processing (portable fallback profile)
:: 3gpp-crawler workspace process atias --profile pdf-only
3gpp-crawler workspace process atias --profile markdown-only --docx-direct --device cuda
:: 3gpp-crawler workspace process atias --profile default
:: 3gpp-crawler workspace process atias --profile advanced --device cuda
