@echo off
setlocal

set OLLAMA_LLM_LIBRARY=cuda_v12
set OLLAMA_DEBUG=1
set CUDA_VISIBLE_DEVICES=0
:: 5GB of reserved overhead left too little of the 8GB card for the model,
:: forcing layers onto CPU. 0 lets Ollama use the VRAM it actually needs.
set OLLAMA_GPU_OVERHEAD=0
:: Keep the model resident between requests so idle gaps (reading feedback,
:: switching tabs) don't pay a full reload on the next question.
set OLLAMA_KEEP_ALIVE=30m
set OLLAMA_FLASH_ATTENTION=1

set LOGDIR=%~dp0logs
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

ollama serve > "%LOGDIR%\ollama_debug.log" 2>&1
