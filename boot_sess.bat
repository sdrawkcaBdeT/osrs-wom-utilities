pushd %~dp0
start "GUI" cmd /k "python bbd_gui.py"
start "Matrix" cmd /k "python bbd_matrix.py"
start "BBD Tracker" cmd /k "python bbd_tracker.py"
start "Time Tracker" cmd /k "python time_tracker.py"