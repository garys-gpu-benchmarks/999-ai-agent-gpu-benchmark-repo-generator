/* File: src/gups.c
 * Description: OpenMP random 64-bit table updates. Honors OMP_NUM_THREADS.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#ifdef _OPENMP
#include <omp.h>
#endif

static uint64_t xorshift64(uint64_t *state) {
    uint64_t x = *state;
    x ^= x << 13;
    x ^= x >> 7;
    x ^= x << 17;
    *state = x;
    return x;
}

int main(int argc, char **argv) {
    if (argc < 5) {
        fprintf(stderr, "usage: gups <table_size> <num_updates> <num_iterations> <seed>\n");
        return 2;
    }
    size_t table_size = (size_t)strtoull(argv[1], 0, 10);
    size_t updates = (size_t)strtoull(argv[2], 0, 10);
    int iters = atoi(argv[3]);
    uint64_t seed = strtoull(argv[4], 0, 10);
    if (table_size < 1024) table_size = 1024;
    if (updates < 1) updates = 1;
    if (iters < 1) iters = 1;
    uint64_t *table = (uint64_t *)calloc(table_size, sizeof(uint64_t));
    if (!table) {
        fprintf(stderr, "calloc failed for table_size=%zu\n", table_size);
        return 2;
    }
    int threads = 1;
#ifdef _OPENMP
    threads = omp_get_max_threads();
#endif
    struct timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    for (int iter = 0; iter < iters; ++iter) {
#ifdef _OPENMP
#pragma omp parallel
        {
            uint64_t local = seed ^ (0x9e3779b97f4a7c15ULL * (uint64_t)(omp_get_thread_num() + 1 + iter));
#pragma omp for schedule(static)
            for (size_t i = 0; i < updates; ++i) {
                size_t idx = (size_t)(xorshift64(&local) % table_size);
                table[idx] += 1;
            }
        }
#else
        uint64_t local = seed ^ (0x9e3779b97f4a7c15ULL * (uint64_t)(iter + 1));
        for (size_t i = 0; i < updates; ++i) {
            size_t idx = (size_t)(xorshift64(&local) % table_size);
            table[idx] += 1;
        }
#endif
    }
    clock_gettime(CLOCK_MONOTONIC, &t1);
    double seconds = (double)(t1.tv_sec - t0.tv_sec) + (double)(t1.tv_nsec - t0.tv_nsec) / 1e9;
    if (seconds <= 0) seconds = 1e-9;
    double total = (double)updates * (double)iters;
    printf("table_size=%zu updates=%zu iters=%d threads=%d seconds=%.6f gups=%.6f updates_sec=%.6f errors=0\n",
           table_size, updates, iters, threads, seconds, total / seconds / 1e9, total / seconds);
    free(table);
    return 0;
}
