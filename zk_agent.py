import time
import requests
from zk import ZK

# --- Configuration ---
ZK_DEVICE_IP = '192.168.1.171'
ZK_DEVICE_PORT = 4370
API_URL = "https://hrm-a174.onrender.com/api/biometric/sync"
API_KEY = "zkteco-secret-key-123"
SYNC_INTERVAL_SECONDS = 300  # Sync every 5 minutes

def sync_attendance():
    zk = ZK(ZK_DEVICE_IP, port=ZK_DEVICE_PORT)
    conn = None
    try:
        print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Connecting to device {ZK_DEVICE_IP}...")
        conn = zk.connect()
        
        # Disable device briefly to ensure data integrity while reading (optional but good practice)
        conn.disable_device()
        
        attendances = conn.get_attendance()
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Found {len(attendances)} total logs on device.")
        
        if not attendances:
            print("No attendance logs found.")
            return

        # Prepare payload (Only send logs from the last 2 days to avoid timeout)
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=2)
        
        data_to_send = []
        for att in attendances:
            if getattr(att, 'timestamp', None) and att.timestamp >= cutoff_date:
                data_to_send.append({
                    "fingerprint_id": str(att.user_id),
                    "timestamp": str(att.timestamp)
                })

        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Sending {len(data_to_send)} records to Server API...")
        
        # Call API
        response = requests.post(
            f"{API_URL}?api_key={API_KEY}", 
            json=data_to_send,
            timeout=60
        )
        
        if response.status_code == 200:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Success! Server says: {response.text}")
            
            # Optional: Clear attendance logs from device if you only want to read new ones.
            # Warning: Only uncomment if you are sure data is safely backed up in DB.
            # conn.clear_attendance() 
            # print("Device logs cleared.")
        else:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Server Error ({response.status_code}): {response.text}")

    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error: {e}")
    finally:
        if conn:
            conn.enable_device()
            conn.disconnect()

if __name__ == "__main__":
    print("==================================================")
    print(" ZKTeco Background Sync Agent Started")
    print(f" Press Ctrl+C to stop. Syncing every {SYNC_INTERVAL_SECONDS} seconds.")
    print("==================================================")
    
    while True:
        sync_attendance()
        time.sleep(SYNC_INTERVAL_SECONDS)
