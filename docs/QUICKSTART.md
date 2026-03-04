# 🚀 快速开始指南

_5 分钟上手企业级数据库发布系统_

---

## 📋 这个系统能帮你什么？

| 以前的问题 | 现在的解决方案 |
|-----------|--------------|
| ❌ 环境不一致，上线就报错 | ✅ 声明式管理，自动对比差异 |
| ❌ 随便改表结构，没人知道 | ✅ 所有变更走审批，全程留痕 |
| ❌ 高危 SQL 误删库 | ✅ 自动识别高危操作，DBA 必审 |
| ❌ 出问题不知道谁改的 | ✅ 完整审计日志，可追溯可回滚 |

---

## 🎯 角色说明

| 角色 | 职责 | 常用操作 |
|------|------|---------|
| 👨‍💻 **开发** | 提交表结构变更 | 修改 Schema → 提交审批 |
| 👔 **组长** | 审核所有变更 | 审批通过/拒绝 |
| 🛡️ **DBA** | 审核高危 SQL | 审核 DROP、TRUNCATE 等 |
| 🔧 **运维** | 执行生产变更 | 确认并执行上线 |

---

## 📦 安装部署（运维看这里）

### 前置条件

```bash
# 检查 Python 版本
python3 --version  # 需要 3.8+

# 检查 MySQL 版本
mysql --version    # 需要 8.0+

# 检查 Docker（可选，用于测试）
docker --version
```

### 步骤 1: 克隆代码

```bash
git clone git@github.com:Verkaka/database-release-system.git
cd database-release-system
```

### 步骤 2: 安装依赖

```bash
pip3 install mysql-connector-python pyyaml
```

### 步骤 3: 配置环境

创建配置文件 `config/environments.yaml`:

```yaml
environments:
  dev:
    host: localhost
    port: 3306
    database: dev_db
    user: dev_user
    password: dev_password
  
  staging:
    host: staging-db.internal
    port: 3306
    database: staging_db
    user: deploy_user
    password: ${DB_PASSWORD}  # 从环境变量读取
  
  prod:
    host: prod-db.internal
    port: 3306
    database: prod_db
    user: deploy_user
    password: ${DB_PASSWORD}
```

### 步骤 4: 初始化数据库

在每个环境执行：

```bash
mysql -h <host> -u <user> -p <database> < scripts/init_log_table.sql
```

---

## 👨‍💻 开发使用指南

### 场景 1: 新建一张表

**第 1 步**: 在 `schema/prod/` 下创建文件 `users.yaml`

```yaml
version: "1.0"
database: production_db
environment: prod

tables:
  - name: users
    description: 用户表
    columns:
      - name: id
        type: BIGINT UNSIGNED
        primary_key: true
        auto_increment: true
        comment: "用户 ID"
      
      - name: email
        type: VARCHAR(255)
        not_null: true
        unique: true
        comment: "邮箱"
      
      - name: created_at
        type: TIMESTAMP
        default: CURRENT_TIMESTAMP
        comment: "创建时间"
```

**第 2 步**: 生成变更计划

```bash
python3 scripts/schema_diff.py \
  --current current_schema.json \
  --target schema/prod/users.yaml \
  --output changes.json
```

**第 3 步**: 提交审批

系统会自动创建审批请求，通知组长审批。

**第 4 步**: 等待审批通过后，运维执行上线

---

### 场景 2: 给现有表加字段

**第 1 步**: 修改已有的 Schema 文件

```yaml
# 在 users.yaml 中添加字段
columns:
  - name: id
    type: BIGINT UNSIGNED
    primary_key: true
  
  # 新增字段 👇
  - name: phone
    type: VARCHAR(20)
    not_null: false
    comment: "手机号"
```

**第 2 步**: 生成变更并提交

```bash
python3 scripts/schema_diff.py \
  --current current_schema.json \
  --target schema/prod/users.yaml \
  --output changes.json
```

系统会自动生成：
```sql
ALTER TABLE `users` ADD COLUMN `phone` VARCHAR(20);
```

---

### 场景 3: 创建索引

**第 1 步**: 在表定义中添加索引

```yaml
tables:
  - name: users
    columns: [...]
    indexes:
      - name: idx_email
        columns: [email]
        type: UNIQUE
        comment: "邮箱唯一索引"
```

**第 2 步**: 提交审批

⚠️ **注意**: 创建索引属于**中等风险**操作，需要 DBA 审批。

---

## 👔 组长审批指南

### 收到审批通知后

**第 1 步**: 查看变更内容

```bash
cat changes.json
```

或查看审批系统 Web 界面（待开发）

**第 2 步**: 确认变更合理性

检查清单：
- [ ] 变更是否符合业务需求
- [ ] 字段命名是否规范
- [ ] 是否影响现有功能

**第 3 步**: 审批操作

```bash
# 审批通过
python3 workflows/approve.py --request-id DB-12345678 --action approve --comment "同意"

# 拒绝
python3 workflows/approve.py --request-id DB-12345678 --action reject --comment "需要补充说明"
```

---

## 🛡️ DBA 审批指南

### 什么变更需要你审批？

| 风险等级 | 操作类型 | 是否需要 DBA |
|---------|---------|------------|
| 🔴 高危 | DROP TABLE、TRUNCATE、DELETE | ✅ 必须 |
| 🔴 高危 | 删除字段、修改字段类型 | ✅ 必须 |
| 🟡 中等 | 创建/删除索引 | ✅ 必须 |
| 🟢 低危 | 新建表、添加字段 | ❌ 不需要 |

### 审批检查清单

- [ ] SQL 是否有性能问题
- [ ] 是否会影响线上服务
- [ ] 是否有回滚方案
- [ ] 是否需要在低峰期执行

---

## 🔧 运维执行指南

### 测试环境执行

审批通过后，自动执行：

```bash
# 蓝鲸 CI 自动执行
python3 scripts/migration_executor.py \
  --input migration.sql \
  --host staging-db.internal \
  --user deploy_user \
  --database staging_db
```

### 生产环境执行

**第 1 步**: 收到执行通知

**第 2 步**: 下载迁移脚本

```bash
# 从审批系统下载
wget https://approval-system/api/migration/DB-12345678.sql
```

**第 3 步**: 确认变更内容

```bash
cat DB-12345678.sql
```

**第 4 步**: 执行变更

```bash
mysql -h prod-db.internal -u deploy_user -p prod_db < DB-12345678.sql
```

**第 5 步**: 确认执行成功

```bash
# 检查表结构
mysql -h prod-db.internal -u deploy_user -p prod_db -e "DESC users;"

# 更新审批状态
python3 workflows/complete.py --request-id DB-12345678
```

---

## 🔍 常见问题

### Q1: 如何查看历史变更？

```bash
mysql -h <host> -u <user> -p <database> -e "SELECT * FROM schema_migrations ORDER BY executed_at DESC LIMIT 10;"
```

### Q2: 如何回滚变更？

```bash
python3 scripts/migration_executor.py \
  --request-id DB-12345678 \
  --action rollback \
  --host <host> \
  --user <user> \
  --database <database>
```

### Q3: 如何判断风险等级？

系统自动判断规则：

```python
高危操作：DROP, TRUNCATE, DELETE FROM, 删除字段，修改字段类型
中等风险：创建/删除索引
低危操作：新建表，添加字段
```

### Q4: 审批超时怎么办？

默认审批超时时间：**72 小时**

超时后：
- 系统自动拒绝请求
- 通知提交人重新提交
- 记录超时日志

---

## 📞 获取帮助

| 问题类型 | 联系方式 |
|---------|---------|
| 技术问题 | @GoldenTechDEVBot |
| 产品需求 | @GoldenTechPMBot |
| 测试问题 | @GoldenTechQABot |

---

## 📚 更多文档

- [完整 API 文档](API.md)
- [部署指南](DEPLOYMENT.md)
- [故障排查](TROUBLESHOOTING.md)
- [最佳实践](BEST_PRACTICES.md)

---

_最后更新：2026-03-05_  
_版本：v1.0.0_
