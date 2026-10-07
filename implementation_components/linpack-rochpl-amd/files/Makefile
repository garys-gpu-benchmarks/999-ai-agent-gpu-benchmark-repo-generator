# File: Makefile
# Description: Build bin/rochpl with hipcc, rocSOLVER, and rocBLAS.
# HIPCC_COMPILE_FLAGS_APPEND comes from scripts/lib/hipcc_host_gcc.sh (GCC 15/14/13).
ROCM ?= /opt/rocm
CXX = $(ROCM)/bin/hipcc
CXXFLAGS = -O2 -I$(ROCM)/include $(HIPCC_COMPILE_FLAGS_APPEND)
LDFLAGS = -L$(ROCM)/lib -L$(ROCM)/lib64 -lrocsolver -lrocblas
all: bin/rochpl
bin/rochpl: src/rochpl.cpp
	mkdir -p bin
	$(CXX) $(CXXFLAGS) src/rochpl.cpp -o bin/rochpl $(LDFLAGS)
clean:
	rm -f bin/rochpl
