# 商业化能力 TD（Technical Design）

> 目标：把「功能可用」升级为「商业闭环可用」——支付自动化、计量对账、运维指标三大件，
> 配合既有的会员套餐/配额/API Key/收款码基建，达到可收费运营标准。

## 现状盘点（2026-10-10）

| 能力 | 现状 | 差距 |
|---|---|---|
| 会员套餐 | free/pro/vip + 日配额（30/200/9999） | ✅ 完备 |
| 订单 | 创建（优惠券抵扣）+ 凭证截图 + 人工审核开通 | ❌ 无支付自动化 |
| 收款 | 收款码（admin 上传）/ 转帐说明 | ❌ 无 Webhook 自动履约 |
| LLM 计量 | usage_logs 全量记录（user_id/api_key/feature/model/耗时） | ❌ 无用户侧账单、无运维指标 |
| API Key 网关 | /v1 已按 user_id 扣配额 + log_usage 计费记录；gateway_open 默认关 | ⚠️ 缺对账报表 |
| 到期降级 | 惰性降级（登录时置 free）+ 到期站内信 | ✅ 可用 |

## 本期落地（P0 商业闭环）

### 1. 支付抽象层 `common/payment.py`
- `PaymentProvider` 协议：`checkout(order)` / `verify_webhook(payload, sign)`
- `MockProvider`（沙箱）：签名 = HMAC-SHA256(order_id, secret)，E2E 验收专用；test/dev/local（含未设 APP_ENV）默认启用，生产必须 config 显式开启
- `AlipayProvider`：契约骨架（RSA2 验签 runbook 见下），未接商户凭据时显式 501，不做假实现
- `mark_order_paid(order_id, provider, ref, amount, source)`：
  - 状态机 `pending → paid → approved`（幂等：approved 重放直接返回）
  - 金额不匹配 → 停留 `paid` 转人工审核（防 webhook 伪造自动开通）
  - 匹配 + `payment_auto_activate=1`（config，默认开）→ 复用 `review_order` 开通逻辑自动履约

### 2. 端点
- `POST /api/orders/{order_id}/checkout/{provider}` — 生成支付指令（mock 返回沙箱说明；alipay 501 待集成）
- `POST /api/orders/webhook` — 支付回调（验签 → mark_order_paid）
- `GET /api/billing/summary` — 用户计量中心（今日/30日 调用数、成功率的 token 量、成本预估）
- `GET /api/admin/metrics` — 运维指标（7日 p50/p95、错误率、功能分布、任务积压、DB 体积）

### 3. 数据迁移
orders 表幂增列：`payment_provider / payment_ref / paid_at`（ALTER TABLE IF 缺失，旧库安全）。

## 收款渠道接入 Runbook（P1，凭据到位后）

| 渠道 | 步骤 | 工作量 |
|---|---|---|
| 支付宝当面付 | 1) 商户后台建「当面付」应用 → 2) 填 `ALIPAY_APP_ID/KEY/ALIPAY_PUBLIC_KEY` 到 .env → 3) 实现 `AlipayProvider.verify_webhook` RSA2 验签（对照 docs 注释）→ 4) 沙箱号验收 | ~0.5d |
| 微信支付 | 商户号 + APIv3 证书 → `WechatPayProvider`（平台证书下载/序列号管理） | ~1d |
| Stripe | 订单已预留 `stripe_session_id` 列 → 接 PaymentIntent Webhook | ~0.5d |

## 验收清单
- [x] mock 支付全链路：create → webhook → 自动开通（会员+配额+有效期）（单测 test_payment_webhook.py + E2E K 商业探针）
- [x] webhook 幂等重放（重复回调不重复开通）
- [x] 金额不匹配 → 转人工审核（不自动开通）
- [x] rejected 订单不可再支付（409）
- [x] 用户计量中心聚合正确（/api/billing/summary）
- [x] 运维指标端点可用（/api/admin/metrics，仅 admin）
- [ ] 支付宝实付验收（待商户凭据，见 Runbook）
