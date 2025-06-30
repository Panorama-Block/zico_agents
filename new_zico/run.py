#!/usr/bin/env python3
"""
Startup script for Zico Multi-Agent System
"""

import os
import sys
import uvicorn
from pathlib import Path
from dotenv import load_dotenv

# Add src to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def main():
    """Main startup function"""
    
    # Load .env file first
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        print(f"✅ Loaded environment from {env_file}")
    else:
        print("⚠️  Warning: .env file not found!")
        print("📝 Please create a .env file with your GEMINI_API_KEY")
        print("💡 You can copy from env.example as a starting point")
        print()
    
    # Check for required environment variables
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("❌ Error: GEMINI_API_KEY environment variable is required!")
        print("🔑 Please set your Google Gemini API key in the .env file")
        print("📖 Get your API key from: https://makersuite.google.com/app/apikey")
        print()
        print("📋 Current environment variables:")
        for key, value in os.environ.items():
            if "GEMINI" in key or "API" in key:
                print(f"  {key}: {'*' * len(value) if value else 'None'}")
        sys.exit(1)
    
    # Configuration
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("DEBUG", "True").lower() == "true"
    
    print("🚀 Starting Zico Multi-Agent System...")
    print(f"🌐 Server will be available at: http://{host}:{port}")
    print(f"🔧 Debug mode: {debug}")
    print("📚 API documentation: http://localhost:8000/docs")
    print()
    
    # Start the server
    uvicorn.run(
        "src.app:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info"
    )

if __name__ == "__main__":
    main() 