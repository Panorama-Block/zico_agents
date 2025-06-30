#!/usr/bin/env python3
"""
Simple test to verify basic functionality
"""

import os
import sys
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def test_imports():
    """Test if all imports work"""
    print("🧪 Testing imports...")
    
    try:
        from dotenv import load_dotenv
        print("✅ dotenv imported")
        
        from src.agents.config import Config
        print("✅ Config imported")
        
        from src.agents.supervisor.simple_supervisor import SimpleSupervisor
        print("✅ SimpleSupervisor imported")
        
        from src.agents.crypto_data.agent import CryptoDataAgent
        print("✅ CryptoDataAgent imported")
        
        from src.models.chatMessage import ChatMessage, AgentType
        print("✅ ChatMessage models imported")
        
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_config():
    """Test configuration loading"""
    print("\n🔧 Testing configuration...")
    
    try:
        # Load .env file
        env_file = Path(__file__).parent / ".env"
        if env_file.exists():
            from dotenv import load_dotenv
            load_dotenv(env_file)
            print("✅ .env file loaded")
        
        # Check API key
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            print(f"✅ API key found (length: {len(api_key)})")
        else:
            print("❌ API key not found")
            return False
        
        # Test LLM creation
        from src.agents.config import Config
        llm = Config.get_llm()
        print("✅ LLM created successfully")
        
        return True
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def test_supervisor():
    """Test supervisor creation"""
    print("\n🤖 Testing supervisor...")
    
    try:
        from src.agents.config import Config
        from src.agents.supervisor.simple_supervisor import SimpleSupervisor
        
        llm = Config.get_llm()
        supervisor = SimpleSupervisor(llm)
        print("✅ Supervisor created successfully")
        
        # Test simple message
        messages = [{"role": "user", "content": "Hello"}]
        response = supervisor.invoke(messages)
        print("✅ Supervisor invoked successfully")
        print(f"📄 Response: {response['response'][:100]}...")
        
        return True
    except Exception as e:
        print(f"❌ Supervisor test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Simple Functionality Test")
    print("=" * 50)
    
    tests = [
        ("Imports", test_imports),
        ("Configuration", test_config),
        ("Supervisor", test_supervisor)
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
        print("\n🎉 All tests passed! Your system is ready to run.")
        print("🚀 You can now run: python run.py")
    else:
        print("\n⚠️  Some tests failed. Please check the errors above.")

if __name__ == "__main__":
    main() 