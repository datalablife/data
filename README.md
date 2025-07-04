# Python 3.11 开发环境

这个仓库包含使用Python 3.11版本的开发环境配置。可以使用Conda或UV进行环境管理。

## 环境设置

### 方法一：使用Conda创建环境

```bash
# 创建新环境
conda env create -f environment.yml

# 激活环境
conda activate dev_env_py311

# 查看已安装的包
conda list
```

更新环境：

```bash
conda env update -f environment.yml --prune
```

删除环境：

```bash
conda env remove -n dev_env_py311
```

### 方法二：使用UV创建环境（推荐，速度更快）

首先安装UV：

```bash
# 使用pip安装UV
pip install uv

# 或者使用conda安装
conda install -c conda-forge uv
```

创建环境并安装依赖：

```bash
# 创建虚拟环境
uv venv --python 3.11

# 激活环境（Linux/macOS）
source .venv/bin/activate

# 激活环境（Windows）
.venv\Scripts\activate

# 安装依赖
uv pip install -r requirements.txt
# 或使用
uv sync
```

常用UV命令：

```bash
# 添加新包
uv add numpy pandas matplotlib

# 添加开发依赖
uv add --dev pytest black flake8

# 运行Python脚本
uv run python script.py

# 运行测试
uv run pytest
```

## 为什么选择UV？

- **速度快**: 比pip快10-100倍，比conda快得多
- **现代化**: 使用Rust编写，性能优异
- **兼容性**: 完全兼容pip和PyPI
- **简单**: 统一的命令行界面
- **可靠**: 确定性的依赖解析
