# 📝 命令速查表

_常用命令一页纸_

---

## 🔧 日常开发

### 生成变更计划

```bash
python3 scripts/schema_diff.py \
  --current current_schema.json \
  --target schema/prod/users.yaml \
  --output changes.json
```

### 查看变更内容

```bash
cat changes.json | python3 -m json.tool
```

### 干跑测试（不实际执行）

```bash
python3 scripts/migration_executor.py \
  --input migration.sql \
  --host localhost \
  --user root \
  --password <password> \
  --database test_db \
  --dry-run
```

---

## ✅ 审批操作

### 审批通过

```bash
python3 workflows/approve.py \
  --request-id DB-12345678 \
  --action approve \
  --role team_lead \
  --approver zhangsan \
  --comment "同意上线"
```

### 审批拒绝

```bash
python3 workflows/approve.py \
  --request-id DB-12345678 \
  --action reject \
  --role team_lead \
  --approver zhangsan \
  --comment "需要补充索引"
```

### 查看审批状态

```bash
python3 workflows/status.py --request-id DB-12345678
```

---

## 🚀 执行变更

### 执行迁移

```bash
python3 scripts/migration_executor.py \
  --input migration.sql \
  --host prod-db.internal \
  --user deploy_user \
  --password <password> \
  --database prod_db \
  --request-id DB-12345678
```

### 回滚变更

```bash
python3 scripts/migration_executor.py \
  --request-id DB-12345678 \
  --action rollback \
  --host prod-db.internal \
  --user deploy_user \
  --password <password> \
  --database prod_db
```

### 查看迁移历史

```bash
mysql -h <host> -u <user> -p <database> -e \
  "SELECT request_id, status, executed_at, executed_by FROM schema_migrations ORDER BY executed_at DESC LIMIT 10;"
```

---

## 🔍 故障排查

### 检查表是否存在

```bash
mysql -h <host> -u <user> -p <database> -e \
  "SHOW TABLES LIKE 'schema_migrations';"
```

### 查看表结构

```bash
mysql -h <host> -u <user> -p <database> -e \
  "DESC schema_migrations;"
```

### 查看未完成的审批

```bash
python3 workflows/list.py --status pending
```

### 查看高危变更

```bash
python3 scripts/risk_check.py --input changes.json --output risk_report.json
cat risk_report.json | python3 -m json.tool
```

---

## 📊 环境配置

### 测试环境连接

```bash
export DB_HOST=staging-db.internal
export DB_USER=deploy_user
export DB_PASSWORD=<password>
export DB_NAME=staging_db
```

### 生产环境连接

```bash
export DB_HOST=prod-db.internal
export DB_USER=deploy_user
export DB_PASSWORD=<password>
export DB_NAME=prod_db
```

---

## 🐳 Docker 测试

### 启动测试数据库

```bash
docker run -d --name db-test \
  -e MYSQL_ROOT_PASSWORD=test123 \
  -e MYSQL_DATABASE=test_db \
  -e MYSQL_USER=test_user \
  -e MYSQL_PASSWORD=test123 \
  -p 3306:3306 \
  mysql:8.0
```

### 停止测试数据库

```bash
docker stop db-test && docker rm db-test
```

### 连接测试数据库

```bash
mysql -h 127.0.0.1 -P 3306 -u test_user -ptest123 test_db
```

---

## 📋 Schema 文件模板

### 新建表

```yaml
version: "1.0"
database: my_db
environment: prod

tables:
  - name: table_name
    description: 表描述
    columns:
      - name: id
        type: BIGINT UNSIGNED
        primary_key: true
        auto_increment: true
        comment: "主键 ID"
      
      - name: column_name
        type: VARCHAR(255)
        not_null: true
        default: ''
        comment: "字段描述"
    
    indexes:
      - name: idx_column
        columns: [column_name]
        type: UNIQUE
        comment: "索引描述"
```

### 添加字段

```yaml
# 在现有表中添加字段
tables:
  - name: existing_table
    columns:
      - name: id
        type: BIGINT
      
      # 新增字段
      - name: new_column
        type: VARCHAR(100)
        not_null: false
        comment: "新增字段"
```

---

## ⚠️ 风险等级参考

| 操作 | 风险等级 | 审批要求 |
|------|---------|---------|
| CREATE TABLE | 🟢 低危 | 组长 |
| ADD COLUMN | 🟢 低危 | 组长 |
| CREATE INDEX | 🟡 中等 | 组长 + DBA |
| DROP INDEX | 🟡 中等 | 组长 + DBA |
| DROP COLUMN | 🔴 高危 | 组长 + DBA |
| DROP TABLE | 🔴 高危 | 组长 + DBA |
| MODIFY COLUMN | 🔴 高危 | 组长 + DBA |

---

_最后更新：2026-03-05_
