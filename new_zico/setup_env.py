#!/usr/bin/env python3
"""
Setup script to create .env file
"""

import os
from pathlib import Path

def setup_env():
    """Setup .env file"""
    print("🔧 Setting up .env file")
    print("=" * 50)
    
    current_dir = Path.cwd()
    env_file = current_dir / ".env"
    example_file = current_dir / "env.example"
    
    # Check if .env already exists
    if env_file.exists():
        print(f"⚠️  .env file already exists at: {env_file}")
        response = input("Do you want to overwrite it? (y/N): ").strip().lower()
        if response != 'y':
            print("❌ Setup cancelled")
            return
    
    # Check if env.example exists
    if not example_file.exists():
        print(f"❌ env.example file not found at: {example_file}")
        return
    
    # Read example file
    with open(example_file, 'r') as f:
        example_content = f.read()
    
    # Get API key from user
    print("\n🔑 Please enter your Google Gemini API key:")
    print("📖 Get your API key from: https://makersuite.google.com/app/apikey")
    print()
    
    api_key = input("GEMINI_API_KEY: ").strip()
    
    if not api_key:
        print("❌ API key is required!")
        return
    
    # Create .env content
    env_content = f"""# Google Gemini API Configuration
GEMINI_API_KEY={api_key}

# Model Configuration
GEMINI_MODEL=gemini-1.5-pro
GEMINI_EMBEDDING_MODEL=models/embedding-001

# Application Configuration
DEBUG=True
LOG_LEVEL=INFO

# Server Configuration
HOST=0.0.0.0
PORT=8000

# Optional: Database Configuration (for production)
# DATABASE_URL=postgresql://user:password@localhost/zico_db

# Optional: Redis Configuration (for caching)
# REDIS_URL=redis://localhost:6379
"""
    
    # Write .env file
    try:
        with open(env_file, 'w') as f:
            f.write(env_content)
        
        print(f"\n✅ .env file created successfully at: {env_file}")
        print(f"🔑 API key length: {len(api_key)} characters")
        
        # Test loading
        print("\n🧪 Testing .env file loading...")
        os.environ.clear()  # Clear existing env vars for testing
        
        from dotenv import load_dotenv
        load_dotenv(env_file)
        
        loaded_key = os.getenv("GEMINI_API_KEY")
        if loaded_key == api_key:
            print("✅ .env file loaded successfully!")
        else:
            print("❌ .env file loading failed!")
            
    except Exception as e:
        print(f"❌ Error creating .env file: {e}")

if __name__ == "__main__":
    setup_env() 