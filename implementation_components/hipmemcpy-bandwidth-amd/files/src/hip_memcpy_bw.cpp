// File: src/hip_memcpy_bw.cpp
// Description: Timed hipMemcpy H2D/D2H/D2D sweep. direction=all runs all three.
#include <hip/hip_runtime.h>

#include <chrono>
#include <cctype>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

static void die(const char *msg) {
    std::fprintf(stderr, "%s\n", msg);
    std::exit(1);
}

static void hip_check(hipError_t status, const char *msg) {
    if (status != hipSuccess) {
        die(msg);
    }
}

static int parse_bool(const char *value) {
    if (value == nullptr || value[0] == '\0') {
        return 0;
    }
    if (std::strcmp(value, "1") == 0) {
        return 1;
    }
    if (std::strcmp(value, "0") == 0) {
        return 0;
    }
    std::string lowered(value);
    for (char &ch : lowered) {
        ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    }
    if (lowered == "true" || lowered == "yes" || lowered == "on") {
        return 1;
    }
    return 0;
}

static std::string upper_copy(std::string text) {
    for (char &ch : text) {
        ch = static_cast<char>(std::toupper(static_cast<unsigned char>(ch)));
    }
    return text;
}

static bool wants_direction(const std::string &direction, const char *token) {
    const std::string folded = upper_copy(direction);
    if (folded.empty() || folded == "ALL" || folded == "*") {
        return true;
    }
    return folded.find(token) != std::string::npos;
}

static void usage() {
    std::fprintf(
        stdout,
        "usage: hip_memcpy_bw [--direction H2D,D2H,D2D|all] [--pinned-memory true|false|1|0]\n"
        "                     [--min-bytes N] [--max-bytes N|-b N] [--step-factor N]\n"
        "                     [--warmup-iters N] [--num-iterations N|-n N]\n");
}

int main(int argc, char **argv) {
    std::string direction = "all";
    int pinned = 1;
    size_t min_bytes = 1024;
    size_t max_bytes = 1024 * 1024;
    int step_factor = 4;
    int warmup = 1;
    int iters = 3;
    for (int i = 1; i < argc; ++i) {
        auto take = [&](const char *flag) -> const char * {
            if (std::strcmp(argv[i], flag) == 0 && i + 1 < argc) {
                return argv[++i];
            }
            return nullptr;
        };
        if (std::strcmp(argv[i], "--help") == 0 || std::strcmp(argv[i], "-h") == 0) {
            usage();
            return 0;
        }
        if (const char *value = take("--direction")) {
            direction = value;
        } else if (const char *value = take("--pinned-memory")) {
            pinned = parse_bool(value);
        } else if (const char *value = take("--min-bytes")) {
            min_bytes = static_cast<size_t>(std::atoll(value));
        } else if (const char *value = take("-b")) {
            max_bytes = static_cast<size_t>(std::atoll(value));
        } else if (const char *value = take("--max-bytes")) {
            max_bytes = static_cast<size_t>(std::atoll(value));
        } else if (const char *value = take("--step-factor")) {
            step_factor = std::max(2, std::atoi(value));
        } else if (const char *value = take("--warmup-iters")) {
            warmup = std::max(0, std::atoi(value));
        } else if (const char *value = take("-n")) {
            iters = std::max(1, std::atoi(value));
        } else if (const char *value = take("--num-iterations")) {
            iters = std::max(1, std::atoi(value));
        }
    }
    if (min_bytes < 1) {
        min_bytes = 1;
    }
    if (max_bytes < min_bytes) {
        max_bytes = min_bytes;
    }
    if (hipSetDevice(0) != hipSuccess) {
        die("hipSetDevice failed");
    }
    std::printf("sample_index,status,direction,pinned_memory,transfer_size_bytes,latency_us,bandwidth_GBps,error_message\n");
    int index = 0;
    auto run_host_dir = [&](const char *name, hipMemcpyKind kind) {
        for (size_t bytes = min_bytes; bytes <= max_bytes; bytes *= static_cast<size_t>(step_factor)) {
            void *host = nullptr;
            void *dev = nullptr;
            if (pinned) {
                if (hipHostMalloc(&host, bytes, hipHostMallocDefault) != hipSuccess) {
                    die("hipHostMalloc failed");
                }
            } else {
                host = std::malloc(bytes);
                if (host == nullptr) {
                    die("malloc failed");
                }
            }
            if (hipMalloc(&dev, bytes) != hipSuccess) {
                die("hipMalloc failed");
            }
            std::memset(host, 1, bytes);
            if (kind == hipMemcpyDeviceToHost) {
                if (hipMemcpy(dev, host, bytes, hipMemcpyHostToDevice) != hipSuccess) {
                    die("hipMemcpy prime D2H failed");
                }
            }
            const void *src = (kind == hipMemcpyHostToDevice) ? host : dev;
            void *dst = (kind == hipMemcpyHostToDevice) ? dev : host;
            for (int warm = 0; warm < warmup; ++warm) {
                hip_check(hipMemcpy(dst, src, bytes, kind), "hipMemcpy warmup failed");
            }
            hip_check(hipDeviceSynchronize(), "hipDeviceSynchronize warmup failed");
            const auto t0 = std::chrono::steady_clock::now();
            for (int n = 0; n < iters; ++n) {
                hip_check(hipMemcpy(dst, src, bytes, kind), "hipMemcpy timed copy failed");
            }
            hip_check(hipDeviceSynchronize(), "hipDeviceSynchronize timed copy failed");
            const auto t1 = std::chrono::steady_clock::now();
            const double us = std::chrono::duration<double, std::micro>(t1 - t0).count() / iters;
            const double gbps = (static_cast<double>(bytes) / 1.0e9) / (us / 1.0e6);
            std::printf("%d,ok,%s,%d,%zu,%.3f,%.3f,\n", index++, name, pinned, bytes, us, gbps);
            hip_check(hipFree(dev), "hipFree failed");
            if (pinned) {
                hip_check(hipHostFree(host), "hipHostFree failed");
            } else {
                std::free(host);
            }
            if (bytes > max_bytes / static_cast<size_t>(step_factor)) {
                break;
            }
        }
    };
    if (wants_direction(direction, "H2D")) {
        run_host_dir("H2D", hipMemcpyHostToDevice);
    }
    if (wants_direction(direction, "D2H")) {
        run_host_dir("D2H", hipMemcpyDeviceToHost);
    }
    if (wants_direction(direction, "D2D")) {
        for (size_t bytes = min_bytes; bytes <= max_bytes; bytes *= static_cast<size_t>(step_factor)) {
            void *src = nullptr;
            void *dst = nullptr;
            if (hipMalloc(&src, bytes) != hipSuccess || hipMalloc(&dst, bytes) != hipSuccess) {
                die("hipMalloc D2D failed");
            }
            if (hipMemset(src, 1, bytes) != hipSuccess) {
                die("hipMemset D2D failed");
            }
            for (int warm = 0; warm < warmup; ++warm) {
                hip_check(hipMemcpy(dst, src, bytes, hipMemcpyDeviceToDevice), "hipMemcpy D2D warmup failed");
            }
            hip_check(hipDeviceSynchronize(), "hipDeviceSynchronize D2D warmup failed");
            const auto t0 = std::chrono::steady_clock::now();
            for (int n = 0; n < iters; ++n) {
                hip_check(hipMemcpy(dst, src, bytes, hipMemcpyDeviceToDevice), "hipMemcpy D2D timed copy failed");
            }
            hip_check(hipDeviceSynchronize(), "hipDeviceSynchronize D2D timed copy failed");
            const auto t1 = std::chrono::steady_clock::now();
            const double us = std::chrono::duration<double, std::micro>(t1 - t0).count() / iters;
            const double gbps = (static_cast<double>(bytes) / 1.0e9) / (us / 1.0e6);
            std::printf("%d,ok,D2D,%d,%zu,%.3f,%.3f,\n", index++, pinned, bytes, us, gbps);
            hip_check(hipFree(src), "hipFree D2D src failed");
            hip_check(hipFree(dst), "hipFree D2D dst failed");
            if (bytes > max_bytes / static_cast<size_t>(step_factor)) {
                break;
            }
        }
    }
    if (index == 0) {
        die("no hipMemcpy directions ran; pass --direction all or H2D,D2H,D2D");
    }
    return 0;
}
