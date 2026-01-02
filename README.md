        
# Windows下部署RAG框架前后端流程

## 一、后端部署

### 1. 安装Python环境

#### 方法一：使用Miniconda（推荐）
1. 下载Miniconda安装包：https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe
2. 运行安装包，按照向导完成安装
3. 安装完成后，打开Anaconda Prompt

#### 方法二：使用系统Python
1. 确保安装Python 3.11+版本
2. 打开命令提示符或PowerShell

### 2. 创建虚拟环境

在命令行中执行：
```bash
# 使用conda创建虚拟环境（推荐）
conda create -n rag-project01 python=3.11.9
conda activate rag-project01

# 或使用venv创建虚拟环境
python -m venv rag-project01
rag-project01\Scripts\activate
```

### 3. 安装后端依赖

进入项目根目录，执行：
```bash
cd d:\Work\learn-rag\Canzhao\rag-project01-framework-master
pip install -r requirements_win.txt
```

### 4. 配置环境变量

在命令行中设置API密钥（或添加到系统环境变量）：
```bash
set OPENAI_API_KEY="your_openai_api_key"
set DEEPSEEK_API_KEY="your_deepseek_api_key"

# 可选：当使用 LlamaParser（llama-parse）时需要
set LLAMA_CLOUD_API_KEY="your_llama_cloud_api_key"
```

> 说明：
> - `LLAMA_CLOUD_API_KEY` 仅在 `/load` 选择 `loading_method=llamaparser` 时需要。
> - Unstructured 解析 PDF（尤其是 hi_res / 表格 / 图片）可能需要额外系统依赖；如安装失败，请优先参考你们现有的 `requirements_win.txt` 版本组合。

### 5. 启动后端服务

进入backend目录，执行：
```bash
cd backend
uvicorn main:app --reload --port 8001 --host 0.0.0.0
```

后端服务将在http://localhost:8001启动

释放端口：
  netstat -ano | findstr :8001
  tasklist /FI PID eq “端口号”

## 二、前端部署

### 1. 安装Node.js和npm

1. 下载Node.js安装包：https://nodejs.org/en/download/
2. 运行安装包，按照向导完成安装（包含npm）
3. 验证安装：
   ```bash
   node -v
   npm -v
   ```
   确保Node.js版本≥14.18或16+

### 2. 安装前端依赖

进入frontend目录，执行：
```bash
cd d:\Work\learn-rag\Canzhao\rag-project01-framework-master\frontend
npm install
```

### 3. 配置API地址

前端配置文件已默认指向localhost:8001，如果需要修改，编辑：
`frontend\src\config\config.js`

### 4. 启动前端服务

在frontend目录下执行：
```bash
npm run dev
```

# 如果提示vite未安装，执行以下命令
npm install vite

前端服务将在http://localhost:5175启动（默认端口）

## 三、访问应用

1. 打开浏览器，访问http://localhost:5175
2. 前端将自动连接到后端服务

## 四、常见问题

1. **端口占用**：如果8001或5175端口被占用，可以修改启动命令中的端口号
2. **依赖安装失败**：尝试使用国内镜像源，如：
   ```bash
   pip install -r requirements_win.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
   npm install --registry=https://registry.npmmirror.com
   ```
3. **API密钥错误**：确保正确设置了OPENAI_API_KEY和DEEPSEEK_API_KEY环境变量

## 五、数据处理接口（Load / Chunk / Parse）

本项目后端提供三类核心数据处理接口：

- **Load File**：把原始文件加载并标准化成 `chunks`（落盘到 `backend/01-loaded-docs/`）
- **Chunk File**：把 loaded 的 chunks 再按不同策略切块（落盘到 `backend/01-chunked-docs/`）
- **Parse File**：对 PDF/MD 进行更“结构化”的解析（尤其是表格/图片），并以 JSON+Metadata 形式保存（可选落盘到 `backend/00-parsed-docs/`）

### 5.1 Load File（新增 Unstructured / LlamaParser 参数）

接口：`POST http://localhost:8001/load`

基础必填参数（Form）：
- `file`：上传文件
- `loading_method`：`pymupdf` / `pypdf` / `pdfplumber` / `unstructured` / `llamaparser`

Unstructured 相关参数（可选，Form）：
- `strategy`：`fast` / `hi_res` / `ocr_only`
- `chunking_strategy`：`basic` / `by_title`
- `chunking_options`：JSON 字符串（例如：`{"maxCharacters":4000,"overlap":200}`）
- `include_header_footer`：是否保留页眉页脚（不传则使用默认行为）
- `infer_table_structure`：是否推断表格结构（不传则使用默认行为）
- `extract_images_in_pdf`：是否提取 PDF 图片元素（不传则使用默认行为）
- `languages`：逗号分隔语言列表，如：`eng,chi_sim`

LlamaParser 相关参数（可选，Form）：
- `llamaparser_api_key`：不传则读取环境变量 `LLAMA_CLOUD_API_KEY`
- `llamaparser_model`：可选（不同版本是否生效取决于 llama-parse 实现）

输出：
- 返回 `loaded_content`（JSON，包含 `chunks` 列表和 metadata）
- 并在 `backend/01-loaded-docs/` 下落盘一份 JSON

### 5.2 Chunk File（多方案切块，保持 JSON 结构）

接口：`POST http://localhost:8001/chunk`

请求 Body（JSON）：
- `doc_id`：`01-loaded-docs` 下的文件名（例如：`074_unstructured_fast_basic_*.json`）
- `chunking_option`：
   - 现有：`by_pages` / `fixed_size` / `by_paragraphs` / `by_sentences`
   - 新增：`by_separators`
- `chunk_size`：切块大小（默认 1000）
- `chunk_overlap`：切块重叠（默认 200；对 `by_sentences/by_separators` 为真实 overlap，对 `fixed_size` 为近似 overlap）
- `separators`：仅 `by_separators` 使用，自定义分隔符数组，如：`["\n\n","\n",". "," "]`

输出：
- 返回标准化 JSON：`filename/total_chunks/total_pages/loading_method/chunking_method/timestamp/chunks[]`
- 并在 `backend/01-chunked-docs/` 下生成一份结果文件

### 5.3 Parse File（表格/图片转文本，JSON+Metadata 落盘）

接口：`POST http://localhost:8001/parse`

说明：
- **不传** `parse_backend`：保持原逻辑（ParsingService），用于简单解析展示。
- **传** `parse_backend=unstructured`：启用新 Parse File 流程，将 PDF 中的 **表格/图片等元素统一转为文本**并输出为 `chunks` JSON，且保留丰富 metadata。

新增参数（Form，可选）：
- `parse_backend`：目前支持 `unstructured`
- `save_json`：`true/false`，为 true 时会落盘到 `backend/00-parsed-docs/`
- `strategy`：Unstructured 策略，默认建议 `hi_res`
- `include_header_footer` / `infer_table_structure` / `extract_images_in_pdf` / `languages`：同 Load File

输出：
- 返回 `parsed_content`
- 若 `save_json=true` 且 `parse_backend` 已设置，会额外返回 `filepath`，并保存到 `backend/00-parsed-docs/`

## 六、项目结构

- **后端**：FastAPI框架，主要文件为`backend/main.py`
- **前端**：React + Vite，主要配置在`frontend/package.json`和`frontend/src/config/config.js`
- **数据存储**：后端自动创建相关目录存储文档、向量等数据

新增/相关目录：
- `backend/01-loaded-docs/`：Load File 的 JSON 产物
- `backend/01-chunked-docs/`：Chunk File 的 JSON 产物
- `backend/00-parsed-docs/`：Parse File 新流程（Unstructured 表格/图片转文本）的 JSON 产物（当 `save_json=true`）

以上就是在Windows环境下部署RAG框架前后端的完整流程。
        