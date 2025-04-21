import re
import sys
import requests
import os
from typing import List, Set, Tuple, Optional
from collections import Counter

# 配置常量
DEFAULT_URL = "https://raw.githubusercontent.com/felixonmars/dnsmasq-china-list/master/accelerated-domains.china.conf"
OUTPUT_DIR = "dist"
DEFAULT_OUTPUT = os.path.join(OUTPUT_DIR, "whitelist.hostrules")
PREWHITE_FILE = "prewhite.hostrules"
PREBLACK_FILE = "preblack.hostrules"
SEPARATOR_COMMENT = "# -------autogen------"
BLACKLIST_COMMENT_PREFIX = "# blocked "


def is_blacklisted(domain: str, blacklist: List[str]) -> Optional[str]:
    """
    检查一个域名是否在黑名单中，或是黑名单中某个域名的子域名
    
    Args:
        domain: 要检查的域名
        blacklist: 黑名单域名列表
    
    Returns:
        匹配的黑名单域名，如果不匹配则返回None
    """
    if not domain.startswith('.'):
        domain = '.' + domain
    
    for black_domain in blacklist:
        black = black_domain.strip()
        if not black or black.startswith('#'):  # 跳过空行和注释
            continue
            
        if not black.startswith('.'):
            black = '.' + black
            
        # 检查domain是否是black或其子域名
        if domain == black or domain.endswith(black):
            return black
    
    return None

def load_blacklist() -> List[str]:
    """
    加载黑名单文件内容
    
    Returns:
        黑名单域名列表
    """
    blacklist = []
    
    if os.path.isfile(PREBLACK_FILE):
        try:
            with open(PREBLACK_FILE, 'r', encoding='utf-8') as f:
                blacklist = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
                if blacklist:
                    print(f"找到预定义黑名单文件 '{PREBLACK_FILE}'，包含 {len(blacklist)} 个需要排除的域名")
        except Exception as e:
            print(f"读取预定义黑名单文件时出错：{e}")
    else:
        print(f"未找到预定义黑名单文件 '{PREBLACK_FILE}'")
    
    return blacklist

def process_domain(domain: str, blacklist: List[str]) -> Tuple[str, bool]:
    """
    处理单个域名，检查是否在黑名单中并格式化
    
    Args:
        domain: 原始域名
        blacklist: 黑名单域名列表
    
    Returns:
        (格式化后的域名, 是否被加入黑名单)
    """
    domain_with_dot = f".{domain}"
    
    # 检查是否在黑名单中
    if blacklist:
        matched_blacklist = is_blacklisted(domain, blacklist)
        if matched_blacklist:
            # 将域名添加为注释
            return f"{BLACKLIST_COMMENT_PREFIX}{domain_with_dot}", True
    
    # 不在黑名单中，正常添加
    return domain_with_dot, False

def extract_domains_from_url(url: str, output_file: str) -> bool:
    """
    从URL下载内容，提取域名并以特定格式保存到输出文件
    
    Args:
        url: 源URL
        output_file: 输出文件路径
    
    Returns:
        是否成功
    """
    processed_domains = []
    blacklisted_count = 0
    blacklist = load_blacklist()
    
    # 从URL获取内容
    try:
        print(f"正在从 {url} 获取域名列表...")
        response = requests.get(url, timeout=30)
        response.raise_for_status()  # 如果请求失败则抛出异常
        content = response.text
    except requests.exceptions.RequestException as e:
        print(f"获取URL内容时出错：{e}")
        return False
    
    # 使用正则表达式提取所有域名
    domain_pattern = re.compile(r'server=/([^/]+)/')
    matches = domain_pattern.findall(content)
    
    if not matches:
        print("警告：未找到任何域名")
        return False
    
    # 处理所有匹配的域名
    for domain in matches:
        processed_domain, is_blacklisted = process_domain(domain, blacklist)
        processed_domains.append(processed_domain)
        if is_blacklisted:
            blacklisted_count += 1
    
    if blacklisted_count > 0:
        print(f"已将 {blacklisted_count} 个在黑名单中的域名或其子域名标记为注释")
    
    # 添加预定义白名单域名并保存
    return save_domains_with_prewhite(processed_domains, output_file)

def extract_domains_from_file(input_file: str, output_file: str) -> bool:
    """
    从本地文件中提取域名并以特定格式保存到输出文件
    
    Args:
        input_file: 输入文件路径
        output_file: 输出文件路径
    
    Returns:
        是否成功
    """
    processed_domains = []
    blacklisted_count = 0
    blacklist = load_blacklist()
    
    # 读取输入文件
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 使用正则表达式提取所有域名
        domain_pattern = re.compile(r'server=/([^/]+)/')
        matches = domain_pattern.findall(content)
        
        if not matches:
            print("警告：未在输入文件中找到任何域名")
            return False
            
        # 处理所有匹配的域名
        for domain in matches:
            processed_domain, is_blacklisted = process_domain(domain, blacklist)
            processed_domains.append(processed_domain)
            if is_blacklisted:
                blacklisted_count += 1
                
    except FileNotFoundError:
        print(f"错误：找不到输入文件 '{input_file}'")
        return False
    except Exception as e:
        print(f"读取文件时出错：{e}")
        return False
    
    if blacklisted_count > 0:
        print(f"已将 {blacklisted_count} 个在黑名单中的域名或其子域名标记为注释")
    
    # 添加预定义白名单域名并保存
    return save_domains_with_prewhite(processed_domains, output_file)

def save_domains_with_prewhite(domains: List[str], output_file: str) -> bool:
    """
    将域名列表保存到输出文件，并在开头添加预定义白名单的内容
    
    Args:
        domains: 处理后的域名列表
        output_file: 输出文件路径
    
    Returns:
        是否成功
    """
    all_domains = []
    prewhite_domains_set: Set[str] = set()
    blacklist = load_blacklist()
    
    # 检查是否存在预定义白名单文件
    if os.path.isfile(PREWHITE_FILE):
        try:
            with open(PREWHITE_FILE, 'r', encoding='utf-8') as f:
                prewhite_domains = []
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):  # 跳过空行和注释
                        prewhite_domains.append(line)
                        continue
                    
                    # 检查白名单域名是否在黑名单中
                    if blacklist:
                        matched_blacklist = is_blacklisted(line, blacklist)
                        if matched_blacklist:
                            # 将域名添加为注释
                            prewhite_domains.append(f"{BLACKLIST_COMMENT_PREFIX}{line}")
                            print(f"警告：白名单中的域名 '{line}' 在黑名单中或是黑名单中域名的子域名，已标记为注释")
                            continue
                    
                    prewhite_domains.append(line)
                    if line and not line.startswith('#'):
                        prewhite_domains_set.add(line)
                
                if prewhite_domains:
                    print(f"找到预定义白名单文件 '{PREWHITE_FILE}'，包含 {len(prewhite_domains)} 个域名")
                    all_domains.extend(prewhite_domains)
                else:
                    print(f"预定义白名单文件 '{PREWHITE_FILE}' 存在但为空")
        except Exception as e:
            print(f"读取预定义白名单文件时出错：{e}")
    else:
        print(f"未找到预定义白名单文件 '{PREWHITE_FILE}'")
    
    # 始终添加分隔注释，无论是否有预定义白名单
    all_domains.append(SEPARATOR_COMMENT)
    
    # 过滤从源获取的域名（排除已在预定义白名单中的域名）
    filtered_domains = []
    for domain in domains:
        # 如果是注释（已标记为黑名单的域名），直接添加
        if domain.startswith(BLACKLIST_COMMENT_PREFIX):
            filtered_domains.append(domain)
            continue
            
        # 普通域名，检查是否在白名单中
        if domain in prewhite_domains_set:
            continue  # 跳过已在预定义白名单中的域名
        
        filtered_domains.append(domain)
    
    all_domains.extend(filtered_domains)
    
    # 计算统计信息
    stats = Counter()
    for domain in all_domains:
        if not domain:
            continue
        elif domain.startswith(BLACKLIST_COMMENT_PREFIX):
            stats['blacklisted'] += 1
        elif domain.startswith('#'):
            stats['comments'] += 1
        else:
            stats['effective'] += 1
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # 保存到输出文件
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(all_domains) + '\n')
        
        print(f"成功将总共 {len(all_domains)} 个条目保存到 '{output_file}'")
        print(f"  其中包含 {stats['effective']} 个有效域名")
        print(f"  其中包含 {stats['blacklisted']} 个被标记为注释的黑名单域名")
        print(f"  其中包含 {stats['comments']} 个其他注释")
        print(f"  已在自动生成的内容前面添加分隔注释：'{SEPARATOR_COMMENT}'")
        return True
    except Exception as e:
        print(f"保存文件时出错：{e}")
        return False

def resolve_output_path(filename: str) -> str:
    """
    解析输出文件路径，如果只提供文件名则添加到默认输出目录
    
    Args:
        filename: 输出文件名或路径
    
    Returns:
        完整的输出文件路径
    """
    if not os.path.dirname(filename):
        return os.path.join(OUTPUT_DIR, filename)
    return filename

def print_help() -> None:
    """打印帮助信息"""
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
    print(f"预定义黑名单文件: {PREBLACK_FILE} (如果存在会自动排除这些域名及其子域名，但会保留为注释)")

def main() -> int:
    """主函数，处理命令行参数并执行相应操作"""
    # 处理命令行参数
    if len(sys.argv) == 1:
        # 没有参数时使用默认值
        print(f"未提供参数，使用默认URL: {DEFAULT_URL}")
        print(f"默认输出文件: {DEFAULT_OUTPUT}")
        success = extract_domains_from_url(DEFAULT_URL, DEFAULT_OUTPUT)
    elif len(sys.argv) == 2:
        # 只有一个参数时，假定为输出文件，使用默认URL
        output_file = resolve_output_path(sys.argv[1])
        print(f"使用默认URL: {DEFAULT_URL}")
        print(f"输出文件: {output_file}")
        success = extract_domains_from_url(DEFAULT_URL, output_file)
    elif sys.argv[1] == "--url" and len(sys.argv) >= 3:
        # 使用--url参数
        url = sys.argv[2]
        output_file = DEFAULT_OUTPUT if len(sys.argv) <= 3 else resolve_output_path(sys.argv[3])
        print(f"使用URL: {url}")
        print(f"输出文件: {output_file}")
        success = extract_domains_from_url(url, output_file)
    elif sys.argv[1] == "--file" and len(sys.argv) >= 3:
        # 使用--file参数从本地文件读取
        input_file = sys.argv[2]
        output_file = DEFAULT_OUTPUT if len(sys.argv) <= 3 else resolve_output_path(sys.argv[3])
        print(f"从本地文件读取: {input_file}")
        print(f"输出文件: {output_file}")
        success = extract_domains_from_file(input_file, output_file)
    else:
        # 其他情况显示帮助信息
        print_help()
        return 1
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
