# 测试套件

VideoSummary 翻译模块的集成测试。

## 📁 测试文件

```
tests/test_translate/
├── test_google_translator.py   # Google 翻译器（免费 API）
├── test_bing_translator.py     # Bing 翻译器（免费 API）
├── test_llm_translator.py      # LLM 翻译器（需要 API 密钥）
└── test_deeplx_translator.py   # DeepLX 翻译器（可选）
```

## 🚀 运行测试

### 快速测试（免费 API）

```bash
# Google + Bing 翻译器（无需配置）
uv run pytest tests/test_translate/test_google_translator.py tests/test_translate/test_bing_translator.py -v
```

### 完整测试（需要 API 密钥）

```bash
# 1. 配置环境变量
export LLM_BASE_URL=https://api.openai.com/v1
export LLM_API_KEY=sk-your-key
export LLM_MODEL=gpt-4o-mini

# 2. 运行所有测试
uv run pytest tests/test_translate/ -v
```

### 运行特定测试

```bash
# 只运行 Google 翻译器
uv run pytest tests/test_translate/test_google_translator.py::TestGoogleTranslator::test_translate_simple_text -v

# 跳过需要 API 的测试
uv run pytest tests/test_translate/ -m "not integration" -v
```

## ⚙️ 环境变量

### 本地开发

创建 `.env` 文件（已在 .gitignore 中）：

```bash
# LLM 翻译器测试（必需）
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-your-api-key
LLM_MODEL=gpt-4o-mini

# DeepLX 翻译器测试（可选）
DEEPLX_ENDPOINT=https://api.deeplx.org/translate
```

### CI/CD

GitHub Actions 中通过 **Settings → Secrets** 配置：

- `LLM_BASE_URL`
- `LLM_API_KEY`
- `LLM_MODEL`
- `DEEPLX_ENDPOINT`（可选）

详见 [docs/CI_SETUP.md](../docs/CI_SETUP.md)

## 📊 测试结果示例

```
=================== 6 passed, 6 skipped ===================

✅ test_google_translator.py    3 passed
✅ test_bing_translator.py      3 passed
⏭️ test_llm_translator.py       4 skipped (no API key)
⏭️ test_deeplx_translator.py    2 skipped (no endpoint)
```

## 🐛 常见问题

### 测试被跳过

**原因**: 缺少环境变量

**解决**:

```bash
export LLM_BASE_URL=...
export LLM_API_KEY=...
export LLM_MODEL=...
```

### ImportError

**原因**: 缺少依赖

**解决**:

```bash
uv sync --all-extras
```

### 翻译测试失败

**原因**: 免费 API 可能不稳定或有频率限制

**解决**:

- Google/Bing 测试失败是正常的（免费服务）
- 等待几分钟后重试
- 只运行 LLM 测试（更稳定）

## 📝 添加新测试

```python
# tests/test_translate/test_my_translator.py
import pytest
from app.core.translate.my_translator import MyTranslator

@pytest.mark.integration
class TestMyTranslator:
    @pytest.fixture
    def translator(self, target_language):
        return MyTranslator(
            thread_num=2,
            batch_num=5,
            target_language=target_language,
            update_callback=None,
        )

    def test_translate(self, translator, sample_asr_data):
        result = translator.translate_subtitle(sample_asr_data)
        assert len(result.segments) == len(sample_asr_data.segments)
        for seg in result.segments:
            assert seg.translated_text  # 确保有翻译结果
```

## 🔗 相关文档

- [CI/CD 配置](../docs/CI_SETUP.md)
- [测试指南](../docs/TESTING.md)
