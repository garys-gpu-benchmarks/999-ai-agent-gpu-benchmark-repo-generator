// File: src/cudnn_conv.cu
// cuDNN convolution harness used by collect_cudnn_conv.py.
// One RESULT line per requested direction. Solver search is timed wall clock.
#include <cuda_bf16.h>
#include <cuda_fp16.h>
#include <cuda_runtime.h>
#include <cudnn.h>

#include <chrono>
#include <cmath>
#include <cctype>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#define CHECK_CUDA(cmd) do { cudaError_t e = (cmd); if (e != cudaSuccess) { \
  fprintf(stderr, "CUDA %s\n", cudaGetErrorString(e)); return 1; } } while (0)
#define CHECK_CUDNN(cmd) do { cudnnStatus_t s = (cmd); if (s != CUDNN_STATUS_SUCCESS) { \
  fprintf(stderr, "cuDNN %s\n", cudnnGetErrorString(s)); return 1; } } while (0)

static std::string lower_copy(std::string text) {
    for (char& ch : text) ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    return text;
}

enum class Dir { Fwd, BwdData, BwdWeights };

static int parse_dtype(const std::string& raw, cudnnDataType_t* dt, int* elem, const char** effective) {
    const std::string key = lower_copy(raw);
    if (key == "fp16") {
        *dt = CUDNN_DATA_HALF;
        *elem = 2;
        *effective = "HALF";
        return 0;
    }
    if (key == "bf16") {
        *dt = CUDNN_DATA_BFLOAT16;
        *elem = 2;
        *effective = "BFLOAT16";
        return 0;
    }
    if (key == "fp32") {
        *dt = CUDNN_DATA_FLOAT;
        *elem = 4;
        *effective = "FLOAT";
        return 0;
    }
    fprintf(stderr, "unsupported dtype %s\n", raw.c_str());
    return 2;
}

static int parse_directions(const std::string& raw, std::vector<Dir>* dirs) {
    const std::string key = lower_copy(raw);
    dirs->clear();
    if (key == "all") {
        dirs->push_back(Dir::Fwd);
        dirs->push_back(Dir::BwdData);
        dirs->push_back(Dir::BwdWeights);
        return 0;
    }
    if (key == "fwd" || key == "forward") {
        dirs->push_back(Dir::Fwd);
        return 0;
    }
    if (key == "bwd_data" || key == "bwd-data") {
        dirs->push_back(Dir::BwdData);
        return 0;
    }
    if (key == "bwd_weights" || key == "bwd-weights" || key == "bwd_filter" || key == "bwd-filter") {
        dirs->push_back(Dir::BwdWeights);
        return 0;
    }
    fprintf(stderr, "unsupported conv_direction %s\n", raw.c_str());
    return 2;
}

enum class SearchKind { Find, Heuristic, Get, Fixed, None };

static int parse_search(const std::string& raw, SearchKind* kind, const char** name) {
    const std::string key = lower_copy(raw);
    if (key == "find") {
        *kind = SearchKind::Find;
        *name = "find";
        return 0;
    }
    if (key == "heuristic") {
        *kind = SearchKind::Heuristic;
        *name = "heuristic";
        return 0;
    }
    if (key == "get") {
        *kind = SearchKind::Get;
        *name = "get";
        return 0;
    }
    if (key == "fixed") {
        *kind = SearchKind::Fixed;
        *name = "fixed";
        return 0;
    }
    if (key == "none") {
        *kind = SearchKind::None;
        *name = "none";
        return 0;
    }
    fprintf(stderr, "unsupported search_strategy %s\n", raw.c_str());
    return 2;
}

static const char* direction_name(Dir dir) {
    if (dir == Dir::Fwd) return "fwd";
    if (dir == Dir::BwdData) return "bwd_data";
    return "bwd_weights";
}

__global__ void fill_float(float* p, size_t n) {
    size_t i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) p[i] = (static_cast<int>(i % 201) - 100) / 100.0f;
}

__global__ void fill_half(__half* p, size_t n) {
    size_t i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) p[i] = __float2half((static_cast<int>(i % 201) - 100) / 100.0f);
}

__global__ void fill_bf16(__nv_bfloat16* p, size_t n) {
    size_t i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) p[i] = __float2bfloat16((static_cast<int>(i % 201) - 100) / 100.0f);
}

static int fill_buffer(void* p, size_t bytes, int elem, cudnnDataType_t dt) {
    if (bytes == 0) return 0;
    size_t n = bytes / static_cast<size_t>(elem);
    int blocks = static_cast<int>((n + 255) / 256);
    if (dt == CUDNN_DATA_HALF) fill_half<<<blocks, 256>>>(static_cast<__half*>(p), n);
    else if (dt == CUDNN_DATA_BFLOAT16) fill_bf16<<<blocks, 256>>>(static_cast<__nv_bfloat16*>(p), n);
    else fill_float<<<blocks, 256>>>(static_cast<float*>(p), n);
    CHECK_CUDA(cudaGetLastError());
    CHECK_CUDA(cudaDeviceSynchronize());
    return 0;
}

static double elapsed_ms(std::chrono::steady_clock::time_point start, std::chrono::steady_clock::time_point stop) {
    return std::chrono::duration<double, std::milli>(stop - start).count();
}

template <typename Perf>
static int first_success(const Perf* perf, int count, int* algo) {
    for (int i = 0; i < count; ++i) {
        if (perf[i].status == CUDNN_STATUS_SUCCESS) {
            *algo = static_cast<int>(perf[i].algo);
            return 0;
        }
    }
    return 1;
}

static void print_result(
    Dir dir, const std::string& dtype, const char* dtype_effective, const std::string& input_source,
    int batch, int cin, int hin, int win, int cout, int kh, int kw, int sh, int sw, int pad_h, int pad_w,
    int groups, const char* search_name, int algo, size_t workspace, int warmup, int iters,
    double ms, double tflops, double gbps, double search_ms) {
    printf(
        "RESULT direction=%s dtype=%s dtype_effective=%s input_source=%s batch_size=%d input_channels=%d "
        "input_height=%d input_width=%d output_channels=%d kernel_height=%d kernel_width=%d stride_h=%d "
        "stride_w=%d pad_h=%d pad_w=%d group_count=%d search_strategy=%s algo=%d workspace_bytes=%zu "
        "warmup_iters=%d num_iterations=%d kernel_time_msec=%.6f tflops=%.6f memory_bandwidth_gb_s=%.6f "
        "solver_search_msec=",
        direction_name(dir), dtype.c_str(), dtype_effective, input_source.c_str(), batch, cin, hin, win, cout,
        kh, kw, sh, sw, pad_h, pad_w, groups, search_name, algo, workspace, warmup, iters, ms, tflops, gbps);
    if (std::isnan(search_ms)) printf("nan");
    else printf("%.6f", search_ms);
    printf(" status=ok\n");
}

int main(int argc, char** argv) {
    std::string dtype = "FP16";
    std::string input_source = "synthetic";
    std::string conv_direction = "all";
    int batch = 1, cin = 8, hin = 16, win = 16, cout = 8, kh = 3, kw = 3, sh = 1, sw = 1, groups = 1;
    std::string search = "find";
    int warmup = 1, iters = 2;
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        auto take_i = [&](int& dest) { if (i + 1 < argc) dest = atoi(argv[++i]); };
        auto take_s = [&](std::string& dest) { if (i + 1 < argc) dest = argv[++i]; };
        if (arg == "--dtype") take_s(dtype);
        else if (arg == "--input-source") take_s(input_source);
        else if (arg == "--conv-direction") take_s(conv_direction);
        else if (arg == "--batch-size") take_i(batch);
        else if (arg == "--input-channels") take_i(cin);
        else if (arg == "--input-height") take_i(hin);
        else if (arg == "--input-width") take_i(win);
        else if (arg == "--output-channels") take_i(cout);
        else if (arg == "--kernel-height") take_i(kh);
        else if (arg == "--kernel-width") take_i(kw);
        else if (arg == "--stride-h") take_i(sh);
        else if (arg == "--stride-w") take_i(sw);
        else if (arg == "--group-count") take_i(groups);
        else if (arg == "--search-strategy") take_s(search);
        else if (arg == "--warmup-iters") take_i(warmup);
        else if (arg == "--num-iterations") take_i(iters);
    }
    if (batch < 1 || cin < 1 || hin < 1 || win < 1 || cout < 1 || kh < 1 || kw < 1 || sh < 1 || sw < 1 || groups < 1 || iters < 1) {
        fprintf(stderr, "convolution shape is not positive\n");
        return 2;
    }
    if (cin % groups != 0) {
        fprintf(stderr, "input_channels %d is not divisible by group_count %d\n", cin, groups);
        return 2;
    }
    cudnnDataType_t dt = CUDNN_DATA_FLOAT;
    int elem = 4;
    const char* dtype_effective = "FLOAT";
    int dtype_rc = parse_dtype(dtype, &dt, &elem, &dtype_effective);
    if (dtype_rc != 0) return dtype_rc;
    std::vector<Dir> directions;
    int dir_rc = parse_directions(conv_direction, &directions);
    if (dir_rc != 0) return dir_rc;
    SearchKind search_kind = SearchKind::Find;
    const char* search_name = "find";
    int search_rc = parse_search(search, &search_kind, &search_name);
    if (search_rc != 0) return search_rc;

    const int pad_h = kh / 2;
    const int pad_w = kw / 2;
    const int hout = (hin + 2 * pad_h - kh) / sh + 1;
    const int wout = (win + 2 * pad_w - kw) / sw + 1;
    if (hout < 1 || wout < 1) {
        fprintf(stderr, "output spatial size is empty (%d x %d)\n", hout, wout);
        return 1;
    }

    cudnnHandle_t handle;
    CHECK_CUDNN(cudnnCreate(&handle));
    cudnnTensorDescriptor_t xDesc, yDesc;
    cudnnFilterDescriptor_t wDesc;
    cudnnConvolutionDescriptor_t convDesc;
    CHECK_CUDNN(cudnnCreateTensorDescriptor(&xDesc));
    CHECK_CUDNN(cudnnCreateTensorDescriptor(&yDesc));
    CHECK_CUDNN(cudnnCreateFilterDescriptor(&wDesc));
    CHECK_CUDNN(cudnnCreateConvolutionDescriptor(&convDesc));
    CHECK_CUDNN(cudnnSetTensor4dDescriptor(xDesc, CUDNN_TENSOR_NCHW, dt, batch, cin, hin, win));
    CHECK_CUDNN(cudnnSetTensor4dDescriptor(yDesc, CUDNN_TENSOR_NCHW, dt, batch, cout, hout, wout));
    CHECK_CUDNN(cudnnSetFilter4dDescriptor(wDesc, dt, CUDNN_TENSOR_NCHW, cout, cin / groups, kh, kw));
    CHECK_CUDNN(cudnnSetConvolution2dDescriptor(convDesc, pad_h, pad_w, sh, sw, 1, 1, CUDNN_CROSS_CORRELATION, CUDNN_DATA_FLOAT));
    if (groups > 1) CHECK_CUDNN(cudnnSetConvolutionGroupCount(convDesc, groups));
    if (dt == CUDNN_DATA_HALF || dt == CUDNN_DATA_BFLOAT16) {
        CHECK_CUDNN(cudnnSetConvolutionMathType(convDesc, CUDNN_TENSOR_OP_MATH));
    }

    const size_t xbytes = (size_t)batch * cin * hin * win * (size_t)elem;
    const size_t ybytes = (size_t)batch * cout * hout * wout * (size_t)elem;
    const size_t wbytes = (size_t)cout * (cin / groups) * kh * kw * (size_t)elem;
    void *x = nullptr, *y = nullptr, *w = nullptr, *dx = nullptr, *dw = nullptr, *ws = nullptr;
    CHECK_CUDA(cudaMalloc(&x, xbytes));
    CHECK_CUDA(cudaMalloc(&y, ybytes));
    CHECK_CUDA(cudaMalloc(&w, wbytes));
    CHECK_CUDA(cudaMalloc(&dx, xbytes));
    CHECK_CUDA(cudaMalloc(&dw, wbytes));
    if (fill_buffer(x, xbytes, elem, dt) || fill_buffer(w, wbytes, elem, dt) || fill_buffer(y, ybytes, elem, dt)) return 1;

    float alpha = 1.0f, beta = 0.0f;
    cudaEvent_t start, stop;
    CHECK_CUDA(cudaEventCreate(&start));
    CHECK_CUDA(cudaEventCreate(&stop));
    const double flops = 2.0 * batch * cout * hout * wout * (cin / groups) * kh * kw;
    const bool time_search = search_kind == SearchKind::Find || search_kind == SearchKind::Heuristic || search_kind == SearchKind::Get;

    for (Dir dir : directions) {
        int algo = 0;
        double search_ms = std::nan("");
        size_t workspace = 0;
        if (dir == Dir::Fwd) {
            if (time_search) {
                cudnnConvolutionFwdAlgoPerf_t perf[CUDNN_CONVOLUTION_FWD_ALGO_COUNT];
                int returned = 0;
                CHECK_CUDA(cudaDeviceSynchronize());
                auto t0 = std::chrono::steady_clock::now();
                cudnnStatus_t st = (search_kind == SearchKind::Find)
                    ? cudnnFindConvolutionForwardAlgorithm(handle, xDesc, wDesc, convDesc, yDesc, CUDNN_CONVOLUTION_FWD_ALGO_COUNT, &returned, perf)
                    : cudnnGetConvolutionForwardAlgorithm_v7(handle, xDesc, wDesc, convDesc, yDesc, CUDNN_CONVOLUTION_FWD_ALGO_COUNT, &returned, perf);
                CHECK_CUDA(cudaDeviceSynchronize());
                auto t1 = std::chrono::steady_clock::now();
                if (st != CUDNN_STATUS_SUCCESS) {
                    fprintf(stderr, "cuDNN forward search %s\n", cudnnGetErrorString(st));
                    return 1;
                }
                search_ms = elapsed_ms(t0, t1);
                if (first_success(perf, returned, &algo) != 0) {
                    fprintf(stderr, "cuDNN forward search returned no successful algorithm\n");
                    return 1;
                }
            } else {
                algo = static_cast<int>(CUDNN_CONVOLUTION_FWD_ALGO_IMPLICIT_GEMM);
            }
            CHECK_CUDNN(cudnnGetConvolutionForwardWorkspaceSize(handle, xDesc, wDesc, convDesc, yDesc, static_cast<cudnnConvolutionFwdAlgo_t>(algo), &workspace));
        } else if (dir == Dir::BwdData) {
            if (time_search) {
                cudnnConvolutionBwdDataAlgoPerf_t perf[CUDNN_CONVOLUTION_BWD_DATA_ALGO_COUNT];
                int returned = 0;
                CHECK_CUDA(cudaDeviceSynchronize());
                auto t0 = std::chrono::steady_clock::now();
                cudnnStatus_t st = (search_kind == SearchKind::Find)
                    ? cudnnFindConvolutionBackwardDataAlgorithm(handle, wDesc, yDesc, convDesc, xDesc, CUDNN_CONVOLUTION_BWD_DATA_ALGO_COUNT, &returned, perf)
                    : cudnnGetConvolutionBackwardDataAlgorithm_v7(handle, wDesc, yDesc, convDesc, xDesc, CUDNN_CONVOLUTION_BWD_DATA_ALGO_COUNT, &returned, perf);
                CHECK_CUDA(cudaDeviceSynchronize());
                auto t1 = std::chrono::steady_clock::now();
                if (st != CUDNN_STATUS_SUCCESS) {
                    fprintf(stderr, "cuDNN backward-data search %s\n", cudnnGetErrorString(st));
                    return 1;
                }
                search_ms = elapsed_ms(t0, t1);
                if (first_success(perf, returned, &algo) != 0) {
                    fprintf(stderr, "cuDNN backward-data search returned no successful algorithm\n");
                    return 1;
                }
            } else {
                algo = static_cast<int>(CUDNN_CONVOLUTION_BWD_DATA_ALGO_1);
            }
            CHECK_CUDNN(cudnnGetConvolutionBackwardDataWorkspaceSize(handle, wDesc, yDesc, convDesc, xDesc, static_cast<cudnnConvolutionBwdDataAlgo_t>(algo), &workspace));
        } else {
            if (time_search) {
                cudnnConvolutionBwdFilterAlgoPerf_t perf[CUDNN_CONVOLUTION_BWD_FILTER_ALGO_COUNT];
                int returned = 0;
                CHECK_CUDA(cudaDeviceSynchronize());
                auto t0 = std::chrono::steady_clock::now();
                cudnnStatus_t st = (search_kind == SearchKind::Find)
                    ? cudnnFindConvolutionBackwardFilterAlgorithm(handle, xDesc, yDesc, convDesc, wDesc, CUDNN_CONVOLUTION_BWD_FILTER_ALGO_COUNT, &returned, perf)
                    : cudnnGetConvolutionBackwardFilterAlgorithm_v7(handle, xDesc, yDesc, convDesc, wDesc, CUDNN_CONVOLUTION_BWD_FILTER_ALGO_COUNT, &returned, perf);
                CHECK_CUDA(cudaDeviceSynchronize());
                auto t1 = std::chrono::steady_clock::now();
                if (st != CUDNN_STATUS_SUCCESS) {
                    fprintf(stderr, "cuDNN backward-weights search %s\n", cudnnGetErrorString(st));
                    return 1;
                }
                search_ms = elapsed_ms(t0, t1);
                if (first_success(perf, returned, &algo) != 0) {
                    fprintf(stderr, "cuDNN backward-weights search returned no successful algorithm\n");
                    return 1;
                }
            } else {
                algo = static_cast<int>(CUDNN_CONVOLUTION_BWD_FILTER_ALGO_1);
            }
            CHECK_CUDNN(cudnnGetConvolutionBackwardFilterWorkspaceSize(handle, xDesc, yDesc, convDesc, wDesc, static_cast<cudnnConvolutionBwdFilterAlgo_t>(algo), &workspace));
        }
        if (ws) {
            CHECK_CUDA(cudaFree(ws));
            ws = nullptr;
        }
        if (workspace > 0) CHECK_CUDA(cudaMalloc(&ws, workspace));

        auto launch = [&](int) -> int {
            if (dir == Dir::Fwd) {
                CHECK_CUDNN(cudnnConvolutionForward(handle, &alpha, xDesc, x, wDesc, w, convDesc, static_cast<cudnnConvolutionFwdAlgo_t>(algo), ws, workspace, &beta, yDesc, y));
            } else if (dir == Dir::BwdData) {
                CHECK_CUDNN(cudnnConvolutionBackwardData(handle, &alpha, wDesc, w, yDesc, y, convDesc, static_cast<cudnnConvolutionBwdDataAlgo_t>(algo), ws, workspace, &beta, xDesc, dx));
            } else {
                CHECK_CUDNN(cudnnConvolutionBackwardFilter(handle, &alpha, xDesc, x, yDesc, y, convDesc, static_cast<cudnnConvolutionBwdFilterAlgo_t>(algo), ws, workspace, &beta, wDesc, dw));
            }
            return 0;
        };
        for (int i = 0; i < warmup; ++i) {
            if (launch(i) != 0) return 1;
        }
        CHECK_CUDA(cudaDeviceSynchronize());
        CHECK_CUDA(cudaEventRecord(start));
        for (int i = 0; i < iters; ++i) {
            if (launch(i) != 0) return 1;
        }
        CHECK_CUDA(cudaEventRecord(stop));
        CHECK_CUDA(cudaEventSynchronize(stop));
        float ms = 0;
        CHECK_CUDA(cudaEventElapsedTime(&ms, start, stop));
        ms /= static_cast<float>(iters);
        if (!(ms > 0.0f)) {
            fprintf(stderr, "kernel time for %s was not positive\n", direction_name(dir));
            return 1;
        }
        double bytes_moved = 0;
        if (dir == Dir::Fwd) bytes_moved = (double)(xbytes + wbytes + ybytes);
        else if (dir == Dir::BwdData) bytes_moved = (double)(ybytes + wbytes + xbytes);
        else bytes_moved = (double)(xbytes + ybytes + wbytes);
        double tflops = (flops / 1e12) / (ms / 1e3);
        double gbps = (bytes_moved / 1e9) / (ms / 1e3);
        print_result(dir, dtype, dtype_effective, input_source, batch, cin, hin, win, cout, kh, kw, sh, sw, pad_h, pad_w, groups, search_name, algo, workspace, warmup, iters, ms, tflops, gbps, search_ms);
    }

    if (ws) CHECK_CUDA(cudaFree(ws));
    CHECK_CUDA(cudaFree(x));
    CHECK_CUDA(cudaFree(y));
    CHECK_CUDA(cudaFree(w));
    CHECK_CUDA(cudaFree(dx));
    CHECK_CUDA(cudaFree(dw));
    CHECK_CUDA(cudaEventDestroy(start));
    CHECK_CUDA(cudaEventDestroy(stop));
    CHECK_CUDNN(cudnnDestroyTensorDescriptor(xDesc));
    CHECK_CUDNN(cudnnDestroyTensorDescriptor(yDesc));
    CHECK_CUDNN(cudnnDestroyFilterDescriptor(wDesc));
    CHECK_CUDNN(cudnnDestroyConvolutionDescriptor(convDesc));
    CHECK_CUDNN(cudnnDestroy(handle));
    return 0;
}
