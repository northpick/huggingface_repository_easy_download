# -*- coding: utf-8 -*-
"""
HF下载器 - 修复版
- 修复大文件检测问题
- 添加缓存清理选项
- 直接下载到当前目录
"""

import re
import sys
import os
import warnings
import time
import shutil
import json
from pathlib import Path
from huggingface_hub import snapshot_download, HfApi, HfFileSystem
import concurrent.futures

# 忽略 SSL/HEAD 警告
warnings.filterwarnings("ignore", message=".*SSL: UNEXPECTED_EOF_WHILE_READING.*")
warnings.filterwarnings("ignore", message=".*resume_download.*")

# 初始化文件系统
hffs = HfFileSystem()

def parse_url(u):
    """解析URL，获取仓库ID、仓库名称和子文件夹路径"""
    u = u.strip()
    # 移除末尾的斜杠和可能的查询参数
    u = u.split('?')[0].rstrip("/")
    
    # 提取仓库信息
    m = re.search(r"huggingface\.co/([^/]+)/([^/]+)", u)
    if not m:
        return None, None, None
    
    repo_owner = m.group(1)
    repo_name = m.group(2)
    repo_id = f"{repo_owner}/{repo_name}"
    
    # 提取子文件夹路径
    sub_match = re.search(r"/tree/main/([^?#]+)", u)
    subfolder = sub_match.group(1).rstrip("/") if sub_match else None
    
    return repo_id, repo_name, subfolder

def get_all_files_recursive(repo_id, subfolder=None):
    """递归获取仓库中的所有文件"""
    all_files = []
    
    try:
        # 构建仓库路径
        base_path = f"{repo_id}@main"
        if subfolder:
            base_path = f"{base_path}/{subfolder}"
        
        print(f"正在扫描仓库: {base_path}")
        
        # 使用递归方式获取文件列表
        def scan_directory(path):
            try:
                items = hffs.ls(path, detail=True)
                
                for item in items:
                    # 构建相对路径
                    if item["name"].startswith(f"{repo_id}@main/"):
                        relative_path = item["name"][len(f"{repo_id}@main/"):]
                    else:
                        relative_path = item["name"]
                    
                    if item["type"] == "file":
                        # 如果是文件，添加到列表
                        all_files.append({
                            "path": relative_path,
                            "full_path": item["name"],
                            "size": item.get("size", 0),
                            "type": "file"
                        })
                    elif item["type"] == "directory":
                        # 如果是目录，递归扫描
                        scan_directory(item["name"])
            except Exception as e:
                print(f"  警告: 无法扫描目录 {path}: {e}")
        
        # 开始扫描
        scan_directory(base_path)
        
        print(f"扫描完成，找到 {len(all_files)} 个文件")
        return all_files
    except Exception as e:
        print(f"获取文件列表时出错: {e}")
        return []

def get_files_from_api(repo_id, subfolder=None):
    """通过API获取文件列表（备选方法）"""
    try:
        api = HfApi()
        
        # 获取仓库信息
        repo_info = api.repo_info(repo_id, repo_type="model")
        
        # 列出所有文件
        all_files = []
        
        # 构建前缀
        prefix = subfolder if subfolder else ""
        
        # 获取文件列表
        files = api.list_repo_files(repo_id, repo_type="model")
        
        for file_path in files:
            # 如果指定了子文件夹，只处理该文件夹下的文件
            if prefix:
                if not file_path.startswith(prefix):
                    continue
                # 移除子文件夹前缀
                relative_path = file_path[len(prefix):].lstrip('/')
                if not relative_path:  # 如果是子文件夹本身，跳过
                    continue
            else:
                relative_path = file_path
            
            # 获取文件信息
            try:
                file_info = hffs.info(f"{repo_id}@main/{file_path}")
                all_files.append({
                    "path": relative_path if relative_path else file_path,
                    "full_path": file_path,
                    "size": file_info.get("size", 0),
                    "type": "file"
                })
            except:
                all_files.append({
                    "path": relative_path if relative_path else file_path,
                    "full_path": file_path,
                    "size": 0,
                    "type": "file"
                })
        
        print(f"通过API找到 {len(all_files)} 个文件")
        return all_files
    except Exception as e:
        print(f"API获取文件失败: {e}")
        return []

def format_file_size(size_bytes):
    """格式化文件大小"""
    if size_bytes == 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    unit_index = 0
    
    while size_bytes >= 1024 and unit_index < len(units) - 1:
        size_bytes /= 1024
        unit_index += 1
    
    if unit_index == 0:
        return f"{size_bytes} B"
    elif unit_index == 1:
        return f"{size_bytes:.1f} KB"
    elif unit_index == 2:
        return f"{size_bytes:.1f} MB"
    else:
        return f"{size_bytes:.2f} {units[unit_index]}"

def download_small_files(repo_id, target_dir, subfolder=None):
    """下载小文件到目标目录"""
    try:
        print("正在下载小文件...")
        
        # 定义小文件模式（这些扩展名的文件通常较小）
        allow_patterns = [
            "*.json", "*.txt", "*.yaml", "*.yml", "*.md", 
            "*.py", "*.cpp", "*.c", "*.h", "*.hpp",
            "*.html", "*.css", "*.js", "*.xml", "*.ini", "*.cfg",
            "*.png", "*.jpg", "*.jpeg", "*.gif", "*.bmp", "*.webp",
            "*.csv", "*.tsv", "*.log",
            "tokenizer/*", "scheduler/*", "feature_extractor/*",
            "config.json", "model_index.json", "preprocessor_config.json",
            "*.vocab", "*.merges", "*.model"
        ]
        
        # 定义大文件模式（这些文件不下载，只生成链接）
        ignore_patterns = [
            "*.safetensors", "*.bin", "*.pt", "*.ckpt", "*.pth", 
            "*.msgpack", "*.h5", "*.gguf", "*.onnx", "*.tflite",
            "*/pytorch_model*.bin", "*/model*.safetensors",
            "*/diffusion_pytorch_model*.bin"
        ]
        
        # 如果有子文件夹，调整模式
        if subfolder:
            allow_patterns = [f"{subfolder}/{p}" for p in allow_patterns]
            ignore_patterns = [f"{subfolder}/{p}" for p in ignore_patterns]
        
        # 下载到目标目录
        cache_path = snapshot_download(
            repo_id=repo_id,
            repo_type="model",
            local_dir=target_dir,  # 直接下载到目标目录
            local_dir_use_symlinks=False,
            allow_patterns=allow_patterns,
            ignore_patterns=ignore_patterns,
            resume_download=True,
            max_workers=4,
            tqdm_class=None
        )
        
        print("✅ 小文件下载完成")
        return True
    except Exception as e:
        print(f"下载小文件时出错: {e}")
        return False

def classify_files_by_size(file_list, size_threshold_mb=50):
    """按大小分类文件"""
    small_files = []
    big_files = []
    
    for file_info in file_list:
        file_size = file_info["size"]
        file_path = file_info["path"]
        
        # 大小判断：小于阈值为小文件，否则为大文件
        if file_size < size_threshold_mb * 1024 * 1024:  # 转换为字节
            small_files.append(file_info)
        else:
            # 检查文件扩展名，确保不是小文件类型
            small_extensions = ['.json', '.txt', '.yaml', '.yml', '.md', '.py', 
                               '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.csv']
            if any(file_path.lower().endswith(ext) for ext in small_extensions):
                # 即使文件大，但扩展名是小文件类型，也当作小文件处理
                small_files.append(file_info)
            else:
                big_files.append(file_info)
    
    return small_files, big_files

def generate_big_file_links(repo_id, repo_name, big_files, target_dir, subfolder=None):
    """生成大文件链接"""
    if not big_files:
        print("没有检测到大文件")
        return None
    
    print(f"检测到 {len(big_files)} 个大文件:")
    
    # 创建链接文件名
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    if subfolder:
        safe_subfolder = subfolder.replace('/', '_').replace('\\', '_')
        link_filename = f"{repo_name}_{safe_subfolder}_大文件_{timestamp}.txt"
    else:
        link_filename = f"{repo_name}_大文件_{timestamp}.txt"
    
    link_file = target_dir / link_filename
    
    try:
        with open(link_file, "w", encoding="utf-8") as f:
            f.write(f"HuggingFace 大文件下载链接\n")
            f.write("=" * 70 + "\n")
            f.write(f"仓库: {repo_id}\n")
            f.write(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            if subfolder:
                f.write(f"子文件夹: {subfolder}\n")
            f.write(f"大文件数量: {len(big_files)} 个\n")
            f.write("=" * 70 + "\n\n")
            
            total_size = 0
            for i, file_info in enumerate(big_files, 1):
                file_path = file_info["path"]
                file_size = file_info["size"]
                total_size += file_size
                
                # 生成下载链接
                download_url = f"https://huggingface.co/{repo_id}/resolve/main/{file_path}"
                if subfolder and not file_path.startswith(subfolder):
                    # 确保文件路径包含子文件夹
                    full_path = f"{subfolder}/{file_path}" if subfolder else file_path
                    download_url = f"https://huggingface.co/{repo_id}/resolve/main/{full_path}"
                
                f.write(f"【文件 {i}】\n")
                f.write(f"文件名: {Path(file_path).name}\n")
                f.write(f"路径: {file_path}\n")
                f.write(f"大小: {format_file_size(file_size)}\n")
                f.write(f"下载链接: {download_url}\n")
                f.write("-" * 70 + "\n\n")
            
            f.write(f"\n总计: {len(big_files)} 个文件，总大小: {format_file_size(total_size)}\n")
        
        print(f"✅ 已生成大文件链接文件: {link_file}")
        print(f"   包含 {len(big_files)} 个大文件，总大小: {format_file_size(total_size)}")
        
        # 显示文件列表
        print("\n📁 大文件列表:")
        for i, file_info in enumerate(big_files[:20], 1):
            file_name = Path(file_info["path"]).name
            print(f"   {i:2d}. {file_name[:50]:50} {format_file_size(file_info['size']):>10}")
        
        if len(big_files) > 20:
            print(f"   ... 还有 {len(big_files) - 20} 个文件")
        
        return link_file
    except Exception as e:
        print(f"生成链接文件时出错: {e}")
        return None

def ask_for_cache_cleanup(repo_folder):
    """询问是否清理缓存"""
    print("\n" + "=" * 70)
    print("缓存清理选项")
    print("=" * 70)
    
    # 检查.cache文件夹
    cache_folder = repo_folder / ".cache"
    
    if cache_folder.exists():
        # 计算缓存大小
        cache_size = 0
        try:
            for root, dirs, files in os.walk(cache_folder):
                for file in files:
                    try:
                        cache_size += os.path.getsize(os.path.join(root, file))
                    except:
                        pass
        except:
            cache_size = 0
        
        print(f"检测到缓存文件夹: {cache_folder}")
        print(f"缓存大小: {format_file_size(cache_size)}")
        
        # 询问用户
        while True:
            choice = input("\n是否删除缓存文件夹？(y/n): ").strip().lower()
            if choice in ['y', 'yes', '是']:
                try:
                    shutil.rmtree(cache_folder)
                    print("✅ 缓存文件夹已删除")
                except Exception as e:
                    print(f"删除缓存文件夹时出错: {e}")
                break
            elif choice in ['n', 'no', '否']:
                print("✅ 已保留缓存文件夹")
                break
            else:
                print("请输入 y/n 或 是/否")
    else:
        print("未找到缓存文件夹")

def main():
    print("=" * 70)
    print("HF下载器 - 修复版".center(70))
    print("=" * 70)
    
    # 测试URL（用于调试）
    # url = "https://huggingface.co/hustvl/vitmatte-small-composition-1k/tree/main"
    url = input("\n请输入HuggingFace仓库链接 → ").strip()
    
    if not url:
        print("错误: 请输入有效的链接!")
        input("按回车键退出...")
        sys.exit(1)
    
    # 解析URL
    repo_id, repo_name, subfolder = parse_url(url)
    
    if not repo_id:
        print("错误: 无法解析链接，请检查链接格式!")
        input("按回车键退出...")
        sys.exit(1)
    
    print(f"\n✅ 仓库信息:")
    print(f"   仓库ID: {repo_id}")
    print(f"   仓库名称: {repo_name}")
    if subfolder:
        print(f"   子文件夹: {subfolder}")
    else:
        print(f"   子文件夹: 根目录")
    
    # 创建仓库文件夹
    repo_folder = Path.cwd() / repo_name
    try:
        repo_folder.mkdir(exist_ok=True)
        print(f"✅ 已创建文件夹: {repo_folder}")
    except Exception as e:
        print(f"❌ 创建文件夹失败: {e}")
        input("按回车键退出...")
        sys.exit(1)
    
    # 步骤1: 获取文件列表
    print("\n" + "=" * 70)
    print("步骤1: 扫描仓库文件")
    print("=" * 70)
    
    # 尝试多种方法获取文件列表
    all_files = []
    
    print("尝试方法1: 递归扫描...")
    all_files = get_all_files_recursive(repo_id, subfolder)
    
    if not all_files:
        print("\n方法1失败，尝试方法2: 使用API...")
        all_files = get_files_from_api(repo_id, subfolder)
    
    if not all_files:
        print("❌ 无法获取文件列表，请检查网络连接和链接有效性!")
        input("按回车键退出...")
        sys.exit(1)
    
    # 显示文件统计
    print(f"\n📊 文件统计:")
    print(f"   总计: {len(all_files)} 个文件")
    
    # 按大小分类文件
    small_files, big_files = classify_files_by_size(all_files, size_threshold_mb=50)
    
    print(f"   小文件（<50MB）: {len(small_files)} 个")
    print(f"   大文件（≥50MB）: {len(big_files)} 个")
    
    # 显示文件大小分布
    if all_files:
        sizes = [f["size"] for f in all_files]
        max_size = max(sizes) if sizes else 0
        avg_size = sum(sizes) / len(sizes) if sizes else 0
        print(f"   最大文件: {format_file_size(max_size)}")
        print(f"   平均大小: {format_file_size(avg_size)}")
    
    # 步骤2: 下载小文件
    print("\n" + "=" * 70)
    print("步骤2: 下载小文件")
    print("=" * 70)
    
    if small_files:
        total_small_size = sum(f["size"] for f in small_files)
        print(f"正在下载 {len(small_files)} 个小文件，总大小: {format_file_size(total_small_size)}")
        
        # 下载小文件
        success = download_small_files(repo_id, repo_folder, subfolder)
        
        if success:
            # 检查下载的文件
            downloaded_files = []
            for root, dirs, files in os.walk(repo_folder):
                for file in files:
                    if file != ".gitattributes":  # 忽略.gitattributes文件
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, repo_folder)
                        downloaded_files.append(rel_path)
            
            print(f"✅ 已下载 {len(downloaded_files)} 个文件到: {repo_folder}")
            
            # 显示下载的文件
            if downloaded_files:
                print("\n📄 已下载的文件:")
                for i, file in enumerate(downloaded_files[:10], 1):
                    print(f"   {i:2d}. {file}")
                if len(downloaded_files) > 10:
                    print(f"   ... 还有 {len(downloaded_files) - 10} 个文件")
        else:
            print("⚠️  小文件下载可能不完整，但继续执行...")
    else:
        print("没有小文件需要下载")
    
    # 步骤3: 生成大文件链接
    print("\n" + "=" * 70)
    print("步骤3: 生成大文件下载链接")
    print("=" * 70)
    
    if big_files:
        total_big_size = sum(f["size"] for f in big_files)
        print(f"检测到 {len(big_files)} 个大文件，总大小: {format_file_size(total_big_size)}")
        
        link_file = generate_big_file_links(repo_id, repo_name, big_files, repo_folder, subfolder)
    else:
        print("✅ 没有大文件需要生成链接")
    
    # 步骤4: 缓存清理
    ask_for_cache_cleanup(repo_folder)
    
    # 完成提示
    print("\n" + "=" * 70)
    print("下载任务完成!".center(70))
    print("=" * 70)
    
    print(f"\n📂 文件夹位置: {repo_folder}")
    
    # 显示文件夹内容统计
    print(f"\n📊 文件夹内容统计:")
    try:
        file_count = 0
        dir_count = 0
        total_size = 0
        
        for root, dirs, files in os.walk(repo_folder):
            dir_count += len(dirs)
            for file in files:
                if file.endswith('.txt') and '大文件' in file:
                    continue  # 不统计链接文件
                try:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
                    file_count += 1
                except:
                    pass
        
        print(f"   文件数量: {file_count} 个")
        print(f"   文件夹数量: {dir_count} 个")
        print(f"   总大小: {format_file_size(total_size)}")
    except:
        pass
    
    print("\n📋 下一步操作:")
    print("   1. 小文件已下载到上述文件夹")
    
    if big_files:
        print("   2. 大文件链接已生成到txt文件中")
        print("   3. 请使用下载工具（IDM、迅雷等）下载大文件")
    
    print("\n" + "=" * 70)
    
    input("\n按回车键退出程序...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断操作，程序退出")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 程序运行出错: {e}")
        import traceback
        traceback.print_exc()
        input("按回车键退出...")
        sys.exit(1)# -*- coding: utf-8 -*-
"""
HF下载器 - 修复版
- 修复大文件检测问题
- 添加缓存清理选项
- 直接下载到当前目录
"""

import re
import sys
import os
import warnings
import time
import shutil
import json
from pathlib import Path
from huggingface_hub import snapshot_download, HfApi, HfFileSystem
import concurrent.futures

# 忽略 SSL/HEAD 警告
warnings.filterwarnings("ignore", message=".*SSL: UNEXPECTED_EOF_WHILE_READING.*")
warnings.filterwarnings("ignore", message=".*resume_download.*")

# 初始化文件系统
hffs = HfFileSystem()

def parse_url(u):
    """解析URL，获取仓库ID、仓库名称和子文件夹路径"""
    u = u.strip()
    # 移除末尾的斜杠和可能的查询参数
    u = u.split('?')[0].rstrip("/")
    
    # 提取仓库信息
    m = re.search(r"huggingface\.co/([^/]+)/([^/]+)", u)
    if not m:
        return None, None, None
    
    repo_owner = m.group(1)
    repo_name = m.group(2)
    repo_id = f"{repo_owner}/{repo_name}"
    
    # 提取子文件夹路径
    sub_match = re.search(r"/tree/main/([^?#]+)", u)
    subfolder = sub_match.group(1).rstrip("/") if sub_match else None
    
    return repo_id, repo_name, subfolder

def get_all_files_recursive(repo_id, subfolder=None):
    """递归获取仓库中的所有文件"""
    all_files = []
    
    try:
        # 构建仓库路径
        base_path = f"{repo_id}@main"
        if subfolder:
            base_path = f"{base_path}/{subfolder}"
        
        print(f"正在扫描仓库: {base_path}")
        
        # 使用递归方式获取文件列表
        def scan_directory(path):
            try:
                items = hffs.ls(path, detail=True)
                
                for item in items:
                    # 构建相对路径
                    if item["name"].startswith(f"{repo_id}@main/"):
                        relative_path = item["name"][len(f"{repo_id}@main/"):]
                    else:
                        relative_path = item["name"]
                    
                    if item["type"] == "file":
                        # 如果是文件，添加到列表
                        all_files.append({
                            "path": relative_path,
                            "full_path": item["name"],
                            "size": item.get("size", 0),
                            "type": "file"
                        })
                    elif item["type"] == "directory":
                        # 如果是目录，递归扫描
                        scan_directory(item["name"])
            except Exception as e:
                print(f"  警告: 无法扫描目录 {path}: {e}")
        
        # 开始扫描
        scan_directory(base_path)
        
        print(f"扫描完成，找到 {len(all_files)} 个文件")
        return all_files
    except Exception as e:
        print(f"获取文件列表时出错: {e}")
        return []

def get_files_from_api(repo_id, subfolder=None):
    """通过API获取文件列表（备选方法）"""
    try:
        api = HfApi()
        
        # 获取仓库信息
        repo_info = api.repo_info(repo_id, repo_type="model")
        
        # 列出所有文件
        all_files = []
        
        # 构建前缀
        prefix = subfolder if subfolder else ""
        
        # 获取文件列表
        files = api.list_repo_files(repo_id, repo_type="model")
        
        for file_path in files:
            # 如果指定了子文件夹，只处理该文件夹下的文件
            if prefix:
                if not file_path.startswith(prefix):
                    continue
                # 移除子文件夹前缀
                relative_path = file_path[len(prefix):].lstrip('/')
                if not relative_path:  # 如果是子文件夹本身，跳过
                    continue
            else:
                relative_path = file_path
            
            # 获取文件信息
            try:
                file_info = hffs.info(f"{repo_id}@main/{file_path}")
                all_files.append({
                    "path": relative_path if relative_path else file_path,
                    "full_path": file_path,
                    "size": file_info.get("size", 0),
                    "type": "file"
                })
            except:
                all_files.append({
                    "path": relative_path if relative_path else file_path,
                    "full_path": file_path,
                    "size": 0,
                    "type": "file"
                })
        
        print(f"通过API找到 {len(all_files)} 个文件")
        return all_files
    except Exception as e:
        print(f"API获取文件失败: {e}")
        return []

def format_file_size(size_bytes):
    """格式化文件大小"""
    if size_bytes == 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    unit_index = 0
    
    while size_bytes >= 1024 and unit_index < len(units) - 1:
        size_bytes /= 1024
        unit_index += 1
    
    if unit_index == 0:
        return f"{size_bytes} B"
    elif unit_index == 1:
        return f"{size_bytes:.1f} KB"
    elif unit_index == 2:
        return f"{size_bytes:.1f} MB"
    else:
        return f"{size_bytes:.2f} {units[unit_index]}"

def download_small_files(repo_id, target_dir, subfolder=None):
    """下载小文件到目标目录"""
    try:
        print("正在下载小文件...")
        
        # 定义小文件模式（这些扩展名的文件通常较小）
        allow_patterns = [
            "*.json", "*.txt", "*.yaml", "*.yml", "*.md", 
            "*.py", "*.cpp", "*.c", "*.h", "*.hpp",
            "*.html", "*.css", "*.js", "*.xml", "*.ini", "*.cfg",
            "*.png", "*.jpg", "*.jpeg", "*.gif", "*.bmp", "*.webp",
            "*.csv", "*.tsv", "*.log",
            "tokenizer/*", "scheduler/*", "feature_extractor/*",
            "config.json", "model_index.json", "preprocessor_config.json",
            "*.vocab", "*.merges", "*.model"
        ]
        
        # 定义大文件模式（这些文件不下载，只生成链接）
        ignore_patterns = [
            "*.safetensors", "*.bin", "*.pt", "*.ckpt", "*.pth", 
            "*.msgpack", "*.h5", "*.gguf", "*.onnx", "*.tflite",
            "*/pytorch_model*.bin", "*/model*.safetensors",
            "*/diffusion_pytorch_model*.bin"
        ]
        
        # 如果有子文件夹，调整模式
        if subfolder:
            allow_patterns = [f"{subfolder}/{p}" for p in allow_patterns]
            ignore_patterns = [f"{subfolder}/{p}" for p in ignore_patterns]
        
        # 下载到目标目录
        cache_path = snapshot_download(
            repo_id=repo_id,
            repo_type="model",
            local_dir=target_dir,  # 直接下载到目标目录
            local_dir_use_symlinks=False,
            allow_patterns=allow_patterns,
            ignore_patterns=ignore_patterns,
            resume_download=True,
            max_workers=4,
            tqdm_class=None
        )
        
        print("✅ 小文件下载完成")
        return True
    except Exception as e:
        print(f"下载小文件时出错: {e}")
        return False

def classify_files_by_size(file_list, size_threshold_mb=50):
    """按大小分类文件"""
    small_files = []
    big_files = []
    
    for file_info in file_list:
        file_size = file_info["size"]
        file_path = file_info["path"]
        
        # 大小判断：小于阈值为小文件，否则为大文件
        if file_size < size_threshold_mb * 1024 * 1024:  # 转换为字节
            small_files.append(file_info)
        else:
            # 检查文件扩展名，确保不是小文件类型
            small_extensions = ['.json', '.txt', '.yaml', '.yml', '.md', '.py', 
                               '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.csv']
            if any(file_path.lower().endswith(ext) for ext in small_extensions):
                # 即使文件大，但扩展名是小文件类型，也当作小文件处理
                small_files.append(file_info)
            else:
                big_files.append(file_info)
    
    return small_files, big_files

def generate_big_file_links(repo_id, repo_name, big_files, target_dir, subfolder=None):
    """生成大文件链接"""
    if not big_files:
        print("没有检测到大文件")
        return None
    
    print(f"检测到 {len(big_files)} 个大文件:")
    
    # 创建链接文件名
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    if subfolder:
        safe_subfolder = subfolder.replace('/', '_').replace('\\', '_')
        link_filename = f"{repo_name}_{safe_subfolder}_大文件_{timestamp}.txt"
    else:
        link_filename = f"{repo_name}_大文件_{timestamp}.txt"
    
    link_file = target_dir / link_filename
    
    try:
        with open(link_file, "w", encoding="utf-8") as f:
            f.write(f"HuggingFace 大文件下载链接\n")
            f.write("=" * 70 + "\n")
            f.write(f"仓库: {repo_id}\n")
            f.write(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            if subfolder:
                f.write(f"子文件夹: {subfolder}\n")
            f.write(f"大文件数量: {len(big_files)} 个\n")
            f.write("=" * 70 + "\n\n")
            
            total_size = 0
            for i, file_info in enumerate(big_files, 1):
                file_path = file_info["path"]
                file_size = file_info["size"]
                total_size += file_size
                
                # 生成下载链接
                download_url = f"https://huggingface.co/{repo_id}/resolve/main/{file_path}"
                if subfolder and not file_path.startswith(subfolder):
                    # 确保文件路径包含子文件夹
                    full_path = f"{subfolder}/{file_path}" if subfolder else file_path
                    download_url = f"https://huggingface.co/{repo_id}/resolve/main/{full_path}"
                
                f.write(f"【文件 {i}】\n")
                f.write(f"文件名: {Path(file_path).name}\n")
                f.write(f"路径: {file_path}\n")
                f.write(f"大小: {format_file_size(file_size)}\n")
                f.write(f"下载链接: {download_url}\n")
                f.write("-" * 70 + "\n\n")
            
            f.write(f"\n总计: {len(big_files)} 个文件，总大小: {format_file_size(total_size)}\n")
        
        print(f"✅ 已生成大文件链接文件: {link_file}")
        print(f"   包含 {len(big_files)} 个大文件，总大小: {format_file_size(total_size)}")
        
        # 显示文件列表
        print("\n📁 大文件列表:")
        for i, file_info in enumerate(big_files[:20], 1):
            file_name = Path(file_info["path"]).name
            print(f"   {i:2d}. {file_name[:50]:50} {format_file_size(file_info['size']):>10}")
        
        if len(big_files) > 20:
            print(f"   ... 还有 {len(big_files) - 20} 个文件")
        
        return link_file
    except Exception as e:
        print(f"生成链接文件时出错: {e}")
        return None

def ask_for_cache_cleanup(repo_folder):
    """询问是否清理缓存"""
    print("\n" + "=" * 70)
    print("缓存清理选项")
    print("=" * 70)
    
    # 检查.cache文件夹
    cache_folder = repo_folder / ".cache"
    
    if cache_folder.exists():
        # 计算缓存大小
        cache_size = 0
        try:
            for root, dirs, files in os.walk(cache_folder):
                for file in files:
                    try:
                        cache_size += os.path.getsize(os.path.join(root, file))
                    except:
                        pass
        except:
            cache_size = 0
        
        print(f"检测到缓存文件夹: {cache_folder}")
        print(f"缓存大小: {format_file_size(cache_size)}")
        
        # 询问用户
        while True:
            choice = input("\n是否删除缓存文件夹？(y/n): ").strip().lower()
            if choice in ['y', 'yes', '是']:
                try:
                    shutil.rmtree(cache_folder)
                    print("✅ 缓存文件夹已删除")
                except Exception as e:
                    print(f"删除缓存文件夹时出错: {e}")
                break
            elif choice in ['n', 'no', '否']:
                print("✅ 已保留缓存文件夹")
                break
            else:
                print("请输入 y/n 或 是/否")
    else:
        print("未找到缓存文件夹")

def main():
    print("=" * 70)
    print("HF下载器 - 修复版".center(70))
    print("=" * 70)
    
    # 测试URL（用于调试）
    # url = "https://huggingface.co/hustvl/vitmatte-small-composition-1k/tree/main"
    url = input("\n请输入HuggingFace仓库链接 → ").strip()
    
    if not url:
        print("错误: 请输入有效的链接!")
        input("按回车键退出...")
        sys.exit(1)
    
    # 解析URL
    repo_id, repo_name, subfolder = parse_url(url)
    
    if not repo_id:
        print("错误: 无法解析链接，请检查链接格式!")
        input("按回车键退出...")
        sys.exit(1)
    
    print(f"\n✅ 仓库信息:")
    print(f"   仓库ID: {repo_id}")
    print(f"   仓库名称: {repo_name}")
    if subfolder:
        print(f"   子文件夹: {subfolder}")
    else:
        print(f"   子文件夹: 根目录")
    
    # 创建仓库文件夹
    repo_folder = Path.cwd() / repo_name
    try:
        repo_folder.mkdir(exist_ok=True)
        print(f"✅ 已创建文件夹: {repo_folder}")
    except Exception as e:
        print(f"❌ 创建文件夹失败: {e}")
        input("按回车键退出...")
        sys.exit(1)
    
    # 步骤1: 获取文件列表
    print("\n" + "=" * 70)
    print("步骤1: 扫描仓库文件")
    print("=" * 70)
    
    # 尝试多种方法获取文件列表
    all_files = []
    
    print("尝试方法1: 递归扫描...")
    all_files = get_all_files_recursive(repo_id, subfolder)
    
    if not all_files:
        print("\n方法1失败，尝试方法2: 使用API...")
        all_files = get_files_from_api(repo_id, subfolder)
    
    if not all_files:
        print("❌ 无法获取文件列表，请检查网络连接和链接有效性!")
        input("按回车键退出...")
        sys.exit(1)
    
    # 显示文件统计
    print(f"\n📊 文件统计:")
    print(f"   总计: {len(all_files)} 个文件")
    
    # 按大小分类文件
    small_files, big_files = classify_files_by_size(all_files, size_threshold_mb=50)
    
    print(f"   小文件（<50MB）: {len(small_files)} 个")
    print(f"   大文件（≥50MB）: {len(big_files)} 个")
    
    # 显示文件大小分布
    if all_files:
        sizes = [f["size"] for f in all_files]
        max_size = max(sizes) if sizes else 0
        avg_size = sum(sizes) / len(sizes) if sizes else 0
        print(f"   最大文件: {format_file_size(max_size)}")
        print(f"   平均大小: {format_file_size(avg_size)}")
    
    # 步骤2: 下载小文件
    print("\n" + "=" * 70)
    print("步骤2: 下载小文件")
    print("=" * 70)
    
    if small_files:
        total_small_size = sum(f["size"] for f in small_files)
        print(f"正在下载 {len(small_files)} 个小文件，总大小: {format_file_size(total_small_size)}")
        
        # 下载小文件
        success = download_small_files(repo_id, repo_folder, subfolder)
        
        if success:
            # 检查下载的文件
            downloaded_files = []
            for root, dirs, files in os.walk(repo_folder):
                for file in files:
                    if file != ".gitattributes":  # 忽略.gitattributes文件
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, repo_folder)
                        downloaded_files.append(rel_path)
            
            print(f"✅ 已下载 {len(downloaded_files)} 个文件到: {repo_folder}")
            
            # 显示下载的文件
            if downloaded_files:
                print("\n📄 已下载的文件:")
                for i, file in enumerate(downloaded_files[:10], 1):
                    print(f"   {i:2d}. {file}")
                if len(downloaded_files) > 10:
                    print(f"   ... 还有 {len(downloaded_files) - 10} 个文件")
        else:
            print("⚠️  小文件下载可能不完整，但继续执行...")
    else:
        print("没有小文件需要下载")
    
    # 步骤3: 生成大文件链接
    print("\n" + "=" * 70)
    print("步骤3: 生成大文件下载链接")
    print("=" * 70)
    
    if big_files:
        total_big_size = sum(f["size"] for f in big_files)
        print(f"检测到 {len(big_files)} 个大文件，总大小: {format_file_size(total_big_size)}")
        
        link_file = generate_big_file_links(repo_id, repo_name, big_files, repo_folder, subfolder)
    else:
        print("✅ 没有大文件需要生成链接")
    
    # 步骤4: 缓存清理
    ask_for_cache_cleanup(repo_folder)
    
    # 完成提示
    print("\n" + "=" * 70)
    print("下载任务完成!".center(70))
    print("=" * 70)
    
    print(f"\n📂 文件夹位置: {repo_folder}")
    
    # 显示文件夹内容统计
    print(f"\n📊 文件夹内容统计:")
    try:
        file_count = 0
        dir_count = 0
        total_size = 0
        
        for root, dirs, files in os.walk(repo_folder):
            dir_count += len(dirs)
            for file in files:
                if file.endswith('.txt') and '大文件' in file:
                    continue  # 不统计链接文件
                try:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
                    file_count += 1
                except:
                    pass
        
        print(f"   文件数量: {file_count} 个")
        print(f"   文件夹数量: {dir_count} 个")
        print(f"   总大小: {format_file_size(total_size)}")
    except:
        pass
    
    print("\n📋 下一步操作:")
    print("   1. 小文件已下载到上述文件夹")
    
    if big_files:
        print("   2. 大文件链接已生成到txt文件中")
        print("   3. 请使用下载工具（IDM、迅雷等）下载大文件")
    
    print("\n" + "=" * 70)
    
    input("\n按回车键退出程序...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断操作，程序退出")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 程序运行出错: {e}")
        import traceback
        traceback.print_exc()
        input("按回车键退出...")
        sys.exit(1)