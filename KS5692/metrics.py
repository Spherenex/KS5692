def summarize(history):
    def avg(key):
        values=[x.get(key,0) for x in history]; return sum(values)/len(values) if values else 0
    def extrema(key,fn):
        values=[x.get(key,0) for x in history]
        return fn(values) if values else 0
    return {"avg_latency":avg("latency"),"min_latency":extrema("latency",min),"max_latency":extrema("latency",max),
            "avg_jitter":avg("jitter"),"max_jitter":extrema("jitter",max),
            "avg_throughput":avg("throughput"),"avg_utilization":avg("utilization"),
            "avg_queue_wait":avg("queue_wait")}
