# X Monitor - Alfred Workflow

自动获取 X (Twitter) 上特定账号的发文并推送通知到 macOS 电脑。

## 功能特点

- 监控多个 X/Twitter 账号的新推文
- 自动发送 macOS 系统通知
- 支持后台自动定时检查
- 无需 Twitter API 密钥（使用 Nitter 公共实例）
- 通过 Alfred 快捷命令管理

## 安装

1. 下载 `X Monitor.alfredworkflow` 文件
2. 双击安装到 Alfred
3. 运行 `setup.sh` 脚本启用后台自动检查（可选）

## Alfred 命令

| 命令 | 说明 |
|------|------|
| `xcheck` | 立即检查所有监控账号的新推文 |
| `xadd @username` | 添加要监控的账号 |
| `xremove @username` | 移除监控的账号 |
| `xlist` | 列出所有监控的账号 |

## 命令行使用

```bash
# 检查所有账号
python3 x_monitor.py

# 添加账号
python3 x_monitor.py --add @elonmusk

# 移除账号
python3 x_monitor.py --remove @elonmusk

# 列出所有账号
python3 x_monitor.py --list

# 只检查特定账号
python3 x_monitor.py --check @elonmusk

# 设置检查间隔（分钟）
python3 x_monitor.py --set-interval 10

# 设置 Nitter 实例
python3 x_monitor.py --set-nitter https://nitter.poast.org
```

## 后台自动检查

运行 `setup.sh` 脚本会安装 launchd 服务，每 5 分钟自动检查一次新推文：

```bash
chmod +x setup.sh
./setup.sh
```

停止后台服务：
```bash
launchctl unload ~/Library/LaunchAgents/com.alfred.x-monitor.plist
```

查看日志：
```bash
tail -f /tmp/x-monitor.log
```

## 配置文件

配置文件 `config.json` 位于脚本同目录下：

```json
{
  "accounts": ["elonmusk", "OpenAI"],
  "check_interval_minutes": 5,
  "max_notifications_per_check": 5,
  "nitter_instance": "https://nitter.poast.org",
  "notification_sound": "default"
}
```

## 工作原理

本工具使用 [Nitter](https://github.com/zedeus/nitter) 实例的 RSS 订阅功能来获取 Twitter/X 账号的推文，无需 Twitter API 密钥。Nitter 是一个开源的、注重隐私的 Twitter 前端。

## 重要说明

由于 Twitter/X 在 2023 年后大幅限制了 API 访问，目前获取推文数据的方式有以下几种：

1. **Nitter 公共实例**（本工具默认方式）- 免费但可能不稳定，部分实例有 Cloudflare 保护
2. **自建 Nitter 实例** - 最可靠的方式，需要一定技术能力
3. **Twitter 官方 API** - 需要开发者账号，基础版 $100/月

### 推荐：自建 Nitter 实例

如果公共实例不可用，建议自建 Nitter 实例：

```bash
# 使用 Docker 快速部署
docker run -d --name nitter -p 8080:8080 zedeus/nitter
```

然后配置本工具使用本地实例：
```bash
python3 x_monitor.py --set-nitter http://localhost:8080
```

详细部署指南：https://github.com/zedeus/nitter/wiki/Docker

## 注意事项

- 需要 Python 3.6+
- 需要 macOS 系统（用于系统通知）
- 公共 Nitter 实例可能有速率限制或被 Cloudflare 保护
- 建议自建 Nitter 实例以获得最佳体验

## 故障排除

**问题：无法获取推文（403 Forbidden 或 Bot Protection）**
- 公共 Nitter 实例可能被 Cloudflare 保护
- 尝试更换其他 Nitter 实例：`python3 x_monitor.py --set-nitter https://xcancel.com`
- 查看可用实例列表：https://status.d420.de/
- 最佳方案：自建 Nitter 实例

**问题：没有收到通知**
- 确保 macOS 系统通知已开启
- 检查 `/tmp/x-monitor.log` 日志文件

## 许可证

MIT License
