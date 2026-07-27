@echo off
setlocal

set CUDA_VISIBLE_DEVICES=
set OLLAMA_LLM_LIBRARY=cpu
set OLLAMA_GPU_OVERHEAD=0
set OLLAMA_DEBUG=1
set OLLAMA_KEEP_ALIVE=30m

set LOGDIR=%~dp0logs
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

ollama serve > "%LOGDIR%\ollama_cpu.log" 2>&1
