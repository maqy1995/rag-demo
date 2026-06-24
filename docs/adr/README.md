# ADR — Architecture Decision Records

> 跨角色。**一旦写定全员遵循**。任何与 ADR 冲突的代码/文档都不应合入。

## 流程

1. 复制 `0000-template.md` → `NNNN-<slug>.md`，状态写 `Proposed`。
2. 在 multica 评论里 @产品 @审查员 @环境运维，请求 1 个工作日内 review。
3. 异议在 ADR 文件底部"异议"小节追加，作者负责汇总。
4. 三方均无异议或一周无回复 → 状态改 `Accepted`，合入。
5. 推翻已 `Accepted` 的 ADR → 新建一张 `supersedes NNNN` 的 ADR，不直接改旧文件。

## 编号

永远 4 位数字（`0001`, `0002`, …），按合入时间递增，不重用。

## 当前 ADR

| 编号 | 标题 | 状态 |
|------|------|------|
| _无_ | | |