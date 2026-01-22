# huggingface_repository_easy_download

一个智能、高效的HuggingFace仓库下载工具，自动分离小文件与大文件，解决网络不稳定环境下的仓库下载难题。

### ✨ 核心特性

- **智能文件分离**：自动识别并下载小于50MB的小文件，为大文件生成专用下载链接
- **断点续传支持**：下载中断后可恢复，避免重复下载
- **缓存友好**：提供缓存清理选项，释放磁盘空间
- **子文件夹支持**：可指定下载仓库内的特定子目录
- **仓库结构保持**：自动按仓库名称创建本地文件夹，保持原始文件结构

### 📦 安装与快速开始

#### 直接使用
1. 下载本项目文件
2. 项目已安装Python和相关包
3. 运行`download.bat`（Windows）或直接执行`python download.py`


### 🚀 使用方法

#### 基础使用
1. 运行程序后，粘贴HuggingFace仓库链接
   ```
   示例链接：https://huggingface.co/hustvl/vitmatte-small-composition-1k/tree/main
   ```
2. 程序将自动：
   - 创建以仓库命名的本地文件夹
   - 下载所有小文件（<50MB）
   - 生成大文件下载链接到txt文件

#### 高级选项
- **自定义大小阈值**：在代码中修改`size_threshold_mb`参数调整大小文件分界
- **指定子文件夹**：使用tree/main/子文件夹路径格式的链接下载特定目录
- **缓存管理**：程序结束时可选择清理下载缓存

### 📁 项目结构
```
huggingface-downloader/
├── download.py          # 核心下载脚本
├── download.bat          # Windows启动脚本
├── README.md           # 项目说明
├── python             # Python便携包
├── update.py          # 更新huggingface_hub库
└── LICENSE            # 开源许可证

```

### 🔧 功能对比

| 特性 | 本工具 | 传统下载方式 |
|------|--------|--------------|
| 大文件处理 | ✅ 生成直链，用下载工具加速 | ❌ 直接下载，易中断 |
| 网络优化 | ✅ 小文件批量，大文件分离 | ❌ 统一处理，无优化 |
| 断点续传 | ✅ 自动支持 | ❌ 需手动处理 |
| 结构保持 | ✅ 自动创建仓库文件夹 | ❌ 文件散落或需手动整理 |
| 缓存清理 | ✅ 提供清理选项 | ❌ 缓存积累占用空间 |

### 📝 使用示例

#### 示例1：下载整个仓库
```
请输入HuggingFace仓库链接 → https://huggingface.co/hustvl/vitmatte-small-composition-1k
```
结果：创建`vitmatte-small-composition-1k`文件夹，下载小文件并生成大文件链接。

#### 示例2：下载特定子文件夹
```
请输入HuggingFace仓库链接 → https://huggingface.co/runwayml/stable-diffusion-v1-5/tree/main/text_encoder
```
结果：仅下载text_encoder子目录内容。

#### 示例3：批量下载后使用链接
1. 程序生成`模型名_大文件_时间戳.txt`
2. 使用IDM、XDM导入链接文件
3. 享受稳定高速的大文件下载
---

### 🚀 使用XDM下载大文件（推荐）

本工具生成的大文件链接，最适合配合 **[Xtreme Download Manager](https://subhra74.github.io/xdm/)** 这类专业下载工具使用，以获得最快的下载速度和最强的断点续传能力。

#### 为何选择XDM？
- **免费开源**：完全免费，无广告
- **跨平台**：支持 Windows、Linux、macOS
- **下载加速**：支持多线程、带宽优化，速度远超浏览器
- **链接批量导入**：可直接导入我们生成的`大文件链接.txt`
- **与浏览器集成**：可捕获浏览器下载链接

#### 分步教程

**第1步：安装并配置XDM**
 从[官网](https://xtremedownloadmanager.com/)下载并安装XDM。

**第2步：从链接文件导入链接**
1.  运行本工具后，找到生成的 `[仓库名]_大文件_时间戳.txt` 文件。
2.  复制链接，打开XDM，点击新建。
3.  XDM会自动下载任务。

**第3步：开始高速下载**
1.  在XDM主界面，你可以看到所有排队任务。
2.  点击“开始”按钮，XDM将使用多线程技术全力下载。

#### 💡 高级技巧与故障排除
- **任务管理**：在XDM中，你可以随时暂停、恢复或删除任务。即使关闭电脑，下次启动也可继续。
- **速度不理想**：尝试在XDM设置中进一步增加“最大连接数”，或在“网络”选项中调整“速度优化”。
- **链接失效**：如果某个链接下载失败，请回到本工具重新运行（链接通常会更新），生成新的链接文件。
- **磁盘空间不足**：这是下载大模型最常见的错误。务必在开始前确认目标盘有足够空间（例如，一个70B的模型可能需要140GB以上的空间）。

### ❓ 常见问题

#### Q: 为什么大文件不直接下载？
A: 大模型文件常达数GB，直接下载易因网络波动中断。本工具生成专用链接供专业下载工具使用，支持多线程、断点续传。

#### Q: 如何调整大小文件阈值？
A: 在`download.py`中找到`classify_files_by_size`函数，修改`size_threshold_mb`参数（默认50MB）。

#### Q: 支持私有仓库吗？
A: 当前版本主要针对公开仓库。如需私有仓库支持，可配置HuggingFace访问令牌。


### 🤝 贡献指南

欢迎贡献代码、报告问题或提出建议！

1. Fork本仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

### 📄 许可证

本项目采用 [MIT许可证]。简单来说，你可以自由使用、修改和分发代码，只需保留原许可证声明。

### 🙏 致谢

- 感谢[HuggingFace团队](https://huggingface.co)提供的优秀平台
- 使用[huggingface-hub](https://github.com/huggingface/huggingface_hub) Python库

---
