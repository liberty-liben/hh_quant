import os
import sqlite3
import database_config as config
from uploader.uploader_akshare import AkShareUploader


def init_database():
    # 检测数据库状态
    if not os.path.exists(config.DATABASE_PATH):
        # 如果数据库文件不存在，SQLite将会创建一个
        conn = sqlite3.connect(config.DATABASE_PATH)
        print(f"数据库 {config.DATABASE_PATH} 创建成功。")
        conn.close()
    else:
        print(f"数据库 {config.DATABASE_PATH} 已经存在。")


def init_database_schema():
    conn = sqlite3.connect(config.DATABASE_PATH)
    print(f"数据库 {config.DATABASE_PATH} 连接成功。")
    # 创建一个cursor对象来帮助执行SQL语句
    cursor = conn.cursor()
    # 读取SQL模式文件
    with open(config.DATABASE_SCHEMA_PATH, "r") as f:
        create_table_sqls = f.read().split(";")  # 拆分每一个数据表的建表逻辑
        for create_table_sql in create_table_sqls:
            try:
                cursor.execute(create_table_sql)
            except Exception as e:
                print(e)
    # 提交事务
    conn.commit()
    # 关闭cursor和连接
    cursor.close()
    conn.close()
    print(f"数据库和表已经从文件 {config.DATABASE_SCHEMA_PATH} 创建于 {config.DATABASE_PATH}")


def init_database_data():
    conn = sqlite3.connect(config.DATABASE_PATH)
    # 初始化downloader
    uploader = AkShareUploader(db_conn=conn)
    # 开始下载数据（2024-02-07）
    uploader._upload_stock_history_info(table_name=config.TABLE_STOCK_HISTORY_INFO)  # 个股历史数据

    # --------------------------------------------------------------------------------------------------------------vs
    # uploader._upload_index_base_info(table_name=config.TABLE_INDEX_BASE_INFO)
    # uploader._upload_index_history_info(table_name=config.TABLE_INDEX_HISTORY_INFO)
    # uploader._upload_stock_trade_date(table_name=config.TABLE_STOCK_TRADE_DATA_INFO)
    # uploader._upload_stock_base_info(table_name=config.TABLE_STOCK_BASE_INFO)
    # uploader._upload_stock_individual_info(table_name=config.TABLE_STOCK_INDIVIDUAL_INFO)  # 个股基础数据
    #
    # uploader._upload_stock_event_info(table_name=config.TABLE_STOCK_EVENT_INFO)
    # 关闭连接
    conn.close()


if __name__ == "__main__":
    # 初始化数据库
    init_database()
    # 初始化数据表
    init_database_schema()
    # 插入数据
    init_database_data()