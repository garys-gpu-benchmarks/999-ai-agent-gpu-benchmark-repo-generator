// File: src/rccl_perf.cpp
// Description: Single-process RCCL size sweep. argv0 selects the collective.
#include <hip/hip_runtime.h>
#include <rccl/rccl.h>

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

static void die(const char *msg) {
    std::fprintf(stderr, "%s\n", msg);
    std::exit(1);
}

int main(int argc, char **argv) {
    size_t min_bytes = 1024;
    size_t max_bytes = 1024 * 1024;
    int iters = 10;
    int warmup = 2;
    int factor = 2;
    int requested_gpus = 2;
    for (int i = 1; i < argc; ++i) {
        if (!std::strcmp(argv[i], "-b") && i + 1 < argc) {
            min_bytes = static_cast<size_t>(std::atoll(argv[++i]));
        } else if (!std::strcmp(argv[i], "-e") && i + 1 < argc) {
            max_bytes = static_cast<size_t>(std::atoll(argv[++i]));
        } else if (!std::strcmp(argv[i], "-n") && i + 1 < argc) {
            iters = std::max(1, std::atoi(argv[++i]));
        } else if (!std::strcmp(argv[i], "-w") && i + 1 < argc) {
            warmup = std::max(0, std::atoi(argv[++i]));
        } else if (!std::strcmp(argv[i], "-f") && i + 1 < argc) {
            factor = std::max(2, std::atoi(argv[++i]));
        } else if (!std::strcmp(argv[i], "-g") && i + 1 < argc) {
            requested_gpus = std::max(1, std::atoi(argv[++i]));
        }
    }
    if (min_bytes < 1) {
        min_bytes = 1;
    }
    if (max_bytes < min_bytes) {
        max_bytes = min_bytes;
    }
    const std::string name = argv[0] ? argv[0] : "all_reduce_perf";
    if (name.find("all_reduce") == std::string::npos) {
        die("this reference collector measures all_reduce only");
    }
    int available_gpus = 0;
    if (hipGetDeviceCount(&available_gpus) != hipSuccess || available_gpus < 1) {
        die("RCCL bandwidth requires a visible GPU");
    }
    const int num_gpus = std::min(requested_gpus, available_gpus);
    std::vector<int> devices(num_gpus);
    std::vector<ncclComm_t> comms(num_gpus);
    std::vector<hipStream_t> streams(num_gpus);
    for (int rank = 0; rank < num_gpus; ++rank) {
        devices[rank] = rank;
    }
    if (ncclCommInitAll(comms.data(), num_gpus, devices.data()) != ncclSuccess) {
        die("ncclCommInitAll failed");
    }
    for (int rank = 0; rank < num_gpus; ++rank) {
        hipSetDevice(rank);
        if (hipStreamCreate(&streams[rank]) != hipSuccess) {
            die("hipStreamCreate failed");
        }
    }
    std::printf("# num_gpus=%d collective=all_reduce\n", num_gpus);
    std::printf("# bytes    time(us)   algbw(GB/s)  busbw(GB/s)\n");
    for (size_t bytes = min_bytes; bytes <= max_bytes; bytes *= static_cast<size_t>(factor)) {
        size_t count = bytes / sizeof(float);
        if (count < 1) {
            count = 1;
        }
        std::vector<float *> send(num_gpus, nullptr);
        std::vector<float *> recv(num_gpus, nullptr);
        for (int rank = 0; rank < num_gpus; ++rank) {
            hipSetDevice(rank);
            if (hipMalloc(&send[rank], count * sizeof(float)) != hipSuccess ||
                hipMalloc(&recv[rank], count * sizeof(float)) != hipSuccess) {
                die("hipMalloc failed");
            }
        }
        auto launch = [&]() {
            ncclGroupStart();
            for (int rank = 0; rank < num_gpus; ++rank) {
                ncclAllReduce(
                    send[rank], recv[rank], count, ncclFloat, ncclSum,
                    comms[rank], streams[rank]);
            }
            ncclGroupEnd();
        };
        for (int warm = 0; warm < warmup; ++warm) {
            launch();
        }
        for (int rank = 0; rank < num_gpus; ++rank) {
            hipSetDevice(rank);
            hipStreamSynchronize(streams[rank]);
        }
        const auto t0 = std::chrono::steady_clock::now();
        for (int n = 0; n < iters; ++n) {
            launch();
        }
        for (int rank = 0; rank < num_gpus; ++rank) {
            hipSetDevice(rank);
            hipStreamSynchronize(streams[rank]);
        }
        const auto t1 = std::chrono::steady_clock::now();
        const double us = std::chrono::duration<double, std::micro>(t1 - t0).count() / iters;
        const double alg = (static_cast<double>(bytes) / 1.0e9) / (us / 1.0e6);
        const double bus = alg * (2.0 * (num_gpus - 1) / num_gpus);
        std::printf("%zu 1 1 1 1 %.3f %.3f %.3f\n", bytes, us, alg, bus);
        for (int rank = 0; rank < num_gpus; ++rank) {
            hipSetDevice(rank);
            hipFree(send[rank]);
            hipFree(recv[rank]);
        }
        if (bytes > max_bytes / static_cast<size_t>(factor)) {
            break;
        }
    }
    for (int rank = 0; rank < num_gpus; ++rank) {
        hipSetDevice(rank);
        hipStreamDestroy(streams[rank]);
        ncclCommDestroy(comms[rank]);
    }
    return 0;
}
