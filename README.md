# 🚀 Database Release System - 企业级数据库声明式发布系统

> _让数据库变更像代码一样可管理、可追溯、可回滚_

[![Tests](https://img.shields.io/badge/tests-12%20passed-brightgreen)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()
[![Python](https://img.shields.io/badge/python-3.8+-blue)]()
[![MySQL](https://img.shields.io/badge/mysql-8.0+-orange)]()

---

## 📖 快速导航

| 文档 | 说明 | 适合人群 |
|------|------|---------|
| [🚀 快速开始](docs/QUICKSTART.md) | 5 分钟上手指南 | 所有人 |
| [📝 命令速查](docs/CHEATSHEET.md) | 常用命令一页纸 | 开发/运维 |
| [📦 部署指南](docs/DEPLOYMENT.md) | 完整部署步骤 | 运维 |
| [❓ 常见问题](docs/FAQ.md) | FAQ 与故障排查 | 所有人 |

---

## 🎯 这个系统能帮你什么？

| 痛点 | 解决方案 |
|------|---------|
| ❌ 环境不一致，上线就报错 | ✅ 声明式管理，自动对比差异 |
| ❌ 随便改表结构，没人知道 | ✅ 所有变更走审批，全程留痕 |
| ❌ 高危 SQL 误删库 | ✅ 自动识别高危，DBA 必审 |
| ❌ 出问题不知道谁改的 | ✅ 完整审计日志，可追溯回滚 |

---

## ⚡ 3 分钟快速体验

### 步骤 1: 安装依赖

```bash
git clone git@github.com:Verkaka/database-release-system.git
cd database-release-system
pip3 install mysql-connector-python pyyaml
```

### 步骤 2: 启动测试数据库

```bash
docker run -d --name db-test \
  -e MYSQL_ROOT_PASSWORD=test123 \
  -e MYSQL_DATABASE=test_db \
  -p 3306:3306 \
  mysql:8.0
```

### 步骤 3: 执行第一个变更

```bash
python3 scripts/migration_executor.py \
  --input <(echo "CREATE TABLE users (id BIGINT PRIMARY KEY, email VARCHAR(255));") \
  --host localhost \
  --user root \
  --password test123 \
  --database test_db \
  --request-id DEMO-001
```

### 步骤 4: 验证结果

```bash
mysql -h localhost -u root -ptest123 test_db -e "DESC users;"
```

---

## 🏗️ 核心功能

### 1. 声明式 Schema 管理

用 YAML 定义表结构，版本控制，自动对比：

```yaml
# schema/prod/users.yaml
version: "1.0"
tables:
  - name: users
    columns:
      - name: id
        type: BIGINT UNSIGNED
        primary_key: true
      - name: email
        type: VARCHAR(255)
        unique: true
```

### 2. 多级审批流程

```
开发提交 → 组长审批 → DBA 审批（高危） → 运维执行
```

| 变更类型 | 风险 | 组长 | DBA |
|---------|------|------|-----|
| 新建表 | 🟢 | ✅ | ❌ |
| 添加字段 | 🟢 | ✅ | ❌ |
| 创建索引 | 🟡 | ✅ | ✅ |
| 删除字段 | 🔴 | ✅ | ✅ |

### 3. 蓝鲸 CI/CD 集成

```yaml
# ci/blueking-ci.yml
pipeline:
  stages:
    - schema_validate
    - generate_diff
    - risk_assessment
    - create_approval
    - wait_approval
    - deploy_staging
    - manual_production
```

### 4. 审计与回滚

- 所有变更记入 `schema_migrations` 表
- 自动生成回滚 SQL
- 支持一键回滚

---

## 📁 项目结构

```
database-release-system/
├── docs/                    # 📚 文档
│   ├── QUICKSTART.md       # 快速开始
│   ├── CHEATSHEET.md       # 命令速查
│   ├── DEPLOYMENT.md       # 部署指南
│   └── FAQ.md              # 常见问题
├── schema/                  # 📋 Schema 定义
│   ├── dev/
│   ├── test/
│   └── prod/
├── scripts/                 # 🔧 核心脚本
│   ├── schema_diff.py      # Schema 对比
│   ├── migration_executor.py  # 迁移执行
│   └── init_log_table.sql  # 初始化脚本
├── workflows/               # 🔄 工作流
│   └── approval_workflow.py # 审批流程
├── ci/                      # 🚀 CI/CD
│   └── blueking-ci.yml     # 蓝鲸流水线
└── test/                    # 🧪 测试
    ├── test_all.py         # 单元测试
    └── TEST_REPORT.md      # 测试报告
```

---

## 📊 测试结果

| 测试类型 | 用例数 | 通过率 |
|---------|--------|--------|
| 单元测试 | 7/7 | 100% |
| 集成测试 | 5/5 | 100% |
| **总计** | **12/12** | **100%** |

详细报告：[test/TEST_REPORT.md](test/TEST_REPORT.md)

---

## 👥 角色说明

| 角色 | 职责 | 常用操作 |
|------|------|---------|
| 👨‍💻 开发 | 提交变更 | 修改 Schema → 提交审批 |
| 👔 组长 | 审核变更 | 审批通过/拒绝 |
| 🛡️ DBA | 审核高危 SQL | 审核 DROP、索引等 |
| 🔧 运维 | 执行上线 | 确认并执行生产变更 |

---

## 🛠️ 技术栈

- **Python 3.8+** - 核心语言
- **MySQL 8.0+** - 目标数据库
- **蓝鲸 CI/CD** - 流水线引擎
- **YAML/JSON** - 配置格式
- **Docker** - 测试环境

---

## 📞 获取帮助

| 问题类型 | 联系方式 |
|---------|---------|
| 技术问题 | @GoldenTechDEVBot |
| 产品需求 | @GoldenTechPMBot |
| 测试问题 | @GoldenTechQABot |

---

## 📄 License

MIT License

---

_最后更新：2026-03-05 | 版本：v1.0.0_
