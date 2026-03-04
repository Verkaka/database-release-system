# Database Release System - 企业级数据库声明式发布系统

基于 Atlas 和 Bytebase 理念设计的企业级数据库发布流程，支持 MySQL 声明式管理、多级审批、蓝鲸 CI/CD 集成。

## 功能特性

- ✅ **声明式 Schema 管理** - 使用 YAML/SQL 定义期望状态
- ✅ **自动变更对比** - 智能生成迁移计划
- ✅ **多级审批流程** - 组长审批 + DBA 审批（高危 SQL）
- ✅ **风险评估** - 自动识别高危操作
- ✅ **蓝鲸 CI/CD 集成** - 自动化发布流水线
- ✅ **审计追溯** - 完整执行日志，支持回滚

## 目录结构

```
database-release-system/
├── schema/                 # Schema 定义
│   ├── dev/               # 开发环境
│   ├── test/              # 测试环境
│   └── prod/              # 生产环境
├── scripts/               # 核心脚本
│   ├── schema_diff.py     # Schema 对比引擎
│   ├── migration_executor.py  # 迁移执行器
│   ├── validate_schema.py # Schema 验证
│   └── risk_check.py      # 风险评估
├── workflows/             # 工作流
│   └── approval_workflow.py  # 审批流程引擎
├── ci/                    # CI/CD 配置
│   └── blueking-ci.yml    # 蓝鲸流水线
├── config/                # 配置文件
│   └── environments.yaml  # 环境配置
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
pip install mysql-connector-python pyyaml
```

### 2. 配置环境

编辑 `config/environments.yaml`:

```yaml
environments:
  dev:
    host: localhost
    port: 3306
    database: dev_db
    user: dev_user
  
  staging:
    host: staging-db.internal
    port: 3306
    database: staging_db
    user: deploy_user
  
  prod:
    host: prod-db.internal
    port: 3306
    database: prod_db
    user: deploy_user
```

### 3. 定义 Schema

在 `schema/prod/` 下创建 YAML 文件:

```yaml
version: "1.0"
database: production_db
environment: prod

tables:
  - name: users
    columns:
      - name: id
        type: BIGINT UNSIGNED
        primary_key: true
        auto_increment: true
      - name: email
        type: VARCHAR(255)
        unique: true
        not_null: true
```

### 4. 生成变更计划

```bash
python scripts/schema_diff.py \
  --current current_schema.json \
  --target schema/prod/users.yaml \
  --output changes.json
```

### 5. 执行迁移

```bash
python scripts/migration_executor.py \
  --input migration.sql \
  --host prod-db.internal \
  --user deploy_user \
  --database prod_db \
  --request-id DB-12345678
```

### 6. 蓝鲸 CI/CD 集成

将 `ci/blueking-ci.yml` 部署到蓝鲸 CI 平台，配置以下环境变量:

- `DB_HOST_STAGING` - 测试环境数据库地址
- `DB_HOST_PROD` - 生产环境数据库地址
- `DB_USER` - 数据库用户
- `APPROVAL_API_TOKEN` - 审批系统 API Token
- `NOTIFY_WEBHOOK` - 通知 Webhook 地址

## 审批流程

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌─────────────┐
│  开发提交    │ →  │  蓝鲸 CI      │ →  │  审批系统    │ →  │  运维执行    │
│  Schema     │    │  自动检查     │    │  组长/DBA   │    │  生产环境    │
└─────────────┘    └──────────────┘    └─────────────┘    └─────────────┘
```

### 审批规则

| 变更类型 | 风险等级 | 组长审批 | DBA 审批 | 运维执行 |
|---------|---------|---------|---------|---------|
| 新建表   | LOW     | ✅      | ❌      | ✅      |
| 添加字段 | LOW     | ✅      | ❌      | ✅      |
| 创建索引 | MEDIUM  | ✅      | ✅      | ✅      |
| 删除字段 | HIGH    | ✅      | ✅      | ✅      |
| DROP TABLE | HIGH  | ✅      | ✅      | ✅      |

## 使用示例

### 创建审批请求

```python
from workflows.approval_workflow import ApprovalWorkflow

workflow = ApprovalWorkflow({
    'approval_chain': ['team_lead', 'dba'],
    'dba_required_for_risk': ['high', 'medium'],
    'approvers': {
        'team_lead': ['lead1', 'lead2'],
        'dba': ['dba1'],
        'ops': ['ops1']
    }
})

# 创建请求
request = workflow.create_request(
    submitter='dev1',
    submitter_name='张三',
    changes=[
        {'type': 'CREATE', 'target': 'TABLE users', 'risk': 'low'}
    ]
)

# 审批
workflow.approve(request.request_id, 'lead1', 'team_lead', '同意')
workflow.approve(request.request_id, 'dba1', 'dba', '已审核')

# 执行
workflow.execute(request.request_id, 'ops1')
```

### Schema 对比

```python
from scripts.schema_diff import SchemaDiff, load_schema_from_file

# 加载 Schema
current = load_schema_from_file('current_schema.json')
target = load_schema_from_file('schema/prod/users.yaml')

# 执行对比
diff = SchemaDiff()
changes = diff.compare(current, target)

# 输出变更
for change in changes:
    print(f"[{change['risk'].upper()}] {change['type']}: {change['description']}")
```

## 安全与审计

- 所有变更自动记录到 `schema_migrations` 表
- 支持回滚操作（自动生成立即回滚 SQL）
- 高危操作强制 DBA 审批
- 生产环境变更必须运维手动执行

## 技术栈

- **Python 3.8+** - 核心脚本语言
- **MySQL 8.0+** - 目标数据库
- **蓝鲸 CI/CD** - 流水线引擎
- **YAML/JSON** - 配置格式

## 开发团队

- **产品**: @GoldenTechPMBot
- **开发**: @GoldenTechDEVBot
- **测试**: @GoldenTechQABot

## License

MIT License
