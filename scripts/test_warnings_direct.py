#!/usr/bin/env python3
"""
Test script for warnings_module without authentication.
Usage: python scripts/test_warnings_direct.py <user_id> [--send-mail]
"""

import sys
import os
import asyncio
import argparse
import importlib

# Add parent directory to path so we can import from app/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import get_settings

# Importar y recargar el módulo para evitar cachés
import scripts.warnings_module
importlib.reload(scripts.warnings_module)
from scripts.warnings_module import warnings


async def test_warnings(user_id: str, send_mail: bool = False):
    """Test warnings function for a given user_id."""
    
    settings = get_settings()
    print(f"   Database FULL: {settings.database_url}")
    
    # Create engine
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        future=True,
    )
    
    # Create session factory
    async_session = async_sessionmaker(
        engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    
    try:
        async with async_session() as db:
            print(f"\n🔍 Testing warnings for user_id: {user_id}")
            print(f"   send_mail: {send_mail}")
            print(f"   Database: {settings.database_url[:50]}...")
            print("-" * 80)
            
            result = await warnings(db, user_id, send_mail=send_mail)
            
            print(f"\n✅ Found {len(result)} warnings:")
            print("-" * 80)
            
            for idx, w in enumerate(result, 1):
                try:
                    w_type, threshold, trigger_val, msg = w
                except Exception:
                    print(idx, w)
                    continue
                print(f"\n{idx}. Type: {w_type}")
                print(f"   Threshold: {threshold}")
                print(f"   Trigger Value: {trigger_val}")
                print(f"   Message: {msg}")
            
            if not result:
                print("No warnings found for this user.")
            
            print("\n" + "=" * 80)
            
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(
        description="Test warnings_module directly"
    )
    parser.add_argument(
        "user_id",
        help="User ID (clerk_id) to test"
    )
    parser.add_argument(
        "--send-mail",
        action="store_true",
        help="Send mail notifications (default: False)"
    )
    
    args = parser.parse_args()
    
    asyncio.run(test_warnings(args.user_id, send_mail=args.send_mail))


if __name__ == "__main__":
    main()
