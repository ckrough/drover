# ADR-002: Privacy-First Design

## Status
Accepted

## Context
Drover processes potentially sensitive personal documents (bank statements, medical records, tax forms). Users need confidence that their document content is handled appropriately.

Key concerns:
1. Where does document content go?
2. Who can access classification data?
3. What telemetry is collected?
4. How do we support privacy-conscious users?

## Decision
Implement a privacy-first architecture with the following principles:

### 1. Local-First Default
- **Default provider**: Ollama (runs locally, zero data leaves machine)
- **No cloud requirement**: Full functionality with local models
- **Explicit opt-in**: Cloud providers require explicit configuration

### 2. Zero Telemetry
- **No usage tracking**: No analytics, crash reports, or usage telemetry
- **No phone-home**: Application never contacts external services unexpectedly
- **No logging to cloud**: All logs are local-only

### 3. Minimal Data Retention
- **No document storage**: Drover never persists document content
- **Ephemeral processing**: Content exists only during classification
- **No classification history**: No database of past classifications (by default)

### 4. User Control
- **Configuration transparency**: All settings documented and visible
- **Provider choice**: User selects AI provider with full understanding of privacy implications
- **API key management**: Keys stored in environment variables, never in config files

## Implementation Details

### Provider Privacy Profiles
| Provider | Data Location | Privacy Level |
|----------|--------------|---------------|
| Ollama | Local machine | Highest |
| OpenAI | OpenAI servers | Medium (data may be used for training) |
| Anthropic | Anthropic servers | Medium-High (stronger data retention policies) |
| OpenRouter | Various providers | Varies by underlying model |

### Configuration Example
```yaml
# drover.yaml - Privacy-focused configuration
ai:
  provider: ollama          # Local-only processing
  model: llama3.2:latest    # Runs entirely on your machine

# Optional: cloud provider for better accuracy
# ai:
#   provider: anthropic
#   model: claude-sonnet-4-20250514
```

### Environment Variables for Secrets
```bash
# Secrets stay in environment, not config files
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
```

## Consequences

### Positive
- **GDPR/CCPA alignment**: Minimizes data processing and storage
- **Enterprise friendly**: Can be deployed in air-gapped environments
- **User trust**: Clear privacy story for sensitive document handling
- **Differentiation**: Stands out from cloud-only document AI tools

### Negative
- **Local model quality**: Smaller local models may be less accurate than cloud models
- **Hardware requirements**: Ollama requires reasonable CPU/GPU for good performance
- **Feature limitations**: Some advanced features may require cloud (e.g., embeddings for RAG cache)

### Mitigations
- Document privacy implications of each provider in README
- Provide model recommendations for different accuracy/privacy tradeoffs
- Optional cloud features are clearly marked as opt-in

## Related
- `config.py:AIProvider` - Provider enumeration with Ollama as default
- `config.py:DroverConfig` - Configuration with environment variable support
- `README.md` - Privacy documentation for users
- `CLAUDE.md` - Development guidelines preserving privacy stance
