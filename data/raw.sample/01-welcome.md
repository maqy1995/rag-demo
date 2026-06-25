# 欢迎使用 rag-demo

## 简介

rag-demo 是一个本地知识库问答系统。它会扫描你 vault 里的 .md / .txt 笔记，
用一个向量索引（占位）做检索，然后让 LLM 回答你的问题。

## 核心概念

- **vault**: 你的笔记目录（包含 .md / .txt 文件）。
- **index**: 向量索引的落盘目录。
- **retrieve**: 从索引里挑出 top-k 个相关 chunk。
- **generate**: 把 chunk 喂给 LLM，让它合成答案。

## 快速开始

```bash
uv sync --extra dev
uv run rag-demo doctor
uv run rag-demo ingest --data ./data/raw --index ./data/index
uv run rag-demo up --port 8000
```

打开 http://127.0.0.1:8000 就能看到一个简单的 demo UI。

## 这是什么

这是一个面向开发者的 demo 项目，目的是让你快速搭起来一整套本地 RAG 流水线，
跑通之后再决定要不要换更重的栈。
