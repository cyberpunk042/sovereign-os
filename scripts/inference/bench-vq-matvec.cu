// SDD-403 phase 4 gate: does a VQ decode hold the int4 nibble path's throughput?
//
// The whole VQ lane rests on one unmeasured assumption: that decoding a fixed-width
// codebook index is at least as cheap as extracting an int4 nibble. Plausible (a
// shared-memory lookup vs a shift-and-mask) but never measured. If it does not hold,
// the lane dies here for a few hours instead of a few days.
//
// Baseline is Colibri's quant_matmul, measured at 254 GB/s on this card
// (bench-expert-matvec.cu), at GLM expert shape I=6144 O=2048 B=1.
//
// Bytes read per output row:
//   int4                     6144 * 0.5 B = 3072 B
//   VQ d=4 K=256   x1        1536 idx * 1 B = 1536 B   <- HALF: 2 b/w
//   VQ d=4 K=256x2 x2        3072 B                    <- same as int4: 4 b/w
// So the 2 b/w point may be faster as well as smaller — worth knowing separately from
// the residency win.
//
// build: nvcc -O3 -arch=sm_120 bench-vq-matvec.cu -o bench-vq-matvec
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <vector>
#include <algorithm>
#include <cuda_runtime.h>

#define CK(x) do{ cudaError_t e_=(x); if(e_){printf("CUDA %s @%d\n",cudaGetErrorString(e_),__LINE__); exit(1);} }while(0)

// ---------------- BASELINE: Colibri int4 nibble decode (fmt=2) --------------------
__device__ __forceinline__ float nib(const uint8_t *q, int i){
    uint8_t v = q[i >> 1]; int n = (i & 1) ? (v >> 4) : (v & 15);
    return (float)(n & 8 ? n - 16 : n);
}
__global__ static void mv_int4(float *y, const float *x, const uint8_t *w,
                               const float *sc, int I, int O, size_t rb){
    int o = blockIdx.x; float s = 0.f; const uint8_t *row = w + (size_t)o * rb;
    for (int i = threadIdx.x; i < I; i += blockDim.x) s += x[i] * nib(row, i);
    __shared__ float p[256]; p[threadIdx.x] = s; __syncthreads();
    for (int n = blockDim.x >> 1; n; n >>= 1){
        if (threadIdx.x < n) p[threadIdx.x] += p[threadIdx.x + n];
        __syncthreads();
    }
    if (!threadIdx.x) y[o] = p[0] * sc[o];
}

// ---------------- VQ: one uint8 index -> d floats from a shared codebook ----------
// Codebook is K*d floats, shared by the whole tensor: 256*4*4 B = 4 KB -> shared mem.
template<int D>
__global__ static void mv_vq1(float *y, const float *x, const uint8_t *idx,
                              const float *cb, const float *sc, int I, int O, size_t rb){
    extern __shared__ float s_cb[];
    const int K = 256;
    for (int t = threadIdx.x; t < K * D; t += blockDim.x) s_cb[t] = cb[t];
    __syncthreads();

    int o = blockIdx.x; float s = 0.f;
    const uint8_t *row = idx + (size_t)o * rb;           // rb = I/D index bytes
    const int nvec = I / D;
    for (int v = threadIdx.x; v < nvec; v += blockDim.x){
        const float *c = s_cb + (int)row[v] * D;
        const float *xv = x + v * D;
        #pragma unroll
        for (int k = 0; k < D; ++k) s += xv[k] * c[k];
    }
    __shared__ float p[256]; p[threadIdx.x] = s; __syncthreads();
    for (int n = blockDim.x >> 1; n; n >>= 1){
        if (threadIdx.x < n) p[threadIdx.x] += p[threadIdx.x + n];
        __syncthreads();
    }
    if (!threadIdx.x) y[o] = p[0] * sc[o];
}

// two-stage residual: two index streams, two codebooks, summed
template<int D>
__global__ static void mv_vq2(float *y, const float *x, const uint8_t *i0,
                              const uint8_t *i1, const float *cb0, const float *cb1,
                              const float *sc, int I, int O, size_t rb){
    extern __shared__ float s_cb[];
    const int K = 256;
    for (int t = threadIdx.x; t < K * D; t += blockDim.x){
        s_cb[t] = cb0[t]; s_cb[K * D + t] = cb1[t];
    }
    __syncthreads();

    int o = blockIdx.x; float s = 0.f;
    const uint8_t *r0 = i0 + (size_t)o * rb, *r1 = i1 + (size_t)o * rb;
    const int nvec = I / D;
    for (int v = threadIdx.x; v < nvec; v += blockDim.x){
        const float *c0 = s_cb + (int)r0[v] * D;
        const float *c1 = s_cb + K * D + (int)r1[v] * D;
        const float *xv = x + v * D;
        #pragma unroll
        for (int k = 0; k < D; ++k) s += xv[k] * (c0[k] + c1[k]);
    }
    __shared__ float p[256]; p[threadIdx.x] = s; __syncthreads();
    for (int n = blockDim.x >> 1; n; n >>= 1){
        if (threadIdx.x < n) p[threadIdx.x] += p[threadIdx.x + n];
        __syncthreads();
    }
    if (!threadIdx.x) y[o] = p[0] * sc[o];
}

static double med(std::vector<double> v){ std::sort(v.begin(), v.end()); return v[v.size()/2]; }

int main(int argc, char **argv){
    const int I = argc > 1 ? atoi(argv[1]) : 6144;
    const int O = argc > 2 ? atoi(argv[2]) : 2048;
    const int reps = argc > 3 ? atoi(argv[3]) : 200;
    const int D = 4, K = 256;

    cudaDeviceProp p; CK(cudaGetDeviceProperties(&p, 0));
    printf("device %s (sm_%d%d)  I=%d O=%d B=1\n", p.name, p.major, p.minor, I, O);

    size_t rb4 = (size_t)I / 2;          // int4 bytes/row
    size_t rbv = (size_t)I / D;          // VQ index bytes/row
    float *x, *y, *sc, *cb0, *cb1; uint8_t *w4, *iv0, *iv1;
    CK(cudaMalloc(&x, I * 4));  CK(cudaMalloc(&y, O * 4));  CK(cudaMalloc(&sc, O * 4));
    CK(cudaMalloc(&w4, O * rb4)); CK(cudaMalloc(&iv0, O * rbv)); CK(cudaMalloc(&iv1, O * rbv));
    CK(cudaMalloc(&cb0, K * D * 4)); CK(cudaMalloc(&cb1, K * D * 4));
    std::vector<uint8_t> h(O * rb4); for (auto &c : h) c = rand() & 0xFF;
    CK(cudaMemcpy(w4, h.data(), O * rb4, cudaMemcpyHostToDevice));
    CK(cudaMemcpy(iv0, h.data(), O * rbv, cudaMemcpyHostToDevice));
    CK(cudaMemcpy(iv1, h.data(), O * rbv, cudaMemcpyHostToDevice));
    std::vector<float> hf(std::max(I, K * D), 0.01f);
    CK(cudaMemcpy(x, hf.data(), I * 4, cudaMemcpyHostToDevice));
    CK(cudaMemcpy(sc, hf.data(), O * 4, cudaMemcpyHostToDevice));
    CK(cudaMemcpy(cb0, hf.data(), K * D * 4, cudaMemcpyHostToDevice));
    CK(cudaMemcpy(cb1, hf.data(), K * D * 4, cudaMemcpyHostToDevice));

    cudaEvent_t a, b; CK(cudaEventCreate(&a)); CK(cudaEventCreate(&b));
    auto run = [&](int which){
        if (which == 0) mv_int4<<<O,256>>>(y, x, w4, sc, I, O, rb4);
        else if (which == 1) mv_vq1<D><<<O,256,K*D*4>>>(y, x, iv0, cb0, sc, I, O, rbv);
        else mv_vq2<D><<<O,256,2*K*D*4>>>(y, x, iv0, iv1, cb0, cb1, sc, I, O, rbv);
    };
    const char *names[3] = {"int4 nibble (Colibri baseline)", "VQ d=4 K=256 x1  (2.0 b/w)",
                            "VQ d=4 K=256 x2  (4.0 b/w)"};
    double bytes[3] = {(double)O*rb4, (double)O*rbv, (double)O*rbv*2};

    printf("\n  %-32s %9s %11s %10s %9s\n", "kernel", "ms", "GB/s", "% roofline", "vs int4");
    double t0 = 0;
    for (int k = 0; k < 3; ++k){
        run(k); CK(cudaDeviceSynchronize());
        std::vector<double> t;
        for (int r = 0; r < reps; ++r){
            CK(cudaEventRecord(a)); run(k); CK(cudaEventRecord(b));
            CK(cudaEventSynchronize(b));
            float ms = 0; CK(cudaEventElapsedTime(&ms, a, b)); t.push_back(ms);
        }
        double ms = med(t), gbs = bytes[k] / (ms * 1e-3) / 1e9;
        if (!k) t0 = ms;
        printf("  %-32s %9.4f %11.1f %9.1f%% %8.2fx\n",
               names[k], ms, gbs, 100.0 * gbs / 1790.0, t0 / ms);
    }
    printf("\n  The lane needs the VQ rows to hold the int4 row's GB/s. The 2.0 b/w row\n");
    printf("  reads HALF the bytes, so a speedup there is residency AND throughput.\n");
    return 0;
}
