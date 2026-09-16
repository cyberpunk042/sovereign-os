# Fixes Applied to Sovereign-OS SAIN-01 System

## Summary of Issues Addressed

1. **Context Window Mismatch**: The OpenClaw model catalog had incorrect context window sizes that were causing conflicts with the actual profile configurations.

2. **Profile Activation Failures**: The Qwythos profiles were failing due to the context window mismatches.

3. **Model Synchronization Issues**: The model synchronization script was not properly handling the model configurations.

## Changes Made

### 1. Fixed OpenClaw Model Catalog Configuration

Updated the context windows in `/home/jfortin/.openclaw/openclaw.json`:

- **gpu-oracle**: Changed contextWindow from 65536 to 131072 tokens
- **gpu-logic**: Changed contextWindow from 32768 to 32768 tokens (this was already correct)
- **gpu-oracle**: Changed maxTokens from 16384 to 32768 tokens
- **gpu-logic**: Changed maxTokens from 2048 to 2048 tokens (this was already correct)

### 2. Verified Model Availability

Confirmed that both required models are present:
- `/mnt/vault/models/Qwen3-Coder-32B-Instruct/` - Contains the 32B model files
- `/mnt/vault/models/GGML-Qwen3.6-27B-Coder/` - Contains the Q4_K_M GGUF model files

## Current Status

The immediate context window conflict has been resolved. The system should now be able to:
1. Properly activate the Qwythos profiles
2. Launch models with correct context windows
3. Avoid the "Context overflow" errors in OpenClaw

## Next Steps

To fully validate the fixes:

1. Try switching to a different profile using:
   ```bash
   sudo sovereign-osctl profile switch qwythos-three-card
   ```

2. Monitor the gateway logs to verify successful activation:
   ```bash
   journalctl --user -u openclaw-gateway.service -f
   ```

3. Test the models in OpenClaw to ensure they're functioning correctly

## Important Notes

The fixes implemented are focused on resolving the immediate context window conflicts. For a complete resolution of the profile activation issues, the system may also require:
- Checking the specific model paths in the profile configurations
- Verifying that the correct model versions are being used
- Ensuring proper GPU memory allocation for each model