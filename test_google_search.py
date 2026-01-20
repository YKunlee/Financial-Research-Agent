"""测试 Google Custom Search API 是否正常工作"""
import os
import requests
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

def test_google_search():
    """测试搜索龙旗科技 IPO 信息"""
    api_key = os.getenv("GOOGLE_API_KEY")
    cse_id = os.getenv("GOOGLE_CSE_ID")
    
    print("=" * 50)
    print("Google Custom Search API 测试")
    print("=" * 50)
    
    # 检查配置
    print(f"\n1. 检查配置:")
    print(f"   GOOGLE_API_KEY: {'✅ 已配置' if api_key else '❌ 未配置'}")
    print(f"   GOOGLE_CSE_ID:  {'✅ 已配置' if cse_id else '❌ 未配置'}")
    
    if not api_key or not cse_id:
        print("\n❌ 缺少必要配置，请在 .env 文件中填写 GOOGLE_API_KEY 和 GOOGLE_CSE_ID")
        return False
    
    # 执行搜索
    query = "龙旗科技 IPO 招股 上市"
    print(f"\n2. 搜索关键词: {query}")
    
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cse_id,
        "q": query,
        "num": 5,
    }
    
    print(f"\n3. 发送请求到 Google API...")
    try:
        resp = requests.get(url, params=params, timeout=30)
        print(f"   HTTP 状态码: {resp.status_code}")
        
        if resp.status_code != 200:
            print(f"\n❌ API 请求失败:")
            print(f"   {resp.text}")
            return False
        
        payload = resp.json()
        
        # 检查是否有错误
        if "error" in payload:
            print(f"\n❌ API 返回错误:")
            print(f"   {payload['error'].get('message', payload['error'])}")
            return False
        
        items = payload.get("items") or []
        print(f"\n4. 搜索结果: 共 {len(items)} 条")
        
        if not items:
            print("\n⚠️ 未找到搜索结果，可能是关键词问题或 CSE 配置问题")
            print("   请确认 CSE 已设置为「搜索整个網路」")
            return False
        
        print("\n" + "=" * 50)
        print("搜索结果详情:")
        print("=" * 50)
        
        for i, item in enumerate(items, 1):
            title = item.get("title", "无标题")
            link = item.get("link", "")
            snippet = item.get("snippet", "无摘要")
            
            print(f"\n【结果 {i}】")
            print(f"标题: {title}")
            print(f"链接: {link}")
            print(f"摘要: {snippet[:200]}{'...' if len(snippet) > 200 else ''}")
        
        print("\n" + "=" * 50)
        print("✅ Google Search API 测试通过！")
        print("=" * 50)
        return True
        
    except requests.exceptions.Timeout:
        print("\n❌ 请求超时，请检查网络连接或代理设置")
        return False
    except requests.exceptions.RequestException as e:
        print(f"\n❌ 网络请求失败: {e}")
        return False
    except Exception as e:
        print(f"\n❌ 未知错误: {e}")
        return False


if __name__ == "__main__":
    test_google_search()
