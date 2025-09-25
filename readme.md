# CrawlerAI

一个基于人工智能的多功能网络爬虫项目，集成了多种平台的数据抓取和AI处理功能。

## 项目简介

CrawlerAI 是一个综合性的网络爬虫系统，支持多个主流社交媒体和内容平台的数据抓取，并集成了AI功能，如音视频内容转文字、自然语言处理等。该项目旨在为内容分析、数据挖掘和AI训练提供高质量的数据源。

## 主要功能

### 网络爬虫
支持多个主流平台数据抓取：
- 哔哩哔哩 (Bilibili)
- 抖音 (Douyin)
- 快手 (Kuaishou)
- 小红书 (Xiaohongshu)
- 微博 (Weibo)
- 知乎 (Zhihu)
- 百度贴吧 (Baidu Tieba)

实现的爬虫功能，包括：
- 用户登录认证
- 内容抓取（视频、图片、文字等）
- 评论抓取
- 数据存储

### AI功能
1. **音视频处理**：
   - 视频转音频
   - 音频转文字（基于 Faster Whisper）
   - 文本后处理和优化

2. **自然语言处理**：
   - RAG (Retrieval-Augmented Generation) 模型构建
   - 文本向量化
   - 语义搜索

3. **数据处理**：
   - 自动清洗和格式化爬取的数据
   - 构建可用于AI训练的数据集

## 项目结构
. ├── AI/ # AI相关功能模块 │ ├── AI_rag/ # RAG模型相关功能 │ └── audio_video/ # 音视频处理模块 ├── crawler/ # 爬虫核心模块 │ ├── base/ # 基础类和接口 │ ├── media_platform/ # 各平台爬虫实现 │ ├── store/ # 数据存储实现 │ ├── cache/ # 缓存管理 │ ├── config/ # 配置管理 │ ├── proxy/ # 代理管理 │ └── tools/ # 工具函数 ├── data/ # 爬虫数据存储目录 (gitignore) ├── browser_data/ # 浏览器数据目录 (gitignore) ├── model_*_model/ # AI模型存储目录 (gitignore) └── main.py # 主程序入口



## 工作流程

1. **数据采集**：运行爬虫抓取指定平台的数据
2. **数据处理**：将音视频内容转换为文本，清洗和格式化数据
3. **模型构建**：使用处理后的数据构建AI模型
4. **模型应用**：可以使用构建的模型进行语义搜索、问答等任务

## 安装与配置

1. 克隆项目到本地：

git clone <项目地址>

2. 安装依赖：

pip install -r requirements.txt

3. 配置环境变量：
在项目根目录创建 .env 文件
配置必要的API密钥和参数

4. audio_video里面需要配置语音模型，请自行下载，或者使用whisper模型

## 使用方法
项目通过配置参数运行，主要参数包括：

logintype: 登录类型
platform: 平台选择 (bili, zhihu, xhs等)
crawlertype: 爬取类型
