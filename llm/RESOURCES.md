# LLM 原理学习资源

## 核心论文（必读）

- [Attention Is All You Need (Vaswani et al., 2017)](https://arxiv.org/abs/1706.03762)
  Transformer 原始论文。Self-Attention、Multi-Head Attention、Positional Encoding 的定义。
- [Language Models are Unsupervised Multitask Learners (GPT-2, Radford et al., 2019)](https://d4mucfpksywv.cloudfront.net/better-language-models/language_models_are_unsupervised_multitask_learners.pdf)
  奠定了 GPT 系列 decoder-only + zero-shot 的技术路线。
- [LLaMA: Open and Efficient Foundation Language Models (Touvron et al., 2023)](https://arxiv.org/abs/2302.13971)
  Meta 的开源模型，引入 RoPE、RMSNorm、SwiGLU。
- [LLaMA 2: Open Foundation and Fine-Tuned Chat Models (Touvron et al., 2023)](https://arxiv.org/abs/2307.09288)
  GQA（Grouped Query Attention）、RLHF 细节、安全对齐。

## 可视化与教程

- [The Illustrated Transformer (Jay Alammar)](https://jalammar.github.io/illustrated-transformer/)
  最好的 Transformer 可视化教程。适合入门。
- [The Illustrated GPT-2 (Jay Alammar)](https://jalammar.github.io/illustrated-gpt2/)
  GPT-2 内部工作机制可视化。理解 decoder-only 的关键资源。
- [Andrej Karpathy: Let's build GPT from scratch](https://www.youtube.com/watch?v=kCc8FmEb1nY)
  从零实现 GPT 的视频教程。代码驱动，适合工程向深入。
- [Lilian Weng: The Transformer Family](https://lilianweng.github.io/posts/2023-01-27-the-transformer-family-v2/)
  Transformer 变体综述。适合了解不同架构改进的动机。

## 面试重点资源

- [Transformer 面试题 50 题 (GitHub)](https://github.com/DA-southampton/transformer-questions)
  中文面试题库，覆盖从 Attention 到 LLM 训练的全链路。

## 社区

- [r/MachineLearning](https://reddit.com/r/MachineLearning)
- [HuggingFace Discord](https://discord.gg/hugging-face-879548962464493619)
- [EleutherAI Discord](https://discord.gg/eleutherai) — LLM 开源研究社区
