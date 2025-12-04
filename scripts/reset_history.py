import sys
import os

# Add backend directory to path so we can import 'app'
current_dir = os.path.dirname(os.path.abspath(__file__))
# Check if we are in scripts/ and backend is ../backend (Local dev)
if os.path.isdir(os.path.join(current_dir, '../backend')):
    sys.path.append(os.path.join(current_dir, '../backend'))
# Check if we are in /app (docker) and app/ exists
elif os.path.isdir(os.path.join(current_dir, 'app')):
    sys.path.append(current_dir)

from sqlalchemy import text
from app.db import SessionLocal, Scan, Fingerprint, ScanCandidate, BatchScan, BatchScanItem, engine

def reset_history():
    print("WARNING: This will delete ALL scan history, fingerprints, and batch scans.")
    print("This action is irreversible and resets the duplicate detection database.")
    
    # Since this is run via tool, we skip interactive confirmation assuming user already confirmed via chat.
    # but for safety in a real shell we might want input. 
    # I'll just print proceeding.
    print("Proceeding with database cleanup...")

    db = SessionLocal()
    try:
        # Using SQLAlchemy models for deletion where possible, or raw SQL for truncation if faster/cleaner
        # Since cascade is on, deleting scans should delete fingerprints and candidates.
        # However, explicit deletion is safer to ensure everything is gone.
        
        print("Deleting Fingerprints...")
        db.query(Fingerprint).delete()
        
        print("Deleting ScanCandidates...")
        db.query(ScanCandidate).delete()
        
        print("Deleting BatchScanItems...")
        db.query(BatchScanItem).delete()
        
        print("Deleting BatchScans...")
        db.query(BatchScan).delete()
        
        print("Deleting Scans...")
        db.query(Scan).delete()
        
        db.commit()
        print("✅ History reset complete. Database is clean.")
        
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    reset_history()
