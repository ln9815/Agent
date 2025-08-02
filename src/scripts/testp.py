import requests
import time

def get_cookie(url):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(url)
        time.sleep(5)
        page.goto('https://q.10jqka.com.cn/api.php?t=indexflash&')
        cookies = page.context.cookies()
        # print(cookies)
        return {cookie['name']: cookie['value'] for cookie in cookies}

url = 'https://q.10jqka.com.cn/api.php?t=indexflash&'

headers = {
    # 'accept': '*/*',
    # 'accept-language': 'zh-CN,zh;q=0.9',
    # 'cache-control': 'no-cache',
    # 'pragma': 'no-cache',
    # 'priority': 'u=1, i',
    # 'referer': 'https://q.10jqka.com.cn/',
    # 'sec-ch-ua': '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
    # 'sec-ch-ua-mobile': '?0',
    # 'sec-ch-ua-platform': '"macOS"',
    # 'sec-fetch-dest': 'empty',
    # 'sec-fetch-mode': 'cors',
    # 'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
}

cookies = {
    # 'log': '',
    # 'Hm_lvt_722143063e4892925903024537075d0d': '1753110698,1753200952,1753202442,1753708156',
    # 'Hm_lpvt_722143063e4892925903024537075d0d': '1753711757',
    # 'Hm_lvt_929f8b362150b1f77b477230541dbbc2': '1753110698,1753200952,1753202442,1753708156',
    # 'Hm_lpvt_929f8b362150b1f77b477230541dbbc2': '1753711757',
    # 'Hm_lvt_78c58f01938e4d85eaf619eae71b4ed1': '1753358497,1753451289,1753572280,1753606308',
    # 'Hm_lpvt_78c58f01938e4d85eaf619eae71b4ed1': '1753711757',
    'v': 'A3Oyyc3CH5JscdPG9Yw0Z6h9BHyYqAdqwTxLniUQzxLJJJ1yrXiXutEM2-g2'
}
cookies = get_cookie('https://q.10jqka.com.cn')
del cookies['uid']
print(cookies)
try:
    response = requests.get(url, headers=headers, cookies=cookies)
    response.raise_for_status()  # 检查请求是否成功
    print("请求成功")
    print("响应内容：")
    print(response.text)
except requests.exceptions.HTTPError as http_err:
    print(f"HTTP错误: {http_err}")
except requests.exceptions.RequestException as req_err:
    print(f"请求异常: {req_err}")






# print(get_cookie())

import requests

url = 'https://q.10jqka.com.cn/api.php?t=indexflash&'

headers = {
    # 'accept': '*/*',
    # 'accept-language': 'zh-CN,zh;q=0.9',
    # 'cache-control': 'no-cache',
    # 'pragma': 'no-cache',
    # 'priority': 'u=1, i',
    # 'referer': 'https://q.10jqka.com.cn/',
    # 'sec-ch-ua': '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
    # 'sec-ch-ua-mobile': '?0',
    # 'sec-ch-ua-platform': '"macOS"',
    # 'sec-fetch-dest': 'empty',
    # 'sec-fetch-mode': 'cors',
    # 'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
}

cookies = {
    # 'Hm_lvt_722143063e4892925903024537075d0d': '1753110698,1753200952,1753202442,1753708156',
    # 'Hm_lvt_929f8b362150b1f77b477230541dbbc2': '1753110698,1753200952,1753202442,1753708156',
    # 'Hm_lvt_78c58f01938e4d85eaf619eae71b4ed1': '1753358497,1753451289,1753572280,1753606308',
    # 'spversion': '20130314',
    # 'searchGuide': 'sg',
    # 'Hm_lpvt_722143063e4892925903024537075d0d': '1753742998',
    # 'Hm_lpvt_929f8b362150b1f77b477230541dbbc2': '1753742998',
    # 'historystock': 'HK2018%7C*%7C300528%7C*%7C301377',
    # 'Hm_lpvt_78c58f01938e4d85eaf619eae71b4ed1': '1753797705',
    'v': 'A1puJLjz5t1hV2pxdpC9ePlurQt5i95lUA9SCWTTBu241_SlTBsudSCfoh83'
}

response = requests.get(url, headers=headers, cookies=cookies)

if response.status_code == 200:
    print("请求成功")
    print(response.text)
else:
    print(f"请求失败，状态码: {response.status_code}")
    print(response.text)