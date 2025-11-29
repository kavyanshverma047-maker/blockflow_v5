import asyncio, websockets, json, sys
async def run(url="ws://127.0.0.1:8000/ws?channel=market", n=6):
    try:
        async with websockets.connect(url) as ws:
            print("CONNECTED to", url)
            for i in range(n):
                msg = await ws.recv()
                try:
                    data = json.loads(msg)
                except:
                    data = msg
                print("MSG", i+1, data)
    except Exception as e:
        print("CLIENT ERROR", e)
if __name__=="__main__":
    url = sys.argv[1] if len(sys.argv)>1 else "ws://127.0.0.1:8000/ws?channel=market"
    asyncio.run(run(url))
