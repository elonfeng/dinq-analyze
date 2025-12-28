# coding: utf-8
"""
@author: Sam
@date: 2025-03-18
@description: 使用AMiner API搜索缩写的相关研究员信息(B. Zhang).
"""
import os
import time
import requests

def search_person(name, org=None, offset=0, size=10):
    """
    通过AMiner API搜索研究人员
    
    Args:
        name (str): 研究人员姓名
        org (str, optional): 机构名称
        offset (int): 分页起始位置
        size (int): 返回结果数量
        
    Returns:
        dict: API返回的结果
    """
    url = "https://datacenter.aminer.cn/gateway/open_platform/api/person/search"
    
    headers = {
        "Content-Type": "application/json;charset=utf-8",
        "Authorization": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NTc4NDc3MDIsInRpbWVzdGFtcCI6MTc0MjI5NTcwMiwidXNlcl9pZCI6IjY3NWU4ZTc2NWI4OGY2M2VkOWJmMDIzZSJ9.j3L47ZKrjS-xmRJy6eoV1kFS2DmCag5XEDDtqBa7hMo"  # 替换为你的实际token
    }
    
    payload = {
        "name": name,
        "offset": offset,
        "size": size
    }
    
    if org:
        payload["org"] = org
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()  # 检查请求是否成功
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        return None

def get_person_detail(person_id):
    """
    通过AMiner API获取研究人员详细信息
    
    Args:
        person_id (str): 研究人员的AMiner ID
        
    Returns:
        dict: API返回的研究人员详细信息
    """
    url = f"https://datacenter.aminer.cn/gateway/open_platform/api/person/detail"
    
    headers = {
        "Authorization": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NTc4NDc3MDIsInRpbWVzdGFtcCI6MTc0MjI5NTcwMiwidXNlcl9pZCI6IjY3NWU4ZTc2NWI4OGY2M2VkOWJmMDIzZSJ9.j3L47ZKrjS-xmRJy6eoV1kFS2DmCag5XEDDtqBa7hMo"  # 替换为你的实际token
    }
    
    params = {
        "id": person_id
    }
    
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()  # 检查请求是否成功
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"获取详细信息失败: {e}")
        return None


def search_paper(name, org=None, offset=0, size=10):
    """
    通过AMiner API获取论文对应的作者信息
    
    Args:
        name (str): 学术论文全称
        
    Returns:
        dict: API返回的研究人员详细信息
    """
    url = f"https://datacenter.aminer.cn/gateway/open_platform/api/paper/info"
    
    headers = {
        "Authorization": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NTc4NDc3MDIsInRpbWVzdGFtcCI6MTc0MjI5NTcwMiwidXNlcl9pZCI6IjY3NWU4ZTc2NWI4OGY2M2VkOWJmMDIzZSJ9.j3L47ZKrjS-xmRJy6eoV1kFS2DmCag5XEDDtqBa7hMo"  # 替换为你的实际token
    }
    
    params = {
        "ids": [name]
    }
    
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()  # 检查请求是否成功
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"获取详细信息失败: {e}")
        return None

# 使用示例
if __name__ == "__main__":
    # 无法解决缩写问题, 且没有相关学者信息.
    # result = search_person("Bang Zhang", org="Alibaba")
    # print(result)
    # author_id = get_person_detail(result["data"][0]["id"])
    # print(author_id)

    result = search_paper("Multi-view consistent generative adversarial networks for 3d-aware image synthesis")
    