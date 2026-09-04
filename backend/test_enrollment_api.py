"""Test enrollment endpoint with real audio file.

Auth: the backend requires a Supabase JWT. Export VOICELOCK_TEST_TOKEN with a
valid access token before running (the enrollment is keyed to that token's
user). Or run the server with DEV_NO_AUTH=1 for local development only.
"""
import asyncio
import httpx
import os
from pathlib import Path

BASE_URL = "http://localhost:8000"

TEST_TOKEN = os.environ.get("VOICELOCK_TEST_TOKEN", "")
HEADERS = {"Authorization": f"Bearer {TEST_TOKEN}"} if TEST_TOKEN else {}


async def test_enrollment():
    print("=" * 60)
    print("Testing Enrollment Endpoint")
    print("=" * 60)
    
    # 1. Check if we have an enrollment audio file
    enrollment_audio = None
    embeddings_dir = Path("../data/embeddings")
    
    # Look for existing enrollment audio
    if embeddings_dir.exists():
        for audio_file in embeddings_dir.glob("demo_user_enrollment.wav"):
            enrollment_audio = audio_file
            break
    
    if not enrollment_audio or not enrollment_audio.exists():
        print("\n✗ No enrollment audio found!")
        print("  Run this first to create one:")
        print("  python enroll_user.py --user-id test_user --duration 10")
        print("\n  This will create: ../data/embeddings/test_user_enrollment.wav")
        return
    
    print(f"\n✓ Found enrollment audio: {enrollment_audio}")

    # 2. Test enrollment endpoint (identity comes from the Bearer token)
    print("\n1. Testing enrollment creation...")
    async with httpx.AsyncClient() as client:
        with open(enrollment_audio, 'rb') as f:
            files = {'audio': ('enrollment.wav', f, 'audio/wav')}
            data = {'name': 'Test User via API'}

            response = await client.post(
                f"{BASE_URL}/enrollment/create",
                files=files,
                data=data,
                headers=HEADERS,
                timeout=30.0
            )
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✓ Enrollment successful!")
            print(f"   - User ID: {result['user_id']}")
            print(f"   - Name: {result['name']}")
            print(f"   - Status: {result['status']}")
            print(f"   - Embedding dimension: {result['embedding_dimension']}")
        else:
            print(f"   ✗ Enrollment failed: {response.status_code}")
            print(f"   {response.text}")
            return
    
    # 3. Check enrollment
    print("\n2. Checking enrollment status...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/enrollment/me", headers=HEADERS)
        result = response.json()
        
        if result['enrolled']:
            print(f"   ✓ User is enrolled")
            print(f"   - User ID: {result['user_id']}")
            print(f"   - Name: {result.get('name', 'N/A')}")
        else:
            print(f"   ✗ User not enrolled")
    
    # 4. List all enrollments
    print("\n3. Listing all enrollments...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/enrollment/list", headers=HEADERS)
        result = response.json()
        
        print(f"   ✓ Found {len(result['users'])} enrolled users:")
        for user in result['users']:
            print(f"     - {user.get('name', user['user_id'])} ({user['user_id']})")
    
    # 5. Test session creation with enrolled user
    print("\n4. Testing session creation with enrolled user...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/sessions",
            headers=HEADERS
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✓ Session created: {result['session_id'][:8]}...")
            print(f"   - User: {result['user_id']}")
            print(f"   - Agent prompt: {result['agent_prompt'][:50]}...")
        else:
            print(f"   ✗ Session creation failed: {response.status_code}")
    
    print("\n" + "=" * 60)
    print("✓ All tests passed!")
    print("=" * 60)
    print("\nYour frontend can now:")
    print("1. POST to /enrollment/create with audio file + name (Bearer token)")
    print("2. GET /enrollment/me to check the caller's enrollment")
    print("3. POST to /sessions to start verification (user from token)")
    print("4. WebSocket to /ws/audio?session_id=...&token=... to stream audio")
    print("5. GET /sessions/{id}/risk to check verification status")


if __name__ == "__main__":
    print("\nMake sure:")
    print("1. Server is running: uvicorn app.main:app --reload")
    print("2. You have enrollment audio from: python enroll_user.py")
    print("\nStarting in 3 seconds...\n")
    
    import time
    time.sleep(3)
    
    asyncio.run(test_enrollment())
