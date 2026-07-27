// Head-to-head: Colibri's quant_matmul vs an optimised int4 matvec, at GLM expert shape.
//
// Colibri decode profile: expert-matmul = 51.7% of decode, 282 us/expert-load,
// ~67 GB/s effective against a 1790 GB/s card (3.7% of roofline).
//
// Baseline weaknesses (backend_cuda.cu:128):
//   - one block per OUTPUT element -> no reuse of x
//   - 8 x __syncthreads() shared-mem reduction to produce a single float
//   - scalar per-element nibble extraction (weight_at), no vectorised loads
//
// Optimised: x staged once in shared memory and reused across ROWS_PER_BLOCK outputs,
// uint4 (16 B = 32 weights) vectorised weight loads, warp-shuffle reduction, one warp
// per output row.
//
// build: nvcc -O3 -arch=sm_120 expert_matvec.cu -o expert_matvec
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <vector>
#include <cmath>
#include <algorithm>
#include <cuda_runtime.h>

#define CK(x) do{ cudaError_t e=(x); if(e){printf("CUDA %s @%d\n",cudaGetErrorString(e),__LINE__); exit(1);} }while(0)

__host__ __device__ static size_t row_bytes_i4(int I){ return (size_t)(I+1)/2; }

// ---------------- BASELINE: verbatim structure of Colibri quant_matmul (fmt=2) ------------
__device__ static float weight_at_i4(const void *weights, size_t row, int i){
    const uint8_t *q = static_cast<const uint8_t*>(weights) + row;
    uint8_t v = q[i>>1];
    int n = (i&1) ? (v>>4) : (v&15);
    return static_cast<float>(n&8 ? n-16 : n);
}

__global__ static void quant_matmul_baseline(float *y, const float *x, const void *weights,
                                             const float *scales, int S, int I, int O, size_t rb){
    int o = blockIdx.x;
    int s = blockIdx.y;
    float sum = 0.0f;
    size_t row = (size_t)o * rb;
    const float *xs = x + (size_t)s * I;
    for (int i = threadIdx.x; i < I; i += blockDim.x)
        sum += xs[i] * weight_at_i4(weights, row, i);
    __shared__ float partial[256];
    partial[threadIdx.x] = sum;
    __syncthreads();
    for (int n = blockDim.x >> 1; n; n >>= 1){
        if (threadIdx.x < n) partial[threadIdx.x] += partial[threadIdx.x + n];
        __syncthreads();
    }
    if (!threadIdx.x) y[(size_t)s*O + o] = partial[0] * scales[o];
}

// ---------------- OPTIMISED ---------------------------------------------------------------
// One warp per output row; ROWS_PER_BLOCK warps per block; x staged in shared memory once.
template<int ROWS_PER_BLOCK>
__global__ static void quant_matvec_fast(float * __restrict__ y, const float * __restrict__ x,
                                         const uint8_t * __restrict__ weights,
                                         const float * __restrict__ scales,
                                         int I, int O, size_t rb){
    extern __shared__ float xs[];                       // I floats
    const int tid  = threadIdx.x;
    const int lane = tid & 31;
    const int warp = tid >> 5;

    for (int i = tid; i < I; i += blockDim.x) xs[i] = x[i];
    __syncthreads();

    const int o = blockIdx.x * ROWS_PER_BLOCK + warp;
    if (o >= O) return;

    const uint4 *wrow = reinterpret_cast<const uint4*>(weights + (size_t)o * rb);
    const int nvec = (int)(rb / 16);                    // uint4 units in this row
    float sum = 0.0f;

    for (int u = lane; u < nvec; u += 32){
        uint4 w = wrow[u];                              // 16 B = 32 int4 weights
        const uint32_t ws[4] = { w.x, w.y, w.z, w.w };
        const int base = u * 32;
        #pragma unroll
        for (int c = 0; c < 4; ++c){
            uint32_t W = ws[c];
            const int b = base + c*8;
            #pragma unroll
            for (int k = 0; k < 8; ++k){
                int n = (int)((W >> (4*k)) & 0xF);
                sum += xs[b+k] * (float)(n & 8 ? n-16 : n);
            }
        }
    }
    #pragma unroll
    for (int off = 16; off; off >>= 1) sum += __shfl_down_sync(0xffffffff, sum, off);
    if (!lane) y[o] = sum * scales[o];
}

// ---------------- harness ------------------------------------------------------------------
static double bench(void(*launch)(void*), void *ctx, int reps){
    cudaEvent_t a,b; CK(cudaEventCreate(&a)); CK(cudaEventCreate(&b));
    launch(ctx); CK(cudaDeviceSynchronize());            // warm
    std::vector<double> t;
    for (int r=0;r<reps;r++){
        CK(cudaEventRecord(a)); launch(ctx); CK(cudaEventRecord(b));
        CK(cudaEventSynchronize(b));
        float ms=0; CK(cudaEventElapsedTime(&ms,a,b)); t.push_back(ms);
    }
    std::sort(t.begin(), t.end());
    return t[t.size()/2];
}

struct Ctx { float *y,*x,*sc; uint8_t *w; int I,O; size_t rb; };
// Variant 2: same warp-per-row layout but x is read straight from global (it is only
// I*4 = 24 KB and is shared by every block, so it sits in L2). Dropping the shared-mem
// staging removes the occupancy cost that made variant 1 slower than the baseline.
template<int ROWS_PER_BLOCK>
__global__ static void quant_matvec_v2(float * __restrict__ y, const float * __restrict__ x,
                                       const uint8_t * __restrict__ weights,
                                       const float * __restrict__ scales,
                                       int I, int O, size_t rb){
    const int lane = threadIdx.x & 31;
    const int warp = threadIdx.x >> 5;
    const int o = blockIdx.x * ROWS_PER_BLOCK + warp;
    if (o >= O) return;
    const uint4 *wrow = reinterpret_cast<const uint4*>(weights + (size_t)o * rb);
    const int nvec = (int)(rb / 16);
    float sum = 0.0f;
    for (int u = lane; u < nvec; u += 32){
        uint4 w = wrow[u];
        const uint32_t ws[4] = { w.x, w.y, w.z, w.w };
        const int base = u * 32;
        #pragma unroll
        for (int c = 0; c < 4; ++c){
            uint32_t W = ws[c];
            const int b = base + c*8;
            #pragma unroll
            for (int k = 0; k < 8; ++k){
                int n = (int)((W >> (4*k)) & 0xF);
                sum += x[b+k] * (float)(n & 8 ? n-16 : n);
            }
        }
    }
    #pragma unroll
    for (int off = 16; off; off >>= 1) sum += __shfl_down_sync(0xffffffff, sum, off);
    if (!lane) y[o] = sum * scales[o];
}

static Ctx g;
static void run_base(void*){ dim3 gr((unsigned)g.O,1); quant_matmul_baseline<<<gr,256>>>(g.y,g.x,g.w,g.sc,1,g.I,g.O,g.rb); }
static void run_fast(void*){ const int R=8; dim3 gr((unsigned)((g.O+R-1)/R));
                             quant_matvec_fast<R><<<gr,R*32,g.I*sizeof(float)>>>(g.y,g.x,g.w,g.sc,g.I,g.O,g.rb); }
static void run_v2(void*){ const int R=8; dim3 gr((unsigned)((g.O+R-1)/R));
                           quant_matvec_v2<R><<<gr,R*32>>>(g.y,g.x,g.w,g.sc,g.I,g.O,g.rb); }

int main(int argc,char**argv){
    int I = argc>1?atoi(argv[1]):6144;                  // GLM gate/up: K=6144
    int O = argc>2?atoi(argv[2]):2048;                  // GLM gate/up: M=2048
    int reps = argc>3?atoi(argv[3]):200;
    size_t rb = row_bytes_i4(I);

    cudaDeviceProp p; CK(cudaGetDeviceProperties(&p,0));
    printf("device %s (sm_%d%d)  int4 matvec  I=%d O=%d  B=1  weights=%.2f MB\n",
           p.name,p.major,p.minor,I,O,(double)(O*rb)/1e6);

    std::vector<uint8_t> hw(O*rb); std::vector<float> hx(I), hsc(O);
    for(size_t i=0;i<hw.size();i++) hw[i]=(uint8_t)(rand()&0xFF);
    for(int i=0;i<I;i++) hx[i]=(float)((rand()%200-100)/100.0);
    for(int i=0;i<O;i++) hsc[i]=0.00975f;

    CK(cudaMalloc(&g.w,hw.size())); CK(cudaMalloc(&g.x,I*4)); CK(cudaMalloc(&g.sc,O*4)); CK(cudaMalloc(&g.y,O*4));
    CK(cudaMemcpy(g.w,hw.data(),hw.size(),cudaMemcpyHostToDevice));
    CK(cudaMemcpy(g.x,hx.data(),I*4,cudaMemcpyHostToDevice));
    CK(cudaMemcpy(g.sc,hsc.data(),O*4,cudaMemcpyHostToDevice));
    g.I=I; g.O=O; g.rb=rb;

    std::vector<float> yb(O), yf(O);
    run_base(nullptr); CK(cudaDeviceSynchronize()); CK(cudaMemcpy(yb.data(),g.y,O*4,cudaMemcpyDeviceToHost));
    CK(cudaMemset(g.y,0,O*4));
    run_fast(nullptr); CK(cudaDeviceSynchronize()); CK(cudaMemcpy(yf.data(),g.y,O*4,cudaMemcpyDeviceToHost));

    double maxrel=0; for(int i=0;i<O;i++){ double d=fabs(yb[i]-yf[i]), m=fabs(yb[i])+1e-6; maxrel=std::max(maxrel,d/m); }

    CK(cudaMemset(g.y,0,O*4));
    std::vector<float> yv(O);
    run_v2(nullptr); CK(cudaDeviceSynchronize()); CK(cudaMemcpy(yv.data(),g.y,O*4,cudaMemcpyDeviceToHost));
    double maxrel2=0; for(int i=0;i<O;i++){ double d=fabs(yb[i]-yv[i]), m=fabs(yb[i])+1e-6; maxrel2=std::max(maxrel2,d/m); }

    double tb = bench(run_base,nullptr,reps);
    double tf = bench(run_fast,nullptr,reps);
    double tv = bench(run_v2,nullptr,reps);
    double bytes = (double)O*rb;
    printf("\n  %-30s %10s %12s %12s\n","kernel","ms","GB/s","%% roofline");
    printf("  %-30s %10.4f %12.1f %11.1f%%\n","Colibri quant_matmul",tb,bytes/(tb*1e-3)/1e9,100*bytes/(tb*1e-3)/1.79e12);
    printf("  %-30s %10.4f %12.1f %11.1f%%\n","v1 warp+shared-x",   tf,bytes/(tf*1e-3)/1e9,100*bytes/(tf*1e-3)/1.79e12);
    printf("  %-30s %10.4f %12.1f %11.1f%%\n","v2 warp+uint4, x from L2",tv,bytes/(tv*1e-3)/1e9,100*bytes/(tv*1e-3)/1.79e12);
    printf("\n  v1 speedup %.2fx (err %.1e)   v2 speedup %.2fx (err %.1e)\n",
           tb/tf, maxrel, tb/tv, maxrel2);

    // Full GLM expert = gate(O=2048,I=6144) + up(same) + down(O=6144,I=2048)
    printf("\n  projected full GLM expert (gate+up+down):\n");
    printf("    baseline  %7.1f us/expert    (Colibri measured in-engine: 282 us)\n", (tb*2 + tb)*1000);
    printf("    optimised %7.1f us/expert -> expert-matmul %.2fs of the 21.2s decode\n",
           (tf*2 + tf)*1000, 10.963/(tb/tf));
    return 0;
}
