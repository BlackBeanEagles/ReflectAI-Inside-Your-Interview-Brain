@echo off
set OLLAMA_LLM_LIBRARY=cuda_v12
set OLLAMA_DEBUG=1
set CUDA_VISIBLE_DEVICES=0
set OLLAMA_GPU_OVERHEAD=5000000000
ollama serve > "C:\Users\hridy\Desktop\reflect_inter\ollama_debug.log" 2>&1
