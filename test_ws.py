import asyncio, websockets, json

async def run():
    uri = "ws://127.0.0.1:8000/ws"
    print("Connecting to", uri)
    try:
        async with websockets.connect(uri) as ws:
            print("CONNECTED!")

            for i in range(5):
                msg = await ws.recv()
                print("MSG", i+1, msg)

            await ws.close()
    except Exception as e:
        print("CLIENT ERROR:", e)

asyncio.run(run())
