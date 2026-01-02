#!/usr/bin/env python3
"""
Utility script to list available Gemini models and their capabilities
"""
import os
import sys
import django

# Add the project directory to the Python path
sys.path.append('/home/ubuntu/smartacca')

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartacca.settings')
django.setup()

from django.conf import settings
from google import genai

def list_available_models():
    """List all available Gemini models"""
    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        
        print("🔍 Listing available Gemini models...")
        print("=" * 60)
        
        # List all available models
        models = client.models.list()
        
        print(f"Found {len(list(models))} models:")
        print()
        
        # Re-list since we consumed the generator
        models = client.models.list()
        
        for model in models:
            print(f"📝 Model: {model.name}")
            print(f"   Display Name: {model.display_name}")
            print(f"   Description: {model.description}")
            
            # Check supported methods
            if hasattr(model, 'supported_generation_methods'):
                methods = model.supported_generation_methods
                print(f"   Supported Methods: {', '.join(methods) if methods else 'None'}")
            
            # Check rate limits if available
            if hasattr(model, 'rate_limit'):
                print(f"   Rate Limit Info: {model.rate_limit}")
            
            print()
        
    except Exception as e:
        print(f"❌ Error listing models: {str(e)}")
        
        # Fallback: try some common model names
        print("\n🔄 Trying common model names...")
        common_models = [
            'gemini-flash-lite-latest',
            'gemini-1.5-flash',
            'gemini-1.5-flash-latest', 
            'gemini-1.5-pro',
            'gemini-1.5-pro-latest',
            'gemini-2.0-flash',
            'gemini-2.0-flash-latest',
            'models/gemini-flash-lite-latest',
            'models/gemini-1.5-flash',
            'models/gemini-1.5-pro'
        ]
        
        for model_name in common_models:
            try:
                # Try a simple generation to test if the model works
                response = client.models.generate_content(
                    model=model_name,
                    contents="Hello"
                )
                print(f"✅ {model_name} - WORKING")
            except Exception as test_error:
                error_msg = str(test_error)
                if "404" in error_msg or "not found" in error_msg.lower():
                    print(f"❌ {model_name} - NOT FOUND")
                elif "quota" in error_msg.lower() or "429" in error_msg:
                    print(f"⚠️  {model_name} - QUOTA EXCEEDED (but model exists)")
                else:
                    print(f"🔴 {model_name} - ERROR: {error_msg[:100]}")

if __name__ == "__main__":
    list_available_models()