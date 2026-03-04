#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migration Executor - 迁移执行与回滚模块
支持干跑模式、执行记录、回滚操作
"""

import os
import re
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    request_id: str
    executed_at: Optional[str] = None
    executed_by: Optional[str] = None
    dry_run: bool = False
    preview: Optional[str] = None
    error: Optional[str] = None
    affected_rows: int = 0
    rollback_sql: Optional[str] = None


class MigrationExecutor:
    """迁移执行器"""
    
    def __init__(
        self, 
        db_host: str,
        db_user: str,
        db_password: str,
        db_name: str,
        db_port: int = 3306
    ):
        """
        初始化执行器
        
        Args:
            db_host: 数据库主机
            db_user: 数据库用户
            db_password: 数据库密码
            db_name: 数据库名称
            db_port: 数据库端口
        """
        self.db_config = {
            'host': db_host,
            'user': db_user,
            'password': db_password,
            'database': db_name,
            'port': db_port
        }
        self.migration_log_table = "schema_migrations"
    
    def execute(
        self, 
        sql: str, 
        request_id: str, 
        dry_run: bool = False,
        executor: str = ""
    ) -> ExecutionResult:
        """
        执行迁移
        
        Args:
            sql: SQL 脚本内容
            request_id: 请求 ID
            dry_run: 是否干跑模式
            executor: 执行人
        
        Returns:
            ExecutionResult 执行结果
        """
        result = ExecutionResult(
            success=False,
            request_id=request_id,
            dry_run=dry_run,
            executed_by=executor or os.getenv('USER', 'unknown')
        )
        
        if dry_run:
            logger.info("干跑模式：不实际执行 SQL")
            result.success = True
            result.preview = sql
            result.executed_at = datetime.now().isoformat()
            return result
        
        try:
            import mysql.connector
            
            conn = mysql.connector.connect(**self.db_config)
            cursor = conn.cursor()
            
            # 创建迁移日志表（如果不存在）
            self._ensure_log_table(cursor)
            
            # 分割并执行 SQL 语句
            statements = self._split_sql_statements(sql)
            total_affected = 0
            rollback_statements = []
            
            for stmt in statements:
                if stmt.strip():
                    try:
                        cursor.execute(stmt)
                        if cursor.rowcount > 0:
                            total_affected += cursor.rowcount
                        
                        # 生成回滚 SQL
                        rollback = self._generate_rollback_sql(stmt)
                        if rollback:
                            rollback_statements.append(rollback)
                    
                    except mysql.connector.Error as e:
                        logger.error(f"执行语句失败：{e}")
                        conn.rollback()
                        result.error = f"SQL 执行错误：{str(e)}"
                        self._log_failure(request_id, sql, str(e), cursor, conn)
                        cursor.close()
                        conn.close()
                        return result
            
            # 提交事务
            conn.commit()
            
            # 记录成功日志
            self._log_success(
                request_id, sql, cursor, 
                rollback_sql='\n'.join(rollback_statements) if rollback_statements else None,
                conn=conn
            )
            
            result.success = True
            result.executed_at = datetime.now().isoformat()
            result.affected_rows = total_affected
            result.rollback_sql = '\n'.join(rollback_statements) if rollback_statements else None
            
            logger.info(f"迁移执行成功，影响 {total_affected} 行")
            
            cursor.close()
            conn.close()
            
        except ImportError:
            logger.error("未安装 mysql-connector-python，请运行：pip install mysql-connector-python")
            result.error = "缺少依赖：mysql-connector-python"
        
        except Exception as e:
            logger.error(f"执行失败：{e}")
            result.error = str(e)
        
        return result
    
    def rollback(self, request_id: str) -> ExecutionResult:
        """
        回滚指定迁移
        
        Args:
            request_id: 请求 ID
        
        Returns:
            ExecutionResult 执行结果
        """
        try:
            import mysql.connector
            
            conn = mysql.connector.connect(**self.db_config)
            cursor = conn.cursor()
            
            # 获取原始迁移记录
            cursor.execute(f"""
                SELECT sql, rollback_sql FROM {self.migration_log_table}
                WHERE request_id = %s AND status = 'success'
                ORDER BY executed_at DESC LIMIT 1
            """, (request_id,))
            
            row = cursor.fetchone()
            if not row:
                cursor.close()
                conn.close()
                return ExecutionResult(
                    success=False,
                    request_id=request_id,
                    error=f"未找到成功的迁移记录：{request_id}"
                )
            
            original_sql, rollback_sql = row
            
            if not rollback_sql:
                cursor.close()
                conn.close()
                return ExecutionResult(
                    success=False,
                    request_id=request_id,
                    error="该迁移没有可用的回滚 SQL"
                )
            
            # 执行回滚
            result = self.execute(
                sql=rollback_sql,
                request_id=f"{request_id}_rollback",
                executor=os.getenv('USER', 'unknown')
            )
            
            if result.success:
                # 更新原迁移状态
                cursor.execute(f"""
                    UPDATE {self.migration_log_table}
                    SET status = 'rolled_back', rolled_back_at = %s
                    WHERE request_id = %s
                """, (datetime.now().isoformat(), request_id))
                conn.commit()
            
            cursor.close()
            conn.close()
            return result
            
        except Exception as e:
            logger.error(f"回滚失败：{e}")
            return ExecutionResult(
                success=False,
                request_id=request_id,
                error=str(e)
            )
    
    def _ensure_log_table(self, cursor):
        """确保迁移日志表存在"""
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.migration_log_table} (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                request_id VARCHAR(64) NOT NULL,
                `sql` TEXT NOT NULL,
                rollback_sql TEXT,
                executed_at DATETIME NOT NULL,
                executed_by VARCHAR(128),
                status ENUM('success', 'failed', 'rolled_back') NOT NULL,
                error TEXT,
                affected_rows INT DEFAULT 0,
                rolled_back_at DATETIME,
                INDEX idx_request_id (request_id),
                INDEX idx_status (status),
                INDEX idx_executed_at (executed_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
    
    def _split_sql_statements(self, sql: str) -> List[str]:
        """
        分割 SQL 语句（处理多语句）
        
        Args:
            sql: SQL 脚本内容
        
        Returns:
            语句列表
        """
        statements = []
        current = []
        in_string = False
        string_char = None
        
        for char in sql:
            if char in ("'", '"') and (not current or current[-1] != '\\'):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
                    string_char = None
                current.append(char)
            elif char == ';' and not in_string:
                statements.append(''.join(current).strip())
                current = []
            else:
                current.append(char)
        
        if current:
            statements.append(''.join(current).strip())
        
        return statements
    
    def _generate_rollback_sql(self, sql: str) -> Optional[str]:
        """
        生成回滚 SQL（简化版本）
        
        Args:
            sql: 原始 SQL
        
        Returns:
            回滚 SQL 或 None
        """
        sql_upper = sql.upper().strip()
        
        # CREATE TABLE -> DROP TABLE
        if sql_upper.startswith('CREATE TABLE'):
            match = re.search(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`"]?(\w+)[`"]?', sql, re.IGNORECASE)
            if match:
                return f"DROP TABLE IF EXISTS {match.group(1)};"
        
        # ALTER TABLE ADD COLUMN -> ALTER TABLE DROP COLUMN
        elif sql_upper.startswith('ALTER TABLE') and 'ADD COLUMN' in sql_upper:
            match = re.search(
                r'ALTER\s+TABLE\s+[`"]?(\w+)[`"]?\s+ADD\s+COLUMN\s+[`"]?(\w+)[`"]?',
                sql, re.IGNORECASE
            )
            if match:
                return f"ALTER TABLE {match.group(1)} DROP COLUMN {match.group(2)};"
        
        # CREATE INDEX -> DROP INDEX
        elif sql_upper.startswith('CREATE') and 'INDEX' in sql_upper:
            match = re.search(
                r'CREATE\s+(?:UNIQUE\s+)?INDEX\s+[`"]?(\w+)[`"]?\s+ON\s+[`"]?(\w+)[`"]?',
                sql, re.IGNORECASE
            )
            if match:
                return f"DROP INDEX {match.group(1)} ON {match.group(2)};"
        
        return None
    
    def _log_success(self, request_id: str, sql: str, cursor, rollback_sql: Optional[str] = None, conn=None):
        """记录成功日志"""
        cursor.execute(f"""
            INSERT INTO {self.migration_log_table} 
            (request_id, `sql`, rollback_sql, executed_at, executed_by, status, affected_rows)
            VALUES (%s, %s, %s, %s, %s, 'success', %s)
        """, (
            request_id, sql, rollback_sql, 
            datetime.now().isoformat(),
            os.getenv('USER', 'unknown'),
            0
        ))
        if conn:
            conn.commit()
    
    def _log_failure(self, request_id: str, sql: str, error: str, cursor, conn=None):
        """记录失败日志"""
        cursor.execute(f"""
            INSERT INTO {self.migration_log_table} 
            (request_id, `sql`, executed_at, executed_by, status, error)
            VALUES (%s, %s, %s, %s, 'failed', %s)
        """, (
            request_id, sql, 
            datetime.now().isoformat(),
            os.getenv('USER', 'unknown'),
            error
        ))
        if conn:
            conn.commit()
    
    def get_migration_history(self, limit: int = 50) -> List[Dict]:
        """
        获取迁移历史
        
        Args:
            limit: 返回数量限制
        
        Returns:
            迁移记录列表
        """
        try:
            import mysql.connector
            
            conn = mysql.connector.connect(**self.db_config)
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute(f"""
                SELECT * FROM {self.migration_log_table}
                ORDER BY executed_at DESC
                LIMIT %s
            """, (limit,))
            
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            
            return results
            
        except Exception as e:
            logger.error(f"获取迁移历史失败：{e}")
            return []


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='迁移执行工具')
    parser.add_argument('--input', required=True, help='SQL 迁移文件')
    parser.add_argument('--host', required=True, help='数据库主机')
    parser.add_argument('--user', required=True, help='数据库用户')
    parser.add_argument('--password', default='', help='数据库密码')
    parser.add_argument('--database', required=True, help='数据库名称')
    parser.add_argument('--port', type=int, default=3306, help='数据库端口')
    parser.add_argument('--request-id', default='manual', help='请求 ID')
    parser.add_argument('--dry-run', action='store_true', help='干跑模式')
    parser.add_argument('--output', default='execution_result.json', help='输出文件')
    
    args = parser.parse_args()
    
    # 读取 SQL 文件
    with open(args.input, 'r', encoding='utf-8') as f:
        sql = f.read()
    
    # 创建执行器
    executor = MigrationExecutor(
        db_host=args.host,
        db_user=args.user,
        db_password=args.password,
        db_name=args.database,
        db_port=args.port
    )
    
    # 执行迁移
    result = executor.execute(
        sql=sql,
        request_id=args.request_id,
        dry_run=args.dry_run
    )
    
    # 输出结果
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(asdict(result), f, indent=2, ensure_ascii=False)
    
    print(f"执行结果：{'成功' if result.success else '失败'}")
    if result.error:
        print(f"错误：{result.error}")
    print(f"结果已输出到：{args.output}")
