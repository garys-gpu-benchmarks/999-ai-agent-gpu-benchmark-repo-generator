/*
 * McCalpin-style STREAM memory bandwidth benchmark (C, not C++).
 * Compile:
 *   gcc -O3 -fopenmp -DSTREAM_ARRAY_SIZE=<N> -DNTIMES=<K> src/stream.c -o build/stream
 * Kernels: Copy, Scale, Add, Triad. OpenMP parallel for. FP64 (double).
 */

#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <float.h>
#include <limits.h>
#include <string.h>
#include <time.h>
#include <sys/types.h>

#ifdef _OPENMP
#include <omp.h>
#endif

#ifndef STREAM_ARRAY_SIZE
#define STREAM_ARRAY_SIZE 10000000
#endif

#ifndef NTIMES
#define NTIMES 10
#endif
#if NTIMES < 2
#undef NTIMES
#define NTIMES 2
#endif

#ifndef OFFSET
#define OFFSET 0
#endif

#ifndef STREAM_TYPE
#define STREAM_TYPE double
#endif

#define HLINE "-------------------------------------------------------------\n"

#ifndef MIN
#define MIN(x, y) ((x) < (y) ? (x) : (y))
#endif
#ifndef MAX
#define MAX(x, y) ((x) > (y) ? (x) : (y))
#endif

static STREAM_TYPE a[STREAM_ARRAY_SIZE + OFFSET];
static STREAM_TYPE b[STREAM_ARRAY_SIZE + OFFSET];
static STREAM_TYPE c[STREAM_ARRAY_SIZE + OFFSET];

static double avgtime[4] = {0.0, 0.0, 0.0, 0.0};
static double maxtime[4] = {0.0, 0.0, 0.0, 0.0};
static double mintime[4] = {FLT_MAX, FLT_MAX, FLT_MAX, FLT_MAX};

static const char *label[4] = {"Copy:      ", "Scale:     ", "Add:       ", "Triad:     "};

/* Bytes moved per kernel: Copy/Scale = 2 arrays, Add/Triad = 3 arrays. */
static double bytes[4] = {
    2.0 * sizeof(STREAM_TYPE) * STREAM_ARRAY_SIZE,
    2.0 * sizeof(STREAM_TYPE) * STREAM_ARRAY_SIZE,
    3.0 * sizeof(STREAM_TYPE) * STREAM_ARRAY_SIZE,
    3.0 * sizeof(STREAM_TYPE) * STREAM_ARRAY_SIZE
};

static double mysecond(void)
{
#ifdef _OPENMP
    return omp_get_wtime();
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec * 1.0e-9;
#endif
}

static void check_stream_results(void)
{
    STREAM_TYPE aj, bj, cj, scalar;
    STREAM_TYPE aSumErr, bSumErr, cSumErr;
    STREAM_TYPE aAvgErr, bAvgErr, cAvgErr;
    double epsilon;
    ssize_t j;
    int k, ierr;

    scalar = (STREAM_TYPE)3.0;
    aj = (STREAM_TYPE)1.0;
    bj = (STREAM_TYPE)2.0;
    cj = (STREAM_TYPE)0.0;
    /* a[] is doubled during the timing-check warmup, matching official STREAM. */
    aj = (STREAM_TYPE)2.0 * aj;
    for (k = 0; k < NTIMES; k++) {
        cj = aj;
        bj = scalar * cj;
        cj = aj + bj;
        aj = bj + scalar * cj;
    }

    /* Official McCalpin STREAM 5.10 check: per-element abs error, then
     * relative error vs the expected scalar. Summing the raw arrays first
     * loses precision once NTIMES grows values near 1e12, and comparing
     * that absolute residual to 1e-13 falsely fails baseline/extended.
     */
    aSumErr = (STREAM_TYPE)0.0;
    bSumErr = (STREAM_TYPE)0.0;
    cSumErr = (STREAM_TYPE)0.0;
    for (j = 0; j < STREAM_ARRAY_SIZE; j++) {
        aSumErr += (STREAM_TYPE)fabs((double)(a[j] - aj));
        bSumErr += (STREAM_TYPE)fabs((double)(b[j] - bj));
        cSumErr += (STREAM_TYPE)fabs((double)(c[j] - cj));
    }
    aAvgErr = aSumErr / (STREAM_TYPE)STREAM_ARRAY_SIZE;
    bAvgErr = bSumErr / (STREAM_TYPE)STREAM_ARRAY_SIZE;
    cAvgErr = cSumErr / (STREAM_TYPE)STREAM_ARRAY_SIZE;

    if (sizeof(STREAM_TYPE) == 4) {
        epsilon = 1.0e-6;
    } else if (sizeof(STREAM_TYPE) == 8) {
        epsilon = 1.0e-13;
    } else {
        printf("We are not sure what epsilon to use for STREAM_TYPE size %zu\n", sizeof(STREAM_TYPE));
        epsilon = 1.0e-6;
    }

    ierr = 0;
    if (aj != (STREAM_TYPE)0.0 && fabs((double)(aAvgErr / aj)) > epsilon) {
        ierr++;
    }
    if (bj != (STREAM_TYPE)0.0 && fabs((double)(bAvgErr / bj)) > epsilon) {
        ierr++;
    }
    if (cj != (STREAM_TYPE)0.0 && fabs((double)(cAvgErr / cj)) > epsilon) {
        ierr++;
    }

    if (ierr == 0) {
        printf("Solution Validates: avg error less than %e on all three arrays\n", epsilon);
    } else {
        printf("Failed Validation on %d arrays\n", ierr);
        printf("       Expected a,b,c: %f %f %f\n", (double)aj, (double)bj, (double)cj);
        printf("       Observed Avg Err a,b,c: %e %e %e\n", (double)aAvgErr, (double)bAvgErr, (double)cAvgErr);
        printf("       Avg Rel Err a,b,c: %e %e %e\n",
               (aj != (STREAM_TYPE)0.0) ? fabs((double)(aAvgErr / aj)) : (double)aAvgErr,
               (bj != (STREAM_TYPE)0.0) ? fabs((double)(bAvgErr / bj)) : (double)bAvgErr,
               (cj != (STREAM_TYPE)0.0) ? fabs((double)(cAvgErr / cj)) : (double)cAvgErr);
    }
}

int main(void)
{
    int quantum, checktick(void);
    int BytesPerWord;
    int k;
    ssize_t j;
    STREAM_TYPE scalar;
    double t, times[4][NTIMES];
    int nthreads;

    BytesPerWord = (int)sizeof(STREAM_TYPE);
    printf(HLINE);
    printf("STREAM version $Revision: 5.10 $\n");
    printf(HLINE);
    printf("This system uses %d bytes per array element.\n", BytesPerWord);
    printf(HLINE);
    printf("Array size = %llu (elements), Offset = %d (elements)\n",
           (unsigned long long)STREAM_ARRAY_SIZE, OFFSET);
    printf("Memory per array = %.1f MiB (= %.1f GiB).\n",
           BytesPerWord * ((double)STREAM_ARRAY_SIZE / 1024.0 / 1024.0),
           BytesPerWord * ((double)STREAM_ARRAY_SIZE / 1024.0 / 1024.0 / 1024.0));
    printf("Total memory required = %.1f MiB (= %.1f GiB).\n",
           (3.0 * BytesPerWord) * ((double)STREAM_ARRAY_SIZE / 1024.0 / 1024.0),
           (3.0 * BytesPerWord) * ((double)STREAM_ARRAY_SIZE / 1024.0 / 1024.0 / 1024.0));
    printf("Each kernel will be executed %d times.\n", NTIMES);
    printf(" The *best* time for each kernel (excluding the first iteration)\n");
    printf(" will be used to compute the reported bandwidth.\n");
    printf(HLINE);

#ifdef _OPENMP
    nthreads = 1;
#pragma omp parallel
    {
#pragma omp master
        {
            nthreads = omp_get_num_threads();
            printf("Number of Threads requested = %d\n", nthreads);
        }
    }
    printf("Number of Threads counted = %d\n", nthreads);
#else
    (void)nthreads;
    printf("OpenMP is disabled; running single-threaded.\n");
#endif
    printf(HLINE);

#pragma omp parallel for
    for (j = 0; j < STREAM_ARRAY_SIZE; j++) {
        a[j] = (STREAM_TYPE)1.0;
        b[j] = (STREAM_TYPE)2.0;
        c[j] = (STREAM_TYPE)0.0;
    }

    t = mysecond();
#pragma omp parallel for
    for (j = 0; j < STREAM_ARRAY_SIZE; j++) {
        a[j] = (STREAM_TYPE)2.0 * a[j];
    }
    t = 1.0e6 * (mysecond() - t);

    quantum = checktick();
    if (quantum >= 1) {
        printf("Your clock granularity/precision appears to be %d microseconds.\n", quantum);
    } else {
        printf("Your clock granularity appears to be less than one microsecond.\n");
        quantum = 1;
    }
    printf("Each test below will take on the order of %d microseconds.\n", (int)t);
    printf("   (= %d clock ticks)\n", (int)(t / quantum));
    printf("Increase the size of the arrays if this shows that\n");
    printf("you are not getting at least 20 clock ticks per test.\n");
    printf(HLINE);

    scalar = (STREAM_TYPE)3.0;
    for (k = 0; k < NTIMES; k++) {
        times[0][k] = mysecond();
#pragma omp parallel for
        for (j = 0; j < STREAM_ARRAY_SIZE; j++) {
            c[j] = a[j];
        }
        times[0][k] = mysecond() - times[0][k];

        times[1][k] = mysecond();
#pragma omp parallel for
        for (j = 0; j < STREAM_ARRAY_SIZE; j++) {
            b[j] = scalar * c[j];
        }
        times[1][k] = mysecond() - times[1][k];

        times[2][k] = mysecond();
#pragma omp parallel for
        for (j = 0; j < STREAM_ARRAY_SIZE; j++) {
            c[j] = a[j] + b[j];
        }
        times[2][k] = mysecond() - times[2][k];

        times[3][k] = mysecond();
#pragma omp parallel for
        for (j = 0; j < STREAM_ARRAY_SIZE; j++) {
            a[j] = b[j] + scalar * c[j];
        }
        times[3][k] = mysecond() - times[3][k];
    }

    for (k = 1; k < NTIMES; k++) {
        for (j = 0; j < 4; j++) {
            avgtime[j] = avgtime[j] + times[j][k];
            mintime[j] = MIN(mintime[j], times[j][k]);
            maxtime[j] = MAX(maxtime[j], times[j][k]);
        }
    }

    printf("Function    Best Rate MB/s  Avg time     Min time     Max time\n");
    for (j = 0; j < 4; j++) {
        avgtime[j] = avgtime[j] / (double)(NTIMES - 1);
        printf("%s%12.1f  %11.6f  %11.6f  %11.6f\n",
               label[j],
               1.0e-6 * bytes[j] / mintime[j],
               avgtime[j],
               mintime[j],
               maxtime[j]);
    }
    printf(HLINE);
    check_stream_results();
    printf(HLINE);
    return 0;
}

#define TICK_SAMPLES 20

int checktick(void)
{
    int i, minDelta, Delta;
    double t1, t2, timesfound[TICK_SAMPLES];

    for (i = 0; i < TICK_SAMPLES; i++) {
        int spins = 0;
        t1 = mysecond();
        t2 = mysecond();
        while ((t2 - t1) < 1.0e-6 && spins < 10000000) {
            t2 = mysecond();
            spins++;
        }
        timesfound[i] = t1 = t2;
    }

    minDelta = 1000000;
    for (i = 1; i < TICK_SAMPLES; i++) {
        Delta = (int)(1.0e6 * (timesfound[i] - timesfound[i - 1]));
        minDelta = MIN(minDelta, MAX(Delta, 0));
    }
    return minDelta;
}
