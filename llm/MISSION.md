# Mission: 深入理解 LLM 原理

## Why
掌握 LangChain/LangGraph 应用层之后，需要深入模型层——理解 Transformer 架构、GPT 系列的自回归生成原理、LLaMA 等开源模型的改进设计。目标是在面试中能清晰解释模型内部工作机制，读懂核心论文的关键设计决策。

## Success looks like
- 能手画 Transformer 架构图，解释 Self-Attention 的 Q/K/V 计算过程
- 能对比 GPT（decoder-only）、BERT（encoder-only）、T5（encoder-decoder）的架构差异和适用场景
- 能解释 LLaMA 相比原始 Transformer 的改进点（RoPE、RMSNorm、SwiGLU、GQA）
- 能说清楚训练 vs 推理的区别：pre-training、SFT、RLHF、KV cache、speculative decoding
- 面试中能回答：为什么现在都是 decoder-only？Transformer 的复杂度是多少？

## Constraints
- 时间：随 LangChain 课程并行进行，每课 30-40 分钟
- 不需要手写 CUDA 或训练代码，重点是概念和设计哲学
- 数学适度——需要理解矩阵乘法和 softmax，但不深入偏微分推导

## Out of scope
- 完整的前向/反向传播数学推导
- GPU 编程（CUDA、Triton）
- 具体训练脚本编写
- 视觉 Transformer（ViT）、语音 Transformer
