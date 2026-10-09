#!/usr/bin/env bash
# Build the checked-out stable-diffusion.cpp without modifying the LLM venv.
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
sdk="${root}/.runtime/sd-cuda133/nvidia/cu13"
libs=/opt/sovereign-os/venv/vllm/lib/python3.14/site-packages/nvidia/cu13/lib
for header in cublas.h cublasLt.h cublasXt.h cublas_api.h cublas_v2.h; do
  if [ ! -e "${sdk}/include/${header}" ]; then
    ln -s "${libs}/../include/${header}" "${sdk}/include/${header}"
  fi
done
cmake -S "${root}/.runtime/stable-diffusion.cpp" -B "${root}/.runtime/stable-diffusion.cpp/build-cuda133" \
  -DSD_CUDA=ON -DSD_SERVER_BUILD_FRONTEND=OFF -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_ARCHITECTURES=120 \
  -DCMAKE_CUDA_HOST_COMPILER=/usr/bin/g++-14 \
  -DCMAKE_CUDA_COMPILER="${sdk}/bin/nvcc" -DCUDAToolkit_ROOT="${sdk}" \
  -DCUDA_CUDART="${sdk}/lib/libcudart.so.13" -DCUDA_cudart_LIBRARY="${sdk}/lib/libcudart.so.13" \
  -DCUDA_cublas_LIBRARY="${libs}/libcublas.so.13" -DCUDA_cublasLt_LIBRARY="${libs}/libcublasLt.so.13"
cmake --build "${root}/.runtime/stable-diffusion.cpp/build-cuda133" --target sd-cli sd-server -j 6
