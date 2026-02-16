"""Verify Production Deep Drill."""
import requests
import json
import time
import sys

PROXY_URL = "https://experts-reddit-proxy.fly.dev"
TEST_POST_ID = "1qejxci" 
TEST_SUBREDDIT = "wallstreetbets"

def test_proxy_capabilities():
    print("Target: " + PROXY_URL)
    try:
        resp = requests.get(PROXY_URL + "/health", timeout=10)
        print("Health: " + str(resp.status_code))
    except Exception as e:
        print("Health check failed: " + str(e))
        return False

    print("\n🚀 Testing Deep Drill (Limit=60, Depth=5)...")
    start = time.time()
    
    payload = {
        "postId": TEST_POST_ID,
        "subreddit": TEST_SUBREDDIT,
        "comment_limit": 60,
        "comment_depth": 5
    }
    
    try:
        resp = requests.post(PROXY_URL + "/details", json=payload, timeout=60)
        
        if resp.status_code != 200:
            print("❌ Request failed: " + str(resp.status_code))
            print(resp.text)
            return False
            
        data = resp.json()
        top_comments = data.get("top_comments", [])
        
        print("✅ Success in " + str(time.time() - start))
        
        # Check depth (recursively count)
        def count_recursive(comments):
            count = len(comments)
            for c in comments:
                replies = c.get("replies", [])
                if replies:
                    count += count_recursive(replies)
            return count

        total_nodes = count_recursive(top_comments)
        print("🌳 Total nodes (including replies): " + str(total_nodes))

        if top_comments:
            print("Sample comment keys: " + str(top_comments[0].keys()))
            
        if total_nodes > 5:
            print("\n🎉 PASS: Deep Drill is ACTIVE! (Got " + str(total_nodes) + " comments > 5)")
            return True
        else:
            print("\n⚠️ FAIL: Still seeing shallow results (" + str(total_nodes) + " <= 5 comments).")
            return False
            
    except Exception as e:
        print("❌ Error: " + str(e))
        return False

if __name__ == "__main__":
    success = test_proxy_capabilities()
    sys.exit(0 if success else 1)
