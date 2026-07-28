// SDD-403 phase 4: CUDA port of Colibri's matmul_e8 (fmt=6, E8/IQ3 lattice).
//
// colibri.c:294 refuses CUDA for fmt=5/6 -- "no CUDA kernel yet -- tensor stays CPU-side".
// That strands both sub-4-bit formats on the CPU, which is the wrong side of the GLM-5.2
// bottleneck: only 7,094 of 19,456 experts fit VRAM at int4, and a CPU-resident expert
// costs ~10x a VRAM-resident one. fmt=6 is 3.06 b/w -> 8,449 experts fit.
//
// This validates a CUDA decode BIT-EXACTLY against the CPU reference (ported verbatim
// from quant.h) before anything touches backend_cuda.cu, then measures throughput
// against the int4 nibble path.
//
// NOTE: the fmt=6 activation rotation (Q^T x, e8_fwht) is NOT done here. Per quant.h it
// is applied once per (layer, projection group) by the engine -- ~1.4 ms/token -- not
// per expert (~11 ms). matmul_e8 likewise assumes x is already rotated.
//
// build: nvcc -O3 -arch=sm_120 bench-e8-matvec.cu -o bench-e8-matvec
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <vector>
#include <algorithm>
#include <cuda_runtime.h>

#define CK(x) do{ cudaError_t e_=(x); if(e_){printf("CUDA %s @%d\n",cudaGetErrorString(e_),__LINE__); exit(1);} }while(0)

#define E8_QK     256
#define E8_SUB     32
#define E8_BBYTES  98

static const uint8_t h_e8_grid[256][4] = {
  {4,4,4,4},
  {20,4,4,4},
  {36,4,4,4},
  {12,12,4,4},
  {28,12,4,4},
  {62,12,4,4},
  {4,20,4,4},
  {20,20,4,4},
  {12,28,4,4},
  {20,36,4,4},
  {28,62,4,4},
  {44,62,4,4},
  {12,4,12,4},
  {28,4,12,4},
  {4,12,12,4},
  {20,12,12,4},
  {12,20,12,4},
  {44,20,12,4},
  {4,28,12,4},
  {20,28,12,4},
  {12,36,12,4},
  {36,44,12,4},
  {4,62,12,4},
  {4,4,20,4},
  {20,4,20,4},
  {36,4,20,4},
  {12,12,20,4},
  {4,20,20,4},
  {20,20,20,4},
  {12,28,20,4},
  {28,28,20,4},
  {62,28,20,4},
  {12,44,20,4},
  {62,44,20,4},
  {44,62,20,4},
  {12,4,28,4},
  {62,4,28,4},
  {4,12,28,4},
  {20,12,28,4},
  {44,20,28,4},
  {4,62,28,4},
  {28,12,36,4},
  {62,28,36,4},
  {36,36,36,4},
  {62,44,36,4},
  {28,62,36,4},
  {44,62,36,4},
  {12,4,44,4},
  {62,4,44,4},
  {20,28,44,4},
  {20,44,44,4},
  {44,28,52,4},
  {36,52,52,4},
  {4,12,62,4},
  {36,12,62,4},
  {52,12,62,4},
  {28,36,62,4},
  {12,52,62,4},
  {12,4,4,12},
  {28,4,4,12},
  {4,12,4,12},
  {20,12,4,12},
  {12,20,4,12},
  {28,20,4,12},
  {4,28,4,12},
  {20,28,4,12},
  {36,28,4,12},
  {62,36,4,12},
  {4,44,4,12},
  {4,4,12,12},
  {20,4,12,12},
  {12,12,12,12},
  {4,20,12,12},
  {20,20,12,12},
  {12,4,20,12},
  {28,4,20,12},
  {4,12,20,12},
  {20,12,20,12},
  {12,20,20,12},
  {4,28,20,12},
  {20,62,20,12},
  {4,4,28,12},
  {20,4,28,12},
  {4,20,28,12},
  {12,28,28,12},
  {52,36,28,12},
  {52,52,28,12},
  {12,4,36,12},
  {44,4,36,12},
  {4,44,36,12},
  {4,20,44,12},
  {36,20,44,12},
  {52,36,44,12},
  {12,62,44,12},
  {44,4,52,12},
  {20,20,62,12},
  {4,36,62,12},
  {4,4,4,20},
  {20,4,4,20},
  {12,12,4,20},
  {28,12,4,20},
  {4,20,4,20},
  {20,20,4,20},
  {52,20,4,20},
  {12,28,4,20},
  {20,36,4,20},
  {12,4,12,20},
  {28,4,12,20},
  {44,4,12,20},
  {4,12,12,20},
  {20,12,12,20},
  {12,20,12,20},
  {4,28,12,20},
  {28,52,12,20},
  {62,52,12,20},
  {4,62,12,20},
  {4,4,20,20},
  {20,4,20,20},
  {12,12,20,20},
  {62,12,20,20},
  {4,20,20,20},
  {20,20,20,20},
  {62,28,20,20},
  {4,36,20,20},
  {44,44,20,20},
  {12,4,28,20},
  {4,12,28,20},
  {36,12,28,20},
  {4,62,28,20},
  {36,62,28,20},
  {44,28,36,20},
  {28,44,36,20},
  {28,4,44,20},
  {62,20,44,20},
  {12,36,44,20},
  {36,62,44,20},
  {12,4,62,20},
  {28,4,62,20},
  {52,12,62,20},
  {44,36,62,20},
  {12,4,4,28},
  {4,12,4,28},
  {20,12,4,28},
  {12,20,4,28},
  {28,20,4,28},
  {4,44,4,28},
  {44,52,4,28},
  {20,62,4,28},
  {4,4,12,28},
  {20,4,12,28},
  {4,20,12,28},
  {12,28,12,28},
  {36,36,12,28},
  {52,36,12,28},
  {12,4,20,28},
  {28,4,20,28},
  {4,12,20,28},
  {44,20,20,28},
  {20,44,20,28},
  {20,62,20,28},
  {12,12,28,28},
  {28,28,28,28},
  {4,28,36,28},
  {62,36,36,28},
  {20,62,36,28},
  {4,4,44,28},
  {52,4,44,28},
  {20,20,44,28},
  {44,44,44,28},
  {36,12,52,28},
  {52,28,52,28},
  {28,52,52,28},
  {28,28,62,28},
  {4,52,62,28},
  {36,4,4,36},
  {62,12,4,36},
  {44,28,4,36},
  {62,28,4,36},
  {28,44,4,36},
  {62,44,4,36},
  {36,62,12,36},
  {4,20,20,36},
  {62,28,20,36},
  {4,36,20,36},
  {4,52,20,36},
  {52,52,20,36},
  {62,4,28,36},
  {44,36,28,36},
  {36,4,36,36},
  {12,44,36,36},
  {36,52,36,36},
  {44,20,44,36},
  {28,36,44,36},
  {4,62,44,36},
  {44,4,62,36},
  {4,12,62,36},
  {20,12,62,36},
  {4,28,62,36},
  {20,12,4,44},
  {12,36,4,44},
  {4,62,4,44},
  {4,4,12,44},
  {52,4,12,44},
  {52,20,12,44},
  {44,44,12,44},
  {36,12,20,44},
  {20,28,20,44},
  {20,62,20,44},
  {20,4,28,44},
  {28,44,28,44},
  {4,12,36,44},
  {28,20,36,44},
  {62,20,36,44},
  {20,62,36,44},
  {20,4,44,44},
  {12,28,44,44},
  {4,44,52,44},
  {36,20,62,44},
  {20,36,62,44},
  {36,20,4,52},
  {36,36,4,52},
  {52,36,4,52},
  {36,52,4,52},
  {12,20,12,52},
  {12,52,12,52},
  {62,12,20,52},
  {36,52,20,52},
  {4,28,28,52},
  {52,28,28,52},
  {36,36,36,52},
  {44,4,44,52},
  {20,44,44,52},
  {28,28,52,52},
  {28,4,62,52},
  {12,20,62,52},
  {28,4,4,62},
  {44,4,4,62},
  {62,4,4,62},
  {4,12,4,62},
  {20,28,4,62},
  {20,44,4,62},
  {52,20,12,62},
  {4,36,12,62},
  {20,12,20,62},
  {44,36,20,62},
  {20,44,20,62},
  {4,4,28,62},
  {44,12,28,62},
  {28,28,28,62},
  {4,52,28,62},
  {12,20,36,62},
  {12,36,36,62},
  {4,4,44,62},
  {20,4,44,62},
  {36,20,44,62},
  {4,28,52,62}
};
__constant__ uint8_t d_e8_grid[256][4];

static inline int64_t e8_blocks(int I){ return ((int64_t)I + E8_QK - 1) / E8_QK; }
static inline int64_t e8_rowbytes(int I){ return e8_blocks(I) * E8_BBYTES; }

// ---------------- CPU reference (verbatim from quant.h) --------------------------
static float cpu_fp16(uint16_t h){
    uint32_t sign=(uint32_t)(h>>15)<<31, exp=(h>>10)&0x1F, man=h&0x3FF, bits;
    if(!exp)      bits = man ? (sign | ((127-15+1)<<23) | (man<<13)) : sign;
    else if(exp==0x1F) bits = sign | 0x7F800000u | (man<<13);
    else          bits = sign | ((exp+112)<<23) | (man<<13);
    float f; memcpy(&f,&bits,4); return f;
}
static void cpu_expand(const uint8_t *blk, int ib, float d, float *out){
    uint32_t word; memcpy(&word, blk + E8_QK/4 + ib*4, 4);
    float db = d * (0.5f + (float)((word>>28)&0xF)) * 0.5f;
    const uint8_t *idx = blk + ib*8;
    for(int l=0;l<4;l++){
        uint32_t seven=(word>>(7*l))&0x7F;
        const uint8_t *g0=h_e8_grid[idx[l*2+0]], *g1=h_e8_grid[idx[l*2+1]];
        int par=0;
        for(int j=0;j<8;j++){
            int neg = j<7 ? (int)((seven>>j)&1) : 0;
            if(j<7) par^=neg; else neg=par;
            float mag = (j<4 ? (float)g0[j] : (float)g1[j-4]) * 0.5f;
            out[l*8+j] = neg ? -mag*db : mag*db;
        }
    }
}
static void cpu_matmul_e8_f64(double *y, const float *x, const uint8_t *q, int I, int O){
    int64_t nb=e8_blocks(I), rb=e8_rowbytes(I);
    for(int o=0;o<O;o++){
        const uint8_t *wrow=q+(int64_t)o*rb; double acc=0;
        for(int64_t b=0;b<nb;b++){
            const uint8_t *blk=wrow+b*E8_BBYTES;
            uint16_t dh; memcpy(&dh, blk+96, 2);
            float d=cpu_fp16(dh);
            int base=(int)(b*E8_QK);
            for(int ib=0; ib<E8_QK/E8_SUB; ib++){
                int off=base+ib*E8_SUB;
                if(off>=I) break;
                float w[E8_SUB]; cpu_expand(blk, ib, d, w);
                int n = I-off < E8_SUB ? I-off : E8_SUB;
                for(int k=0;k<n;k++) acc += (double)x[off+k]*(double)w[k];
            }
        }
        y[o]=acc;
    }
}
static void cpu_matmul_e8(float *y, const float *x, const uint8_t *q, int I, int O){
    int64_t nb=e8_blocks(I), rb=e8_rowbytes(I);
    for(int o=0;o<O;o++){
        const uint8_t *wrow=q+(int64_t)o*rb; float acc=0;
        for(int64_t b=0;b<nb;b++){
            const uint8_t *blk=wrow+b*E8_BBYTES;
            uint16_t dh; memcpy(&dh, blk+96, 2);
            float d=cpu_fp16(dh);
            int base=(int)(b*E8_QK);
            for(int ib=0; ib<E8_QK/E8_SUB; ib++){
                int off=base+ib*E8_SUB;
                if(off>=I) break;
                float w[E8_SUB]; cpu_expand(blk, ib, d, w);
                int n = I-off < E8_SUB ? I-off : E8_SUB;
                for(int k=0;k<n;k++) acc += x[off+k]*w[k];
            }
        }
        y[o]=acc;
    }
}

// ---------------- CUDA kernel ----------------------------------------------------
__device__ __forceinline__ float dev_fp16(uint16_t h){
    uint32_t sign=(uint32_t)(h>>15)<<31, exp=(h>>10)&0x1F, man=h&0x3FF, bits;
    if(!exp)      bits = man ? (sign | ((127-15+1)<<23) | (man<<13)) : sign;
    else if(exp==0x1F) bits = sign | 0x7F800000u | (man<<13);
    else          bits = sign | ((exp+112)<<23) | (man<<13);
    float f; memcpy(&f,&bits,4); return f;
}

// One block per output row; each thread takes whole 32-weight sub-blocks and
// accumulates their partial dot product. Grid table lives in __constant__.
__global__ static void mv_e8(float *y, const float *x, const uint8_t *q, int I, int O,
                             int64_t nb, int64_t rb){
    // Grid in SHARED, not __constant__: constant memory is a broadcast path and
    // serialises when threads read different addresses, which is our pattern.
    __shared__ uint8_t s_grid[256][4];
    for(int t=threadIdx.x; t<256; t+=blockDim.x){
        s_grid[t][0]=d_e8_grid[t][0]; s_grid[t][1]=d_e8_grid[t][1];
        s_grid[t][2]=d_e8_grid[t][2]; s_grid[t][3]=d_e8_grid[t][3];
    }
    __syncthreads();
    const int o = blockIdx.x;
    const uint8_t *wrow = q + (int64_t)o * rb;
    const int nsub = (int)nb * (E8_QK / E8_SUB);
    float acc = 0.f;

    for(int sb = threadIdx.x; sb < nsub; sb += blockDim.x){
        int b  = sb / (E8_QK / E8_SUB);
        int ib = sb % (E8_QK / E8_SUB);
        int off = b * E8_QK + ib * E8_SUB;
        if(off >= I) continue;
        const uint8_t *blk = wrow + (int64_t)b * E8_BBYTES;
        // E8_BBYTES is 98 -- NOT 4-byte aligned -- so multi-byte loads must be
        // assembled from bytes or the device faults on a misaligned address.
        uint16_t dh = (uint16_t)blk[96] | ((uint16_t)blk[97] << 8);
        float d = dev_fp16(dh);
        const uint8_t *wp = blk + E8_QK/4 + ib*4;
        uint32_t word = (uint32_t)wp[0] | ((uint32_t)wp[1] << 8)
                      | ((uint32_t)wp[2] << 16) | ((uint32_t)wp[3] << 24);
        float db = d * (0.5f + (float)((word>>28)&0xF)) * 0.5f;
        const uint8_t *idx = blk + ib*8;
        int n = I - off < E8_SUB ? I - off : E8_SUB;
        const bool full = (n == E8_SUB);
        #pragma unroll
        for(int l=0;l<4;l++){
            uint32_t seven=(word>>(7*l))&0x7F;
            const uint8_t *g0=s_grid[idx[l*2+0]], *g1=s_grid[idx[l*2+1]];
            // The reference XORs the 7 sign bits across j to close the block with odd
            // parity -- a serial dependency. That value is just the parity of the 7
            // bits, so popcount gives it in one op and all 8 signs become a bitmask.
            uint32_t sgn = seven | ((uint32_t)(__popc(seven) & 1) << 7);
            const float m0 = db * 0.5f;
            #pragma unroll
            for(int j=0;j<8;j++){
                float mag = (j<4 ? (float)g0[j] : (float)g1[j-4]) * m0;
                int k = l*8+j;
                float v = ((sgn>>j)&1u) ? -mag : mag;
                if(full || k < n) acc += x[off+k] * v;
            }
        }
    }
    __shared__ float p[256];
    p[threadIdx.x]=acc; __syncthreads();
    for(int s=blockDim.x>>1; s; s>>=1){
        if(threadIdx.x<s) p[threadIdx.x]+=p[threadIdx.x+s];
        __syncthreads();
    }
    if(!threadIdx.x) y[o]=p[0];
}


// ---- multi-row variant: R output rows per block, x tiled in shared ---------------
// x is re-read once per output row in the naive mapping -> 50 MB of traffic against
// 4.8 MB of E8 weights (10.4x). Processing R rows per block amortises it R-fold.
// One warp per row; within a warp the E8 structure maps exactly: 8 sub-blocks x 4
// lanes = 32 groups of 8 weights = one 256-weight superblock per warp-pass.
template<int R>
__global__ static void mv_e8_multi(float *y, const float *x, const uint8_t *q,
                                   int I, int O, int64_t nb, int64_t rb){
    __shared__ uint8_t s_grid[256][4];
    __shared__ float   s_x[E8_QK];
    for(int t=threadIdx.x; t<256; t+=blockDim.x){
        s_grid[t][0]=d_e8_grid[t][0]; s_grid[t][1]=d_e8_grid[t][1];
        s_grid[t][2]=d_e8_grid[t][2]; s_grid[t][3]=d_e8_grid[t][3];
    }
    const int warp = threadIdx.x >> 5, lane = threadIdx.x & 31;
    const int sub = lane >> 2, l = lane & 3;
    const int o = blockIdx.x * R + warp;
    const uint8_t *wrow = (o < O) ? q + (int64_t)o * rb : q;
    float acc = 0.f;
    for(int64_t b=0; b<nb; ++b){
        __syncthreads();
        for(int t=threadIdx.x; t<E8_QK; t+=blockDim.x){
            int gi = (int)(b*E8_QK) + t;
            s_x[t] = gi < I ? x[gi] : 0.f;
        }
        __syncthreads();
        if(o >= O) continue;
        const uint8_t *blk = wrow + b*E8_BBYTES;
        uint16_t dh = (uint16_t)blk[96] | ((uint16_t)blk[97] << 8);
        float d = dev_fp16(dh);
        const uint8_t *wp = blk + E8_QK/4 + sub*4;
        uint32_t word = (uint32_t)wp[0] | ((uint32_t)wp[1]<<8)
                      | ((uint32_t)wp[2]<<16) | ((uint32_t)wp[3]<<24);
        float db = d * (0.5f + (float)((word>>28)&0xF)) * 0.5f;
        const uint8_t *idx = blk + sub*8;
        uint32_t seven = (word>>(7*l)) & 0x7F;
        uint32_t sgn = seven | ((uint32_t)(__popc(seven)&1) << 7);
        const uint8_t *g0 = s_grid[idx[l*2+0]], *g1 = s_grid[idx[l*2+1]];
        const float m0 = db * 0.5f;
        const int xb = sub*E8_SUB + l*8;
        #pragma unroll
        for(int j=0;j<8;j++){
            float mag = (j<4 ? (float)g0[j] : (float)g1[j-4]) * m0;
            acc += s_x[xb+j] * (((sgn>>j)&1u) ? -mag : mag);
        }
    }
    #pragma unroll
    for(int off=16; off; off>>=1) acc += __shfl_down_sync(0xffffffff, acc, off);
    if(lane==0 && o<O) y[o]=acc;
}

// ---------------- int4 baseline --------------------------------------------------
__device__ __forceinline__ float nib(const uint8_t *q,int i){
    uint8_t v=q[i>>1]; int n=(i&1)?(v>>4):(v&15); return (float)(n&8?n-16:n);
}
__global__ static void mv_int4(float *y,const float *x,const uint8_t *w,const float *sc,
                               int I,int O,size_t rb){
    int o=blockIdx.x; float s=0.f; const uint8_t *row=w+(size_t)o*rb;
    for(int i=threadIdx.x;i<I;i+=blockDim.x) s+=x[i]*nib(row,i);
    __shared__ float p[256]; p[threadIdx.x]=s; __syncthreads();
    for(int n=blockDim.x>>1;n;n>>=1){ if(threadIdx.x<n)p[threadIdx.x]+=p[threadIdx.x+n]; __syncthreads(); }
    if(!threadIdx.x) y[o]=p[0]*sc[o];
}

static double med(std::vector<double> v){ std::sort(v.begin(),v.end()); return v[v.size()/2]; }

int main(int argc,char**argv){
    const int I=argc>1?atoi(argv[1]):6144, O=argc>2?atoi(argv[2]):2048;
    const int reps=argc>3?atoi(argv[3]):200;
    cudaDeviceProp p; CK(cudaGetDeviceProperties(&p,0));
    printf("device %s (sm_%d%d)  I=%d O=%d B=1\n",p.name,p.major,p.minor,I,O);

    int64_t nb=e8_blocks(I), rb=e8_rowbytes(I);
    std::vector<uint8_t> hq((size_t)O*rb);
    srand(1234); for(auto &c:hq) c=(uint8_t)(rand()&0xFF);
    std::vector<float> hx(I); for(int i=0;i<I;i++) hx[i]=(float)((rand()%200-100)/100.0);

    std::vector<float> yref(O);
    cpu_matmul_e8(yref.data(), hx.data(), hq.data(), I, O);

    float *dx,*dy; uint8_t *dq;
    CK(cudaMalloc(&dx,I*4)); CK(cudaMalloc(&dy,O*4)); CK(cudaMalloc(&dq,(size_t)O*rb));
    CK(cudaMemcpy(dx,hx.data(),I*4,cudaMemcpyHostToDevice));
    CK(cudaMemcpy(dq,hq.data(),(size_t)O*rb,cudaMemcpyHostToDevice));
    CK(cudaMemcpyToSymbol(d_e8_grid,h_e8_grid,sizeof(h_e8_grid)));

    mv_e8<<<O,256>>>(dy,dx,dq,I,O,nb,rb); CK(cudaDeviceSynchronize());
    std::vector<float> ygpu(O);
    CK(cudaMemcpy(ygpu.data(),dy,O*4,cudaMemcpyDeviceToHost));

    std::vector<double> y64(O);
    cpu_matmul_e8_f64(y64.data(), hx.data(), hq.data(), I, O);
    double relG=0, relC=0;
    for(int i=0;i<O;i++){
        double den=fabs(y64[i])+1e-6;
        relG=std::max(relG, fabs((double)ygpu[i]-y64[i])/den);
        relC=std::max(relC, fabs((double)yref[i]-y64[i])/den);
    }
    printf("\n  CORRECTNESS -- both paths vs a float64 reference of the SAME decode\n");
    printf("    CPU  (quant.h matmul_e8, fp32 sequential)  max rel %.3e\n", relC);
    printf("    CUDA (this port, fp32 tree reduction)      max rel %.3e\n", relG);
    printf("    -> %s\n", relG <= relC * 2.0
           ? "AGREES: GPU is as accurate as the CPU reference (summation order only)"
           : "MISMATCH: GPU decode differs beyond accumulation order");

    // int4 baseline for the throughput comparison
    size_t rb4=(size_t)I/2;
    uint8_t *w4; float *sc;
    CK(cudaMalloc(&w4,(size_t)O*rb4)); CK(cudaMalloc(&sc,O*4));
    // int4 rows (I/2) are LARGER than E8 rows (98B per 256 weights), so hq cannot
    // back this copy -- its own buffer, or we read past the end of hq.
    std::vector<uint8_t> h4((size_t)O*rb4);
    for(auto &c:h4) c=(uint8_t)(rand()&0xFF);
    CK(cudaMemcpy(w4,h4.data(),(size_t)O*rb4,cudaMemcpyHostToDevice));
    std::vector<float> ones(O,0.01f);
    CK(cudaMemcpy(sc,ones.data(),O*4,cudaMemcpyHostToDevice));

    cudaEvent_t a,b; CK(cudaEventCreate(&a)); CK(cudaEventCreate(&b));
    auto bench=[&](int which){
        std::vector<double> t;
        for(int r=0;r<reps;r++){
            CK(cudaEventRecord(a));
            if(which==1) mv_e8<<<O,256>>>(dy,dx,dq,I,O,nb,rb);
            else if(which==2) mv_e8_multi<8><<<(O+7)/8,256>>>(dy,dx,dq,I,O,nb,rb);
            else      mv_int4<<<O,256>>>(dy,dx,w4,sc,I,O,rb4);
            CK(cudaEventRecord(b)); CK(cudaEventSynchronize(b));
            float ms=0; CK(cudaEventElapsedTime(&ms,a,b)); t.push_back(ms);
        }
        return med(t);
    };
    double t4=bench(0), t8=bench(1), tm=bench(2);
    mv_e8_multi<8><<<(O+7)/8,256>>>(dy,dx,dq,I,O,nb,rb); CK(cudaDeviceSynchronize());
    std::vector<float> ym(O); CK(cudaMemcpy(ym.data(),dy,O*4,cudaMemcpyDeviceToHost));
    double relM=0; for(int i=0;i<O;i++) relM=std::max(relM, fabs((double)ym[i]-y64[i])/(fabs(y64[i])+1e-6));
    double b4=(double)O*rb4, b8=(double)O*rb;
    printf("\n  %-30s %9s %11s %9s\n","kernel","ms","GB/s","vs int4");
    printf("  %-30s %9.4f %11.1f %8.2fx\n","int4 nibble (baseline)",t4,b4/(t4*1e-3)/1e9,1.0);
    printf("  %-30s %9.4f %11.1f %8.2fx\n","fmt=6 E8/IQ3 (1 row/block)",t8,b8/(t8*1e-3)/1e9,t4/t8);
    printf("  %-30s %9.4f %11.1f %8.2fx   (max rel %.2e)\n","fmt=6 E8/IQ3 (8 rows/block)",tm,b8/(tm*1e-3)/1e9,t4/tm,relM);
    printf("\n  bytes/row: int4 %.0f, E8 %.0f (%.2fx less)\n",(double)rb4,(double)rb,(double)rb4/rb);
    return relG <= relC * 2.0 ? 0 : 1;
}
