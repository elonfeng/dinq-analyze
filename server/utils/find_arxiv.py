# coding: utf-8
"""
    @date: 2025-03-22
    @author: Sam Gao
    @description: 根据论文全称, 查找其Arxiv链接.
    @update: 更新API_KEY, 挂上支付, 没限额了. 0.008美金一次.
"""
import os
import random
import json
import time
import requests

# Import API keys from centralized configuration
from server.config.api_keys import API_KEYS

# Tavily API configuration
tavily_api_key = API_KEYS['TAVILY_API_KEY']

def find_arxiv(paper_name):
    query = "Please gave me url link and icon with paper title: {}".format(paper_name)

    url = "https://api.tavily.com/search"
    headers = {
        "Authorization": f"Bearer {tavily_api_key}",
        "Content-Type": "application/json"
    }

    print(f"搜索查询: {query}")
    payload = {
        "query": query,
        "topic": "general",
        "search_depth": "basic",
        "max_results": 1,
        "include_answer": True,
        "include_images": True,
    }

    response = requests.request("POST", url, json=payload, headers=headers)
    response.raise_for_status()
    data = response.json()

    output_data = {"name": paper_name,
                   "arxiv_url": data['results'][0]['url'],
                   "image": data['images'][random.randint(0, len(data['images']) - 1)],
                #    "content": data['results'][0]['content'],
                   }

    return output_data


if __name__ == "__main__":
    paper_name = "PyTorch: An Imperative Style, High-Performance Deep Learning Library"
    t1 = time.time()
    output_data = find_arxiv(paper_name)
    t2 = time.time()
    print(output_data)
    print(f"耗时: {t2 - t1} 秒")

