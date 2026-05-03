@echo off
set CUDA_VISIBLE_DEVICES=
set OLLAMA_LLM_LIBRARY=cpu
set OLLAMA_GPU_OVERHEAD=0
set OLLAMA_DEBUG=1
ollama serve > "C:\Users\hridy\Desktop\reflect_inter\ollama_cpu.log" 2>&1
