import os

# 配置XLSX文件目录 (可修改为你的实际路径)
XLSX_DIR = os.path.expanduser("~/your/xlsx_files")

# 数据库配置
DB_PATH = "xlsearch.db"

# 前端认证密码
AUTH_PASSWORD = "admin"

# 索引配置
BATCH_SIZE = 500  # 批量处理行数
