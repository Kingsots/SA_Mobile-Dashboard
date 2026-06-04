#!/usr/bin/env python3
"""
Simple .env File Checker
Run this to diagnose .env file issues
"""

import os
from pathlib import Path

def check_env_file():
    """Check the .env file thoroughly."""
    print("🔍 .env File Diagnostic Tool")
    print("=" * 40)
    
    # Check current directory
    current_dir = Path.cwd()
    env_path = current_dir / '.env'
    
    print(f"📂 Current directory: {current_dir}")
    print(f"🔍 Looking for .env at: {env_path}")
    
    # Check if file exists
    if not env_path.exists():
        print("❌ .env file not found!")
        
        # List all files to help debug
        print("\n📁 Files in current directory:")
        try:
            for item in sorted(current_dir.iterdir()):
                if item.is_file():
                    print(f"  📄 {item.name}")
        except Exception as e:
            print(f"  ❌ Error listing files: {e}")
        
        print(f"\n💡 Create a .env file with this content:")
        print("TELEGRAM_BOT_TOKEN=8394171370:AAHAU_ww4jjMcjFt_Du6cjg8hfmxtprZ21w")
        print("TELEGRAM_CHAT_ID=1349131996")
        return False
    
    print("✅ .env file found!")
    
    # Check file properties
    try:
        stat = env_path.stat()
        print(f"📏 File size: {stat.st_size} bytes")
        
        if stat.st_size == 0:
            print("❌ File is empty!")
            return False
            
    except Exception as e:
        print(f"❌ Error checking file: {e}")
        return False
    
    # Read and analyze content
    try:
        print(f"\n📄 Reading file content...")
        
        # Read as binary first to check for encoding issues
        with open(env_path, 'rb') as f:
            raw_bytes = f.read()
        
        print(f"📊 Raw bytes: {len(raw_bytes)} bytes")
        print(f"🔤 First 100 bytes: {raw_bytes[:100]}")
        
        # Try to decode as UTF-8
        try:
            content = raw_bytes.decode('utf-8')
            print(f"✅ Successfully decoded as UTF-8")
        except UnicodeDecodeError as e:
            print(f"❌ UTF-8 decode error: {e}")
            # Try other encodings
            for encoding in ['latin1', 'cp1252', 'utf-16']:
                try:
                    content = raw_bytes.decode(encoding)
                    print(f"✅ Successfully decoded as {encoding}")
                    break
                except:
                    continue
            else:
                print(f"❌ Cannot decode file content")
                return False
        
        # Display content
        print(f"\n📝 File content:")
        print("=" * 30)
        print(repr(content))  # Show exact content including whitespace
        print("=" * 30)
        print(content)  # Show formatted content
        print("=" * 30)
        
        # Analyze lines
        lines = content.splitlines()
        print(f"\n📋 Line analysis ({len(lines)} lines):")
        
        found_token = False
        found_chat_id = False
        
        for i, line in enumerate(lines, 1):
            print(f"Line {i}: {repr(line)}")
            
            line_clean = line.strip()
            if line_clean and not line_clean.startswith('#'):
                if '=' in line_clean:
                    key, value = line_clean.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    print(f"  → Key: '{key}', Value: '{value[:20]}...' ({len(value)} chars)")
                    
                    if key == 'TELEGRAM_BOT_TOKEN':
                        found_token = True
                        if not value:
                            print(f"    ❌ Token is empty!")
                        elif len(value) < 40:
                            print(f"    ⚠️  Token seems too short")
                        else:
                            print(f"    ✅ Token looks valid")
                    
                    elif key == 'TELEGRAM_CHAT_ID':
                        found_chat_id = True
                        if not value:
                            print(f"    ❌ Chat ID is empty!")
                        elif not value.isdigit():
                            print(f"    ⚠️  Chat ID should be numeric")
                        else:
                            print(f"    ✅ Chat ID looks valid")
                else:
                    print(f"  ⚠️  No '=' found in line")
            else:
                print(f"  ⏭️  Skipping (empty or comment)")
        
        # Summary
        print(f"\n🎯 Summary:")
        print(f"✅ TELEGRAM_BOT_TOKEN found: {found_token}")
        print(f"✅ TELEGRAM_CHAT_ID found: {found_chat_id}")
        
        if not found_token:
            print(f"❌ Missing TELEGRAM_BOT_TOKEN!")
        if not found_chat_id:
            print(f"❌ Missing TELEGRAM_CHAT_ID!")
        
        if found_token and found_chat_id:
            print(f"\n🎉 .env file looks good!")
            
            # Test loading into environment
            print(f"\n🧪 Testing environment loading...")
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    os.environ[key] = value
                    print(f"  Set {key} = {value[:10]}...")
            
            # Verify
            token = os.getenv('TELEGRAM_BOT_TOKEN')
            chat_id = os.getenv('TELEGRAM_CHAT_ID')
            
            print(f"✅ Final check:")
            print(f"  TELEGRAM_BOT_TOKEN: {'✅ Found' if token else '❌ Missing'}")
            print(f"  TELEGRAM_CHAT_ID: {'✅ Found' if chat_id else '❌ Missing'}")
            
            return bool(token and chat_id)
        else:
            print(f"\n❌ .env file has missing variables!")
            return False
        
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_sample_env():
    """Create a sample .env file."""
    env_content = """TELEGRAM_BOT_TOKEN=8394171370:AAHAU_ww4jjMcjFt_Du6cjg8hfmxtprZ21w
TELEGRAM_CHAT_ID=1349131996"""
    
    env_path = Path('.env')
    
    try:
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(env_content)
        
        print(f"✅ Created sample .env file at: {env_path.absolute()}")
        print(f"📄 Content:")
        print(env_content)
        return True
        
    except Exception as e:
        print(f"❌ Error creating .env file: {e}")
        return False

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'create':
        create_sample_env()
    else:
        success = check_env_file()
        
        if not success:
            print(f"\n💡 To create a sample .env file, run:")
            print(f"python env_checker.py create")