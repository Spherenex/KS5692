class CSMSServer:
    def handle(self,message):
        return {"status":"Accepted","messageType":message["messageType"],"stationId":message["stationId"]}

