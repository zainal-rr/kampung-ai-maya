from utils import OSBridge

def test_osbridge():
    bridge = OSBridge()
    print("[TEST] Sending notification...")
    bridge.notify("Kampung AI", "Testing OSBridge integration. Everything looks sharp.")
    print("[TEST] Success.")

if __name__ == "__main__":
    test_osbridge()
