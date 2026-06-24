# Code Review Checklist

> 复制本文件到 `reports/YYYY-MM-DD-<pr>.md`，逐项打勾。

## 必查

- [ ] PR 描述引用了对应的 multica issue（`Fixes MAQ-XX`）
- [ ] 改动与 `docs/dev/design.md` 一致；若有偏差需附 ADR 链接
- [ ] 没有把任何 `.env` / `.pem` / `*.key` 提交进 git
- [ ] 没有把 `.venv/`、缓存、IDE 临时文件提交（核对 `git status` 干净）
- [ ] 函数签名与 `docs/dev/interfaces.md` 一致
- [ ] 新增/修改的公共函数至少有 1 个测试
- [ ] 失败的 CI 检查全部修复，没有 `--no-verify` 绕过

## 建议查

- [ ] 错误信息含足够上下文（路径、相关 ID），但不泄露密钥
- [ ] 日志输出有级别控制，不在 info 级别打印大段 JSON
- [ ] 对外部输入做校验，不直接拼 SQL / shell / path
- [ ] 锁 / 资源有释放路径（context manager / try-finally）

## 复盘（合入后填）

- 有没有本可以提前发现的问题？
- checklist 本身要不要补充？