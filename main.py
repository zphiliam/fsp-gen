import re
import sys
import requests
import os

# 默认URL地址
DEFAULT_URL = "https://raw.githubusercontent.com/felixonmars/dnsmasq-china-list/master/accelerated-domains.china.conf"
# 输出目录
OUTPUT_DIR = "dist"
# 默认输出文件
DEFAULT_OUTPUT = os.path.join(OUTPUT_DIR, "whitelist.hostrules")
# 预定义白名单文件
PREWHITE_FILE = "prewhite.hostrules"
# 分隔注释
SEPARATOR_COMMENT = "# -------autogen------"

def extract_domains_from_url(url, output_file):
    """
    从URL下载内容，提取域名并以特定格式保存到输出文件
    输入格式: server=/domain.com/114.114.114.114
    输出格式: .domain.com
    """
    domains = []
    
    # 从URL获取内容
    try:
        print(f"正在从 {url} 获取域名列表...")
        response = requests.get(url)
        response.raise_for_status()  # 如果请求失败则抛出异常
        content = response.text
    except requests.exceptions.RequestException as e:
        print(f"获取URL内容时出错：{e}")
        return False
    
    # 处理内容
    for line in content.splitlines():
        # 使用正则表达式提取域名
        match = re.search(r'server=/([^/]+)/', line)
        if match:
            domain = match.group(1)
            domains.append(f".{domain}")
    
    if not domains:
        print("警告：未找到任何域名")
        return False
    
    # 添加预定义白名单域名并保存
    return save_domains_with_prewhite(domains, output_file)

def extract_domains_from_file(input_file, output_file):
    """
    从本地文件中提取域名并以特定格式保存到输出文件
    输入格式: server=/domain.com/114.114.114.114
    输出格式: .domain.com
    """
    domains = []
    
    # 读取输入文件
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            for line in f:
                # 使用正则表达式提取域名
                match = re.search(r'server=/([^/]+)/', line)
                if match:
                    domain = match.group(1)
                    domains.append(f".{domain}")
    except FileNotFoundError:
        print(f"错误：找不到输入文件 '{input_file}'")
        return False
    
    # 添加预定义白名单域名并保存
    return save_domains_with_prewhite(domains, output_file)

def save_domains_with_prewhite(domains, output_file):
    """
    将域名列表保存到输出文件，并在开头添加预定义白名单的内容（如果存在）
    如果域名已经存在于预定义白名单中，则不会重复添加
    在预定义白名单和自动生成的域名之间添加分隔注释
    """
    all_domains = []
    prewhite_domains_set = set()
    
    # 检查是否存在预定义白名单文件
    if os.path.isfile(PREWHITE_FILE):
        try:
            with open(PREWHITE_FILE, 'r', encoding='utf-8') as f:
                prewhite_domains = [line.strip() for line in f if line.strip()]
                if prewhite_domains:
                    print(f"找到预定义白名单文件 '{PREWHITE_FILE}'，包含 {len(prewhite_domains)} 个域名")
                    all_domains.extend(prewhite_domains)
                    # 创建一个集合，用于快速查找域名是否已存在于预定义白名单中
                    prewhite_domains_set = set(prewhite_domains)
                else:
                    print(f"预定义白名单文件 '{PREWHITE_FILE}' 存在但为空")
        except Exception as e:
            print(f"读取预定义白名单文件时出错：{e}")
    else:
        print(f"未找到预定义白名单文件 '{PREWHITE_FILE}'")
    
    # 始终添加分隔注释，无论是否有预定义白名单
    all_domains.append(SEPARATOR_COMMENT)
    
    # 添加从源获取的域名（排除已在预定义白名单中的域名）
    filtered_domains = [domain for domain in domains if domain not in prewhite_domains_set]
    all_domains.extend(filtered_domains)
    
    # 报告过滤掉的重复域名数量
    filtered_count = len(domains) - len(filtered_domains)
    if filtered_count > 0:
        print(f"已过滤掉 {filtered_count} 个已存在于预定义白名单中的重复域名")
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # 保存到输出文件
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            for domain in all_domains:
                f.write(f"{domain}\n")
        print(f"成功将总共 {len(all_domains)} 个域名保存到 '{output_file}'")
        if len(prewhite_domains_set) > 0:
            print(f"  其中包含 {len(prewhite_domains_set)} 个预定义白名单域名")
        print(f"  已在自动生成的内容前面添加分隔注释：'{SEPARATOR_COMMENT}'")
        return True
    except Exception as e:
        print(f"保存文件时出错：{e}")
        return False

if __name__ == "__main__":
    # 处理命令行参数
    if len(sys.argv) == 1:
        # 没有参数时使用默认值
        print(f"未提供参数，使用默认URL: {DEFAULT_URL}")
        print(f"默认输出文件: {DEFAULT_OUTPUT}")
        extract_domains_from_url(DEFAULT_URL, DEFAULT_OUTPUT)
    elif len(sys.argv) == 2:
        # 只有一个参数时，假定为输出文件，使用默认URL
        output_file = sys.argv[1]
        # 如果只提供了文件名而没有路径，添加到默认输出目录
        if not os.path.dirname(output_file):
            output_file = os.path.join(OUTPUT_DIR, output_file)
        print(f"使用默认URL: {DEFAULT_URL}")
        print(f"输出文件: {output_file}")
        extract_domains_from_url(DEFAULT_URL, output_file)
    elif sys.argv[1] == "--url" and len(sys.argv) >= 3:
        # 使用--url参数
        url = sys.argv[2]
        output_file = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_OUTPUT
        # 如果只提供了文件名而没有路径，添加到默认输出目录
        if len(sys.argv) > 3 and not os.path.dirname(output_file):
            output_file = os.path.join(OUTPUT_DIR, output_file)
        print(f"使用URL: {url}")
        print(f"输出文件: {output_file}")
        extract_domains_from_url(url, output_file)
    elif sys.argv[1] == "--file" and len(sys.argv) >= 3:
        # 使用--file参数从本地文件读取
        input_file = sys.argv[2]
        output_file = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_OUTPUT
        # 如果只提供了文件名而没有路径，添加到默认输出目录
        if len(sys.argv) > 3 and not os.path.dirname(output_file):
            output_file = os.path.join(OUTPUT_DIR, output_file)
        print(f"从本地文件读取: {input_file}")
        print(f"输出文件: {output_file}")
        extract_domains_from_file(input_file, output_file)
    else:
        # 其他情况显示帮助信息
        print("使用方法：")
        print("1. 无参数: 使用默认URL和输出文件")
        print("   示例: python main.py")
        print("2. 指定输出文件: python main.py <输出文件>")
        print("   示例: python main.py my_whitelist.hostrules")
        print("3. 指定URL: python main.py --url <URL> [输出文件]")
        print("   示例: python main.py --url https://example.com/domains.txt whitelist.hostrules")
        print("4. 从本地文件: python main.py --file <输入文件> [输出文件]")
        print("   示例: python main.py --file input.txt whitelist.hostrules")
        print(f"默认URL: {DEFAULT_URL}")
        print(f"默认输出目录: {OUTPUT_DIR}")
        print(f"默认输出文件: {DEFAULT_OUTPUT}")
        print(f"预定义白名单文件: {PREWHITE_FILE} (如果存在会自动合并且优先放在前面)")
        sys.exit(1)
