// File: src/gpu_stress.cu
// Description: cuBLAS GEMM load for NVIDIA system stress (203/403). Holds the GPU
//   busy for load_percent of every period_ms window by running FP16 GEMMs
//   (FP32 accumulate) back to back, then idles for the rest of the window, so
//   nvidia-smi utilization.gpu tracks the requested percentage.
// Execution: bin/gpu_stress <seconds> <load_percent> [matrix_n=8192] [period_ms=100]
// Output (stdout, one line each):
//   GPU_LOAD_READY n=<n> period_ms=<p> load_percent=<pct>        after warm-up
//   GPU_LOAD second=<s> gemms=<g> busy_pct=<b>                    once per second
//   GPU_LOAD_DONE seconds=<s> gemms=<g> busy_pct=<b> tflops_busy=<t>
// Exit 0 on success, 2 on any CUDA/cuBLAS error (message on stderr).
// Requirements: CUDA toolkit, NVCC, C++17, cuBLAS. Built by scripts/build.sh
//   with nvcc_arch_flags (native SASS), linked with -lcublas.

#include <cublas_v2.h>
#include <cuda_fp16.h>
#include <cuda_runtime.h>

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <thread>
#include <vector>

#define CUDA_OK(call)                                                          \
  do {                                                                         \
    cudaError_t err__ = (call);                                                \
    if (err__ != cudaSuccess) {                                                \
      std::fprintf(stderr, "CUDA %s at %s:%d\n", cudaGetErrorString(err__),    \
                   __FILE__, __LINE__);                                        \
      return 2;                                                                \
    }                                                                          \
  } while (0)

#define CUBLAS_OK(call)                                                        \
  do {                                                                         \
    cublasStatus_t st__ = (call);                                              \
    if (st__ != CUBLAS_STATUS_SUCCESS) {                                       \
      std::fprintf(stderr, "cuBLAS status %d at %s:%d\n", (int)st__, __FILE__, \
                   __LINE__);                                                  \
      return 2;                                                                \
    }                                                                          \
  } while (0)

using Clock = std::chrono::steady_clock;

static double ms_since(Clock::time_point t) {
  return std::chrono::duration<double, std::milli>(Clock::now() - t).count();
}

int main(int argc, char** argv) {
  if (argc < 3) {
    std::fprintf(stderr, "usage: gpu_stress <seconds> <load_percent> [matrix_n] [period_ms]\n");
    return 2;
  }
  double seconds = std::atof(argv[1]);
  double pct = std::atof(argv[2]);
  int n = argc > 3 ? std::atoi(argv[3]) : 8192;
  double period_ms = argc > 4 ? std::atof(argv[4]) : 100.0;
  if (seconds < 0.1) seconds = 0.1;
  if (pct < 0.0) pct = 0.0;
  if (pct > 100.0) pct = 100.0;
  if (n < 256) n = 256;
  if (period_ms < 10.0) period_ms = 10.0;

  const size_t elems = (size_t)n * (size_t)n;
  // Non-zero, varied inputs: an all-zero GEMM draws less power than real data.
  std::vector<__half> host(elems);
  unsigned int state = 12345u;
  for (size_t i = 0; i < elems; ++i) {
    state = state * 1664525u + 1013904223u;
    host[i] = __float2half(((float)((state >> 9) & 0x3FF) / 1023.0f - 0.5f) * 0.25f);
  }
  __half *a = nullptr, *b = nullptr, *c = nullptr;
  CUDA_OK(cudaMalloc(&a, elems * sizeof(__half)));
  CUDA_OK(cudaMalloc(&b, elems * sizeof(__half)));
  CUDA_OK(cudaMalloc(&c, elems * sizeof(__half)));
  CUDA_OK(cudaMemcpy(a, host.data(), elems * sizeof(__half), cudaMemcpyHostToDevice));
  CUDA_OK(cudaMemcpy(b, host.data(), elems * sizeof(__half), cudaMemcpyHostToDevice));
  CUDA_OK(cudaMemset(c, 0, elems * sizeof(__half)));

  cublasHandle_t handle;
  CUBLAS_OK(cublasCreate(&handle));
  const float alpha = 1.0f, beta = 0.0f;
  auto gemm = [&]() -> cublasStatus_t {
    return cublasGemmEx(handle, CUBLAS_OP_N, CUBLAS_OP_N, n, n, n, &alpha,
                        a, CUDA_R_16F, n, b, CUDA_R_16F, n, &beta,
                        c, CUDA_R_16F, n, CUBLAS_COMPUTE_32F, CUBLAS_GEMM_DEFAULT);
  };
  for (int i = 0; i < 3; ++i) CUBLAS_OK(gemm());
  CUDA_OK(cudaGetLastError());
  CUDA_OK(cudaDeviceSynchronize());
  std::printf("GPU_LOAD_READY n=%d period_ms=%.0f load_percent=%.1f\n", n, period_ms, pct);
  std::fflush(stdout);

  const double busy_ms_target = period_ms * pct / 100.0;
  const Clock::time_point start = Clock::now();
  const double total_ms = seconds * 1000.0;
  unsigned long long gemms = 0, sec_gemms = 0;
  double busy_ms = 0.0, sec_busy_ms = 0.0;
  int reported_second = 0;
  while (ms_since(start) < total_ms) {
    const Clock::time_point period_start = Clock::now();
    while (busy_ms_target > 0.0 && ms_since(period_start) < busy_ms_target) {
      const Clock::time_point g0 = Clock::now();
      CUBLAS_OK(gemm());
      CUDA_OK(cudaGetLastError());
      CUDA_OK(cudaDeviceSynchronize());
      const double g_ms = ms_since(g0);
      busy_ms += g_ms;
      sec_busy_ms += g_ms;
      ++gemms;
      ++sec_gemms;
    }
    const double rest = period_ms - ms_since(period_start);
    if (rest > 0.0) {
      std::this_thread::sleep_for(std::chrono::duration<double, std::milli>(rest));
    }
    const int second = (int)(ms_since(start) / 1000.0);
    if (second > reported_second) {
      std::printf("GPU_LOAD second=%d gemms=%llu busy_pct=%.1f\n", second, sec_gemms,
                  100.0 * sec_busy_ms / (1000.0 * (second - reported_second)));
      std::fflush(stdout);
      reported_second = second;
      sec_gemms = 0;
      sec_busy_ms = 0.0;
    }
  }
  const double elapsed_ms = ms_since(start);
  const double flops = 2.0 * (double)n * (double)n * (double)n * (double)gemms;
  std::printf("GPU_LOAD_DONE seconds=%.3f gemms=%llu busy_pct=%.1f tflops_busy=%.1f\n",
              elapsed_ms / 1000.0, gemms, 100.0 * busy_ms / elapsed_ms,
              busy_ms > 0.0 ? flops / (busy_ms / 1000.0) / 1e12 : 0.0);
  std::fflush(stdout);
  cublasDestroy(handle);
  cudaFree(a);
  cudaFree(b);
  cudaFree(c);
  return 0;
}
