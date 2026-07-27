// Is the 6.2x expert-matmul gap launch overhead? And does CUDA Graph capture remove it?
//
// Measured in Colibri: 282 us/expert in-engine vs 45.5 us of actual kernel time.
// The fallback issues 4 launches per expert (gate, up, silu, down). This reproduces that
// exact pattern at GLM shapes and compares:
//   (a) stream launches, one after another  (what Colibri does today)
//   (b) the same work captured once as a CUDA Graph and replayed (the proposed fix)
//
// build: nvcc -O3 -arch=sm_120 launch_overhead.cu -o launch_overhead
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <vector>
#include <algorithm>
#include <cuda_runtime.h>

#define CK(x) do{ cudaError_t err_=(x); if(err_){printf("CUDA %s @%d\n",cudaGetErrorString(err_),__LINE__); exit(1);} }while(0)

__device__ static float weight_at_i4(const uint8_t *q, int i){
    uint8_t v = q[i>>1]; int n = (i&1)?(v>>4):(v&15); return (float)(n&8?n-16:n);
}
__global__ static void quant_matmul(float *y,const float *x,const uint8_t *w,
                                    const float *sc,int I,int O,size_t rb){
    int o=blockIdx.x; float sum=0.f; const uint8_t *row=w+(size_t)o*rb;
    for(int i=threadIdx.x;i<I;i+=blockDim.x) sum += x[i]*weight_at_i4(row,i);
    __shared__ float p[256]; p[threadIdx.x]=sum; __syncthreads();
    for(int n=blockDim.x>>1;n;n>>=1){ if(threadIdx.x<n) p[threadIdx.x]+=p[threadIdx.x+n]; __syncthreads(); }
    if(!threadIdx.x) y[o]=p[0]*sc[o];
}
__global__ static void silu_mul(float *g,const float *u,size_t n){
    size_t i=(size_t)blockIdx.x*blockDim.x+threadIdx.x;
    if(i<n){ float v=g[i]; g[i]=(v/(1.f+expf(-v)))*u[i]; }
}
__global__ static void empty_kernel(){}

struct Expert { uint8_t *g,*u,*d; float *gs,*us,*ds; };

int main(int argc,char**argv){
    const int D=6144, I=2048;                     // GLM: gate/up are OxI = 2048x6144; down 6144x2048
    int nexp = argc>1?atoi(argv[1]):8;            // experts per group (Colibri measured 7.69)
    int reps = argc>2?atoi(argv[2]):50;
    size_t rbD=(D+1)/2, rbI=(I+1)/2;

    cudaDeviceProp p; CK(cudaGetDeviceProperties(&p,0));
    printf("device %s  |  %d experts/group, 4 launches each = %d launches\n",p.name,nexp,nexp*4);

    // ---- empty-launch overhead ----
    cudaStream_t s; CK(cudaStreamCreate(&s));
    cudaEvent_t a,b; CK(cudaEventCreate(&a)); CK(cudaEventCreate(&b));
    const int NL=10000;
    empty_kernel<<<1,32,0,s>>>(); CK(cudaStreamSynchronize(s));
    CK(cudaEventRecord(a,s));
    for(int i=0;i<NL;i++) empty_kernel<<<1,32,0,s>>>();
    CK(cudaEventRecord(b,s)); CK(cudaEventSynchronize(b));
    float ms=0; CK(cudaEventElapsedTime(&ms,a,b));
    printf("  empty kernel launch: %.3f us each (%d launches in %.2f ms)\n\n", ms*1000.0/NL, NL, ms);

    // ---- allocate a group of experts ----
    std::vector<Expert> E(nexp);
    float *x,*gate,*up,*y;
    CK(cudaMalloc(&x,D*4)); CK(cudaMalloc(&gate,I*4)); CK(cudaMalloc(&up,I*4)); CK(cudaMalloc(&y,D*4));
    CK(cudaMemset(x,0,D*4));
    for(int e=0;e<nexp;e++){
        CK(cudaMalloc(&E[e].g,(size_t)I*rbD)); CK(cudaMalloc(&E[e].u,(size_t)I*rbD));
        CK(cudaMalloc(&E[e].d,(size_t)D*rbI));
        CK(cudaMalloc(&E[e].gs,I*4)); CK(cudaMalloc(&E[e].us,I*4)); CK(cudaMalloc(&E[e].ds,D*4));
        CK(cudaMemset(E[e].g,0x37,(size_t)I*rbD)); CK(cudaMemset(E[e].u,0x51,(size_t)I*rbD));
        CK(cudaMemset(E[e].d,0x29,(size_t)D*rbI));
        CK(cudaMemset(E[e].gs,0,I*4)); CK(cudaMemset(E[e].us,0,I*4)); CK(cudaMemset(E[e].ds,0,D*4));
    }

    auto issue = [&](cudaStream_t st){
        for(int e=0;e<nexp;e++){
            quant_matmul<<<I,256,0,st>>>(gate,x,E[e].g,E[e].gs,D,I,rbD);
            quant_matmul<<<I,256,0,st>>>(up,  x,E[e].u,E[e].us,D,I,rbD);
            silu_mul<<<(unsigned)((I+255)/256),256,0,st>>>(gate,up,I);
            quant_matmul<<<D,256,0,st>>>(y,gate,E[e].d,E[e].ds,I,D,rbI);
        }
    };

    // ---- (a) plain stream launches ----
    issue(s); CK(cudaStreamSynchronize(s));
    std::vector<double> t;
    for(int r=0;r<reps;r++){
        CK(cudaEventRecord(a,s)); issue(s); CK(cudaEventRecord(b,s));
        CK(cudaEventSynchronize(b)); CK(cudaEventElapsedTime(&ms,a,b)); t.push_back(ms);
    }
    std::sort(t.begin(),t.end()); double t_stream=t[t.size()/2];

    // ---- (b) CUDA Graph capture + replay ----
    cudaGraph_t graph; cudaGraphExec_t exec;
    CK(cudaStreamBeginCapture(s,cudaStreamCaptureModeGlobal));
    issue(s);
    CK(cudaStreamEndCapture(s,&graph));
    CK(cudaGraphInstantiate(&exec,graph,nullptr,nullptr,0));
    CK(cudaGraphLaunch(exec,s)); CK(cudaStreamSynchronize(s));
    t.clear();
    for(int r=0;r<reps;r++){
        CK(cudaEventRecord(a,s)); CK(cudaGraphLaunch(exec,s)); CK(cudaEventRecord(b,s));
        CK(cudaEventSynchronize(b)); CK(cudaEventElapsedTime(&ms,a,b)); t.push_back(ms);
    }
    std::sort(t.begin(),t.end()); double t_graph=t[t.size()/2];

    double bytes = (double)nexp*((size_t)2*I*rbD + (size_t)D*rbI);
    printf("  %-34s %10s %12s %13s\n","mode","ms/group","us/expert","GB/s");
    printf("  %-34s %10.4f %12.1f %13.1f\n","(a) stream launches (Colibri today)",t_stream,t_stream*1000/nexp,bytes/(t_stream*1e-3)/1e9);
    printf("  %-34s %10.4f %12.1f %13.1f\n","(b) CUDA Graph replay",             t_graph, t_graph*1000/nexp, bytes/(t_graph*1e-3)/1e9);
    printf("\n  graph speedup: %.2fx\n", t_stream/t_graph);
    printf("  Colibri measures 282 us/expert in-engine; kernel-only floor is ~45.5 us\n");

    double dec = 21.208, em = 10.963;
    double em_g = em / (t_stream/t_graph);
    printf("\n  if the whole expert path were graph-captured:\n");
    printf("    expert-matmul %.2fs -> %.2fs ; decode %.2fs -> %.2fs ; %.2f -> %.2f tok/s\n",
           em, em_g, dec, dec-em+em_g, 64/dec, 64/(dec-em+em_g));
    return 0;
}
