# GPT-Register-Tool 中文使用说明

GPT-Register-Tool 是一个本地 ChatGPT 邮箱注册、会话保存、PayPal/GoPay 支付链接和支付状态管理工具。当前主链路是：

```text
邮箱来源 -> ChatGPT 邮箱 OTP 注册 -> /api/auth/session access_token
-> PayPal/GoPay 支付链接或协议支付 -> session JSON + SQLite 索引 -> WPF 管理界面
```

本项目不要求固定机器路径。默认运行数据放在 `sessions/` 和 `runtime/`，本地配置放在 `config.json`，这些文件不应提交到 Git。

## 快速开始

1. 安装 Python 依赖。

```powershell
python -m pip install -r requirements.txt
```

2. 创建本地配置。

```powershell
Copy-Item config.example.json config.json
```

3. 编辑 `config.json`。

最少需要确认这些配置：

- `proxy.default`：默认代理，建议写 `socks5h://127.0.0.1:7897` 这类本地代理监听；不走代理时可写 `direct` 或留空，具体命令也可以用 `--proxy` 覆盖。
- `email_registration.token_file`：邮箱池文件，默认 `mailbox_tokens.txt`。
- `paypal.billing_regions`：PayPal/Stripe 链接生成的账单地区，PayPal 原始路径通常用 `["US"]`。
- `paypal.proxies` / `paypal.stage_proxies`：PayPal 链接生成代理池和分阶段代理。
- `paypal_nocard.enabled`：是否允许 PayPal no-card 一键支付命令运行。
- `paypal_auto.cards`：no-card 支付使用的卡池 JSON 数组。
- `paypal_auto.addresses`：no-card 支付使用的账单地址 JSON 数组。
- `paypal_nocard.phone_pool`：no-card 支付接码手机号池 JSON 数组。
- `storage.sqlite_path`：SQLite 索引路径，默认 `runtime/accounts.sqlite3`。
- `output.directory`：session JSON 输出目录，默认 `sessions`。

4. 跑一次注册。

```powershell
python chatgpt_phone_reg.py --count 1
```

5. 构建并启动桌面 UI。

```powershell
powershell -ExecutionPolicy Bypass -File .\SmsWorkbench\build_dotnet.ps1
.\dist\net10\SmsWorkbench.exe
```

也可以直接开发构建：

```powershell
dotnet build SmsWorkbench\SmsWorkbench.csproj
```

## 配置文件位置

CLI 会按顺序查找：

1. 当前工作目录的 `config.json`
2. 项目根目录的 `config.json`
3. `sms_tool/config.json`

建议始终在项目根目录运行命令，并只维护项目根目录的 `config.json`。

`config.example.json` 只放占位示例；真实代理、API token、邮箱 token、卡池、手机号池只放 `config.json`。

## 代理配置

### 默认代理

`proxy.default` 是大多数注册、邮箱、刷新、支付链接命令的默认代理：

```json
{
  "proxy": {
    "default": "socks5h://127.0.0.1:7897",
    "pool": [
      "socks5h://127.0.0.1:7897"
    ]
  }
}
```

命令行传 `--proxy` 时会覆盖默认代理：

```powershell
python chatgpt_phone_reg.py --count 1 --proxy socks5h://127.0.0.1:7897
```

### PayPal 链接生成代理

PayPal/Stripe 链接生成读取 `paypal.proxies` 和 `paypal.stage_proxies`：

```json
{
  "paypal": {
    "proxies": [
      "socks5h://127.0.0.1:7897"
    ],
    "stage_proxies": {
      "checkout": "socks5h://127.0.0.1:7897",
      "stripe_init": "socks5h://127.0.0.1:7897",
      "payment_method": "socks5h://127.0.0.1:7897",
      "confirm": "direct"
    }
  }
}
```

`direct` 表示该阶段不使用代理；空字符串会被忽略。

如果某次必须强制用指定代理重新生成 PayPal 链接：

```powershell
python chatgpt_phone_reg.py --email user@example.com --regenerate-paypal-link --proxy socks5h://127.0.0.1:7897
```

### PayPal no-card 代理

PayPal no-card 签约遇到 DataDome 时会按顺序尝试代理：

```text
命令行 --proxy -> paypal_nocard.proxies -> paypal.proxies -> paypal.stage_proxies.checkout -> proxy.default -> proxy.pool
```

建议给 `paypal_nocard.proxies` 放多个干净出口：

```json
{
  "paypal_nocard": {
    "proxies": [
      "socks5h://127.0.0.1:7897",
      "socks5h://127.0.0.1:7898"
    ]
  }
}
```

只有一个本地出口时，DataDome 拦截通常无法靠重试解决，需要换干净 IP 或启用浏览器接管。

### Clash Verge 示例

在 Clash Verge 或其他本地代理客户端里创建本地监听，然后让 `config.json` 指向该监听端口。示例形状：

```yaml
listeners:
  - name: checkout-exit
    type: mixed
    port: 7897
    proxy: Selected-Exit
```

常见路由规则形状：

```yaml
rules:
  - DOMAIN-SUFFIX,stripe.com,Selected-Exit
  - DOMAIN-SUFFIX,stripe.network,Selected-Exit
  - DOMAIN-SUFFIX,openai.com,Selected-Exit
  - DOMAIN-SUFFIX,chatgpt.com,Selected-Exit
  - DOMAIN-SUFFIX,paypal.com,Selected-Exit
```

### 代理验证

不跑真实支付，只检查 PayPal 代理配置：

```powershell
python -m sms_tool.gen_pp_link --dry-run
```

检查本地 SOCKS5 出口：

```powershell
curl.exe --proxy socks5h://127.0.0.1:7897 https://ipinfo.io/json
```

如果本地监听不可达，先修代理客户端；重复跑注册或支付不会修好代理端口。

## 邮箱配置

### Microsoft Graph/OAuth 邮箱池

默认邮箱池文件是 `mailbox_tokens.txt`，每行格式：

```text
email---password---refresh_token---access_token---0
```

说明：

- `email` 是邮箱地址。
- `password` 可以为空，但建议保留字段位置。
- `refresh_token` 必填，用于读取 Microsoft Graph 邮件。
- `access_token` 可为空；程序会用 refresh token 换新 token。
- 最后的 `---0` 是兼容字段，可以保留。

示例：

```text
user1@hotmail.com---Password123---M.C123...refresh...---eyJ0eXAi...access...---0
user2@outlook.com---Password456---M.C456...refresh...------0
```

指定邮箱池：

```powershell
python chatgpt_phone_reg.py --mailbox-file mailbox_tokens.txt --count 4 --workers 4
```

### Chatai 邮箱池

Chatai 文件每行格式：

```text
email----password----client_id----refresh_token
```

运行：

```powershell
python chatgpt_phone_reg.py --chatai-mailbox-file hotmail.txt --count 4 --workers 4
```

解析器接受 UTF-8 BOM，并会修复已知别名畸形：

```text
name@+aliasdomain.com -> name+alias@domain.com
```

### CFWorker 临时邮箱

配置：

```json
{
  "email_registration": {
    "cfworker_url": "https://your-worker.example.com",
    "cfworker_domain": "example.com",
    "cfworker_admin_token": "",
    "cfworker_api_token": "",
    "cfworker_poll_proxy": true,
    "cfworker_direct_fallback": false
  }
}
```

运行：

```powershell
python chatgpt_phone_reg.py --buy-cfworker-mailbox --cfworker-domain example.com --count 1
```

邮箱池里也可以直接放 CFWorker 邮箱：

```text
cfworker://user@example.com
user@example.com
```

### LuckMail

配置 API key 后可以购买或使用 LuckMail token 邮箱：

```json
{
  "email_registration": {
    "luckmail_api_key": "YOUR_API_KEY",
    "luckmail_base_url": "https://mails.luckyous.com",
    "luckmail_purchase_project_code": "openai",
    "luckmail_purchase_email_type": "ms_imap",
    "luckmail_purchase_domain": "outlook.com"
  }
}
```

购买并注册：

```powershell
python chatgpt_phone_reg.py --buy-luckmail-mailbox --count 1
```

使用已有 LuckMail token：

```powershell
python chatgpt_phone_reg.py --luckmail-token tok_xxx --count 1
```

## 注册命令

常规注册：

```powershell
python chatgpt_phone_reg.py --count 4 --workers 4 --proxy socks5h://127.0.0.1:7897
```

只注册并保存 ChatGPT access token，不跑 Codex OAuth/手机号验证：

```powershell
python chatgpt_phone_reg.py --count 1 --registration-at-only
```

跳过支付链接生成：

```powershell
python chatgpt_phone_reg.py --count 1 --skip-paypal-link
```

指定支付链接类型：

```powershell
python chatgpt_phone_reg.py --count 1 --payment-method paypal
python chatgpt_phone_reg.py --count 1 --payment-method gopay
```

重建 SQLite 索引：

```powershell
python chatgpt_phone_reg.py --rebuild-sqlite
```

查看最近邮箱邮件：

```powershell
python chatgpt_phone_reg.py --email user@example.com --view-inbox --inbox-limit 20
```

刷新已有 session：

```powershell
python chatgpt_phone_reg.py --email user@example.com --refresh-session
```

## 手机号复用和 Codex OAuth

`phone_reuse` 用于 OpenAI/Codex OAuth 手机验证。示例：

```json
{
  "phone_reuse": {
    "max_reuse_count": 3,
    "send_cooldown_seconds": 45,
    "send_retry_attempts": 3,
    "send_retry_delay_seconds": 45,
    "state_file": "runtime/phone_reuse_state.json",
    "smsbower": {
      "api_key": "$SMSBOWER_API_KEY",
      "service": "dr",
      "country": "38",
      "country_prefix": "+233",
      "pool_size": 1,
      "sms_timeout": 120,
      "sms_poll_interval": 5
    }
  }
}
```

运行 Codex OAuth 和手机号验证：

```powershell
python chatgpt_phone_reg.py --one-click-sms --email-file pending_emails.txt --proxy socks5h://127.0.0.1:7897
```

注册时启用手机号复用：

```powershell
python chatgpt_phone_reg.py --count 3 --phone-reuse --max-reuse-count 3
```

禁用手机号验证：

```powershell
python chatgpt_phone_reg.py --count 1 --no-phone-reuse
```

## PayPal 链接管理

列出保存的 PayPal/GoPay 链接：

```powershell
python chatgpt_phone_reg.py --list-paypal-links
```

打开某个账号的保存链接：

```powershell
python chatgpt_phone_reg.py --email user@example.com --open-paypal-link
```

重新生成 PayPal 链接：

```powershell
python chatgpt_phone_reg.py --email user@example.com --regenerate-paypal-link --payment-method paypal
```

批量重新生成：

```powershell
python chatgpt_phone_reg.py --email-file pending_emails.txt --regenerate-paypal-link --workers 4 --proxy socks5h://127.0.0.1:7897
```

标记支付状态：

```powershell
python chatgpt_phone_reg.py --email user@example.com --mark-paypal-status completed
python chatgpt_phone_reg.py --email-file paid_emails.txt --mark-paypal-status completed
```

## PayPal no-card 一键支付

no-card 支付不是默认注册流程的一部分，只有显式执行 `--one-click-pay` 时才会运行。它会读取已有账号的 `access_token`，生成或复用 PayPal approve URL，然后从卡池、地址池、手机号池各取一组资源完成 PayPal guest/no-card 签约。

### 必要配置

```json
{
  "paypal_nocard": {
    "enabled": true,
    "locale_country": "US",
    "locale_lang": "en",
    "otp_timeout": 180,
    "impersonate": "chrome136",
    "datadome_browser_seed": true,
    "datadome_browser_timeout": 300,
    "datadome_browser_headless": false,
    "proxies": [
      "socks5h://127.0.0.1:7897"
    ],
    "reuse_saved_url": false,
    "reuse_saved_ready_url": true,
    "saved_url_max_age_seconds": 1800,
    "fallback_to_saved_url": false,
    "phone_pool": [
      {
        "phone": "+10000000000",
        "sms_api_url": "https://sms.example.com/poll"
      }
    ],
    "card_index_file": "runtime/nocard_card_index.txt",
    "phone_index_file": "runtime/nocard_phone_index.txt"
  },
  "paypal_auto": {
    "cards": [
      {
        "number": "4111111111111111",
        "exp_month": "01",
        "exp_year": "2030",
        "cvv": "123"
      }
    ],
    "addresses": [
      {
        "line1": "123 Main St",
        "city": "New York",
        "state": "NY",
        "postal_code": "10001",
        "country": "US"
      }
    ]
  }
}
```

### 卡池格式

`paypal_auto.cards` 是 JSON 数组，每个元素需要：

- `number`：卡号。
- `exp_month`：两位月份，例如 `01`。
- `exp_year`：四位年份，例如 `2030`。
- `cvv`：三位安全码。

### 地址池格式

`paypal_auto.addresses` 是 JSON 数组，每个元素需要：

- `line1`：街道地址。
- `city`：城市。
- `state`：州缩写或州名；代码会把常见美国州名转成两位缩写。
- `postal_code`：邮编。
- `country`：国家代码，当前建议 `US`。

no-card 现在会用同一个卡索引从 `cards` 和 `addresses` 同步取值，所以第 1 张卡配第 1 个地址，第 2 张卡配第 2 个地址。如果地址数量少于卡数量，会按取模轮询。

### 手机池格式

`paypal_nocard.phone_pool` 是 JSON 数组，每个元素需要：

- `phone`：E.164 手机号，例如 `+14482162932`。
- `sms_api_url`：用于轮询短信验证码的接口 URL。

### 轮询游标文件格式

`paypal_nocard.card_index_file` 和 `paypal_nocard.phone_index_file` 是轮询游标文件，不是卡池或手机池。文件内容必须是单个整数：

```text
0
```

当前项目默认是：

```json
{
  "paypal_nocard": {
    "card_index_file": "runtime/nocard_card_index.txt",
    "phone_index_file": "runtime/nocard_phone_index.txt"
  }
}
```

含义：

- `runtime/nocard_card_index.txt`：下一次要取的卡/地址索引。
- `runtime/nocard_phone_index.txt`：下一次要取的手机号索引。
- 文件不存在时会按 `0` 处理并自动创建。
- 如果这里误放手机号列表或 JSON 数组，会被代码当成非法整数并回退为 `0`。

### 运行 no-card 支付

单账号：

```powershell
python chatgpt_phone_reg.py --email user@example.com --one-click-pay --proxy socks5h://127.0.0.1:7897
```

批量：

```powershell
python chatgpt_phone_reg.py --one-click-pay --email-file pending_emails.txt --workers 4 --proxy socks5h://127.0.0.1:7897
```

对所有待支付账号：

```powershell
python chatgpt_phone_reg.py --one-click-pay-all --proxy socks5h://127.0.0.1:7897
```

### DataDome 处理

如果日志出现：

```text
PayPal DataDome 拦截
```

优先处理顺序：

1. 给 `paypal_nocard.proxies` 增加多个干净代理出口。
2. 确认 `--proxy` 和 `paypal_nocard.proxies` 指向真实可用监听。
3. 保持 `paypal_nocard.datadome_browser_seed=true`，`datadome_browser_headless=false`。
4. 运行时如果弹出 PayPal/DataDome 浏览器窗口，手动完成验证，程序会继续尝试拿 EC token 和 cookies。

相关配置：

```json
{
  "paypal_nocard": {
    "datadome_browser_seed": true,
    "datadome_browser_timeout": 300,
    "datadome_browser_headless": false
  }
}
```

浏览器接管需要本地环境安装可用的 Playwright/Camoufox 依赖。没有干净出口时，浏览器接管也可能失败。

## GoPay 支付

GoPay 一键支付使用同一个 `--one-click-pay` 入口，支付方式用 `--payment-method gopay`。

启动本地 provider：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_gopay_provider.ps1
```

执行 GoPay 一键支付：

```powershell
python chatgpt_phone_reg.py --email user@example.com --one-click-pay --payment-method gopay
```

常用配置：

```json
{
  "gopay": {
    "one_click_mode": "protocol",
    "open_link": true,
    "auto_generate": true,
    "provider_api": "byte-v-forge",
    "payment_service_addr": "127.0.0.1:50051",
    "grpcurl_path": "grpcurl",
    "payment_service": "payment.PaymentService",
    "proto_import_path": "services\\gopay-flow\\proto",
    "proto_path": "services\\gopay-flow\\proto\\payment.proto",
    "provider_timeout_seconds": 600,
    "otp_source": "smsbower",
    "country_code": "62",
    "otp_channel": "sms",
    "pin": "147258"
  }
}
```

GoPay SMSBower 不要复用 OpenAI/Ghana 的 `service=dr,country=38`。需要配置 GoPay 自己的服务和国家：

```json
{
  "gopay": {
    "otp": {
      "source": "smsbower",
      "smsbower": {
        "api_key": "$SMSBOWER_API_KEY",
        "service": "ni",
        "country": "6",
        "sms_timeout": 120,
        "sms_poll_interval": 5
      }
    }
  }
}
```

WA rebind 模式：

```json
{
  "gopay": {
    "one_click_mode": "wa_rebind",
    "otp_channel": "wa",
    "wa_rebind": {
      "enabled": true,
      "gopay_app_service_addr": "127.0.0.1:50060",
      "user_id": "local",
      "wa_phone": "859xxxxxxxx",
      "rebind_phone": "859yyyyyyyy"
    }
  }
}
```

带 OTP 完成：

```powershell
python chatgpt_phone_reg.py --email user@example.com --one-click-pay --payment-method gopay --gopay-otp 123456 --gopay-rebind-otp 654321
```

## CPA / SUB2API 导入

CPA 配置：

```json
{
  "cpa_mode": {
    "api_url": "http://your-domain.com:8317",
    "api_token": "YOUR_TOKEN"
  }
}
```

导入到 CPA：

```powershell
python chatgpt_phone_reg.py --import-cpa --email-file paid_emails.txt --import-target cpa
```

SUB2API 配置：

```json
{
  "sub2api": {
    "api_url": "http://your-sub2api-domain.com",
    "api_token": "",
    "email": "",
    "password": "",
    "group_name": "codex",
    "group_ids": "",
    "proxy_name": "",
    "proxy_id": "1,2,3,4,5",
    "priority": 1,
    "concurrency": 10
  }
}
```

导入到 SUB2API：

```powershell
python chatgpt_phone_reg.py --import-cpa --import-target sub2api --email-file paid_emails.txt
```

CPA 401 自动重导：

```powershell
python chatgpt_phone_reg.py --auto-reimport-cpa-401 --import-target cpa
python chatgpt_phone_reg.py --reimport-cpa-401-survivors --import-target sub2api
```

## WPF 桌面界面

`SmsWorkbench` 是本地启动器和管理界面，负责读取 `config.json`、启动 Python CLI、展示邮箱/session/SQLite 状态，并提供批量操作。

主要能力：

- 注册、支付链接生成、一键支付、GoPay 支付。
- 查看邮箱池、session JSON、SQLite 账号状态。
- 账号详情、收件箱查看、复制验证码。
- 标记支付完成、CPA/SUB2API 导入。
- 配置窗口直接维护常用配置。

配置窗口的“代理 / 支付”分类现在包含：

- 默认代理。
- PayPal 代理池。
- NoCard 启用、地区、语言、OTP 超时、TLS 指纹。
- DataDome 浏览器接管、接管超时、Headless。
- NoCard 代理池。
- 保存链接复用策略。
- 卡索引文件、手机索引文件。
- 卡池 JSON、地址池 JSON、手机池 JSON。

代理池字段是一行一个代理。卡池、地址池、手机池字段必须填 JSON 数组；保存时如果 JSON 解析失败，程序会保留原数组，避免误覆盖。

## 数据文件说明

默认本地数据：

- `config.json`：本机真实配置。
- `mailbox_tokens.txt`：邮箱池。
- `sessions/`：注册后保存的 session JSON。
- `runtime/accounts.sqlite3`：账号索引和支付状态。
- `runtime/nocard_card_index.txt`：no-card 卡/地址轮询游标。
- `runtime/nocard_phone_index.txt`：no-card 手机号轮询游标。
- `runtime/phone_reuse_state.json`：手机号复用状态。
- `dist/net10/SmsWorkbench.exe`：WPF 发布输出。

不要提交：

- `config.json`
- `sms_tool/config.json`
- `mailbox_tokens.txt`
- `sessions/`
- `runtime/`
- `dist/`
- `.dotnet/`

## 常见问题

### `config.json 中 paypal_auto.cards 为空`

原因是 `paypal_auto.cards` 没有配置，或者改错了配置文件位置。卡池必须放在项目根目录 `config.json` 的 `paypal_auto.cards`，不是放到 `runtime/nocard_card_index.txt`。

### `runtime/nocard_card_index.txt` 和 `runtime/nocard_phone_index.txt` 应该放什么

只放一个整数，例如：

```text
0
```

这两个文件是轮询游标，不是卡池、地址池、手机号池。

### `PayPal DataDome 拦截`

当前 IP 或纯 HTTP 会话被 PayPal DataDome 拦截。增加干净代理到 `paypal_nocard.proxies` 或 `paypal.proxies`，并开启：

```json
{
  "paypal_nocard": {
    "datadome_browser_seed": true,
    "datadome_browser_headless": false
  }
}
```

运行时按提示在弹出的浏览器里完成验证。

### 邮箱池读取不到

确认：

- 当前目录是项目根目录。
- `config.json` 存在。
- `email_registration.token_file` 指向正确文件。
- 文件是 UTF-8 或 UTF-8 BOM。
- Microsoft Graph 邮箱行至少有 `email---password---refresh_token` 三段。

### PowerShell 中文乱码

本项目 CLI 会尽量把 stdout/stderr 设为 UTF-8。若仍乱码，优先用 Windows Terminal，并在 PowerShell 里执行：

```powershell
chcp 65001
```

### WPF 构建失败

先检查 .NET SDK：

```powershell
dotnet --info
dotnet build SmsWorkbench\SmsWorkbench.csproj
```

如果只是需要发布版，使用项目脚本：

```powershell
powershell -ExecutionPolicy Bypass -File .\SmsWorkbench\build_dotnet.ps1
```

## 测试

PayPal no-card 单测：

```powershell
python -m unittest tests.test_paypal_nocard
```

全量离线测试：

```powershell
python -m unittest discover -s tests
```

WPF 编译：

```powershell
dotnet build SmsWorkbench\SmsWorkbench.csproj
```

## 模块边界

- `chatgpt_phone_reg.py`：兼容入口，转发到 `sms_tool.cli`。
- `sms_tool.cli`：参数解析和命令编排。
- `sms_tool.mailbox`：邮箱池、LuckMail、CFWorker、Microsoft Graph OTP。
- `sms_tool.registration`：ChatGPT 注册协议、邮箱 OTP、access token 获取、批量注册。
- `sms_tool.gen_pp_link` / `sms_tool.paypal_links`：Stripe/PayPal 链接生成和持久化更新。
- `sms_tool.paypal_nocard`：PayPal no-card 协议支付。
- `sms_tool.gopay_payment`：GoPay 一键支付入口。
- `sms_tool.gopay_wa_rebind`：GoPay WA 支付后换绑。
- `sms_tool.codex_oauth` / `sms_tool.codex_export` / `sms_tool.cpa_import`：Codex OAuth、导出和 CPA 上传。
- `sms_tool.storage`：SQLite schema、迁移、去重和状态更新。
- `SmsWorkbench`：WPF 管理界面。
- `browser_extensions/paypal_autofill`：可选浏览器辅助扩展。
