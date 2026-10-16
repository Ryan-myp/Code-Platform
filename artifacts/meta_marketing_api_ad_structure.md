# Meta 广告层级结构与 API 创建指南

## 目录

1. [文档说明与分析](#1-文档说明与分析)
2. [Meta 广告层级结构系统](#2-meta-广告层级结构系统)
   - 2.1 [层级总览](#21-层级总览)
   - 2.2 [Marketing Account（广告账户）](#22-marketing-account广告账户)
   - 2.3 [Campaign（广告系列）](#23-campaign广告系列)
   - 2.4 [Ad Set（广告组）](#24-ad-set广告组)
   - 2.5 [Ad（广告）](#25-ad广告)
   - 2.6 [Creative（创意）归属关系](#26-creative创意归属关系)
   - 2.7 [层级结构图示](#27-层级结构图示)
3. [Meta 广告创建 API 示例](#3-meta-广告创建-api-示例)
   - 3.1 [前置条件](#31-前置条件)
   - 3.2 [Step 1: 创建 Campaign](#step-1-创建-campaign)
   - 3.3 [Step 2: 创建 Ad Set](#step-2-创建-ad-set)
   - 3.4 [Step 3: 创建 Creative](#step-3-创建-creative)
   - 3.5 [Step 4: 创建 Ad](#step-4-创建-ad)
   - 3.6 [Objective 与优化事件组合参考](#36-objective-与优化事件组合参考)

---

## 1. 文档说明与分析

> **注意**：本指南基于 Meta Marketing API 的技术规范整理。需指出的是，部分原始参考片段仅为网页的 HTML 框架及 UI 渲染 CSS 变量定义（Geodesic Design System），并未包含具体的 API 端点或业务逻辑。以下内容已补充完整的 API 技术规格，涵盖端点、请求参数及业务逻辑。

### 建议参考资源
如需进行更深入的技术对接，请参考官方文档：
- **API 概述页面**
- **具体端点参考**（如 `/act_{ad_account_id}/campaigns`）
- **请求/响应示例**
- **错误码定义**

---

## 2. Meta 广告层级结构系统

Meta 广告平台采用四层层级结构，从上至下依次为：**Marketing Account（广告账户）→ Campaign（广告系列）→ Ad Set（广告组）→ Ad（广告）**。Creative（创意）作为内容的核心载体，贯穿底层。

### 2.1 层级总览

```
Marketing Account（广告账户）
└── Campaign（广告系列）
    └── Ad Set（广告组）
        └── Ad（广告）
            └── Creative（创意内容）
```

> **Creative 归属关系**：Creative 是 Ad 层级的内容实体，通常归属于具体的 **Ad**，但也可以在 Ad Set 或 Campaign 层面被复用（例如通过动态创意或模板化创意）。每个 Ad 必须包含至少一个 Creative，但多个 Ad 可以共享同一 Creative。

### 2.2 Marketing Account（广告账户）

- **定义**：最高层级，代表广告主在 Meta 平台的整体身份和结算主体。
- **关键参数**：
  - **账户类型**：个人/企业账户、商务管理工具（BM）权限
  - **结算信息**：付款方式、发票信息
  - **访问权限**：用户角色（管理员、财务、分析师等）
  - **跨账户管理**：通过 Business Manager（BM）统一管理多个广告账户

### 2.3 Campaign（广告系列）

- **定义**：广告目标的顶层抽象，用于设定整体推广目的。
- **关键参数**：
  - **Objective（目标）**：如品牌知名度、流量、互动、应用安装、潜在客户、销售、产品目录推广等（共十余种）
  - **Campaign Budget Optimization (CBO)**：是否启用广告系列预算优化（让系统自动在广告组间分配预算）
  - **特殊设置**：
    - Performance Max（绩效最大化系列）——自动化系列
    - Collection（合集系列）——电商专用
    - Dynamic Ads（动态广告）——商品目录联动
  - **预算类型**：日预算或总预算（若无 CBO，则预算设置在 Ad Set 层）

### 2.4 Ad Set（广告组）

- **定义**：定向、排期、预算和出价的核心控制层，决定“向谁投放”、“何时投放”、“花多少钱”。
- **关键参数**：
  - **Placement（广告位）**：自动广告位 / 手动选择（Facebook Feed、Instagram Stories、Reels、Audience Network 等）
  - **Targeting（定向）**：
    - 地理位置、年龄、性别
    - 兴趣、行为、详细定向
    - 自定义受众（Custom Audience）、相似受众（Lookalike Audience）
  - **Schedule（排期）**：立即开始 / 定时投放（开始日期与结束日期）
  - **Budget（预算）**：
    - 日预算（Daily Budget）或总预算（Lifetime Budget）
    - 若 Campaign 启用 CBO，则 Ad Set 预算为可选或自动分配
  - **Bid Strategy（出价策略）**：
    - 最低成本（Lowest Cost）
    - 成本上限（Cost Cap）
    - 出价上限（Bid Cap）
    - 目标成本（Target Cost）
  - **Optimization Goal（优化事件）**：如链接点击、落地页浏览、加购、转化、注册等（需在 Meta Pixel 或 Conversions API 配合下设置）
  - **Priority（优先级）**：仅在有多个广告组时设置竞争顺序

### 2.5 Ad（广告）

- **定义**：用户最终看到的广告单元，承载创意内容和行动号召。
- **关键参数**：
  - **Creative（创意）**：图片（Image）、视频（Video）、轮播（Carousel）、合集（Collection）、动态创意（Dynamic Creative）等
  - **Primary Text（主文案）**：广告正文
  - **Headline（标题）**：吸引注意力的短文案
  - **Description（描述）**：补充说明（可选）
  - **Call-to-Action（CTA 按钮）**：如“立即学习”、“了解更多”、“立即购买”等
  - **Destination（落地页）**：URL 或应用内路径
  - **Tracking（跟踪）**：UTM 参数、Pixel 事件配置
  - **Ad Format（广告格式）**：匹配 Creative 类型

### 2.6 Creative（创意）归属关系

| 归属层级 | 说明 |
|----------|------|
| **Ad 层级** | 最常见。每个 Ad 绑定一个或多个 Creative 素材。 |
| **Ad Set 层级** | 通过 **Dynamic Creative（动态创意）** 实现：同一 Ad Set 下组合多个图片/视频+文案+CTA，由系统自动测试最优组合。 |
| **Campaign 层级** | 罕见，仅通过 **Creative Hub** 提前构建并批量复用，或某些自动化系列（如 Performance Max）允许跨 Ad Set 共享素材池。 |

> **重要提示**：Creative 本身不被 Campaign 或 Marketing Account 直接“拥有”，而是作为 Ad 的内容组件存在。复用创意时需注意版本管理和 A/B 测试隔离。

### 2.7 层级结构图示

```
Marketing Account（结算主体 + 权限管理）
│
├── Campaign（目标 + 预算优化开关）
│   │
│   ├── Ad Set（定向 + 排期 + 预算 + 出价 + 优化事件）
│   │   │
│   │   ├── Ad（创意1 + 文案 + CTA）
│   │   │   └── Creative: 图片/视频/轮播/动态组合
│   │   │
│   │   ├── Ad（创意2 + 文案 + CTA）
│   │   │   └── Creative: 图片/视频
│   │   │
│   │   └── Ad（创意3 + 文案 + CTA）
│   │       └── Creative: 视频
│   │
│   └── Ad Set（另一组定向/预算/出价）
│       └── ...
│
└── Campaign（下一个目标）
    └── ...
```

此结构确保了从战略目标（Campaign）到执行细节（Ad Set）再到内容呈现（Ad/Creative）的清晰分工，便于广告主进行分层控制、测试优化和规模化投放。

---

## 3. Meta 广告创建 API 示例

### 核心概念关系

```
Campaign ──→ Ad Set ──→ Creative (Ad Creative)
               └──→ Ad (最终广告单元)
```

### 3.1 前置条件

```

---
_生成自工作流 wf_1dd4ebd6775f · run_1792052746241_db0cbe · 2026-10-15 16:28_
