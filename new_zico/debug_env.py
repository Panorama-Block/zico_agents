#!/usr/bin/env python3
"""
Debug script to check environment variable loading
"""

import os
from pathlib import Path
from dotenv import load_dotenv

def debug_env():
    """Debug environment variable loading"""
    print("🔍 Debugging Environment Variables")
    print("=" * 50)
    
    # Check current directory
    current_dir = Path.cwd()
    print(f"📁 Current directory: {current_dir}")
    
    # Check for .env file
    env_file = current_dir / ".env"
    print(f"📄 .env file exists: {env_file.exists()}")
    
    if env_file.exists():
        print(f"📄 .env file path: {env_file.absolute()}")
        print(f"📄 .env file size: {env_file.stat().st_size} bytes")
        
        # Show .env file contents (masked)
        print("\n📋 .env file contents (masked):")
        with open(env_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        if 'KEY' in key.upper() or 'SECRET' in key.upper():
                            masked_value = '*' * len(value) if value else 'None'
                            print(f"  Line {line_num}: {key}={masked_value}")
                        else:
                            print(f"  Line {line_num}: {key}={value}")
                    else:
                        print(f"  Line {line_num}: {line}")
    
    # Check environment before loading .env
    print(f"\n🔍 Environment before loading .env:")
    gemini_key_before = os.getenv("GEMINI_API_KEY")
    print(f"  GEMINI_API_KEY: {'*' * len(gemini_key_before) if gemini_key_before else 'None'}")
    
    # Load .env file
    if env_file.exists():
        print(f"\n📥 Loading .env file...")
        load_dotenv(env_file)
        print(f"✅ .env file loaded")
    
    # Check environment after loading .env
    print(f"\n🔍 Environment after loading .env:")
    gemini_key_after = os.getenv("GEMINI_API_KEY")
    print(f"  GEMINI_API_KEY: {'*' * len(gemini_key_after) if gemini_key_after else 'None'}")
    
    # Check if key changed
    if gemini_key_before != gemini_key_after:
        print(f"✅ Environment variable was loaded successfully!")
    else:
        print(f"⚠️  Environment variable did not change")
    
    # Show all environment variables containing 'GEMINI' or 'API'
    print(f"\n🔍 All relevant environment variables:")
    for key, value in os.environ.items():
        if 'GEMINI' in key.upper() or 'API' in key.upper():
            masked_value = '*' * len(value) if value else 'None'
            print(f"  {key}: {masked_value}")
    
    # Test if the key is valid (basic check)
    if gemini_key_after:
        if len(gemini_key_after) > 10:  # Basic validation
            print(f"\n✅ API key appears to be valid (length: {len(gemini_key_after)})")
        else:
            print(f"\n⚠️  API key seems too short (length: {len(gemini_key_after)})")
    else:
        print(f"\n❌ No API key found")

if __name__ == "__main__":
    debug_env() 