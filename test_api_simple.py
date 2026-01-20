"""使用 OpenAI 官方库测试 API Key"""
from dotenv import load_dotenv
import os

# 加载环境变量
load_dotenv()

def test_openai_key():
    api_key = os.getenv("OPENAI_API_KEY")
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    
    print(f"🔑 API Key: {api_key[:20]}...{api_key[-10:] if api_key else 'None'}")
    print(f"🤖 Model: {model_name}")
    print("\n" + "="*50)
    print("📡 正在测试 API 连接（使用官方库）...")
    print("="*50 + "\n")
    
    try:
        from openai import OpenAI
        
        client = OpenAI(
            api_key=api_key,
            timeout=60.0,
            max_retries=2
        )
        
        # 发送一个最简单的测试请求
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "user", "content": "Say 'Test OK'"}
            ],
            max_tokens=10,
            temperature=0
        )
        
        print("✅ API Key 测试成功!")
        print(f"📝 响应内容: {response.choices[0].message.content}")
        print(f"💰 使用的模型: {model_name} (花费最小)")
        print(f"📊 Token 使用: {response.usage.total_tokens} tokens")
        
        return True
        
    except Exception as e:
        print(f"❌ API Key 测试失败!")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误信息: {str(e)}")
        
        # 检查是否是网络问题
        if "timeout" in str(e).lower() or "timed out" in str(e).lower():
            print("\n⚠️  提示: 这看起来是网络连接问题，不是 API Key 问题")
            print("   请检查:")
            print("   1. 网络连接是否正常")
            print("   2. 是否需要代理访问 OpenAI API")
            print("   3. 防火墙是否阻止了连接")
        
        return False

if __name__ == "__main__":
    success = test_openai_key()
    exit(0 if success else 1)
