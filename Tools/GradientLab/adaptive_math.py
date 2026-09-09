"""Independent double error calculation with explicit binary32 input semantics."""
import math
import struct
from functools import lru_cache

def f32(value):return struct.unpack("f",struct.pack("f",value))[0]

def interval_error(left,right,a,span):
    if span==0:return 0.0
    dl=a+(1-a)*left;dr=a+(1-a)*right
    return span*abs(a*(a-1))*(right-left)**2/(dl*dr*(math.sqrt(dl)+math.sqrt(dr))**2)+.000002

@lru_cache(maxsize=2048)
def select(start,end,bias,minimum=1,maximum=64,tolerance=.01):
    if not 1<=minimum<=maximum<=64 or not math.isfinite(tolerance) or not .00001<=tolerance<=1:raise ValueError("Adaptive bounds")
    bias=f32(bias);tolerance=f32(tolerance);a=(1-bias)/bias
    if not f32(.05)<=bias<=f32(.95):raise ValueError("Bias outside runtime contract")
    start=tuple(map(f32,start));end=tuple(map(f32,end));span=max(abs(x-y) for x,y in zip(start,end))
    nodes=[f32(i/minimum) for i in range(minimum+1)]
    while True:
        errors=[interval_error(l,r,a,span) for l,r in zip(nodes,nodes[1:])]
        worst=max(range(len(errors)),key=errors.__getitem__)
        if errors[worst]<=tolerance or len(errors)==maximum:return tuple(nodes),errors[worst],errors[worst]>tolerance
        nodes.insert(worst+1,f32(f32(nodes[worst]+nodes[worst+1])*.5))
