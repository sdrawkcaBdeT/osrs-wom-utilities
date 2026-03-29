pushd %~dp0
start "Main" cmd /k "python main.py"
start "Market Logger" cmd /k "python market_logger.py"
start "Data Pipeline" cmd /k "python pipeline.py"