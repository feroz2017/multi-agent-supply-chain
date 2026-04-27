from spade.agent import Agent
import asyncio

async def main():
    agent = Agent("alice@localhost", "alicepass")
    
    try:
        await agent.start(auto_register=True)
        print("✅ Connected!")
        await asyncio.sleep(2)
        await agent.stop()
    except Exception as e:
        print(f"❌ Error: {e}")

asyncio.run(main())