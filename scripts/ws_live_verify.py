# Development-only WebSocket verification tool; not part of the application.

import asyncio
import json
import sys

import websockets


async def consume(label: str, url: str, delay: float) -> list[int]:
    await asyncio.sleep(delay)
    sequences: list[int] = []
    trade_messages = 0
    async with websockets.connect(url) as websocket:
        while True:
            message = json.loads(await asyncio.wait_for(websocket.recv(), timeout=40))
            if message["type"] == "trades":
                trade_messages += 1
                sequences.extend(trade["seq"] for trade in message["trades"])
                print(
                    f"{label}: trades message {trade_messages}, "
                    f"rows={len(message['trades'])}, seq={sequences[-1]}"
                )
            elif message["type"] == "progress" and message["status"] == "completed":
                break
    print(
        f"{label}: rows={len(sequences)}, unique={len(set(sequences))}, "
        f"first={min(sequences)}, last={max(sequences)}"
    )
    return sequences


async def main() -> None:
    url = sys.argv[1]
    early, late = await asyncio.gather(consume("early", url, 0), consume("late", url, 9))
    assert early == list(range(1, 501))
    assert late == list(range(1, 501))


if __name__ == "__main__":
    asyncio.run(main())
