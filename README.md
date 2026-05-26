# 多巴胺美食点餐系统 🍽️

一个界面活泼、功能完整的 Web 点餐系统，适用于小团队 / 家庭 / 办公室内部点餐场景。

## 功能概览

- **用户系统** — 注册、登录、个人中心、头像上传、密码修改
- **菜品浏览** — 分类筛选、菜品网格展示，支持图片和 Emoji
- **购物车** — 底部折叠栏 + 展开面板，数量增减，sessionStorage 持久化
- **下单结算** — 提交订单，支持 QQ 邮箱通知商家
- **幸运轮盘** — 选择困难症救星，Canvas 转盘随机选菜
- **管理员功能** — 菜品 CRUD、图片上传、价格微调、拖拽排序
- **订单历史** — 侧栏展示所有订单记录
- **流水热力图** — 年度每日营收 GitHub 风格热力日历
- **双存储模式** — 优先 MySQL，连接失败自动降级为 JSON 文件存储

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | Flask 3.0 |
| 数据库 | MySQL（JSON 文件备用） |
| 前端 | 原生 HTML / CSS / JavaScript |
| WSGI | Gunicorn（生产环境） |
| 密码 | Werkzeug 哈希 |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirement.txt
```

### 2. 配置数据库（可选）

默认连接本地 MySQL，可通过环境变量自定义：

| 环境变量 | 默认值 |
|----------|--------|
| `MYSQL_HOST` | `localhost` |
| `MYSQL_PORT` | `3306` |
| `MYSQL_USER` | `root` |
| `MYSQL_PASSWORD` | (空) |
| `MYSQL_DATABASE` | `dopamine_foodie` |

> 如果 MySQL 不可用，系统会自动使用 `data/` 目录下的 JSON 文件作为存储，无需额外配置。

### 3. 启动

```bash
python main.py
```

访问 http://localhost:5000 ，注册账号即可开始使用。

### 4. 管理员

手动将 `data/users.json`（或 MySQL `users` 表）中用户的 `role` 改为 `admin` 即可获得管理权限。

## 邮箱通知配置

管理员登录后，点击"邮箱设置"，填入 QQ 邮箱和 SMTP 授权码。配置后，用户下单时会自动发送通知邮件。

## 项目结构

```
├── main.py              # 应用入口，Flask 初始化
├── config.py            # 全局配置（密钥、数据库、路径）
├── database.py          # 数据层（MySQL + JSON 双模式）
├── utils.py             # 工具（密码哈希、邮件、权限装饰器）
├── requirement.txt      # 依赖
├── routes/
│   ├── __init__.py
│   ├── pages.py         # 页面路由
│   └── api.py           # REST API 接口
├── templates/
│   ├── login.html       # 登录注册页
│   ├── menu.html        # 主菜单页（点餐、购物车、订单历史）
│   └── wheel.html       # 幸运轮盘页
├── static/
│   ├── css/style.css    # 全局样式
│   ├── images/          # 菜品图片上传目录
│   └── avatars/         # 用户头像上传目录
└── data/                # JSON 数据目录（备用存储）
    ├── users.json
    ├── menu.json
    ├── orders.json
    └── config.json
```

## 生产部署

```bash
gunicorn main:app -w 4 -b 0.0.0.0:5000
```
