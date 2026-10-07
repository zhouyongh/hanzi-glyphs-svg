@echo off
rem 一键拉取「開元小篆」上游仓库到本地查看（只看不入库）。
rem 双击或在命令行运行；实际逻辑在 src\fetch_seal_upstream.py。
setlocal
cd /d "%~dp0"
if defined MIMO_PYTHON (
  "%MIMO_PYTHON%" src\fetch_seal_upstream.py %*
) else (
  python src\fetch_seal_upstream.py %*
)
endlocal
