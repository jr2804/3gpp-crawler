@echo off
cls
call .venv\scripts\activate.bat

SET TDC_AI_CONVERT_MD=1
SET TDC_AI_VLM=0

tdoc-crawler crawl-meetings -s S4
tdoc-crawler crawl --start-date 2016
tdoc-crawler query --agenda "*atias*" --start-date 2018

3gpp-ai workspace deactivate
3gpp-ai workspace delete atias --delete-artifacts
3gpp-ai workspace create atias
:: 3gpp-ai workspace activate atias
3gpp-ai workspace add-members S4-260109 --kind tdocs
3gpp-ai workspace add-members --kind tdocs --agenda "*atias*" --start-date 2017
3gpp-ai workspace add-members 26131 26132 26260 26261 21905 --kind specs --release 19
3gpp-ai workspace add-members 26260 --kind specs --release 18.1.0
3gpp-ai workspace add-members 26260 26261 --kind specs --release 18.0.0
3gpp-ai workspace add-members 26260 --kind specs --release 17
3gpp-ai workspace list-members
:: 3gpp-ai workspace process
:: 3gpp-ai query "Please summarize the evolution of test methods in all ATIAS work items between the releases, in particular focusing on IVAS-capable devices"
