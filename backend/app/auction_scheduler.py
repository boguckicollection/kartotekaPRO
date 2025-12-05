import asyncio
import traceback
from datetime import datetime
from sqlalchemy import desc
from .db import SessionLocal, Auction, AuctionBid, Product
from .settings import settings
from .shoper import ShoperClient
from .websocket import manager
import httpx

async def publish_winning_auction(auction: Auction, winning_bid: AuctionBid):
    """
    Publishes the winning auction to Shoper as a product (or updates existing).
    """
    if not settings.shoper_base_url or not settings.shoper_access_token:
        # Only log once per run/error to avoid spam, or just debug
        # print("⚠️ Shoper credentials not set, skipping auto-publish.")
        return

    if not auction.auto_publish_to_shoper:
        return

    client = ShoperClient(settings.shoper_base_url, settings.shoper_access_token)
    
    try:
        # Case 1: Auction is linked to an existing product
        if auction.product_id:
            print(f"🔄 Updating existing product {auction.product_id} for auction #{auction.id}")
            # We need the Shoper ID, not our local DB ID. 
            # Since 'auction' is attached to the scheduler's session, we can access auction.product relationship if loaded,
            # but better to query freshly or check if it's loaded.
            # To avoid async/sync session issues, we use the IDs directly.
            
            # Create a new session for looking up the product to be safe with async
            db_lookup = SessionLocal()
            try:
                product = db_lookup.query(Product).filter(Product.id == auction.product_id).first()
                if product and product.shoper_id:
                    # Update price and stock
                    updates = {
                        "price": float(auction.current_price),
                        "stock": 1.0
                    }
                    res = await client.update_product(product.shoper_id, updates)
                    if res.get("ok"):
                        print(f"✅ Product {product.shoper_id} updated successfully.")
                        # We can't update 'auction' here easily if it's from another session, 
                        # but the caller (scheduler loop) commits the main session.
                        # We can return the shoper_id to update the caller's object.
                        return product.shoper_id
                    else:
                        print(f"❌ Failed to update product: {res}")
            finally:
                db_lookup.close()
                
        # Case 2: Create new product
        else:
            print(f"🆕 Creating new product for auction #{auction.id}")
            
            # Basic payload
            payload = {
                "category_id": 38, # Default category - TODO: make configurable
                "producer_id": settings.default_producer_id,
                "tax_id": settings.default_tax_id,
                "unit_id": settings.default_unit_id,
                "stock": {
                    "price": float(auction.current_price),
                    "stock": 1.0,
                    "delivery_id": settings.default_delivery_id
                },
                "translations": {
                    settings.default_language_code: {
                        "name": f"[Aukcja] {auction.title}",
                        "short_description": f"Aukcja zakończona dnia {datetime.utcnow().strftime('%Y-%m-%d')}",
                        "description": f"<p>Zwycięzca licytacji: <strong>{winning_bid.username or winning_bid.kartoteka_user_id}</strong></p><p>Kwota końcowa: {auction.current_price} PLN</p>",
                        "active": 1
                    }
                }
            }
            
            headers = {"Authorization": f"Bearer {client.token}", "Accept": "application/json"}
            url = f"{client.base_url}{settings.shoper_products_path}"
            
            async with httpx.AsyncClient() as http:
                r = await http.post(url, json=payload, headers=headers)
                if r.status_code in (200, 201):
                    data = r.json()
                    shoper_id = data.get("product_id") or data.get("id")
                    if shoper_id:
                        print(f"✅ Created Shoper product ID: {shoper_id}")
                        
                        # Upload image if available
                        if auction.image_url:
                            print(f"🖼️ Uploading image: {auction.image_url}")
                            # Use the client method which handles URLs
                            await client.upload_product_image(int(shoper_id), auction.image_url, main=True)
                            
                        return int(shoper_id)
                else:
                    print(f"❌ Failed to create product: {r.text}")

    except Exception as e:
        print(f"❌ Error publishing auction to Shoper: {e}")
        traceback.print_exc()
    return None

async def auction_scheduler_task():
    """
    Background task that periodically checks for expired auctions
    and marks them as ended, determining the winner if any bids exist.
    """
    print("⏳ Auction scheduler started.")
    
    while True:
        try:
            await asyncio.sleep(10)  # Check every 10 seconds
            
            db = SessionLocal()
            try:
                now = datetime.utcnow()
                
                # Find active auctions that have passed their end time
                expired_auctions = db.query(Auction).filter(
                    Auction.status == "active",
                    Auction.end_time <= now
                ).all()
                
                if not expired_auctions:
                    continue
                    
                print(f"🕒 Found {len(expired_auctions)} expired auctions. Processing...")
                
                for auction in expired_auctions:
                    try:
                        # Find the highest bid
                        highest_bid = db.query(AuctionBid).filter(
                            AuctionBid.auction_id == auction.id
                        ).order_by(desc(AuctionBid.amount)).first()
                        
                        auction.status = "ended"
                        auction.ended_at = now
                        
                        if highest_bid:
                            auction.winner_kartoteka_user_id = highest_bid.kartoteka_user_id
                            auction.current_price = highest_bid.amount # Ensure final price is set
                            print(f"✅ Auction #{auction.id} ended. Winner: User {highest_bid.kartoteka_user_id} with {highest_bid.amount}")
                            
                            # Broadcast WebSocket update
                            await manager.broadcast({
                                "type": "auction_ended",
                                "auction_id": auction.id,
                                "winner_id": highest_bid.kartoteka_user_id,
                                "price": highest_bid.amount,
                                "reason": "time_expired"
                            })
                            
                            # Publish to Shoper if enabled
                            if auction.auto_publish_to_shoper:
                                shoper_id = await publish_winning_auction(auction, highest_bid)
                                if shoper_id:
                                    auction.published_shoper_id = shoper_id
                                    
                        else:
                            print(f"❌ Auction #{auction.id} ended with no bids.")
                            
                    except Exception as e:
                        print(f"⚠️ Error processing auction #{auction.id}: {e}")
                        traceback.print_exc()
                        
                db.commit()
                
            except Exception as e:
                print(f"❌ Error in auction scheduler loop: {e}")
                traceback.print_exc()
            finally:
                db.close()
                
        except asyncio.CancelledError:
            print("🛑 Auction scheduler stopped.")
            break
        except Exception as e:
            print(f"💥 Critical error in auction scheduler: {e}")
            await asyncio.sleep(60) # Wait longer on critical fail
