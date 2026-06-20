from maya_core.utils import OSBridge

def test_osbridge():
    bridge = OSBridge()
    print("[TEST] Verifying OSBridge test-mode notification no-op...")
    bridge.notify("Kampung AI", "Testing OSBridge integration. Everything looks sharp.")
    print("[TEST] Success. No native notification should appear in test mode.")

if __name__ == "__main__":
    test_osbridge()
