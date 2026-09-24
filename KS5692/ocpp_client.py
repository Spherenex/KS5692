from models import now_iso

class OCPPClient:
    def message(self,kind,payload=None): return {"messageType":kind,"stationId":"KS5692-CS-01","timestamp":now_iso(),"payload":payload or {}}

