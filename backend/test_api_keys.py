#!/usr/bin/env python3
"""
Test script to verify API keys are working
"""

import asyncio
import sys
from decimal import Decimal

# Add backend to path
sys.path.insert(0, '/Volumes/MyProjects/hybridWebApp/backend')

from app.core.config import settings
from app.services.events_service import events_service
from app.services.news_service import news_service
from app.services.llm_service import llm_service


async def test_eventbrite_api():
    """Test Eventbrite API key"""
    print("\n" + "="*60)
    print("Testing Eventbrite API Key")
    print("="*60)
    
    if not settings.EVENTBRITE_TOKEN:
        print("❌ EVENTBRITE_TOKEN is NOT SET in .env file")
        return False
    
    print(f"✅ EVENTBRITE_TOKEN is SET (length: {len(settings.EVENTBRITE_TOKEN)})")
    
    try:
        # Test with London coordinates
        print("\nTesting API call to Eventbrite...")
        response = await events_service.get_events(
            lat=Decimal("51.5074"),
            lon=Decimal("-0.1278"),
            within_km=10,
            limit=5
        )
        print(f"✅ Eventbrite API is working!")
        print(f"   Found {response.total_count} events")
        if response.events:
            print(f"   First event: {response.events[0].name[:50]}...")
        return True
    except Exception as e:
        print(f"❌ Eventbrite API test failed: {e}")
        return False


async def test_newsapi_key():
    """Test NewsAPI key"""
    print("\n" + "="*60)
    print("Testing NewsAPI Key")
    print("="*60)
    
    if not settings.NEWSAPI_KEY:
        print("❌ NEWSAPI_KEY is NOT SET in .env file")
        return False
    
    print(f"✅ NEWSAPI_KEY is SET (length: {len(settings.NEWSAPI_KEY)})")
    
    try:
        # Test with London coordinates
        print("\nTesting API call to NewsAPI...")
        response = await news_service.get_news(
            lat=Decimal("51.5074"),
            lon=Decimal("-0.1278"),
            radius_km=50,
            limit=5
        )
        print(f"✅ NewsAPI is working!")
        print(f"   Found {response.total_count} articles")
        if response.articles:
            print(f"   First article: {response.articles[0].title[:50]}...")
        return True
    except Exception as e:
        print(f"❌ NewsAPI test failed: {e}")
        return False


async def test_openrouter_key():
    """Test OpenRouter API key"""
    print("\n" + "="*60)
    print("Testing OpenRouter API Key (LLM)")
    print("="*60)
    
    if not settings.OPENROUTER_API_KEY:
        print("❌ OPENROUTER_API_KEY is NOT SET in .env file")
        return False
    
    print(f"✅ OPENROUTER_API_KEY is SET (length: {len(settings.OPENROUTER_API_KEY)})")
    
    try:
        # Test LLM initialization
        print("\nTesting LLM service initialization...")
        await llm_service.initialize()
        
        if llm_service._client:
            print("✅ LLM service initialized successfully")
            
            # Test a simple summary generation
            print("\nTesting summary generation...")
            prompt = "Generate a short summary about London, UK in 2 sentences."
            summary = await llm_service.generate_summary(prompt, max_tokens=100)
            print(f"✅ LLM summary generation is working!")
            print(f"   Summary: {summary[:100]}...")
            return True
        else:
            print("❌ LLM service failed to initialize")
            return False
    except Exception as e:
        print(f"❌ OpenRouter/LLM test failed: {e}")
        return False


async def main():
    """Run all API key tests"""
    print("\n" + "="*60)
    print("API KEY VERIFICATION TEST")
    print("="*60)
    print("\nChecking configuration...")
    
    results = {
        'Eventbrite': await test_eventbrite_api(),
        'NewsAPI': await test_newsapi_key(),
        'OpenRouter (LLM)': await test_openrouter_key()
    }
    
    print("\n" + "="*60)
    print("TEST RESULTS SUMMARY")
    print("="*60)
    
    for service, result in results.items():
        status = "✅ WORKING" if result else "❌ FAILED"
        print(f"{service:20} {status}")
    
    all_working = all(results.values())
    
    if all_working:
        print("\n🎉 All API keys are working correctly!")
    else:
        print("\n⚠️  Some API keys are not working. Please check:")
        print("   1. API keys are set in backend/.env file")
        print("   2. API keys are valid and not expired")
        print("   3. Backend server is running (if testing via API)")
        print("   4. Network connection is working")
    
    return 0 if all_working else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)



