import asyncio
from backend.app.shoper import ShoperClient, upsert_products
from backend.app.settings import settings

async def main():
    print('Settings image base:', settings.shoper_image_base)
    client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
    items = await client.fetch_all_products(limit=5)
    print('Fetched', len(items))
    res = upsert_products(items)
    print('Upsert result:', res)

asyncio.run(main())
