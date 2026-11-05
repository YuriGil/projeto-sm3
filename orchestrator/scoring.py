WEIGHTS={"technical":.18,"visual":.22,"novelty":.18,"process":.12,"portfolio":.15,"hook":.10,"anatomy":.05}
def score(values, is_video=False, near_duplicate=False):
    active={k:v for k,v in WEIGHTS.items() if is_video or k!="hook"}
    denom=sum(active.values())
    result=sum(values.get(k,0)*w for k,w in active.items())/denom
    if near_duplicate: result-=35
    return max(0,round(result,2))
