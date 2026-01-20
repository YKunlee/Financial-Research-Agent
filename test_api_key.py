"""测试 OpenAI API Key 是否有效"""
from dotenv import load_dotenv
import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

# 加载环境变量
load_dotenv()

def test_openai_key():
    api_key = os.getenv("OPENAI_API_KEY")
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    
    print(f"🔑 API Key: {api_key[:20]}...{api_key[-10:] if api_key else 'None'}")
    print(f"🤖 Model: {model_name}")
    print("\n" + "="*50)
    print("📡 正在测试 API 连接...")
    print("="*50 + "\n")
    
    try:
        # 创建最小花费的模型实例
        llm = ChatOpenAI(
            api_key=api_key,
            model=model_name,
            temperature=0,
            max_tokens=50,  # 限制最大 token 以减少花费
            timeout=60,  # 增加超时时间到60秒
            max_retries=2  # 允许重试2次
        )
        
        # 发送一个简单的测试消息
        message = HumanMessage(content="Hello, reply with 'API Key is working!'")
        response = llm.invoke([message])
        
        print("✅ API Key 测试成功!")
        print(f"📝 响应内容: {response.content}")
        print(f"\n💰 使用的模型: {model_name} (花费最小)")
        
        return True
        
    except Exception as e:
        print(f"❌ API Key 测试失败!")
        print(f"错误信息: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_openai_key()
    exit(0 if success else 1)
