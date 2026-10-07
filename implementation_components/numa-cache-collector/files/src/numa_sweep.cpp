// File: src/numa_sweep.cpp
// Description: Random dependent pointer chase used by collect_numa_cache.py. Sequential remains available with --pattern sequential.
#include <algorithm>
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <chrono>
#include <numeric>
#include <random>
#include <thread>
#include <vector>

int main(int argc, char** argv) {
    size_t bytes = 32768;
    size_t stride = 64;
    unsigned long iters = 20000;
    int threads = 1;
    std::string pattern = "random";
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        auto next = [&](size_t& dest) {
            if (i + 1 < argc) dest = static_cast<size_t>(std::strtoull(argv[++i], nullptr, 10));
        };
        if (arg == "--size") next(bytes);
        else if (arg == "--stride") next(stride);
        else if (arg == "--iters") {
            if (i + 1 < argc) iters = std::strtoul(argv[++i], nullptr, 10);
        } else if (arg == "--threads") {
            if (i + 1 < argc) threads = std::atoi(argv[++i]);
        } else if (arg == "--pattern" && i + 1 < argc) {
            pattern = argv[++i];
        }
    }
    if (threads < 1) threads = 1;
    if (stride < sizeof(size_t)) stride = sizeof(size_t);
    size_t count = bytes / stride;
    if (count < 2) count = 2;
    std::vector<char> buf(count * stride, 0);
    std::vector<size_t> order(count);
    std::iota(order.begin(), order.end(), 0);
    if (pattern == "random") {
        std::mt19937_64 rng(0x4e554d4153574545ULL);
        std::shuffle(order.begin(), order.end(), rng);
        for (size_t i = 0; i < count; ++i) {
            const size_t current = order[i];
            const size_t next = order[(i + 1) % count];
            *reinterpret_cast<size_t*>(buf.data() + current * stride) = next;
        }
    } else {
        for (size_t i = 0; i < count; ++i) {
            *reinterpret_cast<size_t*>(buf.data() + i * stride) = (i + 1) % count;
        }
    }
    const volatile char* data = buf.data();
    std::vector<size_t> final_positions(static_cast<size_t>(threads), 0);
    std::atomic<int> ready{0};
    std::atomic<bool> start{false};
    std::vector<std::thread> workers;
    workers.reserve(static_cast<size_t>(threads));
    for (int thread_id = 0; thread_id < threads; ++thread_id) {
        workers.emplace_back([&, thread_id]() {
            size_t idx = order[(count * static_cast<size_t>(thread_id)) / static_cast<size_t>(threads)];
            for (unsigned long i = 0; i < iters / 10 + 100; ++i) {
                idx = *reinterpret_cast<const volatile size_t*>(data + idx * stride);
            }
            ready.fetch_add(1, std::memory_order_release);
            while (!start.load(std::memory_order_acquire)) {
                std::this_thread::yield();
            }
            for (unsigned long i = 0; i < iters; ++i) {
                idx = *reinterpret_cast<const volatile size_t*>(data + idx * stride);
            }
            final_positions[static_cast<size_t>(thread_id)] = idx;
        });
    }
    while (ready.load(std::memory_order_acquire) != threads) {
        std::this_thread::yield();
    }
    const auto t0 = std::chrono::steady_clock::now();
    start.store(true, std::memory_order_release);
    for (auto& worker : workers) worker.join();
    const auto t1 = std::chrono::steady_clock::now();
    double sec = std::chrono::duration<double>(t1 - t0).count();
    double ns = sec * 1e9 / static_cast<double>(iters);
    double gb = (
        static_cast<double>(iters) * static_cast<double>(threads) * static_cast<double>(sizeof(size_t))
    ) / (sec * 1e9);
    size_t checksum = 0;
    for (size_t idx : final_positions) checksum ^= idx;
    std::printf("ns/access = %.4f\n", ns);
    std::printf("bandwidth_gb_s = %.4f\n", gb);
    std::printf("threads = %d\n", threads);
    std::printf("idx_checksum=%zu\n", checksum);
    return 0;
}
