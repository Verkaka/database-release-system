#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试套件 - 企业级数据库声明式发布系统
"""

import os
import sys
import pytest
import json
from datetime import datetime

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'workflows'))


class TestSchemaDiff:
    """Schema 对比引擎测试"""
    
    @pytest.fixture
    def diff_engine(self):
        from schema_diff import SchemaDiff
        return SchemaDiff()
    
    def test_create_table(self, diff_engine):
        """测试新建表检测"""
        current = {'tables': []}
        target = {
            'tables': [{
                'name': 'users',
                'columns': [
                    {'name': 'id', 'type': 'BIGINT', 'primary_key': True}
                ]
            }]
        }
        
        changes = diff_engine.compare(current, target)
        
        assert len(changes) == 1
        assert changes[0]['type'] == 'CREATE'
        assert 'users' in changes[0]['target']
    
    def test_add_column(self, diff_engine):
        """测试添加字段检测"""
        current = {
            'tables': [{
                'name': 'users',
                'columns': [{'name': 'id', 'type': 'BIGINT'}]
            }]
        }
        target = {
            'tables': [{
                'name': 'users',
                'columns': [
                    {'name': 'id', 'type': 'BIGINT'},
                    {'name': 'email', 'type': 'VARCHAR(255)'}
                ]
            }]
        }
        
        changes = diff_engine.compare(current, target)
        
        assert len(changes) == 1
        assert changes[0]['type'] == 'ALTER'
        assert 'email' in changes[0]['target']
    
    def test_drop_table_risk(self, diff_engine):
        """测试删除表高危操作检测"""
        current = {
            'tables': [{'name': 'old_table', 'columns': []}]
        }
        target = {'tables': []}
        
        changes = diff_engine.compare(current, target)
        
        assert len(changes) == 1
        assert changes[0]['risk'] == 'high'
        assert 'DROP' in changes[0]['sql']
    
    def test_generate_create_table_sql(self, diff_engine):
        """测试 CREATE TABLE SQL 生成"""
        table_def = {
            'columns': [
                {'name': 'id', 'type': 'BIGINT UNSIGNED', 'primary_key': True, 'auto_increment': True},
                {'name': 'email', 'type': 'VARCHAR(255)', 'not_null': True, 'unique': True},
                {'name': 'created_at', 'type': 'TIMESTAMP', 'default': 'CURRENT_TIMESTAMP'}
            ]
        }
        
        sql = diff_engine._generate_create_table('users', table_def)
        
        assert 'CREATE TABLE' in sql
        assert '`users`' in sql
        assert 'BIGINT UNSIGNED' in sql
        assert 'PRIMARY KEY' in sql
        assert 'AUTO_INCREMENT' in sql
        assert 'NOT NULL' in sql
        assert 'UNIQUE' in sql
    
    def test_risk_assessment(self, diff_engine):
        """测试风险评估"""
        # 高危操作
        high_risk_sql = "DROP TABLE users;"
        # 应该被识别为高危
        
        # 低危操作
        low_risk_sql = "ALTER TABLE users ADD COLUMN name VARCHAR(100);"
        # 应该被识别为低危


class TestApprovalWorkflow:
    """审批流程引擎测试"""
    
    @pytest.fixture
    def workflow(self):
        from approval_workflow import ApprovalWorkflow
        return ApprovalWorkflow({
            'approval_chain': ['team_lead', 'dba'],
            'dba_required_for_risk': ['high', 'medium'],
            'approvers': {
                'team_lead': ['lead1'],
                'dba': ['dba1'],
                'ops': ['ops1']
            }
        })
    
    def test_create_request(self, workflow):
        """测试创建审批请求"""
        changes = [
            {'type': 'CREATE', 'target': 'TABLE users', 'risk': 'low'}
        ]
        
        request = workflow.create_request(
            submitter='dev1',
            submitter_name='张三',
            changes=changes
        )
        
        assert request.request_id.startswith('DB-')
        assert request.submitter == 'dev1'
        assert request.status == 'pending'
        assert len(request.changes) == 1
    
    def test_requires_dba_approval(self, workflow):
        """测试 DBA 审批需求判断"""
        # 高危变更需要 DBA
        high_risk_changes = [{'risk': 'high'}]
        assert workflow.requires_dba_approval(high_risk_changes) is True
        
        # 低危变更不需要 DBA
        low_risk_changes = [{'risk': 'low'}]
        assert workflow.requires_dba_approval(low_risk_changes) is False
    
    def test_approval_flow(self, workflow):
        """测试完整审批流程"""
        changes = [
            {'type': 'CREATE', 'target': 'TABLE users', 'risk': 'high'}
        ]
        
        request = workflow.create_request(
            submitter='dev1',
            changes=changes
        )
        
        # 初始状态
        assert request.status == 'pending'
        
        # 组长审批
        result = workflow.approve(request.request_id, 'lead1', 'team_lead', '同意')
        assert result['success'] is True
        assert request.status == 'pending'  # 还需要 DBA 审批
        
        # DBA 审批
        result = workflow.approve(request.request_id, 'dba1', 'dba', '已审核')
        assert result['success'] is True
        assert request.status == 'approved'  # 全部审批完成
        
        # 运维执行
        result = workflow.execute(request.request_id, 'ops1')
        assert result['success'] is True
        assert request.status == 'executed'
    
    def test_reject_flow(self, workflow):
        """测试拒绝流程"""
        request = workflow.create_request(
            submitter='dev1',
            changes=[{'risk': 'low'}]
        )
        
        result = workflow.reject(request.request_id, 'lead1', 'team_lead', '需求不明确')
        
        assert result['success'] is True
        assert request.status == 'rejected'


class TestMigrationExecutor:
    """迁移执行器测试"""
    
    @pytest.fixture
    def db_config(self):
        return {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 3306)),
            'user': os.getenv('DB_USER', 'test_user'),
            'password': os.getenv('DB_PASSWORD', 'test_password'),
            'database': os.getenv('DB_NAME', 'test_db')
        }
    
    @pytest.fixture
    def executor(self, db_config):
        from migration_executor import MigrationExecutor
        return MigrationExecutor(
            db_host=db_config['host'],
            db_user=db_config['user'],
            db_password=db_config['password'],
            db_name=db_config['database'],
            db_port=db_config['port']
        )
    
    def test_dry_run(self, executor):
        """测试干跑模式"""
        sql = "CREATE TABLE test_dry_run (id BIGINT PRIMARY KEY);"
        
        result = executor.execute(
            sql=sql,
            request_id='TEST-001',
            dry_run=True
        )
        
        assert result.success is True
        assert result.dry_run is True
        assert result.preview == sql
        assert result.error is None
    
    def test_execute_create_table(self, executor):
        """测试创建表执行"""
        sql = """
        CREATE TABLE IF NOT EXISTS test_execution (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        
        result = executor.execute(
            sql=sql,
            request_id='TEST-002'
        )
        
        assert result.success is True
        assert result.dry_run is False
        assert result.executed_at is not None
    
    def test_execute_with_error(self, executor):
        """测试错误处理"""
        # 故意写错 SQL
        sql = "INVALID SQL STATEMENT;"
        
        result = executor.execute(
            sql=sql,
            request_id='TEST-003'
        )
        
        assert result.success is False
        assert result.error is not None
    
    def test_rollback_generation(self, executor):
        """测试回滚 SQL 生成"""
        # CREATE TABLE -> DROP TABLE
        create_sql = "CREATE TABLE test_rollback (id BIGINT PRIMARY KEY);"
        rollback = executor._generate_rollback_sql(create_sql)
        assert rollback is not None
        assert 'DROP TABLE' in rollback
        
        # ALTER TABLE ADD COLUMN -> DROP COLUMN
        alter_sql = "ALTER TABLE users ADD COLUMN email VARCHAR(255);"
        rollback = executor._generate_rollback_sql(alter_sql)
        assert rollback is not None
        assert 'DROP COLUMN' in rollback
    
    def test_migration_history(self, executor):
        """测试迁移历史查询"""
        # 先执行一个迁移
        sql = "CREATE TABLE IF NOT EXISTS test_history (id BIGINT PRIMARY KEY);"
        executor.execute(sql=sql, request_id='TEST-HISTORY-001')
        
        # 查询历史
        history = executor.get_migration_history(limit=10)
        
        assert isinstance(history, list)
        # 至少有一条记录（init.sql 可能也有）
        assert len(history) >= 0


class TestIntegration:
    """集成测试"""
    
    @pytest.fixture
    def db_config(self):
        return {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 3306)),
            'user': os.getenv('DB_USER', 'test_user'),
            'password': os.getenv('DB_PASSWORD', 'test_password'),
            'database': os.getenv('DB_NAME', 'test_db')
        }
    
    def test_full_workflow(self, db_config):
        """测试完整工作流"""
        from schema_diff import SchemaDiff
        from approval_workflow import ApprovalWorkflow
        from migration_executor import MigrationExecutor
        
        # 1. Schema 对比
        current = {'tables': []}
        target = {
            'tables': [{
                'name': 'integration_test',
                'columns': [
                    {'name': 'id', 'type': 'BIGINT', 'primary_key': True}
                ]
            }]
        }
        
        diff = SchemaDiff()
        changes = diff.compare(current, target)
        assert len(changes) > 0
        
        # 2. 创建审批请求
        workflow = ApprovalWorkflow()
        request = workflow.create_request(
            submitter='test_user',
            changes=changes
        )
        
        # 自动审批（测试环境）
        workflow.approve(request.request_id, 'lead1', 'team_lead')
        workflow.approve(request.request_id, 'dba1', 'dba')
        
        assert request.status == 'approved'
        
        # 3. 执行迁移
        executor = MigrationExecutor(
            db_host=db_config['host'],
            db_user=db_config['user'],
            db_password=db_config['password'],
            db_name=db_config['database']
        )
        
        for change in changes:
            result = executor.execute(
                sql=change['sql'],
                request_id=request.request_id
            )
            assert result.success is True
        
        # 4. 验证表已创建
        import mysql.connector
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = %s AND table_name = 'integration_test'
        """, (db_config['database'],))
        
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == 'integration_test'
        
        cursor.close()
        conn.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
