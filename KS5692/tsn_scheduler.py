import time

class TSNScheduler:
    windows={1:(0,1,"Safety"),2:(1,3,"Control"),3:(3,6,"ADAS"),4:(6,10,"Normal")}
    def active(self):
        ms=(time.time()*1000)%10
        for p,(a,b,n) in self.windows.items():
            if a<=ms<b:return p,n,ms
        return 4,"Normal",ms
    def schedule(self,packet):
        packet.tsn_enqueue_timestamp=time.time(); active,_,_=self.active()
        wait=.00008*packet.priority if active==packet.priority else .00018*packet.priority
        packet.tsn_dequeue_timestamp=packet.tsn_enqueue_timestamp+wait
        return packet,wait*1000

