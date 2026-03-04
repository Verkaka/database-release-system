#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Schema Diff Engine - 声明式数据库对比引擎
对比当前状态与期望状态，生成变更计划
"""

import re
import json
import hashlib
from typing import List, Dict, Tuple, Optional
from enum import Enum
from dataclasses import dataclass, asdict
from datetime import datetime


class ChangeType(Enum):
    """变更类型"""
    CREATE = "CREATE"
    ALTER = "ALTER"
    DROP = "DROP"
    MIGRATE = "MIGRATE"


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"        # 普通字段添加
    MEDIUM = "medium"  # 索引变更
    HIGH = "high"      # DROP, TRUNCATE, 数据类型变更


@dataclass
class Change:
    """变更项"""
    type: str
    target: str
    sql: str
    risk: str
    description: str = ""


class SchemaDiff:
    """Schema 对比引擎"""
    
    def __init__(self):
        self.risk_patterns = {
            RiskLevel.HIGH: [
                r'DROP\s+', r'TRUNCATE\s+', r'DELETE\s+FROM', 
                r'ALTER\s+.*COLUMN\s+.*TYPE', r'ALTER\s+.*DROP\s+COLUMN'
            ],
            RiskLevel.MEDIUM: [
                r'CREATE\s+INDEX', r'DROP\s+INDEX', 
                r'ALTER\s+.*ADD\s+INDEX', r'ALTER\s+.*DROP\s+INDEX'
            ],
            RiskLevel.LOW: [
                r'ALTER\s+.*ADD\s+COLUMN', r'CREATE\s+TABLE'
            ]
        }
    
    def compare(self, current_schema: Dict, target_schema: Dict) -> List[Dict]:
        """
        对比当前状态与期望状态，生成变更计划
        
        Args:
            current_schema: 当前数据库 Schema
            target_schema: 目标期望 Schema
        
        Returns:
            变更列表
        """
        changes = []
        
        # 表级别对比
        current_tables = {t['name']: t for t in current_schema.get('tables', [])}
        target_tables = {t['name']: t for t in target_schema.get('tables', [])}
        
        # 1. 新建表
        for table_name, table_def in target_tables.items():
            if table_name not in current_tables:
                sql = self._generate_create_table(table_name, table_def)
                changes.append({
                    'type': ChangeType.CREATE.value,
                    'target': f"TABLE {table_name}",
                    'sql': sql,
                    'risk': RiskLevel.LOW.value,
                    'description': f"创建新表 {table_name}"
                })
        
        # 2. 变更表（字段、索引）
        for table_name, current_def in current_tables.items():
            if table_name in target_tables:
                target_def = target_tables[table_name]
                column_changes = self._diff_columns(table_name, current_def, target_def)
                changes.extend(column_changes)
                
                index_changes = self._diff_indexes(table_name, current_def, target_def)
                changes.extend(index_changes)
        
        # 3. 删除表（谨慎操作）
        for table_name in current_tables:
            if table_name not in target_tables:
                changes.append({
                    'type': ChangeType.DROP.value,
                    'target': f"TABLE {table_name}",
                    'sql': f"DROP TABLE IF EXISTS {table_name};",
                    'risk': RiskLevel.HIGH.value,
                    'description': f"删除表 {table_name}（高危操作）"
                })
        
        return changes
    
    def _diff_columns(self, table_name: str, current_def: Dict, target_def: Dict) -> List[Dict]:
        """对比字段差异"""
        changes = []
        
        current_cols = {c['name']: c for c in current_def.get('columns', [])}
        target_cols = {c['name']: c for c in target_def.get('columns', [])}
        
        # 新增字段
        for col_name, col_def in target_cols.items():
            if col_name not in current_cols:
                sql = self._generate_add_column(table_name, col_name, col_def)
                changes.append({
                    'type': ChangeType.ALTER.value,
                    'target': f"TABLE {table_name}.{col_name}",
                    'sql': sql,
                    'risk': RiskLevel.LOW.value,
                    'description': f"添加字段 {table_name}.{col_name}"
                })
        
        # 删除字段
        for col_name in current_cols:
            if col_name not in target_cols:
                changes.append({
                    'type': ChangeType.ALTER.value,
                    'target': f"TABLE {table_name}.{col_name}",
                    'sql': f"ALTER TABLE {table_name} DROP COLUMN {col_name};",
                    'risk': RiskLevel.HIGH.value,
                    'description': f"删除字段 {table_name}.{col_name}（高危操作）"
                })
        
        return changes
    
    def _diff_indexes(self, table_name: str, current_def: Dict, target_def: Dict) -> List[Dict]:
        """对比索引差异"""
        changes = []
        
        current_indexes = {i['name']: i for i in current_def.get('indexes', [])}
        target_indexes = {i['name']: i for i in target_def.get('indexes', [])}
        
        # 新增索引
        for idx_name, idx_def in target_indexes.items():
            if idx_name not in current_indexes:
                sql = self._generate_create_index(table_name, idx_name, idx_def)
                changes.append({
                    'type': ChangeType.ALTER.value,
                    'target': f"INDEX {table_name}.{idx_name}",
                    'sql': sql,
                    'risk': RiskLevel.MEDIUM.value,
                    'description': f"创建索引 {table_name}.{idx_name}"
                })
        
        # 删除索引
        for idx_name in current_indexes:
            if idx_name not in target_indexes:
                changes.append({
                    'type': ChangeType.ALTER.value,
                    'target': f"INDEX {table_name}.{idx_name}",
                    'sql': f"DROP INDEX {idx_name} ON {table_name};",
                    'risk': RiskLevel.MEDIUM.value,
                    'description': f"删除索引 {table_name}.{idx_name}"
                })
        
        return changes
    
    def _generate_create_table(self, table_name: str, table_def: Dict) -> str:
        """生成 CREATE TABLE 语句"""
        columns = []
        primary_keys = []
        
        for col in table_def.get('columns', []):
            col_def = f"  `{col['name']}` {col['type']}"
            
            if col.get('primary_key'):
                primary_keys.append(col['name'])
            if col.get('auto_increment'):
                col_def += " AUTO_INCREMENT"
            if col.get('not_null'):
                col_def += " NOT NULL"
            if col.get('unique') and not col.get('primary_key'):
                col_def += " UNIQUE"
            if col.get('default'):
                col_def += f" DEFAULT {col['default']}"
            if col.get('comment'):
                col_def += f" COMMENT '{col['comment']}'"
            
            columns.append(col_def)
        
        if primary_keys:
            columns.append(f"  PRIMARY KEY ({','.join(primary_keys)})")
        
        return f"CREATE TABLE `{table_name}` (\n" + ",\n".join(columns) + "\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"
    
    def _generate_add_column(self, table_name: str, col_name: str, col_def: Dict) -> str:
        """生成 ADD COLUMN 语句"""
        sql = f"ALTER TABLE `{table_name}` ADD COLUMN `{col_name}` {col_def['type']}"
        
        if col_def.get('not_null'):
            sql += " NOT NULL"
        if col_def.get('default'):
            sql += f" DEFAULT {col_def['default']}"
        if col_def.get('comment'):
            sql += f" COMMENT '{col_def['comment']}'"
        
        sql += ";"
        return sql
    
    def _generate_create_index(self, table_name: str, idx_name: str, idx_def: Dict) -> str:
        """生成 CREATE INDEX 语句"""
        idx_type = "UNIQUE" if idx_def.get('type') == 'UNIQUE' else ""
        columns = ','.join(idx_def.get('columns', []))
        
        return f"CREATE {idx_type} INDEX `{idx_name}` ON `{table_name}` ({columns});"
    
    def export_changes(self, changes: List[Dict], output_file: str):
        """导出变更计划到文件"""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'generated_at': datetime.now().isoformat(),
                'total_changes': len(changes),
                'high_risk_count': sum(1 for c in changes if c['risk'] == 'high'),
                'changes': changes
            }, f, indent=2, ensure_ascii=False)
        
        print(f"变更计划已导出到：{output_file}")


def load_schema_from_file(file_path: str) -> Dict:
    """从 YAML/JSON 文件加载 Schema 定义"""
    import yaml
    
    with open(file_path, 'r', encoding='utf-8') as f:
        if file_path.endswith('.yaml') or file_path.endswith('.yml'):
            return yaml.safe_load(f)
        elif file_path.endswith('.json'):
            return json.load(f)
        else:
            raise ValueError(f"不支持的文件格式：{file_path}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Schema 对比工具')
    parser.add_argument('--current', required=True, help='当前 Schema 文件')
    parser.add_argument('--target', required=True, help='目标 Schema 文件')
    parser.add_argument('--output', default='changes.json', help='输出文件')
    
    args = parser.parse_args()
    
    # 加载 Schema
    current_schema = load_schema_from_file(args.current)
    target_schema = load_schema_from_file(args.target)
    
    # 执行对比
    diff_engine = SchemaDiff()
    changes = diff_engine.compare(current_schema, target_schema)
    
    # 导出结果
    diff_engine.export_changes(changes, args.output)
    
    print(f"\n共发现 {len(changes)} 项变更:")
    for change in changes:
        print(f"  [{change['risk'].upper()}] {change['type']}: {change['description']}")
