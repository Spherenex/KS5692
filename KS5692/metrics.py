def summarize(history):
    def avg(key):
        values=[x.get(key,0) for x in history]; return sum(values)/len(values) if values else 0
    return {"avg_latency":avg("latency"),"avg_jitter":avg("jitter"),"avg_throughput":avg("throughput"),"avg_utilization":avg("utilization")}

