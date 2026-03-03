@echo off
cls
call .venv\scripts\activate.bat

:: tdoc-crawler crawl-meetings -s S4
:: tdoc-crawler crawl-tdocs --start-date 2016
:: tdoc-crawler query-tdocs --agenda "*atias*" --start-date 2018

tdoc-crawler ai workspace deactivate
tdoc-crawler ai workspace delete atias --no-preserve-artifacts
tdoc-crawler ai workspace create atias
:: tdoc-crawler ai workspace activate atias
tdoc-crawler ai workspace add-members 26131 26132 26260 26261 21905 --kind specs --release 19
tdoc-crawler ai workspace add-members 26260 26261 --kind specs --release 18.1.0
tdoc-crawler ai workspace add-members 26260 26261 --kind specs --release 18.0.0
tdoc-crawler ai workspace add-members 26260 26261 --kind specs --release 17
tdoc-crawler ai workspace add-members --kind tdocs --agenda "*atias*" --start-date 2017
tdoc-crawler ai workspace list-members
tdoc-crawler ai workspace process
tdoc-crawler ai query "Please summarize the evolution of test methods in all ATIAS work items between the releases, in particular focusing on IVAS-capable devices"
