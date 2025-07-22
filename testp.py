import asyncio
from playwright.async_api import async_playwright
from datetime import datetime
import os

async def save_html_content(url, output_dir="html_output"):
    """
    访问指定URL，等待页面加载完成，提取HTML内容并保存到本地
    
    Args:
        url: 要访问的网页URL
        output_dir: 保存HTML文件的目录
    """
    # 创建输出目录（如果不存在）
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 生成文件名（基于URL和当前时间）
    file_name = f"stock_page_{url.split('/')[-2]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    file_path = os.path.join(output_dir, file_name)
    
    async with async_playwright() as p:
        # 启动浏览器
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # 设置超时时间（30秒）
        page.set_default_timeout(30000)
        
        try:
            print(f"正在访问 {url}...")
            # 访问目标页面
            await page.goto(url)
            
            # 等待页面加载完成
            await page.wait_for_load_state('networkidle')
            print("页面加载完成")
            
            # 提取HTML内容
            html_content = await page.content()
            
            # 保存HTML到本地文件
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            print(f"HTML内容已保存到: {file_path}")
            
        except Exception as e:
            print(f"发生错误: {e}")
        
        finally:
            # 关闭浏览器
            await browser.close()

async def main():
    """
    主函数：访问同花顺港股页面并保存HTML内容
    """
    url = "https://stockpage.10jqka.com.cn/HK2018/"
    await save_html_content(url)

if __name__ == "__main__":
    asyncio.run(main())