#!/usr/bin/env python3
"""
Test script for Zico Multi-Agent System API
"""

import requests
import json
import time

def test_health_check():
    """Test the health check endpoint"""
    try:
        response = requests.get("http://localhost:8000/")
        print("✅ Health check:", response.status_code)
        print("📄 Response:", response.json())
        return True
    except Exception as e:
        print("❌ Health check failed:", e)
        return False

def test_chat_endpoint():
    """Test the chat endpoint"""
    try:
        data = {
            "message": "Hello, how are you?",
            "user_id": "test_user",
            "conversation_id": "test_conv"
        }
        
        response = requests.post(
            "http://localhost:8000/chat",
            json=data,
            headers={"Content-Type": "application/json"}
        )
        
        print("✅ Chat endpoint:", response.status_code)
        print("📄 Response:", json.dumps(response.json(), indent=2))
        return True
    except Exception as e:
        print("❌ Chat endpoint failed:", e)
        return False

def test_crypto_query():
    """Test crypto-related query"""
    try:
        data = {
            "message": "What is the price of Bitcoin?",
            "user_id": "test_user",
            "conversation_id": "test_conv"
        }
        
        response = requests.post(
            "http://localhost:8000/chat",
            json=data,
            headers={"Content-Type": "application/json"}
        )
        
        print("✅ Crypto query:", response.status_code)
        print("📄 Response:", json.dumps(response.json(), indent=2))
        return True
    except Exception as e:
        print("❌ Crypto query failed:", e)
        return False

def main():
    """Run all tests"""
    print("🧪 Testing Zico Multi-Agent System API")
    print("=" * 50)
    
    # Wait a bit for server to start
    print("⏳ Waiting for server to be ready...")
    time.sleep(2)
    
    # Run tests
    tests = [
        ("Health Check", test_health_check),
        ("Chat Endpoint", test_chat_endpoint),
        ("Crypto Query", test_crypto_query)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🔍 Running {test_name}...")
        result = test_func()
        results.append((test_name, result))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    if all_passed:
        print("\n🎉 All tests passed! Your system is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Check the server logs for details.")

if __name__ == "__main__":
    main() 