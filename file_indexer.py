import os
import pandas as pd
import sqlite3
import time
import logging
from config import XLSX_DIR, BATCH_SIZE
from database import get_conn

def index_files():
    conn = get_conn()
    c = conn.cursor()
    
    # 获取已索引文件
    indexed_files = {row[0]: row[1] for row in c.execute("SELECT path, last_modified FROM files")}
    
    # 扫描目录
    for root, _, files in os.walk(XLSX_DIR):
        for file in files:
            if file.endswith(('.xlsx', '.xls')):
                path = os.path.join(root, file)
                mod_time = os.path.getmtime(path)
                
                # 检查是否需要重新索引
                if path in indexed_files and indexed_files[path] >= mod_time:
                    continue
                
                logging.info(f"索引文件: {file}")
                try:
                    # 处理Excel文件
                    xl = pd.ExcelFile(path)
                    
                    # 更新文件元数据
                    c.execute("REPLACE INTO files (path, last_modified) VALUES (?, ?)", 
                              (path, mod_time))
                    file_id = c.lastrowid
                    
                    # 删除旧索引
                    c.execute("DELETE FROM fts_index WHERE file_id = ?", (file_id,))
                    
                    # 处理每个工作表
                    for sheet_name in xl.sheet_names:
                        df = xl.parse(sheet_name, dtype=str)
                        
                        # 批量处理数据
                        batch = []
                        for row_idx, row in df.iterrows():
                            # 拼接所有单元格内容
                            content = " ".join([str(cell) for cell in row.values if pd.notna(cell)])
                            batch.append((file_id, sheet_name, row_idx, content))
                            
                            if len(batch) >= BATCH_SIZE:
                                c.executemany("INSERT INTO fts_index VALUES (?, ?, ?, ?)", batch)
                                batch = []
                        
                        if batch:
                            c.executemany("INSERT INTO fts_index VALUES (?, ?, ?, ?)", batch)
                    
                    conn.commit()
                    logging.info(f"完成索引: {file}, 工作表: {len(xl.sheet_names)}")
                
                except Exception as e:
                    logging.error(f"索引失败 {file}: {str(e)}")
    
    conn.close()