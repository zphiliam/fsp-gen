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
# 预定义黑名单文件
PREBLACK_FILE = "preblack.hostrules"
# 分隔注释
SEPARATOR_COMMENT = "# -------autogen------"
# 黑名单注释前缀
BLACKLIST_COMMENT_PREFIX = "# "

def is_subdomain(domain, parent_domain):
    """
    检查一个域名是否是另一个域名的子域名
    例如：mail.example.com 是 example.com 的子域名
    """
    # 去掉开头的点号
    if domain.startswith('.'):
        domain = domain[1:]
    if parent_domain.startswith('.'):
        parent_domain = parent_domain[1:]
    
    # 检查是否为相同域名
    if domain == parent_domain:
        return True
    
    # 检查是否为子域名 (domain以parent_domain结尾，且domain比parent_domain长，且domain中刚好在parent_domain前有一个点号)
    return domain.endswith('.' + parent_domain)

def is_blacklisted(domain, blacklist):
    """
    检查一个域名是否在黑名单中，或是黑名单中某个域名的子域名
    返回匹配的黑名单域名，如果不匹配则返回None
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

def load_blacklist():
    """
    加载黑名单文件内容
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

def extract_domains_from_url(url, output_file):
    """
    从URL下载内容，提取域名并以特定格式保存到输出文件
    输入格式: server=/domain.com/114.114.114.114
    输出格式: .domain.com
    """
    processed_domains = []
    blacklisted_count = 0
    blacklist = load_blacklist()
    
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
            domain_with_dot = f".{domain}"
            
            # 检查是否在黑名单中
            if blacklist:
                matched_blacklist = is_blacklisted(domain, blacklist)
                if matched_blacklist:
                    # 将域名添加为注释
                    processed_domains.append(f"{BLACKLIST_COMMENT_PREFIX}{domain_with_dot}")
                    blacklisted_count += 1
                    continue
            
            # 不在黑名单中，正常添加
            processed_domains.append(domain_with_dot)
    
    if not processed_domains:
        print("警告：未找到任何域名")
        return False
    
    if blacklisted_count > 0:
        print(f"已将 {blacklisted_count} 个在黑名单中的域名或其子域名标记为注释")
    
    # 添加预定义白名单域名并保存
    return save_domains_with_prewhite(processed_domains, output_file)

def extract_domains_from_file(input_file, output_file):
    """
    从本地文件中提取域名并以特定格式保存到输出文件
    输入格式: server=/domain.com/114.114.114.114
    输出格式: .domain.com
    """
    processed_domains = []
    blacklisted_count = 0
    blacklist = load_blacklist()
    
    # 读取输入文件
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            for line in f:
                # 使用正则表达式提取域名
                match = re.search(r'server=/([^/]+)/', line)
                if match:
                    domain = match.group(1)
                    domain_with_dot = f".{domain}"
                    
                    # 检查是否在黑名单中
                    if blacklist:
                        matched_blacklist = is_blacklisted(domain, blacklist)
                        if matched_blacklist:
                            # 将域名添加为注释
                            processed_domains.append(f"{BLACKLIST_COMMENT_PREFIX}{domain_with_dot}")
                            blacklisted_count += 1
                            continue
                    
                    # 不在黑名单中，正常添加
                    processed_domains.append(domain_with_dot)
    except FileNotFoundError:
        print(f"错误：找不到输入文件 '{input_file}'")
        return False
    
    if blacklisted_count > 0:
        print(f"已将 {blacklisted_count} 个在黑名单中的域名或其子域名标记为注释")
    
    # 添加预定义白名单域名并保存
    return save_domains_with_prewhite(processed_domains, output_file)

def save_domains_with_prewhite(domains, output_file):
    """
    将域名列表保存到输出文件，并在开头添加预定义白名单的内容（如果存在）
    如果域名已经存在于预定义白名单中，则不会重复添加
    在预定义白名单和自动生成的域名之间添加分隔注释
    """
    all_domains = []
    prewhite_domains_set = set()
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
    
    # 报告过滤情况
    # 统计有多少非注释域名（实际有效的域名）
    effective_domains = [d for d in all_domains if not d.startswith('#') and d]
    commented_domains = [d for d in all_domains if d.startswith(BLACKLIST_COMMENT_PREFIX) and not d.startswith(BLACKLIST_COMMENT_PREFIX + ' ')]
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # 保存到输出文件
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            for domain in all_domains:
                f.write(f"{domain}\n")
        print(f"成功将总共 {len(all_domains)} 个条目保存到 '{output_file}'")
        print(f"  其中包含 {len(effective_domains)} 个有效域名")
        print(f"  其中包含 {len(commented_domains)} 个被标记为注释的黑名单域名")
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
        print(f"预定义黑名单文件: {PREBLACK_FILE} (如果存在会自动排除这些域名及其子域名，但会保留为注释)")
        sys.exit(1)
